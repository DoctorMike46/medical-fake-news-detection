import re
import logging
from typing import List, Tuple, Set, Dict, Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from abc import ABC, abstractmethod
from app.nlp.preprocessing.language_detector import LanguageDetector

logger = logging.getLogger(__name__)

@dataclass
class RankingConfig:
    """Configurazione per il ranking dei documenti"""
    lang_whitelist: Tuple[str, ...] = ("it", "en")
    since_days: int = 730
    min_chars: int = 300
    tfidf_ngram_range: Tuple[int, int] = (1, 2)
    tfidf_min_df: int = 1
    tfidf_max_df: float = 0.95

class BaseRanker(ABC):
    """Classe base per algoritmi di ranking"""
    
    def __init__(self, config: Optional[RankingConfig] = None):
        self.config = config or RankingConfig()
    
    @abstractmethod
    def rank(self, query: str, documents: List[dict]) -> List[Tuple[dict, float]]:
        """Rankga documenti per rilevanza rispetto alla query"""
        pass

class TFIDFRanker(BaseRanker):
    """Ranker basato su TF-IDF"""
    
    def rank(self, query: str, documents: List[dict]) -> List[Tuple[dict, float]]:
        """Ranking usando TF-IDF e similarità coseno"""
        if not documents:
            return []
        
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Preparo i testi: query + documenti
            texts = [query] + [
                self._extract_document_text(doc) for doc in documents
            ]
            
            # Creo vettorizzatore TF-IDF
            vectorizer = TfidfVectorizer(
                ngram_range=self.config.tfidf_ngram_range,
                min_df=self.config.tfidf_min_df,
                max_df=self.config.tfidf_max_df,
                stop_words=None
            )
            
            # Calcolo matrice TF-IDF
            tfidf_matrix = vectorizer.fit_transform(texts)
            
            # Calcolo similarità tra query (primo elemento) e documenti
            similarities = cosine_similarity(
                tfidf_matrix[0:1], 
                tfidf_matrix[1:]
            ).ravel()
            
            # Combino documenti con punteggi
            ranked = list(zip(documents, similarities))
            
            logger.debug(f"TF-IDF ranking: {len(ranked)} documents")
            return ranked
            
        except Exception as e:
            logger.error(f"Error in TF-IDF ranking: {e}")
            # Fallback a Jaccard
            return JaccardRanker(self.config).rank(query, documents)
    
    def _extract_document_text(self, doc: dict) -> str:
        """Estrae testo per TF-IDF"""
        title = doc.get("title", "")
        text = doc.get("text", "")
        return f"{title} {text}".strip()

class JaccardRanker(BaseRanker):
    """Ranker basato su Jaccard similarity"""
    
    def rank(self, query: str, documents: List[dict]) -> List[Tuple[dict, float]]:
        """Ranking usando Jaccard similarity sui token"""
        if not documents:
            return []
        
        query_tokens = self._tokenize(query)
        ranked = []
        
        for doc in documents:
            doc_text = self._extract_document_text(doc)
            doc_tokens = self._tokenize(doc_text)
            
            # Calcolo Jaccard similarity
            intersection = len(query_tokens & doc_tokens)
            union = len(query_tokens | doc_tokens)
            
            similarity = intersection / union if union > 0 else 0.0
            ranked.append((doc, similarity))
        
        logger.debug(f"Jaccard ranking: {len(ranked)} documents")
        return ranked
    
    def _tokenize(self, text: str) -> Set[str]:
        """Tokenizza testo per Jaccard"""
        if not text:
            return set()
        
        # Pattern per token alfanumerici
        tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9#]+", text.lower())
        return set(tokens)
    
    def _extract_document_text(self, doc: dict) -> str:
        """Estrae testo per Jaccard"""
        title = doc.get("title", "")
        text = doc.get("text", "")
        return f"{title} {text}".strip()

