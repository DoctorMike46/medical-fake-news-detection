import logging
from typing import Dict, List
from app.core.config import Config
from app.nlp.extraction.signals import SignalExtractor
from app.retrieval.hybrid_retrieval import HybridRetriever
from app.services.data_collection.evergreen.evergreen_service import EverGreenService
from app.services.data_collection.evergreen.institutional_feeds import InstitutionalFeedsCollector
from app.services.llm.llm_manager import LLMManager
from .result_validator import ResponseBuilder, GradeCalculator

logging.basicConfig(level=logging.INFO)


class FactCheckService:
    
    
    def __init__(self, llm_manager: LLMManager = None):
        self.logger = logging.getLogger(__name__)
        
        self.llm_manager = llm_manager or LLMManager()
        
        self.response_builder = ResponseBuilder()
        
        self.logger.info("FactCheckService inizializzato con LLMManager esistente")
    
    def run_factcheck(self, topic: str, post_text: str) -> Dict:
       
        try:
            if not post_text or not topic:
                return self.response_builder.build_error_response(
                    "missing_input", "Topic o testo del post assenti"
                )
            
            topic = self._normalize_topic(topic)
            
            self.logger.info(f"Raccolta evidenze per topic: {topic}")
            evidence_chunks = self._collect_evidence(topic, post_text)
            
            if not evidence_chunks:
                return self._handle_no_evidence(post_text)
            
            self.llm_manager.reset_failed_services()
            
            self.logger.info("Esecuzione fact-checking con LLM")
            
            factcheck_result = None
            try:
                if hasattr(self.llm_manager, 'factcheck_with_retry'):
                    factcheck_result = self.llm_manager.factcheck_with_retry(
                        post_text=post_text,
                        evidence_chunks=evidence_chunks,
                        max_retries=2
                    )
            except Exception as e:
                self.logger.warning(f"Nuovo metodo fallito: {e}")
            
            if not factcheck_result or not self._is_valid_result(factcheck_result):
                self.logger.info("Fallback al metodo legacy")
                factcheck_result = self._legacy_factcheck(post_text, evidence_chunks)
            
            sentiment = self._analyze_sentiment(post_text)
            
            factcheck_result = self._optimize_for_local_claims(
                factcheck_result, post_text
            )
            
            return self._build_final_response(
                factcheck_result, sentiment, evidence_chunks, post_text
            )
            
        except Exception as e:
            self.logger.exception("Errore fatale in run_factcheck")
            return self.response_builder.build_error_response("exception", str(e))
    
    def _normalize_topic(self, topic) -> str:
        """Normalizza il topic in stringa"""
        if not isinstance(topic, str):
            try:
                if hasattr(topic, "__iter__") and not isinstance(topic, dict):
                    return " ".join(str(t) for t in topic)
                else:
                    return str(topic)
            except Exception:
                return str(topic)
        return topic
    
    def _collect_evidence(self, topic: str, post_text: str) -> List[dict]:
        """Raccoglie evidenze per il fact-checking"""
        try:

            evergreen_service = EverGreenService()
            institutional_feeds_collector = InstitutionalFeedsCollector()
            
            base_docs = evergreen_service.get_evergreen_for_topic(topic)
            rss_items = base_docs + institutional_feeds_collector.collect_health_rss()
            
            valid_docs = [
                doc for doc in rss_items
                if isinstance(doc, dict) and 
                   (doc.get("text") or doc.get("content")) and 
                   doc.get("url")
            ]

            hybrid_retriever = HybridRetriever()
            
            context_chunks = hybrid_retriever.select_context_hybrid(
                topic=topic,
                post_text=post_text,
                rss_items=valid_docs,
                email_ncbi=Config.PUBMED_EMAIL,
                api_key_ncbi=Config.ENTREZ_API_KEY,
                top_docs=10,
                candidate_k=200,
                max_chunks=12
            )
            
            return self._clean_evidence_chunks(context_chunks)
            
        except Exception as e:
            self.logger.error(f"Errore raccolta evidenze: {e}")
            return []
    
    def _clean_evidence_chunks(self, chunks: List[dict]) -> List[dict]:
        """Pulisce e deduplica i chunks di evidenze"""
        if not chunks:
            return []
        
        cleaned_chunks = []
        seen_urls = set()
        
        for chunk in chunks:
            meta = chunk.get("meta") or {}
            url = meta.get("url") or ""
            content = chunk.get("content") or chunk.get("text") or ""
            
            if not url or not content or url in seen_urls:
                continue
            
            seen_urls.add(url)
            
            if len(content) > 1200:
                content = content[:1200]
            
            if not meta.get("source") and not meta.get("feed"):
                meta["source"] = "institutional"
            
            cleaned_chunk = {
                "content": content,
                "meta": meta
            }
            
            cleaned_chunks.append(cleaned_chunk)
        
        return cleaned_chunks
    
    def _legacy_factcheck(self, post_text: str, evidence_chunks: List[dict]) -> Dict:
        """
        Fallback al metodo legacy usando evaluate_text_with_rag
        """
        try:
            retrieved_context = []
            for chunk in evidence_chunks:
                meta = chunk.get("meta", {})
                retrieved_context.append({
                    "text": chunk.get("content", ""),
                    "source_url": meta.get("url", ""),
                    "source": meta.get("source", "")
                })
            
            for attempt in range(3):  
                service = self.llm_manager.get_next_service()
                
                if not service:
                    break
                
                try:
                    legacy_result = service.evaluate_text_with_rag(
                        post_text, retrieved_context
                    )
                    
                    if legacy_result and legacy_result.get("grado_disinformazione", -1) >= 0:
                        return self._convert_legacy_result(legacy_result, evidence_chunks)
                    
                except Exception as e:
                    service_name = self._get_service_name(service)
                    self.logger.warning(f"Servizio {service_name} fallito: {e}")
                    self.llm_manager.mark_as_failed(service_name)
                    continue
            
            return self._get_uncertain_result()
            
        except Exception as e:
            self.logger.error(f"Errore legacy factcheck: {e}")
            return self._get_uncertain_result()
    
    def _convert_legacy_result(self, legacy_result: Dict, evidence_chunks: List[dict]) -> Dict:
        """Converte risultato legacy nel formato dual-claim"""
        grado = legacy_result.get("grado_disinformazione", 1)
        motivazione = legacy_result.get("motivazione", "")
        
        if grado == 0:
            verdict = "REAL"
            confidence = 0.9
        elif grado >= 3:
            verdict = "FAKE"
            confidence = 0.8
        elif grado == 2:
            verdict = "FAKE"
            confidence = 0.6
        else:
            verdict = "UNCERTAIN"
            confidence = 0.5
        
        cited_evidence = []
        for i, chunk in enumerate(evidence_chunks[:3], 1): 
            meta = chunk.get("meta", {})
            cited_evidence.append({
                "idx": i,
                "title": meta.get("title", ""),
                "url": meta.get("url", "")
            })
        
        return {
            "general_claim": {
                "verdict": verdict,
                "reasoning": motivazione,
                "cited_evidence": cited_evidence
            },
            "local_claim": {
                "verdict": "UNCERTAIN",
                "reasoning": "Analisi locale/temporale non disponibile nel formato legacy.",
                "cited_evidence": []
            },
            "overall_verdict": verdict,
            "confidence": confidence
        }
    
    def _analyze_sentiment(self, text: str) -> str:
        """Analizza sentiment del testo"""
        try:
            if hasattr(self.llm_manager, 'analyze_sentiment'):
                return self.llm_manager.analyze_sentiment(text)
            else:
                service = self.llm_manager.get_next_service()
                if service:
                    return service.analyze_sentiment_only(text)
        except Exception as e:
            self.logger.warning(f"Errore analisi sentiment: {e}")
        
        return "neutro"
    
    def _optimize_for_local_claims(self, factcheck_result: dict, post_text: str) -> dict:
        """Ottimizza il verdetto se il post non contiene claim locali/temporali"""


        try:
            signal_extractor = SignalExtractor()
            country_signal, year_signal = signal_extractor.extract_locale_year_signals(post_text)
            has_local_claim = bool(country_signal or year_signal)
            
            if not has_local_claim:
                general_verdict = factcheck_result.get("general_claim", {}).get("verdict", "UNCERTAIN")
                factcheck_result["overall_verdict"] = general_verdict.upper()
                
                self.logger.info("Nessun claim locale rilevato, usando solo general_claim")
            
            return factcheck_result
            
        except Exception as e:
            self.logger.warning(f"Errore ottimizzazione local claims: {e}")
            return factcheck_result
    
    def _build_final_response(
        self, 
        factcheck_result: dict, 
        sentiment: str, 
        evidence_chunks: List[dict], 
        post_text: str
    ) -> dict:
        """Costruisce la risposta finale"""
        
        overall_verdict = factcheck_result.get("overall_verdict", "UNCERTAIN")
        confidence = factcheck_result.get("confidence", 0.5)
        
        grade = GradeCalculator.verdict_to_grade(overall_verdict, confidence)
        
        urls = []
        for claim_key in ["general_claim", "local_claim"]:
            claim = factcheck_result.get(claim_key, {}) or {}
            for evidence in claim.get("cited_evidence", []):
                url = evidence.get("url")
                if url and url not in urls:
                    urls.append(url)
        
        motivation = self._build_motivation(factcheck_result)
        
        return {
            "status": "ok",
            "factcheck": factcheck_result,
            "grado_disinformazione": grade,
            "valutazione_testuale": f"Verdetto complessivo: {overall_verdict}",
            "motivazione": motivation,
            "fonti_utilizzate": urls,
            "evidence_count": len(evidence_chunks),
            "sentiment": sentiment,
        }
    
    def _build_motivation(self, factcheck_result: dict) -> str:
        """Costruisce la motivazione dalla struttura dual-claim"""
        if not factcheck_result:
            return "Nessuna motivazione disponibile."
        
        general_reasoning = factcheck_result.get("general_claim", {}).get("reasoning", "")
        local_reasoning = factcheck_result.get("local_claim", {}).get("reasoning", "")
        
        parts = []
        if general_reasoning:
            parts.append(f"Generale: {general_reasoning}")
        if local_reasoning and "non disponibile" not in local_reasoning.lower():
            parts.append(f"Locale/Temporale: {local_reasoning}")
        
        motivation = " | ".join(parts)
        return motivation[:1500] if motivation else "Nessuna motivazione disponibile."
    
    def _handle_no_evidence(self, post_text: str) -> Dict:
        """Gestisce il caso senza evidenze"""
        sentiment = self._analyze_sentiment(post_text)
        
        uncertain_result = {
            "general_claim": {
                "verdict": "UNCERTAIN",
                "reasoning": "Nessuna evidenza disponibile per la valutazione.",
                "cited_evidence": []
            },
            "local_claim": {
                "verdict": "UNCERTAIN",
                "reasoning": "Nessuna evidenza disponibile per la valutazione.",
                "cited_evidence": []
            },
            "overall_verdict": "UNCERTAIN",
            "confidence": 0.3
        }
        
        return {
            "status": "ok",
            "factcheck": uncertain_result,
            "grado_disinformazione": 1,
            "evidence_count": 0,
            "sentiment": sentiment,
            "fonti_utilizzate": [],
            "valutazione_testuale": "Verdetto complessivo: UNCERTAIN",
            "motivazione": "Nessuna evidenza disponibile per la valutazione."
        }
    
    def _get_uncertain_result(self) -> Dict:
        """Ritorna risultato UNCERTAIN di default"""
        return {
            "general_claim": {
                "verdict": "UNCERTAIN",
                "reasoning": "Errore nell'analisi dei servizi LLM.",
                "cited_evidence": []
            },
            "local_claim": {
                "verdict": "UNCERTAIN",
                "reasoning": "Errore nell'analisi dei servizi LLM.",
                "cited_evidence": []
            },
            "overall_verdict": "UNCERTAIN",
            "confidence": 0.2
        }
    
    def _is_valid_result(self, result: Dict) -> bool:
        """Verifica se il risultato è valido"""
        return (
            isinstance(result, dict) and
            "overall_verdict" in result and
            "confidence" in result and
            result.get("overall_verdict") in ["REAL", "FAKE", "UNCERTAIN"]
        )
    
    def _get_service_name(self, service) -> str:
        """Ottiene il nome del servizio"""
        for name, svc in self.llm_manager.llm_services.items():
            if svc is service:
                return name
        return "unknown"