import re
import math
import logging
from collections import Counter
from typing import List, Set, Optional, Dict, Any
from dataclasses import dataclass

from app.nlp.preprocessing.language_detector import LanguageDetector

logger = logging.getLogger(__name__)

# Stop words per lingue supportate
STOP_WORDS = {
    "it": {
        "il", "la", "lo", "i", "gli", "le", "un", "una", "di", "a", "da", "in", 
        "con", "per", "su", "che", "e", "o", "ma", "del", "della", "dei", "delle",
        "nel", "nella", "sui", "dalla", "dalla", "alle", "agli", "col", "coi"
    },
    "en": {
        "the", "a", "an", "of", "to", "in", "on", "for", "with", "that", "and", 
        "or", "but", "is", "are", "was", "were", "be", "been", "have", "has", 
        "had", "do", "does", "did", "will", "would", "could", "should"
    }
}

# Dizionario termini medici comuni
MEDICAL_DICTIONARY = {
    # Malattie infettive
    "botulismo", "botulism", "west nile", "measles", "morbillo", "dengue", 
    "long covid", "covid-19", "coronavirus", "sars-cov-2", "influenza", 
    "tubercolosi", "tuberculosis", "malaria", "febbre gialla", "yellow fever",
    
    # Vaccini e farmaci
    "vaccino", "vaccine", "vaccination", "immunizzazione", "immunization",
    "antibiotico", "antibiotic", "farmaco", "drug", "medicina", "medicine",
    
    # Sintomi e condizioni
    "febbre", "fever", "tosse", "cough", "mal di testa", "headache",
    "nausea", "vomito", "diarrea", "dolore", "pain", "sintomo", "symptom",
    
    # Istituzioni sanitarie
    "who", "oms", "cdc", "iss", "ministero salute", "health ministry",
    "ospedale", "hospital", "clinica", "clinic", "medico", "doctor",
    
    # Termini epidemiologici
    "epidemia", "epidemic", "pandemia", "pandemic", "focolaio", "outbreak",
    "contagio", "contagion", "trasmissione", "transmission", "quarantena", "quarantine"
}

@dataclass
class TermExtractionConfig:
    """Configurazione per l'estrazione di termini"""
    max_terms: int = 8
    min_term_length: int = 3
    remove_stopwords: bool = True
    case_sensitive: bool = False
    include_medical_boost: bool = True

