import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from app.nlp.embeddings.embedding_service import encode_one
from app.nlp.expansion.topic_expander import TopicExpander
from app.nlp.extraction.signals import SignalExtractor
from app.nlp.extraction.term_extractor import TermExtractor
from app.nlp.preprocessing.language_detector import LanguageDetector
from app.retrieval.vector_indexer import VectorIndexer
from .ranking import DocumentFilter, DocumentRanker
from .context_builder import build_rag_context

logger = logging.getLogger(__name__)

@dataclass
class HybridRetrievalConfig:
    """Configurazione per il retrieval ibrido"""
    # Parametri vettoriali
    candidate_k: int = 60
    vector_weight: float = 0.6
    
    # Parametri TF-IDF
    tfidf_weight: float = 0.4
    
    # Parametri boosting
    enable_country_boost: bool = True
    enable_year_boost: bool = True
    enable_category_boost: bool = True
    enable_keyword_boost: bool = True
    enable_institutional_boost: bool = True
    enable_time_decay: bool = True
    
    # Parametri temporali
    time_decay_half_life: int = 540  # giorni
    
    # Parametri finali
    top_docs: int = 5
    max_chunks: int = 6
    words_per_chunk: int = 350

class BoostCalculator:
    """Calcolatore di boost per ranking ibrido"""
    
    @staticmethod
    def country_boost(doc: dict, country_signal: Optional[str]) -> float:
        """Boost per rilevanza geografica"""
        if country_signal != "italy":
            return 1.0
        
        title = doc.get("title", "")
        text = doc.get("text", "")
        combined_text = f"{title} {text}".lower()
        
        # Cerco indicatori italiani
        italian_indicators = ["italia", "italy"]
        has_italian_content = any(indicator in combined_text for indicator in italian_indicators)
        has_italian_lang = doc.get("lang", "").startswith("it")
        
        if has_italian_content or has_italian_lang:
            return 1.15  # +15% boost
        else:
            return 0.92  # -8% penalty
    
    @staticmethod
    def year_boost(doc: dict, claim_year: Optional[int]) -> float:
        """Boost per rilevanza temporale"""
        if not claim_year:
            return 1.0
        
        title = doc.get("title", "")
        text = doc.get("text", "")
        url = doc.get("url", "")
        
        # Cerco anno nel contenuto
        combined_content = f"{title} {text} {url}".lower()
        year_mentioned = str(claim_year) in combined_content
        
        if year_mentioned:
            return 1.12  # +12% boost
        
        # Se è documento di sorveglianza, non penalizzo troppo
        category = doc.get("platform_meta", {}).get("category", "")
        if category == "surveillance":
            return 0.98  # -2% penalty
        else:
            return 0.93  # -7% penalty
    
    @staticmethod
    def category_boost(doc: dict) -> float:
        """Boost per categoria documento"""
        category = doc.get("platform_meta", {}).get("category", "")
        
        # Sorveglianza/epidemiologia ha priorità per dettagli locali/temporali
        if category == "surveillance":
            return 1.10  # +10% boost
        
        return 1.0
    
    @staticmethod
    def keyword_boost(doc: dict, keywords: set) -> float:
        """Boost per presenza di keyword specifiche"""
        if not keywords:
            return 1.0
        
        title = doc.get("title", "")
        text = doc.get("text", "")
        combined_text = f"{title} {text}".lower()
        
        # Conto hit delle keyword
        hits = sum(1 for keyword in keywords if keyword.lower() in combined_text)
        
        # Boost dolce: 1 + 0.05 per hit (max +25%)
        return min(1.0 + 0.05 * hits, 1.25)
    
    @staticmethod
    def time_decay(doc: dict, half_life_days: int = 365) -> float:
        """Calcola decadimento temporale esponenziale"""
        created_str = doc.get("created_utc", "")
        if not created_str:
            return 1.0
        
        try:
            created_date = datetime.fromisoformat(created_str).astimezone(timezone.utc)
            days_ago = (datetime.now(timezone.utc) - created_date).days
            
            # Decadimento esponenziale: 1.0 oggi, 0.5 a half_life_days
            return 0.5 ** (days_ago / max(1, half_life_days))
            
        except Exception:
            return 1.0

