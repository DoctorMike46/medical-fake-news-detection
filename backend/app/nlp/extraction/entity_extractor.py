import logging
from typing import List, Dict, Set, Optional, Tuple
import re
from dataclasses import dataclass
from enum import Enum
from app.nlp.preprocessing.language_detector import LanguageDetector
from .term_extractor import TermExtractor

logger = logging.getLogger(__name__)

class EntityType(Enum):
    """Tipi di entità mediche riconosciute"""
    DISEASE = "disease"
    DRUG = "drug"
    SYMPTOM = "symptom"
    TREATMENT = "treatment"
    ORGANIZATION = "organization"
    PERSON = "person"
    LOCATION = "location"
    DATE = "date"
    NUMBER = "number"
    UNKNOWN = "unknown"

@dataclass
class Entity:
    """Rappresenta un'entità estratta"""
    text: str
    entity_type: EntityType
    start: int
    end: int
    confidence: float
    context: str = ""
    
class MedicalEntityExtractor:
    """
    Estrattore specializzato per entità mediche
    """
    
    def __init__(self):
        self.term_extractor = TermExtractor()
        
        # Pattern per riconoscimento entità mediche
        self.medical_patterns = {
            EntityType.DISEASE: [
                r'\b(?:covid|coronavirus|influenza|diabete|tumore|cancro|aids|hiv)\b',
                r'\b(?:malattia|sindrome|disturbo)\s+(?:di\s+)?[\w\s]{2,20}\b',
                r'\b[\w\s]{2,15}(?:ite|osi|emia|patia)\b'
            ],
            EntityType.DRUG: [
                r'\b(?:farmaco|medicinale|medicina|pillola|compressa|vaccino)\b',
                r'\b[\w\s]{3,20}(?:cillin|mycin|prazol|statin)\b',
                r'\b(?:mg|ml|gr|grammi?|milligrammi?|microgrammi?)\b'
            ],
            EntityType.SYMPTOM: [
                r'\b(?:febbre|dolore|mal\s+di|nausea|vomito|tosse|raffreddore)\b',
                r'\b(?:sintom[io]|segn[io])\s+(?:di\s+)?[\w\s]{2,20}\b'
            ],
            EntityType.TREATMENT: [
                r'\b(?:terapia|trattamento|cura|intervento|operazione|chirurgia)\b',
                r'\b(?:fisioterapia|chemioterapia|radioterapia|immunoterapia)\b'
            ],
            EntityType.ORGANIZATION: [
                r'\b(?:ospedale|clinica|ambulatorio|ASL|ministero|OMS|WHO|CDC|ISS)\b',
                r'\b(?:università|istituto|centro)\s+[\w\s]{2,30}\b'
            ]
        }
        
        # Dizionari di entità conosciute
        self.known_entities = {
            EntityType.DISEASE: {
                'it': {
                    'covid-19', 'coronavirus', 'sars-cov-2', 'influenza', 'diabete',
                    'ipertensione', 'tumore', 'cancro', 'alzheimer', 'parkinson',
                    'sclerosi multipla', 'artrite', 'asma', 'bronchite', 'polmonite'
                },
                'en': {
                    'covid-19', 'coronavirus', 'sars-cov-2', 'influenza', 'diabetes',
                    'hypertension', 'tumor', 'cancer', 'alzheimer', 'parkinson',
                    'multiple sclerosis', 'arthritis', 'asthma', 'bronchitis', 'pneumonia'
                }
            },
            EntityType.DRUG: {
                'it': {
                    'aspirina', 'paracetamolo', 'ibuprofene', 'antibiotico',
                    'vitamina', 'insulina', 'cortisone', 'vaccino'
                },
                'en': {
                    'aspirin', 'paracetamol', 'ibuprofen', 'antibiotic',
                    'vitamin', 'insulin', 'cortisone', 'vaccine'
                }
            }
        }
    
    def extract_entities(self, text: str, lang_hint: Optional[str] = None) -> List[Entity]:
        """
        Estrae entità mediche da un testo
        """
        if not text or not text.strip():
            return []
        

        language_detector = LanguageDetector()
        
        normalized_text = language_detector.normalize_spaces(text)
        
        if not lang_hint:
            lang_hint = language_detector.detect_language(normalized_text)
        
        entities = []
        
        # 1. Estrazione con spaCy
        spacy_entities = self._extract_with_spacy(normalized_text, lang_hint)
        entities.extend(spacy_entities)
        
        # 2. Estrazione con pattern
        pattern_entities = self._extract_with_patterns(normalized_text, lang_hint)
        entities.extend(pattern_entities)
        
        # 3. Estrazione da dizionari
        dict_entities = self._extract_from_dictionaries(normalized_text, lang_hint)
        entities.extend(dict_entities)
        
        entities = self._remove_overlapping_entities(entities)
        
        return entities
    
    def _extract_with_spacy(self, text: str, lang: str) -> List[Entity]:
        """Estrae entità usando spaCy"""
        entities = []
        
        try:
            spacy_entities = self.term_extractor.extract_entities_with_labels(text, lang)
            
            for ent in spacy_entities:
                entity_type = self._map_spacy_label(ent['label'])
                
                entities.append(Entity(
                    text=ent['text'],
                    entity_type=entity_type,
                    start=ent['start'],
                    end=ent['end'],
                    confidence=ent.get('confidence', 0.8),
                    context=self._get_context(text, ent['start'], ent['end'])
                ))
                
        except Exception as e:
            logger.warning(f"spaCy entity extraction failed: {e}")
        
        return entities
    
    def _extract_with_patterns(self, text: str, lang: str) -> List[Entity]:
        """Estrae entità usando pattern regex"""
        entities = []
        text_lower = text.lower()
        
        for entity_type, patterns in self.medical_patterns.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                    entities.append(Entity(
                        text=match.group(),
                        entity_type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.6,  
                        context=self._get_context(text, match.start(), match.end())
                    ))
        
        return entities
    
    def _extract_from_dictionaries(self, text: str, lang: str) -> List[Entity]:
        """Estrae entità da dizionari predefiniti"""
        entities = []
        text_lower = text.lower()
        
        lang_normalized = lang.lower()[:2] 
        
        for entity_type, lang_dict in self.known_entities.items():
            terms = lang_dict.get(lang_normalized, set())
            
            for term in terms:
                start = 0
                while True:
                    pos = text_lower.find(term.lower(), start)
                    if pos == -1:
                        break
                    
                    if self._is_word_boundary(text_lower, pos, pos + len(term)):
                        entities.append(Entity(
                            text=text[pos:pos + len(term)],
                            entity_type=entity_type,
                            start=pos,
                            end=pos + len(term),
                            confidence=0.9,
                            context=self._get_context(text, pos, pos + len(term))
                        ))
                    
                    start = pos + 1
        
        return entities
    
    def _map_spacy_label(self, label: str) -> EntityType:
        """Mappa le etichette spaCy ai nostri tipi"""
        label_mapping = {
            'PERSON': EntityType.PERSON,
            'ORG': EntityType.ORGANIZATION,
            'GPE': EntityType.LOCATION,
            'LOC': EntityType.LOCATION,
            'DATE': EntityType.DATE,
            'CARDINAL': EntityType.NUMBER,
            'ORDINAL': EntityType.NUMBER,
            'QUANTITY': EntityType.NUMBER,
        }
        
        return label_mapping.get(label, EntityType.UNKNOWN)
    
    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Estrae il contesto attorno a un'entità"""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()
    
    def _is_word_boundary(self, text: str, start: int, end: int) -> bool:
        """Verifica se una posizione è un confine di parola"""
        if start > 0 and text[start - 1].isalnum():
            return False
        if end < len(text) and text[end].isalnum():
            return False
        return True
    
    def _remove_overlapping_entities(self, entities: List[Entity]) -> List[Entity]:
        """Rimuove entità sovrapposte, mantenendo quelle con confidenza più alta"""
        if not entities:
            return []
        
        entities.sort(key=lambda x: x.confidence, reverse=True)
        
        filtered = []
        for entity in entities:
            overlaps = False
            for accepted in filtered:
                if (entity.start < accepted.end and entity.end > accepted.start):
                    overlaps = True
                    break
            
            if not overlaps:
                filtered.append(entity)
        
        filtered.sort(key=lambda x: x.start)
        
        return filtered
    
    def extract_medical_entities_summary(self, text: str, 
                                       lang_hint: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Estrae un riassunto delle entità mediche per tipo
        """
        entities = self.extract_entities(text, lang_hint)
        
        summary = {}
        for entity in entities:
            entity_type = entity.entity_type.value
            if entity_type not in summary:
                summary[entity_type] = []
            summary[entity_type].append(entity.text)
        
        for entity_type in summary:
            summary[entity_type] = list(set(summary[entity_type]))
        
        return summary
    
    def get_entity_statistics(self, text: str, 
                            lang_hint: Optional[str] = None) -> Dict[str, int]:
        """
        Statistiche sulle entità estratte
        """
        entities = self.extract_entities(text, lang_hint)
        
        stats = {}
        for entity in entities:
            entity_type = entity.entity_type.value
            stats[entity_type] = stats.get(entity_type, 0) + 1
        
        stats['total'] = len(entities)
        return stats