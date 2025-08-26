import logging
import requests
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from app.core.config import Config
from app.nlp.preprocessing.language_detector import LanguageDetector
from app.nlp.preprocessing.text_cleaner import TextCleaner

logger = logging.getLogger(__name__)

class InstagramService():
    """
    Servizio per raccogliere post da account Instagram pubblici
    Nota: Instagram ha severe limitazioni API. Questo servizio può accedere 
    solo ad account Business/Creator autorizzati.
    """
    
    def __init__(self):
        super().__init__()
        self.access_token = Config.INSTAGRAM_ACCESS_TOKEN
        self.base_url = "https://graph.facebook.com/v18.0"
        
        # Account sanitari italiani pubblici (solo se autorizzati)
        self.monitored_accounts = [
            # Questi devono essere account Business che hanno autorizzato la tua app
            "ministero_salute_official",
            "istsupsan_official"
        ]
    
    def is_available(self) -> bool:
        return bool(self.access_token)
    
    def search_instagram_posts(self, query: str, limit: int = 100,
                             campaign_id: Optional[str] = None) -> List[dict]:
        """
        Cerca post Instagram che contengono la query.
        Limitato agli account autorizzati.
        """
        
        if not self.is_available():
            logger.error("Instagram service not configured")
            return []
        
        posts = []
        
        for account_id in self.monitored_accounts:
            try:
                account_posts = self._get_account_posts(account_id, limit // len(self.monitored_accounts))
                # Filtra per query
                filtered = [p for p in account_posts if self._matches_query(p.get('caption', ''), query)]
                posts.extend(filtered)
                
                if len(posts) >= limit:
                    break
                    
            except Exception as e:
                logger.warning(f"Error fetching Instagram posts from {account_id}: {e}")
                continue
        
        # Normalizza i post
        normalized_posts = []
        for post in posts[:limit]:
            normalized = self._normalize_instagram_post(post, query, campaign_id)
            if normalized:
                normalized_posts.append(normalized)
        
        self.log_collection_stats(query, len(normalized_posts), limit)
        return normalized_posts
    
    def _get_account_posts(self, account_id: str, limit: int = 25) -> List[dict]:
        """Recupera i post di un account specifico"""
        url = f"{self.base_url}/{account_id}/media"
        
        params = {
            "access_token": self.access_token,
            "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
            "limit": min(limit, 25)
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data.get("data", [])
            
        except requests.RequestException as e:
            logger.error(f"Error fetching Instagram posts from {account_id}: {e}")
            return []
    
    def _normalize_instagram_post(self, raw_post: dict, query: str, campaign_id: str) -> dict:
        """Normalizza un post Instagram"""
        
        caption = raw_post.get("caption", "")

        text_cleaner = TextCleaner()

        language_detector = LanguageDetector()

        text = text_cleaner.extract_clean_text_for_analysis(caption)
        lang = language_detector.detect_language(text)
        
        return {
            "source": "instagram",
            "id": raw_post.get("id"),
            "parent_id": None,
            "title": None,
            "text": text,
            "url": raw_post.get("permalink", ""),
            "author_name": None,  # Non disponibile tramite API
            "author_handle": None,
            "created_utc": self._parse_instagram_time(raw_post.get("timestamp")),
            "lang": lang,
            "platform_meta": {
                "media_type": raw_post.get("media_type"),
                "media_url": raw_post.get("media_url"),
                "like_count": raw_post.get("like_count", 0),
                "comments_count": raw_post.get("comments_count", 0)
            },
            "query": query,
            "processed": False,
            "campaign_id": str(campaign_id) if campaign_id else None
        }
    
    def _parse_instagram_time(self, time_str: str) -> str:
        """Converte il timestamp Instagram in formato ISO UTC"""
        if not time_str:
            return None
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return None
    
    def _matches_query(self, text: str, query: str) -> bool:
        """Verifica se il testo contiene la query"""
        if not text or not query:
            return False
        return query.lower() in text.lower()
    
    def search(self, query: str, limit: int = 100, **kwargs) -> List[Dict[str, Any]]:
        """Implementazione del metodo astratto"""
        campaign_id = kwargs.get("campaign_id")
        return self.search_instagram_posts(query, limit, campaign_id)