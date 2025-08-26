import re
import html
import logging
from typing import Optional, List, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class TextCleaner:
    """
    Classe per la pulizia e normalizzazione di testi da social media
    """
    
    def __init__(self):
        # Pattern comuni per la pulizia
        self.url_pattern = re.compile(
            r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?',
            re.IGNORECASE
        )
        
        self.mention_pattern = re.compile(r'@[\w_]+')
        self.hashtag_pattern = re.compile(r'#[\w_]+')
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
        # Pattern per rimozione rumore eccessivo
        self.excessive_punctuation = re.compile(r'[!?.]{3,}')
        self.excessive_caps = re.compile(r'\b[A-Z]{4,}\b')
        self.multiple_spaces = re.compile(r'\s{2,}')
        
        # Emoji pattern (base)
        self.emoji_pattern = re.compile(
            r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+',
            re.UNICODE
        )
    
    def clean_social_media_text(self, text: str, 
                               remove_urls: bool = True,
                               remove_mentions: bool = True,
                               remove_hashtags: bool = False,
                               remove_emails: bool = True,
                               remove_emoji: bool = False,
                               normalize_case: bool = False) -> str:
        """
        Pulizia completa di testo da social media
        
        Args:
            text: Testo da pulire
            remove_urls: Rimuovi URL
            remove_mentions: Rimuovi mention (@user)
            remove_hashtags: Rimuovi hashtag (mantieni per analisi keyword)
            remove_emails: Rimuovi indirizzi email
            remove_emoji: Rimuovi emoji
            normalize_case: Normalizza il case (minuscolo)
            
        Returns:
            Testo pulito
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Decodifica HTML entities
        cleaned = html.unescape(text)
        
        # Rimuovo URL
        if remove_urls:
            cleaned = self.url_pattern.sub(' ', cleaned)
        
        # Rimuovo email
        if remove_emails:
            cleaned = self.email_pattern.sub(' ', cleaned)
        
        # Rimuovo mention
        if remove_mentions:
            cleaned = self.mention_pattern.sub(' ', cleaned)
        
        # Rimuovo hashtag
        if remove_hashtags:
            cleaned = self.hashtag_pattern.sub(' ', cleaned)
        
        # Rimuovo emoji
        if remove_emoji:
            cleaned = self.emoji_pattern.sub(' ', cleaned)
        
        # Normalizzo punteggiatura eccessiva
        cleaned = self.excessive_punctuation.sub('...', cleaned)
        
        # Normalizzo CAPS eccessive
        if normalize_case:
            cleaned = cleaned.lower()
        else:
            cleaned = self.excessive_caps.sub(
                lambda m: m.group().lower() if len(m.group()) > 6 else m.group(), 
                cleaned
            )
        
        # Normalizzo spazi
        cleaned = self.multiple_spaces.sub(' ', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned
    
    def extract_urls(self, text: str) -> List[str]:
        """Estrae tutti gli URL da un testo"""
        if not text:
            return []
        
        return self.url_pattern.findall(text)
    
    def extract_mentions(self, text: str) -> List[str]:
        """Estrae tutte le mention da un testo"""
        if not text:
            return []
        
        mentions = self.mention_pattern.findall(text)
        return [mention[1:] for mention in mentions] 
    
    def extract_hashtags(self, text: str) -> List[str]:
        """Estrae tutti gli hashtag da un testo"""
        if not text:
            return []
        
        hashtags = self.hashtag_pattern.findall(text)
        return [hashtag[1:] for hashtag in hashtags] 
    
    def clean_url(self, url: str) -> str:
        """
        Pulisce un URL rimuovendo parametri di tracking
        """
        if not url:
            return url
        
        try:
            parsed = urlparse(url)
            
            tracking_params = {
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                'fbclid', 'gclid', 'msclkid', 'igshid', 'ref', 'referrer'
            }
            
            if parsed.query:
                from urllib.parse import parse_qsl, urlencode
                
                query_params = parse_qsl(parsed.query)
                clean_params = [
                    (k, v) for k, v in query_params 
                    if k.lower() not in tracking_params
                ]
                
                clean_query = urlencode(clean_params)
                
                from urllib.parse import urlunparse
                clean_url = urlunparse((
                    parsed.scheme, parsed.netloc, parsed.path,
                    parsed.params, clean_query, parsed.fragment
                ))
                
                return clean_url
            
            return url
            
        except Exception as e:
            logger.warning(f"Error cleaning URL {url}: {e}")
            return url
    
    def normalize_whitespace(self, text: str) -> str:
        """
        Normalizza tutti i tipi di whitespace
        """
        if not text:
            return text
        
        text = re.sub(r'[\t\r\n\f\v\u00a0\u2000-\u200f\u2028-\u202f\u205f\u3000]', ' ', text)
        
        text = re.sub(r' +', ' ', text)
        
        return text.strip()
    
    def remove_repeated_chars(self, text: str, max_repeat: int = 3) -> str:
        """
        Rimuove caratteri ripetuti eccessivamente (es. "looooool" -> "lool")
        """
        if not text:
            return text
        
        pattern = r'(.)\1{' + str(max_repeat) + ',}'
        
        return re.sub(pattern, r'\1' * max_repeat, text)
    
    def extract_clean_text_for_analysis(self, text: str) -> str:
        """
        Estrae testo pulito specificamente per analisi NLP
        """
        return self.clean_social_media_text(
            text,
            remove_urls=True,
            remove_mentions=True,
            remove_hashtags=False, 
            remove_emails=True,
            remove_emoji=True,
            normalize_case=False
        )
    
    def strip_noise(self, text: str) -> str:
        """
        Rimuove rumore eccessivo (hashtag e mention multipli)
        """
        if not text:
            return text
        
        text = re.sub(r'(?:#\w+\s*){6,}', '', text)  
        text = re.sub(r'(?:@\w+\s*){6,}', '', text)
        
        text = re.sub(r'\[(?:img|video|image|photo).+?\]', '', text, flags=re.IGNORECASE)
        
        return text.strip()