import re
from app.nlp.preprocessing.text_cleaner import TextCleaner
from app.services.analysis.factcheck_service import FactCheckService
from app.services.analysis.text_enrichment import TextEnrichmentService
from ..llm.llm_manager import LLMManager
from ...core.database.mongoDB import MongoDBManager
import logging
from datetime import datetime


logging.basicConfig(level=logging.INFO)


class AnalysisOrchestrator:
    def __init__(self, mongo_manager: MongoDBManager):
        self.mongo_manager = mongo_manager

        # Inizializzo LLMManager
        try:
            self.llm_manager = LLMManager()
            logging.info("LLMManager inizializzato.")
        except Exception as e:
            logging.error(f"Errore durante l'inizializzazione di LLMManager: {e}. Nessun LLM sarà disponibile.")
            self.llm_manager = None

        # Effettuo l'accesso a PubMedService tramite LLMManager
        self.pubmed_service = self.llm_manager.pubmed_service if self.llm_manager else None

        self.fact_check_service = FactCheckService(self.llm_manager)

    
    def process_single_post(self, post):
        """Processa un singolo post con fact-check RAG, sentiment, concetti medici e validazione PubMed."""
       

        post_id = post.get('id', str(post.get('_id', 'N/A')))
        original_text = (post.get('text') or "") or post.get('title', "")
        topic = (post.get('query') or "").strip()

        # Controlli di base: testo
        if not original_text.strip():
            logging.warning(f"[{post_id}] Nessun testo/titolo: skip.")
            self.mongo_manager.update_post_status('social_posts', post_id, {
                "processed": True,
                "analysis_status": "no_text"
            })
            return
        
        text_cleaner = TextCleaner()

        raw = (post.get('text') or "") or post.get('title', "")
        text1 = text_cleaner.normalize_whitespace(raw)
        text2 = text_cleaner.strip_noise(text1)

        urls = re.findall(r'https?://\S+', text2)
        urls_clean = [text_cleaner.clean_url(u) for u in urls]
        platform_meta = (post.get("platform_meta") or {}).copy()  
        platform_meta["urls_expanded"] = urls_clean

        if len(text2) < 20:
            self.mongo_manager.update_post_status('social_posts', post_id, {
                "processed": True,
                "analysis_status": "too_short",
                "processed_text": text2,
                "platform_meta": platform_meta
            })
            return

        lang = (post.get("lang") or "").lower()

        #  Estrazione concetti medici (LLM + fallback) 
        medical_concepts = []
        try:
            llm_service = self.llm_manager.get_next_service()
        except Exception as e:
            logging.error(f"[{post_id}] get_next_service() errore: {e}")
            llm_service = None

        if llm_service and hasattr(llm_service, "extract_medical_concepts_prova"):
            try:
                mc = llm_service.extract_medical_concepts_prova(text2)
                if isinstance(mc, str):
                    mc = [mc]
                if isinstance(mc, list):
                    medical_concepts = [str(x).strip() for x in mc if str(x).strip()]
                    seen = set()
                    medical_concepts = [x for x in medical_concepts if not (x in seen or seen.add(x))][:5]
            except Exception as e:
                logging.warning(f"[{post_id}] estrazione concetti LLM fallita: {e}")

        text_enrichment_service = TextEnrichmentService()

        if not medical_concepts:
            try:
                medical_concepts = text_enrichment_service.match_concepts_dictionary(text2)[:3]
            except Exception:
                medical_concepts = []

        #  Key terms & topic inferito 
        try:
            key_terms = text_enrichment_service.top_tfidf_terms(text2, lang_hint=lang, k=8)
        except Exception:
            key_terms = []

        try:
            inferred = text_enrichment_service.infer_topic_from_concepts(medical_concepts, key_terms)
        except Exception:
            inferred = None

        topic_final = topic or inferred or "salute"

        #  PubMed 
        pubmed_results = []
        if getattr(self, "pubmed_service", None) and getattr(self.pubmed_service, "is_available", False) and medical_concepts:
            try:
                safe_terms = [t for t in medical_concepts if isinstance(t, str) and t.strip()]
                if safe_terms:
                    query_for_pubmed = " OR ".join(safe_terms)
                    pubmed_results = self.pubmed_service.search_pubmed(query_for_pubmed, max_results=3) or []
                    logging.info(f"[{post_id}] PubMed: trovati {len(pubmed_results)} risultati.")
            except Exception as e:
                logging.warning(f"[{post_id}] ricerca PubMed fallita: {e}")
                pubmed_results = []

        #  Fact-check 
        try:
            fc = self.fact_check_service.run_factcheck(topic=topic_final, post_text=text2)
        except Exception as e:
            logging.error(f"[{post_id}] Errore factcheck: {e}", exc_info=True)
            fc = None

        if fc and fc.get("status") == "ok":
            status = "completed"
            grado = fc.get("grado_disinformazione", 1)
            valutazione = fc.get("valutazione_testuale", "")
            motivazione = fc.get("motivazione", "")
            fonti = fc.get("fonti_utilizzate", []) or []
            sentiment = fc.get("sentiment", "neutro")
            factcheck_obj = fc.get("factcheck", {}) or {}
        else:
            status = "failed_factcheck" if fc else "failed_factcheck_exc"
            grado = -1
            valutazione = "Analisi non disponibile."
            motivazione = "Pipeline non completata o risposta non conforme."
            fonti = []
            sentiment = "neutro"
            factcheck_obj = {}

        update_data = {
            "processed": True,
            "processed_text": text2,
            "medical_concepts": medical_concepts,
            "analysis_status": status,
            "analysis_results": {
                "grado_disinformazione": grado,
                "valutazione_testuale": valutazione,
                "motivazione": motivazione,
                "fonti_utilizzate": fonti,
                "sentiment": sentiment,
                "pubmed_validation": pubmed_results,
                "factcheck": factcheck_obj,
                "key_terms": key_terms,
                "inferred_topic": topic_final,
            },
            "platform_meta": platform_meta,
            "last_processed_at": datetime.now().isoformat()
        }

        self.mongo_manager.update_post_status('social_posts', post_id, update_data)
        logging.info(f"[{post_id}] aggiornato: status={status}, grado={grado}, sentiment={sentiment}.")



    def run_analysis_batch(self, batch_size=50):
            """Processa un batch di post non ancora processati."""
            logging.info(f"Avvio batch di analisi per {batch_size} post.")
            self.llm_manager.reset_failed_services()
            unprocessed_posts = self.mongo_manager.get_unprocessed_posts('social_posts', limit=batch_size)

            if not unprocessed_posts:
                logging.info("Nessun nuovo post da processare.")
                return

            for post in unprocessed_posts:
                self.process_single_post(post)

            logging.info(f"Terminato batch di analisi. Processati {len(unprocessed_posts)} post.")