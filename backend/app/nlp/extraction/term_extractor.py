from __future__ import annotations
import logging
from functools import lru_cache
from typing import List, Set, Dict, Optional, Tuple
import spacy
from spacy.util import is_package
from spacy.cli import download as spacy_download
from spacy.lang.it import Italian
from spacy.lang.en import English
from app.nlp.preprocessing.language_detector import LanguageDetector

logger = logging.getLogger(__name__)

class TermExtractor:
    """
    Classe per l'estrazione di termini e entità da testi medici usando spaCy
    """
    
    def __init__(self):
        self._nlp_models = {}
        self._model_capabilities = {}
        self._initialize_models()
    
    def _initialize_models(self):
        """Inizializza i modelli spaCy disponibili"""
        logger.info("Initializing spaCy models for term extraction")
        
        # Modelli preferiti per lingua
        self.preferred_models = {
            'en': ['en_core_web_sm', 'en_core_web_md'],
            'it': ['it_core_news_sm', 'it_core_news_md'],
        }
        
        # Carica modelli disponibili
        for lang in ['en', 'it']:
            model = self._get_best_model(lang)
            if model:
                self._nlp_models[lang] = model
                self._analyze_model_capabilities(lang, model)
    
    def _get_best_model(self, lang: str) -> Optional[spacy.Language]:
        """
        Ottiene il miglior modello disponibile per una lingua
        """
        logger.debug(f"Loading best model for language: {lang}")
        
        for model_name in self.preferred_models.get(lang, []):
            try:
                if is_package(model_name):
                    model = spacy.load(model_name)
                    logger.info(f"Loaded model: {model_name}")
                    return model
                else:
                    logger.info(f"Attempting to download model: {model_name}")
                    try:
                        spacy_download(model_name)
                        model = spacy.load(model_name)
                        logger.info(f"Downloaded and loaded model: {model_name}")
                        return model
                    except Exception as e:
                        logger.warning(f"Failed to download {model_name}: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Failed to load model {model_name}: {e}")
                continue
        
        logger.warning(f"No advanced models available for {lang}, using blank model")
        if lang == 'en':
            return English()
        elif lang == 'it':
            return Italian()
        else:
            return spacy.blank(lang)
    
    def _analyze_model_capabilities(self, lang: str, model: spacy.Language):
        """Analizza le capacità del modello caricato"""
        capabilities = {
            'has_ner': model.has_pipe('ner'),
            'has_tagger': model.has_pipe('tagger'),
            'has_parser': model.has_pipe('parser'),
            'has_lemmatizer': model.has_pipe('lemmatizer'),
            'model_name': model.meta.get('name', 'unknown'),
            'version': model.meta.get('version', 'unknown')
        }
        
        self._model_capabilities[lang] = capabilities
        logger.info(f"Model capabilities for {lang}: {capabilities}")
    
    @lru_cache(maxsize=100)
    def get_model(self, lang: str) -> spacy.Language:
        """
        Ottiene il modello per una lingua (con cache)
        """
        if lang in self._nlp_models:
            return self._nlp_models[lang]
        
        logger.warning(f"No model cached for {lang}, using blank model")
        return spacy.blank(lang)
    
    def extract_terms(self, text: str, lang_hint: Optional[str] = None,
                     min_length: int = 3, max_terms: int = 50) -> Set[str]:
        """
        Estrae termini rilevanti da un testo
        
        Args:
            text: Testo da analizzare
            lang_hint: Suggerimento lingua (auto-detect se None)
            min_length: Lunghezza minima termini
            max_terms: Numero massimo di termini da estrarre
            
        Returns:
            Set di termini estratti
        """
        if not text or not text.strip():
            return set()
        
        language_detector = LanguageDetector()
        
        if not lang_hint:
            lang_hint = language_detector.detect_language(text)
        
        lang = self._normalize_language_code(lang_hint)
        
        nlp = self.get_model(lang)
        
        try:
            doc = nlp(text[:10000]) 
            
            terms = set()
            capabilities = self._model_capabilities.get(lang, {})
            
            # 1. Estrazione entità (se NER disponibile)
            if capabilities.get('has_ner', False):
                for ent in doc.ents:
                    cleaned_ent = self._clean_term(ent.text)
                    if len(cleaned_ent) >= min_length:
                        terms.add(cleaned_ent)
            
            # 2. Estrazione sostantivi e nomi propri
            if capabilities.get('has_tagger', False):
                for token in doc:
                    if (token.is_alpha and 
                        len(token.text) >= min_length and
                        token.pos_ in {'NOUN', 'PROPN'} and
                        not token.is_stop):
                        
                        # Uso lemma se disponibile
                        if capabilities.get('has_lemmatizer', False) and token.lemma_:
                            term = self._clean_term(token.lemma_)
                        else:
                            term = self._clean_term(token.text)
                        
                        if len(term) >= min_length:
                            terms.add(term)
            
            # 3. Fallback: Estrazione token alfabetici
            if not terms:
                for token in doc:
                    if (token.is_alpha and 
                        len(token.text) >= min_length and
                        not token.is_stop):
                        term = self._clean_term(token.text)
                        if len(term) >= min_length:
                            terms.add(term)
            
            # Limita numero di termini e ordina per lunghezza (termini più lunghi = più specifici)
            sorted_terms = sorted(terms, key=len, reverse=True)
            return set(sorted_terms[:max_terms])
            
        except Exception as e:
            logger.error(f"Error extracting terms from text: {e}")
            return set()
    
    def extract_entities_with_labels(self, text: str, 
                                   lang_hint: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Estrae entità con le loro etichette
        
        Returns:
            Lista di dict con {text, label, start, end}
        """
        if not text or not text.strip():
            return []
        
        language_detector = LanguageDetector()
        
        if not lang_hint:
            lang_hint = language_detector.detect_language(text)
        
        lang = self._normalize_language_code(lang_hint)
        nlp = self.get_model(lang)
        
        try:
            doc = nlp(text[:10000])
            
            entities = []
            capabilities = self._model_capabilities.get(lang, {})
            
            if capabilities.get('has_ner', False):
                for ent in doc.ents:
                    entities.append({
                        'text': ent.text,
                        'label': ent.label_,
                        'start': ent.start_char,
                        'end': ent.end_char,
                        'confidence': getattr(ent, 'confidence', 1.0)
                    })
            
            return entities
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []
    
    def extract_medical_terms(self, text: str, lang_hint: Optional[str] = None) -> Set[str]:
        """
        Estrae termini medici specifici
        """
        # Termini medici comuni da cercare
        medical_keywords = {
            'it': {
                'vaccino', 'farmaco', 'terapia', 'diagnosi', 'sintomo', 'malattia',
                'virus', 'batterio', 'infezione', 'cura', 'medicina', 'dottore',
                'ospedale', 'clinica', 'paziente', 'trattamento', 'prevenzione'
            },
            'en': {
                'vaccine', 'drug', 'therapy', 'diagnosis', 'symptom', 'disease',
                'virus', 'bacteria', 'infection', 'cure', 'medicine', 'doctor',
                'hospital', 'clinic', 'patient', 'treatment', 'prevention'
            }
        }
        
        # Estrazione tutti i termini
        all_terms = self.extract_terms(text, lang_hint)

        language_detector = LanguageDetector()
        
        # Filtra per termini medici
        lang = self._normalize_language_code(lang_hint or language_detector.detect_language(text))
        medical_terms = set()
        
        for term in all_terms:
            term_lower = term.lower()
            keywords = medical_keywords.get(lang, set())
            
            if any(keyword in term_lower for keyword in keywords):
                medical_terms.add(term)
        
        return medical_terms
    
    def _clean_term(self, term: str) -> str:
        """Pulisce un termine estratto"""
        if not term:
            return ""
        
        # Rimozione spazi extra e converto a minuscolo
        cleaned = term.strip().lower()
        
        # Rimozione caratteri non alfabetici all'inizio e fine
        import re
        cleaned = re.sub(r'^[^a-zA-ZÀ-ÿ]+|[^a-zA-ZÀ-ÿ]+$', '', cleaned)
        
        return cleaned
    
    def _normalize_language_code(self, lang_code: str) -> str:
        """Normalizza il codice lingua"""
        if not lang_code:
            return 'en'
        
        lang_code = lang_code.lower().strip()
        
        # Mappa codici lingua
        lang_mapping = {
            'italian': 'it',
            'italiano': 'it',
            'english': 'en',
            'inglese': 'en'
        }
        
        return lang_mapping.get(lang_code, lang_code)
    
    def get_model_info(self, lang: str) -> Dict[str, any]:
        """Informazioni sul modello utilizzato per una lingua"""
        return self._model_capabilities.get(lang, {})
    
    def is_model_available(self, lang: str) -> bool:
        """Verifica se un modello è disponibile per una lingua"""
        return lang in self._nlp_models