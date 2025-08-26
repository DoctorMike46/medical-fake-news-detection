import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from newsapi import NewsApiClient
from app.core.config import Config
from app.nlp.preprocessing.language_detector import LanguageDetector
from app.nlp.preprocessing.text_cleaner import TextCleaner

logger = logging.getLogger(__name__)

class NewsService():
    """
    Servizio per raccogliere notizie da fonti giornalistiche usando NewsAPI
    """
    
    def __init__(self):
        super().__init__()
        self.newsapi = NewsApiClient(api_key=Config.NEWS_API_KEY) if Config.NEWS_API_KEY else None
        
        # Fonti sanitarie italiane affidabili
        self.health_sources = [
            'ansa.it', 'adnkronos.com', 'corriere.it', 'repubblica.it',
            'ilsole24ore.com', 'huffingtonpost.it', 'fanpage.it'
        ]
    
    def is_available(self) -> bool:
        return self.newsapi is not None
    
    def search_news(self, query: str, limit: int = 100, 
                   campaign_id: Optional[str] = None, days_back: int = 30) -> List[dict]:
        """Cerca notizie correlate alla query"""
        
        if not self.is_available():
            logger.error("NewsAPI not configured")
            return []
        
        articles = []
        from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        try:
            # Ricerca generale
            response = self.newsapi.get_everything(
                q=query,
                sources=','.join(self.health_sources),
                from_param=from_date,
                language='it',
                sort_by='relevancy',
                page_size=min(limit, 100)
            )
            
            for article in response.get('articles', []):
                normalized = self._normalize_article(article, query, campaign_id)
                if normalized:
                    articles.append(normalized)
                    
        except Exception as e:
            logger.error(f"Error searching news: {e}")
        
        self.log_collection_stats(query, len(articles), limit)
        return articles[:limit]
    
    def _normalize_article(self, article: dict, query: str, campaign_id: str) -> dict:
        """Normalizza un articolo nel formato standard"""
        
        title = article.get('title', '')
        description = article.get('description', '')
        content = article.get('content', '')
        
        # Combina titolo, descrizione e contenuto
        full_text = f"{title}. {description}. {content}".strip()

        text_cleaner = TextCleaner()

        language_detector = LanguageDetector()

        text = text_cleaner.extract_clean_text_for_analysis(full_text)
        lang = language_detector.detect_language(text)
        
        return {
            "source": "news",
            "id": article.get('url', '').split('/')[-1] or str(hash(article.get('url', ''))),
            "parent_id": None,
            "title": title,
            "text": text,
            "url": article.get('url', ''),
            "author_name": article.get('author'),
            "author_handle": None,
            "created_utc": self._parse_news_time(article.get('publishedAt')),
            "lang": lang,
            "platform_meta": {
                "source_name": article.get('source', {}).get('name', ''),
                "source_id": article.get('source', {}).get('id', ''),
                "description": article.get('description', ''),
                "url_to_image": article.get('urlToImage', '')
            },
            "query": query,
            "processed": False,
            "campaign_id": str(campaign_id) if campaign_id else None
        }
    
    def _parse_news_time(self, time_str: str) -> str:
        """Converte il timestamp dell'articolo in formato ISO UTC"""
        if not time_str:
            return None
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return None
    
    def search(self, query: str, limit: int = 100, **kwargs) -> List[Dict[str, Any]]:
        """Implementazione del metodo astratto"""
        campaign_id = kwargs.get("campaign_id")
        days_back = kwargs.get("days_back", 30)
        return self.search_news(query, limit, campaign_id, days_back)