class HybridRetriever:
    """
    Sistema di retrieval ibrido che combina:
    - Retrieval vettoriale (embeddings)
    - Retrieval lessicale (TF-IDF)  
    - Boosting intelligente
    - Chunking per RAG
    """
    
    def __init__(self, config: Optional[HybridRetrievalConfig] = None):
        self.config = config or HybridRetrievalConfig()
        self.document_filter = DocumentFilter()
        self.document_ranker = DocumentRanker()
        self.boost_calculator = BoostCalculator()
    
    def select_context_hybrid(self, topic: str, post_text: str, rss_items: List[dict],
                             email_ncbi: Optional[str] = None, api_key_ncbi: Optional[str] = None,
                             top_docs: Optional[int] = None, candidate_k: Optional[int] = None,
                             max_chunks: Optional[int] = None) -> List[dict]:
        """
        Pipeline di retrieval ibrido completa:
        1) Analisi del post (lingua, termini, segnali)
        2) Espansione topic con MeSH opzionale
        3) Indicizzazione vettoriale
        4) Retrieval candidati via embedding
        5) Filtro per topic e qualità
        6) Reranking ibrido (TF-IDF + embeddings + boost)
        7) Chunking per RAG
        """
        top_docs = top_docs or self.config.top_docs
        candidate_k = candidate_k or self.config.candidate_k
        max_chunks = max_chunks or self.config.max_chunks

        language_detector = LanguageDetector()
        vector_indexer = VectorIndexer()
        
        post_text = language_detector.normalize_spaces(post_text or "")
        if not rss_items:
            logger.warning("No RSS items provided for hybrid retrieval")
            return []
        
        logger.info(f"Starting hybrid retrieval: topic='{topic}', {len(rss_items)} documents")
        
        # 1. Analisi del post
        analysis_results = self._analyze_post(post_text, topic, email_ncbi, api_key_ncbi)
        
        # 2. Indicizzazione vettoriale
        vector_store = vector_indexer.build_vector_index(rss_items)
        query_embedding = encode_one(post_text, normalize=True)
        
        # 3. Retrieval candidati via embedding
        vector_candidates = self._get_vector_candidates(
            vector_store, query_embedding, candidate_k
        )
        
        # 4. Filtro per topic
        filtered_candidates = self._filter_candidates(
            vector_candidates, analysis_results
        )
        
        # 5. Reranking ibrido
        final_documents = self._hybrid_rerank(
            filtered_candidates, post_text, analysis_results, top_docs
        )
        
        # 6. Chunking per RAG
        context_chunks = build_rag_context(
            final_documents, 
            max_chunks=max_chunks, 
            words_per_chunk=self.config.words_per_chunk
        )
        
        logger.info(f"Hybrid retrieval completed: {len(context_chunks)} context chunks")
        return context_chunks
    
    def _analyze_post(self, post_text: str, topic: str, 
                     email_ncbi: Optional[str], api_key_ncbi: Optional[str]) -> Dict[str, Any]:
        """Analizza il post per estrarre informazioni utili al retrieval"""
        
        language_detector = LanguageDetector()
        term_extractor = TermExtractor()
        signal_extractor = SignalExtractor()
        topic_expander = TopicExpander()
        # Rilevo lingua e estraggo termini
        post_lang = language_detector.detect_language(post_text)
        post_terms = term_extractor.extract_terms(post_text, lang_hint=post_lang)
        
        # Estraggo segnali geografici e temporali
        country_signal, year_signal = signal_extractor.extract_locale_year_signals(post_text)
        
        # Espando topic con termini correlati
        expanded_keys = topic_expander.expand_topic(topic, post_terms, email_ncbi, api_key_ncbi)
        
        # Genero termini obbligatori
        must_terms = self.document_filter.make_must_terms_for_topic(topic, post_text)
        
        analysis = {
            "post_lang": post_lang,
            "post_terms": post_terms,
            "country_signal": country_signal,
            "year_signal": year_signal,
            "expanded_keys": expanded_keys,
            "must_terms": must_terms,
            "topic": topic
        }
        
        logger.debug(f"Post analysis: lang={post_lang}, country={country_signal}, year={year_signal}")
        return analysis
    
    def _get_vector_candidates(self, vector_store, query_embedding, candidate_k: int) -> List[Tuple[dict, float]]:
        """Ottiene candidati dal retrieval vettoriale"""
        try:
            vector_results = vector_store.search(query_embedding, top_k=candidate_k)
            logger.debug(f"Vector search returned {len(vector_results)} candidates")
            return vector_results
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    def _filter_candidates(self, candidates: List[Tuple[dict, float]], 
                          analysis: Dict[str, Any]) -> List[Tuple[dict, float]]:
        """Filtra candidati per topic e qualità"""
        
        # Estraggo solo i documenti (senza punteggi vettoriali)
        candidate_docs = [doc for doc, score in candidates]
        
        # Applico filtri
        filtered_docs = self.document_filter.filter_by_topic(
            documents=candidate_docs,
            topic=analysis["topic"],
            post_text="",
            post_lang=analysis["post_lang"],
            expanded_keys=analysis["expanded_keys"],
            must_terms=analysis["must_terms"]
        )
        
        # Se nessun documento passa i filtri, applico fallback
        if not filtered_docs:
            filtered_docs = self._apply_fallback_filtering(candidates, analysis)
        
        # Ricostruisco lista con punteggi vettoriali
        vector_scores = {id(doc): score for doc, score in candidates}
        filtered_with_scores = [
            (doc, vector_scores.get(id(doc), 0.0)) 
            for doc in filtered_docs
        ]
        
        logger.debug(f"Filtered to {len(filtered_with_scores)} candidates")
        return filtered_with_scores
    
    def _apply_fallback_filtering(self, candidates: List[Tuple[dict, float]], 
                                 analysis: Dict[str, Any]) -> List[dict]:
        """Applica filtri di fallback quando i filtri principali sono troppo restrittivi"""
        
        must_terms = analysis["must_terms"]
        
        # Fallback 1: documenti che matchano almeno un must_term
        if must_terms:
            fallback_docs = []
            for doc, score in candidates:
                title = doc.get("title", "")
                text = doc.get("text", "")
                combined_text = f"{title} {text}".lower()
                
                if any(term.lower() in combined_text for term in must_terms):
                    fallback_docs.append(doc)
            
            if fallback_docs:
                logger.debug(f"Fallback 1: {len(fallback_docs)} documents with must terms")
                return fallback_docs[:max(self.config.top_docs * 3, 10)]
        
        # Fallback 2: primi documenti dal vector search
        fallback_docs = [doc for doc, score in candidates[:max(self.config.top_docs * 3, 10)]]
        logger.debug(f"Fallback 2: {len(fallback_docs)} top vector search results")
        return fallback_docs
    
    def _hybrid_rerank(self, candidates: List[Tuple[dict, float]], post_text: str,
                      analysis: Dict[str, Any], top_docs: int) -> List[dict]:
        """Reranking ibrido combinando TF-IDF, embedding e boost"""
        
        if not candidates:
            return []
        
        # Estrazione documenti
        docs = [doc for doc, vec_score in candidates]
        
        # Creo mapping punteggi vettoriali
        vector_scores = {id(doc): score for doc, score in candidates}
        
        # Calcolo punteggi TF-IDF
        tfidf_ranked = self.document_ranker.tfidf_ranker.rank(post_text, docs)
        tfidf_scores = {id(doc): score for doc, score in tfidf_ranked}
        
        # Calcolo punteggio ibrido per ogni documento
        hybrid_scored = []
        
        for doc in docs:
            doc_id = id(doc)
            
            # Punteggi base
            vector_sim = vector_scores.get(doc_id, 0.0)
            tfidf_sim = tfidf_scores.get(doc_id, 0.0)
            
            # Calcolo boost factors
            boost_factors = self._calculate_boost_factors(doc, analysis)
            
            # Punteggio ibrido
            hybrid_score = self._calculate_hybrid_score(
                vector_sim, tfidf_sim, boost_factors
            )
            
            hybrid_scored.append((doc, hybrid_score))
        
        # Ordino per punteggio decrescente
        hybrid_scored.sort(key=lambda x: x[1], reverse=True)
        
        # Restituisco top documenti
        final_docs = [doc for doc, score in hybrid_scored[:top_docs]]
        
        logger.debug(f"Hybrid reranking completed: {len(final_docs)} final documents")
        return final_docs
    
    def _calculate_boost_factors(self, doc: dict, analysis: Dict[str, Any]) -> Dict[str, float]:
        """Calcola tutti i fattori di boost per un documento"""
        
        boost_factors = {}
        
        if self.config.enable_country_boost:
            boost_factors["country"] = self.boost_calculator.country_boost(
                doc, analysis["country_signal"]
            )
        
        if self.config.enable_year_boost:
            boost_factors["year"] = self.boost_calculator.year_boost(
                doc, analysis["year_signal"]
            )
        
        if self.config.enable_category_boost:
            boost_factors["category"] = self.boost_calculator.category_boost(doc)
        
        if self.config.enable_keyword_boost:
            boost_factors["keyword"] = self.boost_calculator.keyword_boost(
                doc, analysis["must_terms"]
            )
        vector_indexer = VectorIndexer()
        
        if self.config.enable_institutional_boost:
            boost_factors["institutional"] = vector_indexer._is_institutional_source(doc)
        
        if self.config.enable_time_decay:
            boost_factors["time_decay"] = self.boost_calculator.time_decay(
                doc, self.config.time_decay_half_life
            )
        
        return boost_factors
    
    def _calculate_hybrid_score(self, vector_sim: float, tfidf_sim: float, 
                               boost_factors: Dict[str, float]) -> float:
        """Calcola il punteggio finale ibrido"""
        
        # Punteggio base: combinazione pesata di vector e TF-IDF
        base_score = (
            self.config.vector_weight * vector_sim + 
            self.config.tfidf_weight * tfidf_sim
        )
        
        # Applico tutti i boost factors
        final_score = base_score
        for factor_name, factor_value in boost_factors.items():
            final_score *= factor_value
        
        return final_score
    
    def get_retrieval_statistics(self, topic: str, post_text: str, 
                                rss_items: List[dict]) -> Dict[str, Any]:
        """Ottiene statistiche dettagliate sul processo di retrieval"""
        
        analysis = self._analyze_post(post_text, topic, None, None)

        vector_indexer = VectorIndexer()
        
        # Statistiche sui documenti di input
        total_docs = len(rss_items)
        
        # Analisi lingue
        lang_distribution = {}
        for doc in rss_items:
            lang = doc.get("lang", "unknown")
            lang_distribution[lang] = lang_distribution.get(lang, 0) + 1
        
        # Analisi fonti
        source_distribution = {}
        institutional_count = 0
        for doc in rss_items:
            source = doc.get("source", "unknown")
            source_distribution[source] = source_distribution.get(source, 0) + 1
            
            if vector_indexer._is_institutional_source(doc) > 1.0:
                institutional_count += 1
        
        return {
            "input_statistics": {
                "total_documents": total_docs,
                "language_distribution": lang_distribution,
                "source_distribution": source_distribution,
                "institutional_documents": institutional_count
            },
            "analysis_results": {
                "detected_language": analysis["post_lang"],
                "country_signal": analysis["country_signal"],
                "year_signal": analysis["year_signal"],
                "expanded_keys_count": len(analysis["expanded_keys"]),
                "must_terms_count": len(analysis["must_terms"])
            },
            "config": {
                "vector_weight": self.config.vector_weight,
                "tfidf_weight": self.config.tfidf_weight,
                "candidate_k": self.config.candidate_k,
                "top_docs": self.config.top_docs
            }
        }
