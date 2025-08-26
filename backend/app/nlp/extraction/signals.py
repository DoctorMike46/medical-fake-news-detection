import re
import logging
from typing import Optional, Tuple, Dict, List, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from app.nlp.preprocessing.language_detector import LanguageDetector

logger = logging.getLogger(__name__)

@dataclass
class LocationSignal:
    """Rappresenta un segnale geografico estratto"""
    country: str
    region: Optional[str] = None
    city: Optional[str] = None
    confidence: float = 1.0
    context: str = ""

@dataclass  
class TimeSignal:
    """Rappresenta un segnale temporale estratto"""
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    relative_time: Optional[str] = None 
    confidence: float = 1.0
    context: str = ""

class SignalExtractor:
    """
    Estrattore di segnali geografici e temporali da testi
    """
    
    def __init__(self):
        # Pattern per paesi
        self.country_patterns = {
            'italy': {
                'it': [
                    r'\b(?:italia|italy|italiano|italiana|italiani|italiane)\b',
                    r'\bregioni?\s+italiane?\b',
                    r'\bstato\s+italiano\b',
                    r'\bpaese\s+nostro\b',
                    r'\bnazione\s+italiana\b'
                ],
                'en': [
                    r'\b(?:italy|italian|italians)\b',
                    r'\bitalian\s+(?:state|country|nation|regions?)\b'
                ]
            },
            'usa': {
                'it': [
                    r'\b(?:stati\s+uniti|usa|america|americano|americana)\b',
                    r'\bstati\s+uniti\s+d\'america\b'
                ],
                'en': [
                    r'\b(?:united\s+states|usa|america|american|americans)\b',
                    r'\bunited\s+states\s+of\s+america\b'
                ]
            },
            'france': {
                'it': [r'\b(?:francia|francese|francesi)\b'],
                'en': [r'\b(?:france|french)\b']
            },
            'germany': {
                'it': [r'\b(?:germania|tedesco|tedeschi|tedesca|tedesche)\b'],
                'en': [r'\b(?:germany|german|germans)\b']
            },
            'spain': {
                'it': [r'\b(?:spagna|spagnolo|spagnoli|spagnola|spagnole)\b'],
                'en': [r'\b(?:spain|spanish)\b']
            },
            'uk': {
                'it': [r'\b(?:regno\s+unito|inghilterra|inglese|inglesi|britannia|britannico)\b'],
                'en': [r'\b(?:united\s+kingdom|uk|england|britain|british)\b']
            }
        }
        
        # Pattern per regioni italiane
        self.italian_regions = {
            'lombardia': [r'\blombardia\b', r'\bmilan[oo]?\b', r'\bbergamo\b'],
            'lazio': [r'\blazio\b', r'\broma\b', r'\bromano\b'],
            'campania': [r'\bcampania\b', r'\bnapoli\b', r'\bnapoletano\b'],
            'veneto': [r'\bveneto\b', r'\bvenezia\b', r'\bveneziano\b', r'\bpadova\b'],
            'sicilia': [r'\bsicilia\b', r'\bsiciliano\b', r'\bpalermo\b', r'\bcatania\b'],
            'piemonte': [r'\bpiemonte\b', r'\btorino\b', r'\btorinese\b'],
            'puglia': [r'\bpuglia\b', r'\bbari\b', r'\bbarese\b'],
            'emilia-romagna': [r'\bemilia.?romagna\b', r'\bbologna\b', r'\bbolognese\b'],
            'toscana': [r'\btoscana\b', r'\bfirenze\b', r'\bfiorentino\b'],
            'calabria': [r'\bcalabria\b', r'\bcalabrese\b'],
            'sardegna': [r'\bsardegna\b', r'\bsardo\b', r'\bcagliari\b'],
            'liguria': [r'\bliguria\b', r'\bgenova\b', r'\bgenovese\b']
        }
        
        # Pattern temporali
        self.year_patterns = [
            r'\b(20[01]\d|19\d{2})\b',  # Anni 1900-2019
            r'\bnell?\'?\s*(20[01]\d|19\d{2})\b',  # "nel 2023", "nell'2023"
            r'\banno\s+(20[01]\d|19\d{2})\b',  # "anno 2023"
            r'\bdel\s+(20[01]\d|19\d{2})\b'   # "del 2023"
        ]
        
        # Pattern per mesi
        self.month_patterns = {
            'it': {
                'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
                'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8,
                'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12,
                # Abbreviazioni
                'gen': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mag': 5, 'giu': 6,
                'lug': 7, 'ago': 8, 'set': 9, 'ott': 10, 'nov': 11, 'dic': 12
            },
            'en': {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12,
                # Abbreviazioni
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
        }
        
        # Pattern per tempo relativo
        self.relative_time_patterns = {
            'it': [
                r'\b(?:oggi|stamattina|stasera|stanotte)\b',
                r'\b(?:ieri|l\'altro\s+ieri)\b',
                r'\b(?:domani|dopodomani)\b',
                r'\b(?:questa|la\s+scorsa|la\s+prossima)\s+settimana\b',
                r'\b(?:questo|il\s+scorso|il\s+prossimo)\s+mese\b',
                r'\b(?:quest\'|l\')\s*anno\b',
                r'\b(?:recentemente|ultimamente|di\s+recente)\b'
            ],
            'en': [
                r'\b(?:today|tonight|this\s+morning|this\s+evening)\b',
                r'\b(?:yesterday|the\s+day\s+before\s+yesterday)\b',
                r'\b(?:tomorrow|the\s+day\s+after\s+tomorrow)\b',
                r'\b(?:this|last|next)\s+week\b',
                r'\b(?:this|last|next)\s+month\b',
                r'\b(?:this|last|next)\s+year\b',
                r'\b(?:recently|lately|not\s+long\s+ago)\b'
            ]
        }
    
    def extract_location_signals(self, text: str, lang_hint: Optional[str] = None) -> List[LocationSignal]:
        """
        Estrae segnali geografici (paesi, regioni, città) dal testo
        """
        if not text or not text.strip():
            return []
        
        language_detector = LanguageDetector()
        
        normalized_text = language_detector.normalize_spaces(text.lower())
        
        if not lang_hint:
            lang_hint = language_detector.detect_language(text)
        
        lang = lang_hint.lower()[:2] if lang_hint else 'it'
        
        signals = []
        
        for country, lang_patterns in self.country_patterns.items():
            patterns = lang_patterns.get(lang, [])
            
            for pattern in patterns:
                matches = re.finditer(pattern, normalized_text, re.IGNORECASE)
                for match in matches:
                    confidence = 0.9  
                    context = self._get_context(text, match.start(), match.end())
                    
                    signals.append(LocationSignal(
                        country=country,
                        confidence=confidence,
                        context=context
                    ))
        
        italy_signals = [s for s in signals if s.country == 'italy']
        if italy_signals:
            region_signals = self._extract_italian_regions(normalized_text, text)
            signals.extend(region_signals)
        
        return self._deduplicate_location_signals(signals)
    
    def extract_time_signals(self, text: str, lang_hint: Optional[str] = None) -> List[TimeSignal]:
        """
        Estrae segnali temporali (anni, mesi, tempo relativo) dal testo
        """
        if not text or not text.strip():
            return []
        

        language_detector = LanguageDetector()
        
        normalized_text = language_detector.normalize_spaces(text.lower())
        
        if not lang_hint:
            lang_hint = language_detector.detect_language(text)
        
        lang = lang_hint.lower()[:2] if lang_hint else 'it'
        
        signals = []
        
        year_signals = self._extract_years(normalized_text, text)
        signals.extend(year_signals)
        
        month_signals = self._extract_months(normalized_text, text, lang)
        signals.extend(month_signals)
        
        relative_signals = self._extract_relative_time(normalized_text, text, lang)
        signals.extend(relative_signals)
        
        return self._deduplicate_time_signals(signals)
    
    def extract_locale_year_signals(self, text: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Funzione di compatibilità: estrae segnali di paese e anno
        
        Returns:
            Tupla (country_code, year) - usa None se non trovato
        """
        if not text:
            return None, None
        
        location_signals = self.extract_location_signals(text)
        time_signals = self.extract_time_signals(text)
        
        # Trova paese (priorità a Italy per compatibilità)
        country = None
        for signal in location_signals:
            if signal.country == 'italy':
                country = 'italy'
                break
        
        # Se non trova Italy, prendi il primo paese trovato
        if not country and location_signals:
            country = location_signals[0].country
        
        # Trova anno più recente
        year = None
        for signal in time_signals:
            if signal.year and (not year or signal.year > year):
                year = signal.year
        
        return country, year
    
    def _extract_italian_regions(self, normalized_text: str, original_text: str) -> List[LocationSignal]:
        """Estrae regioni italiane specifiche"""
        signals = []
        
        for region, patterns in self.italian_regions.items():
            for pattern in patterns:
                matches = re.finditer(pattern, normalized_text, re.IGNORECASE)
                for match in matches:
                    context = self._get_context(original_text, match.start(), match.end())
                    
                    signals.append(LocationSignal(
                        country='italy',
                        region=region,
                        confidence=0.8,
                        context=context
                    ))
        
        return signals
    
    def _extract_years(self, normalized_text: str, original_text: str) -> List[TimeSignal]:
        """Estrae anni dal testo"""
        signals = []
        
        for pattern in self.year_patterns:
            matches = re.finditer(pattern, normalized_text, re.IGNORECASE)
            for match in matches:
                year_match = re.search(r'(20[01]\d|19\d{2})', match.group())
                if year_match:
                    year = int(year_match.group())
                    
                    # Verifica che l'anno sia ragionevole (1990-2030)
                    if 1990 <= year <= 2030:
                        context = self._get_context(original_text, match.start(), match.end())
                        
                        signals.append(TimeSignal(
                            year=year,
                            confidence=0.9,
                            context=context
                        ))
        
        return signals
    
    def _extract_months(self, normalized_text: str, original_text: str, lang: str) -> List[TimeSignal]:
        """Estrae mesi dal testo"""
        signals = []
        
        month_dict = self.month_patterns.get(lang, {})
        
        for month_name, month_num in month_dict.items():
            pattern = r'\b' + re.escape(month_name) + r'\b'
            matches = re.finditer(pattern, normalized_text, re.IGNORECASE)
            
            for match in matches:
                context = self._get_context(original_text, match.start(), match.end())
                
                signals.append(TimeSignal(
                    month=month_num,
                    confidence=0.8,
                    context=context
                ))
        
        return signals
    
    def _extract_relative_time(self, normalized_text: str, original_text: str, lang: str) -> List[TimeSignal]:
        """Estrae espressioni di tempo relativo"""
        signals = []
        
        patterns = self.relative_time_patterns.get(lang, [])
        
        for pattern in patterns:
            matches = re.finditer(pattern, normalized_text, re.IGNORECASE)
            for match in matches:
                context = self._get_context(original_text, match.start(), match.end())
                
                signals.append(TimeSignal(
                    relative_time=match.group(),
                    confidence=0.7,
                    context=context
                ))
        
        return signals
    
    def _get_context(self, text: str, start: int, end: int, window: int = 30) -> str:
        """Estrae contesto attorno a un match"""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()
    
    def _deduplicate_location_signals(self, signals: List[LocationSignal]) -> List[LocationSignal]:
        """Rimuove segnali geografici duplicati"""
        if not signals:
            return []
        
        # Raggruppa per paese e regione
        unique_signals = {}
        
        for signal in signals:
            key = (signal.country, signal.region)
            if key not in unique_signals or signal.confidence > unique_signals[key].confidence:
                unique_signals[key] = signal
        
        return list(unique_signals.values())
    
    def _deduplicate_time_signals(self, signals: List[TimeSignal]) -> List[TimeSignal]:
        """Rimuove segnali temporali duplicati"""
        if not signals:
            return []
        
        # Raggruppa per anno/mese/tempo relativo
        unique_signals = {}
        
        for signal in signals:
            key = (signal.year, signal.month, signal.relative_time)
            if key not in unique_signals or signal.confidence > unique_signals[key].confidence:
                unique_signals[key] = signal
        
        return list(unique_signals.values())
    
    def get_signal_summary(self, text: str, lang_hint: Optional[str] = None) -> Dict[str, any]:
        """
        Restituisce un riassunto di tutti i segnali estratti
        """
        location_signals = self.extract_location_signals(text, lang_hint)
        time_signals = self.extract_time_signals(text, lang_hint)
        
        country, year = self.extract_locale_year_signals(text)
        
        return {
            'location_signals': [
                {
                    'country': s.country,
                    'region': s.region,
                    'confidence': s.confidence,
                    'context': s.context[:50] + '...' if len(s.context) > 50 else s.context
                }
                for s in location_signals
            ],
            'time_signals': [
                {
                    'year': s.year,
                    'month': s.month,
                    'relative_time': s.relative_time,
                    'confidence': s.confidence,
                    'context': s.context[:50] + '...' if len(s.context) > 50 else s.context
                }
                for s in time_signals
            ],
            'legacy_format': {
                'country': country,
                'year': year
            }
        }