class TextEnrichmentService:
    """
    Servizio per l'arricchimento e analisi di testi medici
    """
    
    def __init__(self, config: Optional[TermExtractionConfig] = None):
        self.config = config or TermExtractionConfig()
        self.medical_terms = MEDICAL_DICTIONARY
    
    def tokenize(self, text: str, preserve_case: bool = False) -> List[str]:
        """
        Tokenizza un testo estraendo token alfanumerici
        
        Args:
            text: Testo da tokenizzare
            preserve_case: Se mantenere il case originale
            
        Returns:
            Lista di token
        """
        if not text:
            return []
        
        # Pattern per token: lettere (inclusi accenti), numeri, apostrofi, trattini
        pattern = r"[A-Za-zÀ-ÿ0-9\-']{2,}"
        
        if preserve_case or self.config.case_sensitive:
            tokens = re.findall(pattern, text)
        else:
            tokens = re.findall(pattern, text.lower())
        
        return tokens
    
    def remove_stopwords(self, tokens: List[str], lang: str = "it") -> List[str]:
        """
        Rimuove stop words dalla lista di token
        
        Args:
            tokens: Lista di token
            lang: Codice lingua
            
        Returns:
            Token filtrati
        """
        if not self.config.remove_stopwords:
            return tokens
        
        lang = lang.lower()[:2]
        stop_words = STOP_WORDS.get(lang, STOP_WORDS["it"])
        
        # Filtro stop words
        filtered_tokens = [token for token in tokens if token.lower() not in stop_words]
        
        return filtered_tokens
    
    def top_tfidf_terms(self, text: str, lang_hint: str = "it", k: Optional[int] = None) -> List[str]:
        """
        Estrae i termini più frequenti da un testo
        
        Args:
            text: Testo da analizzare
            lang_hint: Suggerimento lingua
            k: Numero massimo di termini (default da config)
            
        Returns:
            Lista di termini più rilevanti
        """
        if not text:
            return []
        
        k = k or self.config.max_terms

        language_detector = LanguageDetector()
        
        # Auto-detect lingua se non specificata
        if not lang_hint:
            lang_hint = language_detector.detect_language(text)
        
        tokens = self.tokenize(text)
        
        tokens = self.remove_stopwords(tokens, lang_hint)
        
        tokens = [t for t in tokens if len(t) >= self.config.min_term_length]
        
        if not tokens:
            return []
        
        term_counts = Counter(tokens)
        
        if self.config.include_medical_boost:
            term_counts = self._apply_medical_boost(term_counts)
        
        top_terms = [term for term, count in term_counts.most_common(k)]
        
        logger.debug(f"Extracted {len(top_terms)} top terms for language {lang_hint}")
        return top_terms
    
    def _apply_medical_boost(self, term_counts: Counter) -> Counter:
        """
        Applica boost ai termini medici rilevanti
        """
        boosted_counts = term_counts.copy()
        
        for term in term_counts:
            if any(med_term in term.lower() for med_term in self.medical_terms):
                boosted_counts[term] = int(term_counts[term] * 1.5)
        
        return boosted_counts
    
    def match_concepts_dictionary(self, text: str, max_concepts: int = 10) -> List[str]:
        """
        Trova concetti medici nel testo usando il dizionario
        
        Args:
            text: Testo da analizzare
            max_concepts: Numero massimo di concetti da restituire
            
        Returns:
            Lista di concetti medici trovati
        """
        if not text:
            return []
        
        language_detector = LanguageDetector()
        
        text_normalized = language_detector.normalize_spaces(text.lower())
        found_concepts = []
        
        # Cerco ogni termine del dizionario nel testo
        for term in self.medical_terms:
            if term.lower() in text_normalized:
                found_concepts.append(term)
        
        # Rimuovo duplicati e ordina per lunghezza decrescente
        unique_concepts = list(set(found_concepts))
        sorted_concepts = sorted(unique_concepts, key=lambda x: -len(x))
        
        logger.debug(f"Found {len(sorted_concepts)} medical concepts in text")
        return sorted_concepts[:max_concepts]
    
    def infer_topic_from_concepts(self, concepts: Optional[List[str]], 
                                 key_terms: Optional[List[str]]) -> Optional[str]:
        """
        Inferisce il topic principale da concetti e termini chiave
        
        Args:
            concepts: Lista di concetti medici
            key_terms: Lista di termini chiave
            
        Returns:
            Topic inferito o None
        """
        # Priorità ai concetti medici
        for concept in (concepts or []):
            if isinstance(concept, str) and len(concept.strip()) > 3:
                return concept.strip()
        
        # Fallback sui termini chiave
        for term in (key_terms or []):
            if isinstance(term, str) and len(term.strip()) > 3:
                return term.strip()
        
        return None
    
    def extract_medical_entities(self, text: str, lang_hint: str = "it") -> Dict[str, Any]:
        """
        Estrazione completa di entità mediche da un testo
        
        Args:
            text: Testo da analizzare
            lang_hint: Suggerimento lingua
            
        Returns:
            Dizionario con entità estratte
        """
        if not text:
            return {
                "key_terms": [],
                "medical_concepts": [],
                "inferred_topic": None,
                "language": "unknown",
                "token_count": 0
            }
        language_detector = LanguageDetector()

        normalized_text = language_detector.normalize_spaces(text)
        
        detected_lang = language_detector.detect_language(normalized_text) if not lang_hint else lang_hint
        
        key_terms = self.top_tfidf_terms(normalized_text, detected_lang)
        
        medical_concepts = self.match_concepts_dictionary(normalized_text)
        
        inferred_topic = self.infer_topic_from_concepts(medical_concepts, key_terms)
        
        tokens = self.tokenize(normalized_text)
        
        result = {
            "key_terms": key_terms,
            "medical_concepts": medical_concepts,
            "inferred_topic": inferred_topic,
            "language": detected_lang,
            "token_count": len(tokens),
            "has_medical_content": len(medical_concepts) > 0
        }
        
        logger.debug(f"Medical entity extraction completed: {len(key_terms)} terms, {len(medical_concepts)} concepts")
        return result
    
    def add_medical_terms(self, new_terms: Set[str]):
        """
        Aggiunge nuovi termini al dizionario medico
        
        Args:
            new_terms: Set di nuovi termini medici
        """
        original_count = len(self.medical_terms)
        self.medical_terms.update(new_terms)
        added_count = len(self.medical_terms) - original_count
        
        logger.info(f"Added {added_count} new medical terms to dictionary")
    
    def get_medical_term_statistics(self, text: str) -> Dict[str, Any]:
        """
        Calcola statistiche sui termini medici in un testo
        
        Args:
            text: Testo da analizzare
            
        Returns:
            Statistiche sui termini medici
        """
        if not text:
            return {"total_terms": 0, "medical_terms": 0, "medical_ratio": 0.0}
        
        # Tokenizza
        tokens = self.tokenize(text)
        total_terms = len(tokens)
        
        # Conta termini medici
        medical_count = 0
        found_medical_terms = []
        
        for token in tokens:
            if any(med_term in token.lower() for med_term in self.medical_terms):
                medical_count += 1
                found_medical_terms.append(token)
        
        medical_ratio = medical_count / total_terms if total_terms > 0 else 0.0
        
        return {
            "total_terms": total_terms,
            "medical_terms": medical_count,
            "medical_ratio": medical_ratio,
            "found_medical_terms": list(set(found_medical_terms)),
            "is_medical_text": medical_ratio > 0.1  # Soglia 10%
        }