import logging
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import feedparser
import trafilatura
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.nlp.preprocessing.language_detector import LanguageDetector
from app.nlp.preprocessing.text_cleaner import TextCleaner

logger = logging.getLogger(__name__)

class InstitutionalFeedsCollector:
    """
    Collector robusto per feed RSS istituzionali con retry, timeout e caching
    """
    
    def __init__(self):
        """Inizializza il collector con configurazione ottimizzata"""
        
        # Feed istituzionali predefiniti
        self.default_feeds = [
            ("WHO - News", "https://www.who.int/rss-feeds/news-english.xml"),
            ("CDC - Newsroom", "https://tools.cdc.gov/api/v2/resources/media/404952.rss"),
            ("ECDC - News", "https://www.ecdc.europa.eu/en/rss"),
            ("ISS - Notizie", "https://www.iss.it/rss/news"),
            ("Ministero Salute", "https://www.salute.gov.it/rss/news.jsp"),
        ]
        
        # Configurazione requests con retry e timeout
        self.session = self._create_robust_session()
        
        # Cache per fetch contenuti
        self._content_cache: Dict[str, Tuple[float, str]] = {}
        self._cache_ttl = 3600  # 1 ora
        
        logger.info("InstitutionalFeedsCollector initialized with robust HTTP session")
    
    def _create_robust_session(self) -> requests.Session:
        """Crea sessione HTTP con retry policy e timeout ottimali"""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        # Mount adapter con retry
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Headers per evitare blocking
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; HealthBot/1.0; +https://healthmonitor.ai/bot)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
        })
        
        # Timeout di default
        session.timeout = 30
        
        return session
    
    def collect_health_rss(self, 
                          feeds: Optional[List[Tuple[str, str]]] = None, 
                          limit_per_feed: int = 50,
                          include_content: bool = True) -> List[Dict]:
        """
        Raccoglie articoli da feed RSS istituzionali
        
        Args:
            feeds: Lista di tuple (nome, url) o None per usare default
            limit_per_feed: Limite articoli per feed
            include_content: Se estrarre contenuto completo degli articoli
            
        Returns:
            Lista di articoli normalizzati
        """
        feeds = feeds or self.default_feeds
        
        if not feeds:
            logger.warning("No feeds provided for collection")
            return []
        
        logger.info(f"Collecting from {len(feeds)} institutional feeds")
        
        all_articles = []
        
        for feed_name, feed_url in feeds:
            try:
                articles = self._process_single_feed(
                    feed_name, 
                    feed_url, 
                    limit_per_feed, 
                    include_content
                )
                all_articles.extend(articles)
                
                logger.debug(f"Collected {len(articles)} articles from {feed_name}")
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing feed '{feed_name}' ({feed_url}): {e}")
                continue
        
        logger.info(f"Total collected: {len(all_articles)} articles from {len(feeds)} feeds")
        return all_articles
    
    def _process_single_feed(self, 
                           feed_name: str, 
                           feed_url: str, 
                           limit: int,
                           include_content: bool) -> List[Dict]:
        """Processa un singolo feed RSS"""
        try:
            logger.debug(f"Parsing RSS feed: {feed_name}")
            parsed_feed = self._parse_rss_feed(feed_url)
            
            if not parsed_feed or not parsed_feed.entries:
                logger.warning(f"No entries found in feed: {feed_name}")
                return []
            
            articles = []
            entries = parsed_feed.entries[:limit] if limit else parsed_feed.entries
            
            for entry in entries:
                try:
                    article = self._normalize_rss_entry(
                        entry, 
                        feed_name, 
                        parsed_feed, 
                        include_content
                    )
                    
                    if article:
                        articles.append(article)
                        
                except Exception as e:
                    logger.warning(f"Error processing entry from {feed_name}: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"Error processing feed {feed_name}: {e}")
            return []
    
    @lru_cache(maxsize=50)
    def _parse_rss_feed(self, feed_url: str) -> Optional[feedparser.FeedParserDict]:
        """Parse RSS feed con cache LRU"""
        try:
            response = self.session.get(feed_url, timeout=20)
            response.raise_for_status()
            
            parsed = feedparser.parse(response.content)
            
            if parsed.bozo and parsed.bozo_exception:
                logger.warning(f"RSS parse warning for {feed_url}: {parsed.bozo_exception}")
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing RSS feed {feed_url}: {e}")
            return None
    
    def _normalize_rss_entry(self, 
                           entry: feedparser.FeedParserDict, 
                           feed_name: str,
                           parsed_feed: feedparser.FeedParserDict,
                           include_content: bool) -> Optional[Dict]:
        """Normalizza un entry RSS nel formato standard"""
        
        article_url = entry.get("link", "")
        title = entry.get("title", "")
        
        if not article_url or not title:
            return None
        
        published_date = self._extract_publication_date(entry)
        
        if include_content and article_url:
            content = self._fetch_article_content(article_url)
        else:
            content = entry.get("summary", "") or entry.get("description", "")
        

        text_cleaner = TextCleaner()

        clean_content = text_cleaner.extract_clean_text_for_analysis(content) if content else ""
        clean_title = text_cleaner.extract_clean_text_for_analysis(title)
        
        feed_language = self._detect_feed_language(parsed_feed, clean_content)
        
        article = {
            "source": "rss",
            "id": entry.get("id", article_url),
            "parent_id": None,
            "title": clean_title,
            "text": clean_content,
            "url": article_url,
            "author_name": entry.get("author"),
            "author_handle": None,
            "created_utc": published_date,
            "lang": feed_language,
            "platform_meta": {
                "feed": feed_name,
                "feed_url": entry.get("link", ""),
                "category": self._categorize_feed(feed_name),
                "original_summary": entry.get("summary", ""),
                "tags": self._extract_tags(entry)
            },
            "query": None,
            "processed": False,
            "campaign_id": None
        }
        
        return article
    
    def _extract_publication_date(self, entry: feedparser.FeedParserDict) -> Optional[str]:
        """Estrae e normalizza data di pubblicazione"""
        date_fields = ["published_parsed", "updated_parsed", "created_parsed"]
        
        for field in date_fields:
            parsed_date = entry.get(field)
            if parsed_date:
                try:
                    dt = datetime(*parsed_date[:6], tzinfo=timezone.utc)
                    return dt.isoformat()
                except (TypeError, ValueError) as e:
                    logger.debug(f"Error parsing date from {field}: {e}")
                    continue
        
        logger.debug("No valid publication date found, using current time")
        return datetime.now(timezone.utc).isoformat()
    
    def _fetch_article_content(self, url: str) -> Optional[str]:
        """Estrae contenuto completo dell'articolo con cache"""
        
        if url in self._content_cache:
            cached_time, cached_content = self._content_cache[url]
            if time.time() - cached_time < self._cache_ttl:
                logger.debug(f"Cache hit for article content: {url}")
                return cached_content
        
        try:
            logger.debug(f"Fetching full article content: {url}")
            
            response = self.session.get(url, timeout=25)
            response.raise_for_status()
            
            # Estraggo contenuto con trafilatura
            content = trafilatura.extract(
                response.text,
                include_comments=False,
                include_tables=False,
                include_formatting=False,
                include_links=False
            )
            
            if content:
                self._content_cache[url] = (time.time(), content)
                logger.debug(f"Successfully extracted content ({len(content)} chars)")
                return content
            else:
                logger.debug(f"No content extracted from {url}")
                return None
                
        except Exception as e:
            logger.warning(f"Error fetching content from {url}: {e}")
            return None
    
    def _detect_feed_language(self, 
                            parsed_feed: feedparser.FeedParserDict, 
                            sample_text: str) -> str:
        """Rileva lingua del feed"""
        
        feed_language = parsed_feed.feed.get("language", "")
        if feed_language:
            lang_code = feed_language.lower().split('-')[0]
            if lang_code in ['it', 'en', 'es', 'fr', 'de']:
                return lang_code
        
        language_detector = LanguageDetector()
        if sample_text:
            try:
                detected = language_detector.detect_language(sample_text)
                if detected and detected != 'und':
                    return detected
            except Exception as e:
                logger.debug(f"Language detection failed: {e}")
        
        return "en"
    
    def _categorize_feed(self, feed_name: str) -> str:
        """Categorizza tipo di feed basandosi sul nome"""
        feed_lower = feed_name.lower()
        
        if any(keyword in feed_lower for keyword in ["surveillance", "epidem", "data"]):
            return "surveillance"
        elif any(keyword in feed_lower for keyword in ["news", "notizie", "press"]):
            return "news"
        elif any(keyword in feed_lower for keyword in ["alert", "warning", "emergency"]):
            return "alert"
        else:
            return "institutional"
    
    def _extract_tags(self, entry: feedparser.FeedParserDict) -> List[str]:
        """Estrae tag/categorie dall'entry RSS"""
        tags = []
        
        if hasattr(entry, 'tags') and entry.tags:
            tags.extend([tag.term for tag in entry.tags if hasattr(tag, 'term')])
        
        if hasattr(entry, 'categories') and entry.categories:
            tags.extend(entry.categories)
        
        clean_tags = []
        for tag in tags:
            if isinstance(tag, str) and len(tag.strip()) > 1:
                clean_tags.append(tag.strip())
        
        return clean_tags[:5] 
    
    def fetch_content_with_fallback(self, url: str, feed_name: str, topic: str = "") -> Optional[str]:
        """
        Fetch contenuto con fallback per il servizio evergreen
        
        Args:
            url: URL della risorsa
            feed_name: Nome del feed/fonte
            topic: Topic per generare fallback contestuale
            
        Returns:
            Contenuto estratto o fallback generato
        """
        content = self._fetch_article_content(url)
        
        if content and len(content.strip()) >= 100:
            return content
        
        logger.debug(f"Generating fallback content for {url}")
        
        fallback_content = self._generate_contextual_fallback(url, feed_name, topic)
        
        return fallback_content
    
    def _generate_contextual_fallback(self, url: str, feed_name: str, topic: str) -> str:
        """Genera contenuto di fallback contestuale"""
        
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        if "who.int" in domain:
            template = (
                f"Documento ufficiale dell'Organizzazione Mondiale della Sanità su {topic}. "
                f"Include linee guida internazionali, raccomandazioni per la salute pubblica "
                f"e dati epidemiologici aggiornati. Fonte autorevole per professionisti sanitari "
                f"e decisori politici."
            )
        elif "cdc.gov" in domain:
            template = (
                f"Risorsa informativa dei Centers for Disease Control and Prevention su {topic}. "
                f"Contiene protocolli di prevenzione, dati di sorveglianza epidemiologica "
                f"e raccomandazioni cliniche per il territorio statunitense."
            )
        elif "iss.it" in domain:
            template = (
                f"Pubblicazione dell'Istituto Superiore di Sanità italiano su {topic}. "
                f"Include dati di sorveglianza nazionale, linee guida cliniche "
                f"e aggiornamenti epidemiologici per il contesto italiano."
            )
        elif "salute.gov.it" in domain:
            template = (
                f"Comunicazione ufficiale del Ministero della Salute italiano su {topic}. "
                f"Contiene disposizioni normative, raccomandazioni per i cittadini "
                f"e aggiornamenti sulle politiche sanitarie nazionali."
            )
        else:
            template = (
                f"Documento istituzionale di {feed_name} su {topic}. "
                f"Fonte autorevole contenente informazioni mediche e sanitarie, "
                f"linee guida professionali, dati epidemiologici e raccomandazioni "
                f"per operatori sanitari e cittadini. Consultare il link per dettagli completi."
            )
        
        context_info = []
        
        if topic:
            context_info.append(f"Argomento principale: {topic}")
        
        if parsed_url.path and len(parsed_url.path) > 1:
            path_parts = [part for part in parsed_url.path.split('/') if part]
            if path_parts:
                context_info.append(f"Sezione: {path_parts[-1].replace('-', ' ').replace('_', ' ').title()}")
        
        if context_info:
            full_content = template + " " + " | ".join(context_info) + "."
        else:
            full_content = template
        
        return full_content
    
    def get_feed_statistics(self) -> Dict[str, any]:
        """Ottiene statistiche sui feed configurati"""
        
        stats = {
            "total_feeds": len(self.default_feeds),
            "feeds_by_category": {},
            "content_cache_size": len(self._content_cache),
            "cache_hit_ratio": 0.0,
            "feeds_detail": []
        }
        
        for feed_name, feed_url in self.default_feeds:
            category = self._categorize_feed(feed_name)
            stats["feeds_by_category"][category] = stats["feeds_by_category"].get(category, 0) + 1
            
            parsed_url = urlparse(feed_url)
            stats["feeds_detail"].append({
                "name": feed_name,
                "domain": parsed_url.netloc,
                "category": category,
                "url": feed_url
            })
        
        return stats
    
    def test_feed_connectivity(self) -> Dict[str, any]:
        """Testa la connettività di tutti i feed configurati"""
        
        results = {
            "total_tested": len(self.default_feeds),
            "successful": 0,
            "failed": 0,
            "feed_results": []
        }
        
        for feed_name, feed_url in self.default_feeds:
            start_time = time.time()
            
            try:
                response = self.session.head(feed_url, timeout=10)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    status = "success"
                    results["successful"] += 1
                else:
                    status = f"http_error_{response.status_code}"
                    results["failed"] += 1
                
                results["feed_results"].append({
                    "name": feed_name,
                    "url": feed_url,
                    "status": status,
                    "response_time_ms": round(response_time * 1000, 2),
                    "status_code": response.status_code
                })
                
            except Exception as e:
                results["failed"] += 1
                results["feed_results"].append({
                    "name": feed_name,
                    "url": feed_url,
                    "status": "error",
                    "error": str(e),
                    "response_time_ms": round((time.time() - start_time) * 1000, 2)
                })
        
        results["success_rate"] = results["successful"] / results["total_tested"] if results["total_tested"] > 0 else 0
        
        return results
    
    def clear_content_cache(self) -> int:
        """Pulisce la cache dei contenuti e restituisce numero elementi rimossi"""
        cache_size = len(self._content_cache)
        self._content_cache.clear()
        
        self._parse_rss_feed.cache_clear()
        
        logger.info(f"Cleared content cache ({cache_size} items)")
        return cache_size
    
    def add_custom_feed(self, name: str, url: str, validate: bool = True) -> bool:
        """
        Aggiunge un feed personalizzato alla lista
        
        Args:
            name: Nome descrittivo del feed
            url: URL del feed RSS
            validate: Se validare il feed prima di aggiungerlo
            
        Returns:
            True se aggiunto con successo
        """
        if not name or not url:
            logger.error("Feed name and URL are required")
            return False
        
        if validate:
            try:
                response = self.session.head(url, timeout=10)
                if response.status_code != 200:
                    logger.error(f"Feed validation failed: HTTP {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Feed validation failed: {e}")
                return False
        
        for existing_name, existing_url in self.default_feeds:
            if existing_url == url:
                logger.warning(f"Feed URL already exists with name: {existing_name}")
                return False
        
        self.default_feeds.append((name, url))
        logger.info(f"Added custom feed: {name} ({url})")
        
        return True