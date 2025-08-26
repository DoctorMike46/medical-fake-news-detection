import re
import unicodedata
import langid
import logging
from typing import Optional, Dict, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

langid.set_languages(['it', 'en', 'es', 'fr', 'de'])

class LanguageDetector:
    """
    Classe per la rilevazione e gestione delle lingue nei testi
    """
    
    def __init__(self):
        self.language_mapping = {
            'it': 'italiano',
            'en': 'english',
            'es': 'español', 
            'fr': 'français',
            'de': 'deutsch',
            'pt': 'português',
            'ru': 'русский',
            'ar': 'العربية',
            'zh': '中文',
            'ja': '日本語'
        }
        
        self.language_patterns = {
            'it': [
                r'\b(il|la|lo|gli|le|un|una|del|della|dei|delle|nel|nella|per|con|che|sono|essere|avere)\b',
                r'\b(questo|questa|questi|queste|quello|quella|quelli|quelle)\b',
                r'\b(molto|anche|più|già|ancora|sempre|mai|ogni|tutti|tutte)\b'
            ],
            'en': [
                r'\b(the|and|of|to|in|for|with|on|at|by|from|that|this|these|those)\b',
                r'\b(have|has|had|will|would|could|should|can|may|might)\b',
                r'\b(very|much|more|most|some|any|all|each|every|many)\b'
            ]
        }
    
    @lru_cache(maxsize=1000)
    def detect_language(self, text: str, min_confidence: float = 0.7) -> str:
        """
        Rileva la lingua di un testo con cache e confidence threshold
        
        Args:
            text: Testo da analizzare
            min_confidence: Soglia minima di confidenza (0.0-1.0)
            
        Returns:
            Codice lingua ISO (es. 'it', 'en') o 'und' se non determinabile
        """
        if not text or not text.strip():
            return "und"
        
        cleaned_text = self._preprocess_for_detection(text)
        
        if len(cleaned_text) < 10:
            logger.debug(f"Text too short for reliable detection: '{cleaned_text[:50]}'")
            return "und"
        
        try:
            lang, confidence = langid.classify(cleaned_text)
            
            logger.debug(f"Language detected: {lang} (confidence: {confidence:.3f})")
            
            if confidence < min_confidence:
                logger.debug(f"Low confidence detection: {confidence:.3f} < {min_confidence}")
                
                pattern_lang = self._detect_by_patterns(cleaned_text)
                if pattern_lang:
                    logger.debug(f"Pattern-based detection: {pattern_lang}")
                    return pattern_lang
                
                return "und"
            
            return lang
            
        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return "und"
    
    def _preprocess_for_detection(self, text: str) -> str:
        """
        Preprocessa il testo per migliorare la detection
        """
        # Rimuovo URL
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
        
        # Rimuovo mention e hashtag
        text = re.sub(r'@\w+|#\w+', '', text)
        
        # Rimuovo emoji e caratteri speciali eccessivi
        text = re.sub(r'[^\w\s\.\,\!\?\:\;]', ' ', text)
        
        # Normalizzo spazi
        text = self.normalize_spaces(text)
        
        return text
    
    def _detect_by_patterns(self, text: str) -> Optional[str]:
        """
        Rileva la lingua usando pattern di parole comuni
        """
        text_lower = text.lower()
        
        scores = {}
        for lang, patterns in self.language_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
                score += matches
            
            if score > 0:
                scores[lang] = score
        
        if scores:
            best_lang = max(scores, key=scores.get)
            if scores[best_lang] >= 3:
                return best_lang
        
        return None
    
    def detect_with_confidence(self, text: str) -> Tuple[str, float]:
        """
        Rileva lingua con valore di confidenza
        
        Returns:
            Tupla (lingua, confidenza)
        """
        if not text or not text.strip():
            return "und", 0.0
        
        try:
            cleaned_text = self._preprocess_for_detection(text)
            lang, confidence = langid.classify(cleaned_text)
            return lang, confidence
        except Exception as e:
            logger.warning(f"Language detection with confidence failed: {e}")
            return "und", 0.0
    
    def get_language_name(self, lang_code: str) -> str:
        """
        Converte codice lingua in nome completo
        """
        return self.language_mapping.get(lang_code, lang_code)
    
    def is_supported_language(self, lang_code: str, 
                            supported_langs: Optional[list] = None) -> bool:
        """
        Verifica se una lingua è supportata
        """
        if supported_langs is None:
            supported_langs = ['it', 'en']
        
        return lang_code in supported_langs
    
    @staticmethod
    def normalize_spaces(text: str) -> str:
        """
        Normalizza gli spazi multipli in spazio singolo
        """
        if not text:
            return text
        return re.sub(r'\s+', ' ', text).strip()
    
    @staticmethod
    def strip_accents(text: str) -> str:
        """
        Rimuove gli accenti dai caratteri mantenendo la leggibilità
        """
        if not text:
            return text
        
        # Normalizzazione NFD (Normalization Form Decomposed)
        normalized = unicodedata.normalize('NFD', text)
        
        # Rimuovo i caratteri di combinazione (accenti)
        without_accents = ''.join(
            char for char in normalized 
            if unicodedata.category(char) != 'Mn'
        )
        
        return without_accents
    
    @staticmethod
    def clean_text_encoding(text: str) -> str:
        """
        Pulisce problemi di encoding comuni
        """
        if not text:
            return text
        
        # Sostituzione comune per caratteri mal codificati
        replacements = {
            'â€™': "'",
            'â€œ': '"',
            'â€\x9d': '"',
            'â€"': '–',
            'â€"': '—',
            'Â ': ' ',
            'Ã ': 'à',
            'Ã¨': 'è',
            'Ã©': 'é',
            'Ã¬': 'ì',
            'Ã²': 'ò',
            'Ã¹': 'ù'
        }
        
        cleaned = text
        for bad, good in replacements.items():
            cleaned = cleaned.replace(bad, good)
        
        return cleaned
    
    def detect_multiple_languages(self, text: str, 
                                threshold: float = 0.3) -> Dict[str, float]:
        """
        Rileva più lingue presenti in un testo (utile per testi misti)
        """
        if not text or len(text) < 50:
            return {}
        
        # Divido il testo in frasi
        sentences = re.split(r'[.!?]+', text)
        
        language_scores = {}
        
        for sentence in sentences:
            if len(sentence.strip()) < 10:
                continue
            
            lang, confidence = self.detect_with_confidence(sentence)
            
            if confidence >= threshold:
                if lang in language_scores:
                    language_scores[lang] += confidence
                else:
                    language_scores[lang] = confidence
        
        # Normalizzo i punteggi
        if language_scores:
            total_score = sum(language_scores.values())
            language_scores = {
                lang: score / total_score 
                for lang, score in language_scores.items()
            }
        
        return language_scores


_detector = LanguageDetector()


def detect_language_with_confidence(text: str) -> Tuple[str, float]:
    """
    Rileva lingua con confidenza
    """
    return _detector.detect_with_confidence(text)

def is_italian(text: str, min_confidence: float = 0.7) -> bool:
    """
    Verifica se un testo è in italiano
    """
    lang, confidence = _detector.detect_with_confidence(text)
    return lang == 'it' and confidence >= min_confidence

def is_english(text: str, min_confidence: float = 0.7) -> bool:
    """
    Verifica se un testo è in inglese
    """
    lang, confidence = _detector.detect_with_confidence(text)
    return lang == 'en' and confidence >= min_confidence