class DocumentFilter:
    """Classe per filtraggio documenti per topic e criteri di qualità"""
    
    def __init__(self, config: Optional[RankingConfig] = None):
        self.config = config or RankingConfig()
    
    def make_must_terms_for_topic(self, topic: str, post_text: str = "") -> Set[str]:
        """
        Genera termini obbligatori basati su topic e contenuto del post
        """
        topic_lower = topic.lower()
        post_lower = (post_text or "").lower()
        
        must_terms = set()
        
        
        # Se il post menziona Italia, richiedo termini geografici
        italian_indicators = ["italia", "italy", "italiano", "regioni italiane"]
        if any(indicator in post_lower for indicator in italian_indicators):
            must_terms.update({"italia", "italy"})
        
        # Termini medici generali basati sul topic
        medical_must_terms = self._get_medical_must_terms(topic_lower)
        must_terms.update(medical_must_terms)
        
        logger.debug(f"Generated must terms for topic '{topic}': {must_terms}")
        return must_terms
    
    def _get_medical_must_terms(self, topic: str) -> Set[str]:
        """Genera termini medici obbligatori basati sul topic"""
        medical_mapping = {
            "vaccino": {"vaccin", "immuniz"},
            "covid": {"covid", "coronavirus", "sars"},
            "influenza": {"influenza", "flu"},
            "diabete": {"diabet"},
            "tumore": {"tumor", "cancer", "oncolog"},
            "antibiotico": {"antibiotic", "antimicrob"}
        }
        
        must_terms = set()
        for key, terms in medical_mapping.items():
            if key in topic:
                must_terms.update(terms)
        
        return must_terms
    
    def filter_by_topic(self, documents: List[dict], topic: str, post_text: str,
                       post_lang: str, expanded_keys: Set[str],
                       must_terms: Optional[Set[str]] = None) -> List[dict]:
        """
        Filtra documenti per rilevanza al topic
        """
        if not documents:
            return []
        
        must_terms = must_terms or self.make_must_terms_for_topic(topic, post_text)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.config.since_days)
        
        filtered = []
        
        for doc in documents:
            # Filtro lingua
            if not self._check_language_filter(doc, self.config.lang_whitelist):
                continue
            
            # Filtro data
            if not self._check_date_filter(doc, cutoff_date):
                continue
            
            # Filtro lunghezza minima
            if not self._check_length_filter(doc, self.config.min_chars):
                continue
            
            # Filtro must terms (se definiti)
            if must_terms and not self._check_must_terms(doc, must_terms):
                continue
            
            # Filtro chiavi espanse
            if not self._check_expanded_keys(doc, expanded_keys):
                continue
            
            filtered.append(doc)
        
        logger.debug(f"Filtered {len(filtered)} documents from {len(documents)} candidates")
        return filtered
    
    def _check_language_filter(self, doc: dict, lang_whitelist: Tuple[str, ...]) -> bool:
        """Verifica filtro lingua"""
        if not lang_whitelist:
            return True
        
        doc_lang = doc.get("lang", "")
        if not doc_lang:
            return True  
        
        # Prendo solo i primi 2 caratteri del codice lingua
        lang_code = doc_lang.split("-")[0].lower()
        return lang_code in lang_whitelist
    
    def _check_date_filter(self, doc: dict, cutoff_date: datetime) -> bool:
        """Verifica filtro data"""
        created_str = doc.get("created_utc", "")
        if not created_str:
            return True  
        
        try:
            created_date = datetime.fromisoformat(created_str)
            return created_date >= cutoff_date
        except Exception:
            return True
    
    def _check_length_filter(self, doc: dict, min_chars: int) -> bool:
        """Verifica filtro lunghezza minima"""
        title = doc.get("title", "")
        text = doc.get("text", "")

        language_detector = LanguageDetector()
        combined_text = language_detector.normalize_spaces(f"{title} {text}")
        
        return len(combined_text) >= min_chars
    
    def _check_must_terms(self, doc: dict, must_terms: Set[str]) -> bool:
        """Verifica presenza di termini obbligatori"""
        if not must_terms:
            return True
        
        title = doc.get("title", "")
        text = doc.get("text", "")
        combined_text = f"{title} {text}".lower()
        
        return any(term.lower() in combined_text for term in must_terms)
    
    def _check_expanded_keys(self, doc: dict, expanded_keys: Set[str]) -> bool:
        """Verifica presenza di chiavi espanse"""
        if not expanded_keys:
            return True
        
        title = doc.get("title", "")
        text = doc.get("text", "")
        combined_text = f"{title} {text}".lower()
        
        return any(key.lower() in combined_text for key in expanded_keys)

class DocumentRanker:
    """Classe principale per ranking e filtraggio documenti"""
    
    def __init__(self, config: Optional[RankingConfig] = None):
        self.config = config or RankingConfig()
        self.filter = DocumentFilter(config)
        self.tfidf_ranker = TFIDFRanker(config)
        self.jaccard_ranker = JaccardRanker(config)
    
    def rank_for_post(self, post_text: str, documents: List[dict], 
                     top_k: int = 5, use_tfidf: bool = True) -> List[dict]:
        """
        Rankga documenti per rilevanza rispetto a un post
        
        Args:
            post_text: Testo del post come query
            documents: Lista di documenti da rankgare
            top_k: Numero di documenti top da restituire
            use_tfidf: Se usare TF-IDF (altrimenti Jaccard)
            
        Returns:
            Lista di documenti rankgati
        """
        if not documents:
            return []
        
        ranker = self.tfidf_ranker if use_tfidf else self.jaccard_ranker
        
        try:
            ranked_docs = ranker.rank(post_text, documents)
            
            ranked_docs.sort(key=lambda x: x[1], reverse=True)
            
            return [doc for doc, score in ranked_docs[:top_k]]
            
        except Exception as e:
            logger.error(f"Error in ranking: {e}")
            return documents[:top_k]  


# Istanze globali e funzioni di compatibilità
_default_filter = DocumentFilter()
_default_ranker = DocumentRanker()

def make_must_terms_for_topic(topic: str, post_text: str = "") -> Set[str]:
    return _default_filter.make_must_terms_for_topic(topic, post_text)

def filter_by_topic(items: List[dict], topic: str, post_text: str,
                   post_lang: str, expanded_keys: Set[str],
                   lang_whitelist=("it", "en"), since_days=730,
                   min_chars=300, must_terms: Set[str] = None) -> List[dict]:

    config = RankingConfig(
        lang_whitelist=lang_whitelist,
        since_days=since_days,
        min_chars=min_chars
    )
    
    filter_instance = DocumentFilter(config)
    return filter_instance.filter_by_topic(
        items, topic, post_text, post_lang, expanded_keys, must_terms
    )

# Funzioni di utilità
def _contains_any(text: str, keys: Set[str]) -> bool:
    """Verifica se il testo contiene almeno una delle chiavi"""
    if not text or not keys:
        return False
    
    text_lower = text.lower()
    return any(key.lower() in text_lower for key in keys)

def _tok(s: str) -> Set[str]:
    """Tokenizza stringa"""
    ranker = JaccardRanker()
    return ranker._tokenize(s)