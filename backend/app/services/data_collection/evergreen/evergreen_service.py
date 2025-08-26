import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.nlp.preprocessing.language_detector import LanguageDetector
from .content_indexer import ContentIndexer
from .institutional_feeds import InstitutionalFeedsCollector
from .topic_analyzer import TopicAnalyzer

logger = logging.getLogger(__name__)

class EverGreenService:
    """
    Servizio principale per la gestione di contenuti istituzionali evergreen
    
    Coordina:
    - Analisi dei topic (TopicAnalyzer)
    - Cache e persistenza (ContentIndexer) 
    - Raccolta contenuti (InstitutionalFeedsCollector)
    """
    
    def __init__(self, 
                 cache_ttl_hours: int = 24,
                 enable_fallback_content: bool = True):
        """
        Inizializza il servizio evergreen
        
        Args:
            cache_ttl_hours: TTL cache in ore
            enable_fallback_content: Se abilitare contenuto di fallback
        """
        self.topic_analyzer = TopicAnalyzer()
        self.content_indexer = ContentIndexer(default_ttl_seconds=cache_ttl_hours * 3600)
        self.feeds_collector = InstitutionalFeedsCollector()
        
        self.enable_fallback = enable_fallback_content
        self.service_name = "EverGreenService"
        
        logger.info(f"{self.service_name} initialized (cache_ttl={cache_ttl_hours}h, fallback={enable_fallback_content})")
    
    def get_evergreen_for_topic(self, 
                               topic: str, 
                               max_sources: int = 10,
                               use_cache: bool = True,
                               force_refresh: bool = False) -> List[Dict]:
        """
        Ottiene contenuti evergreen per un topic
        
        Args:
            topic: Topic medico da analizzare
            max_sources: Numero massimo di fonti da processare
            use_cache: Se utilizzare il sistema di cache
            force_refresh: Se forzare il refresh anche con cache valida
            
        Returns:
            Lista di documenti evergreen formattati
        """
        if not topic or not topic.strip():
            logger.warning("Empty topic provided to EverGreen service")
            return []
        
        topic_normalized = topic.strip()
        logger.info(f"Processing evergreen content for topic: '{topic_normalized}'")
        
        try:
            # 1. Controllo override manuali prima di tutto
            override_content = self._get_manual_overrides(topic_normalized)
            if override_content:
                logger.info(f"Using manual overrides for topic: {topic_normalized}")
                return self._format_evergreen_documents(override_content, topic_normalized)
            
            # 2. Gestione
            if use_cache and not force_refresh:
                cached_content = self._get_cached_content(topic_normalized)
                if cached_content:
                    logger.info(f"Using cached content for topic: {topic_normalized}")
                    return cached_content
            
            # 3. Generazione nuovi contenuti
            logger.info(f"Generating fresh content for topic: {topic_normalized}")
            fresh_content = self._generate_fresh_content(topic_normalized, max_sources)
            
            # 4. Salvo in cache
            if use_cache and fresh_content:
                self._cache_generated_content(topic_normalized, fresh_content)
            
            return fresh_content
            
        except Exception as e:
            logger.error(f"Error in EverGreen service for topic '{topic}': {e}")
            
            # Fallback di emergenza
            if self.enable_fallback:
                return self._create_emergency_fallback(topic_normalized)
            else:
                return []
    
    def _get_manual_overrides(self, topic: str) -> Optional[List[Dict]]:
        """Recupera override manuali se esistenti"""
        try:
            overrides = self.content_indexer.xload_overrides()
            topic_key = self.topic_analyzer.normalize_topic_key(topic)
            
            override_data = overrides.get(topic_key)
            if not override_data or not isinstance(override_data, dict):
                return None
            
            sources = override_data.get("sources", [])
            if not sources:
                return None
            
            # Processo le fonti override
            override_documents = []
            for source_entry in sources:
                if isinstance(source_entry, (list, tuple)) and len(source_entry) >= 2:
                    feed_name, url = source_entry[0], source_entry[1]
                elif isinstance(source_entry, dict):
                    feed_name = source_entry.get("feed", "Manual Override")
                    url = source_entry.get("url", "")
                else:
                    continue
                
                if url:
                    # Fetch contenuto con fallback
                    content = self.feeds_collector.fetch_content_with_fallback(url, feed_name, topic)
                    if content:
                        override_documents.append({
                            "source_feed": feed_name,
                            "url": url,
                            "content": content,
                            "topic": topic,
                            "override": True
                        })
            
            return override_documents if override_documents else None
            
        except Exception as e:
            logger.warning(f"Error loading manual overrides: {e}")
            return None
    
    def _get_cached_content(self, topic: str) -> Optional[List[Dict]]:
        """Recupera contenuto dalla cache se valido"""
        try:
            cached_entry = self.content_indexer.get_cached_content(topic)
            if not cached_entry:
                return None
            
            # Ricostruisco documenti da cache
            cached_sources = cached_entry.get("sources", [])
            if not cached_sources:
                return None
            
            cached_documents = []
            for source_entry in cached_sources:
                if len(source_entry) >= 2:
                    feed_name, url = source_entry[0], source_entry[1]
                    
                    content = self.feeds_collector.fetch_content_with_fallback(url, feed_name, topic)
                    if content:
                        cached_documents.append({
                            "source_feed": feed_name,
                            "url": url,
                            "content": content,
                            "topic": topic,
                            "cached": True
                        })
            
            if cached_documents:
                formatted = self._format_evergreen_documents(cached_documents, topic)
                return formatted
            
            return None
            
        except Exception as e:
            logger.warning(f"Error retrieving cached content for '{topic}': {e}")
            return None
    
    def _generate_fresh_content(self, topic: str, max_sources: int) -> List[Dict]:
        """Genera contenuto fresco per il topic"""
        
        # 1. Analizzo topic per ottenere aliases e URLs
        topic_profile = self.topic_analyzer.generate_topic_profile(topic)
        
        sources = topic_profile.get("sources", [])
        if not sources:
            logger.warning(f"No institutional sources generated for topic: {topic}")
            return []
        
        limited_sources = sources[:max_sources]
        
        # 2. Raccolgo contenuto dalle fonti
        fresh_documents = []
        
        for source_entry in limited_sources:
            if isinstance(source_entry, (list, tuple)) and len(source_entry) >= 2:
                feed_name, url = source_entry[0], source_entry[1]
            else:
                continue
            
            try:
                content = self.feeds_collector.fetch_content_with_fallback(url, feed_name, topic)
                
                if content:
                    fresh_documents.append({
                        "source_feed": feed_name,
                        "url": url,
                        "content": content,
                        "topic": topic,
                        "generated": True,
                        "aliases_it": topic_profile.get("aliases", {}).get("it", []),
                        "aliases_en": topic_profile.get("aliases", {}).get("en", [])
                    })
                
            except Exception as e:
                logger.warning(f"Error fetching content from {feed_name} ({url}): {e}")
                continue
        
        if fresh_documents:
            formatted = self._format_evergreen_documents(fresh_documents, topic)
            logger.info(f"Generated {len(formatted)} fresh documents for topic: {topic}")
            return formatted
        else:
            logger.warning(f"No content could be generated for topic: {topic}")
            return []
    
    def _cache_generated_content(self, topic: str, documents: List[Dict]) -> None:
        """Salva contenuto generato nella cache"""
        try:
            sources = []
            aliases_it = []
            aliases_en = []
            
            for doc in documents:
                # Source info
                platform_meta = doc.get("platform_meta", {})
                feed_name = platform_meta.get("feed", "Unknown")
                url = doc.get("url", "")
                
                if feed_name and url:
                    sources.append([feed_name, url])
                
                # Aliases
                if not aliases_it and doc.get("aliases_it"):
                    aliases_it = doc["aliases_it"]
                if not aliases_en and doc.get("aliases_en"):
                    aliases_en = doc["aliases_en"]
            
            # Metadata 
            cache_metadata = {
                "generated_documents_count": len(documents),
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "service_version": "2.0"
            }
            
            # Salvo in cache
            self.content_indexer.upsert_topic_content(
                topic=topic,
                sources=sources,
                aliases_it=aliases_it,
                aliases_en=aliases_en,
                metadata=cache_metadata
            )
            
            logger.debug(f"Cached content for topic '{topic}': {len(sources)} sources")
            
        except Exception as e:
            logger.error(f"Error caching generated content for '{topic}': {e}")
    
    def _format_evergreen_documents(self, raw_documents: List[Dict], topic: str) -> List[Dict]:
        """Formatta documenti grezzi nel formato standard dell'applicazione"""
        
        formatted_documents = []
        now_iso = datetime.now(timezone.utc).isoformat()
        
        for doc in raw_documents:
            try:
                feed_name = doc.get("source_feed", "Unknown")
                url = doc.get("url", "")
                content = doc.get("content", "")
                
                if not content or len(content.strip()) < 50:
                    if self.enable_fallback:
                        content = self._generate_minimal_fallback(topic, feed_name)
                    else:
                        continue
                
                if len(content) > 5000:
                    content = content[:4500] + "... [contenuto troncato]"

                language_detector = LanguageDetector()
                
                detected_lang = language_detector.detect_language(content)
                category = self._categorize_institutional_source(url, feed_name)
                
                # Costruisco documento formattato
                formatted_doc = {
                    "source": "rss",
                    "id": f"evergreen::{feed_name}::{abs(hash(url))}",
                    "parent_id": None,
                    "title": self._generate_document_title(feed_name, topic),
                    "text": content,
                    "url": url,
                    "author_name": None,
                    "author_handle": None,
                    "created_utc": now_iso,
                    "lang": detected_lang,
                    "platform_meta": {
                        "feed": feed_name,
                        "evergreen": True,
                        "category": category,
                        "topic": topic,
                        "is_override": doc.get("override", False),
                        "is_cached": doc.get("cached", False),
                        "is_generated": doc.get("generated", False)
                    },
                    "query": None,
                    "processed": False,
                    "campaign_id": None
                }
                
                formatted_documents.append(formatted_doc)
                
            except Exception as e:
                logger.warning(f"Error formatting document from {doc.get('source_feed', 'unknown')}: {e}")
                continue
        
        logger.debug(f"Formatted {len(formatted_documents)} documents for topic '{topic}'")
        return formatted_documents
    
    def _categorize_institutional_source(self, url: str, feed_name: str) -> str:
        """Categorizza una fonte istituzionale"""
        url_lower = url.lower()
        feed_lower = feed_name.lower()
        
        # Surveillance/epidemiologia
        if any(keyword in url_lower or keyword in feed_lower for keyword in [
            "surveillance", "sorveglianza", "epidem", "disease-data", 
            "bollettino", "bulletin", "monitoring"
        ]):
            return "surveillance"
        
        # News/comunicazione
        if any(keyword in url_lower or keyword in feed_lower for keyword in [
            "news", "newsroom", "notizie", "press", "comunicat"
        ]):
            return "news"
        
        # Alert/emergenze
        if any(keyword in url_lower or keyword in feed_lower for keyword in [
            "alert", "emergency", "outbreak", "warning", "allerta"
        ]):
            return "alert"
        
        # Fact sheets/linee guida
        if any(keyword in url_lower for keyword in [
            "fact-sheet", "guideline", "linee-guida", "raccomandaz"
        ]):
            return "factsheet"
        
        return "institutional"
    
    def _generate_document_title(self, feed_name: str, topic: str) -> str:
        """Genera titolo descrittivo per il documento"""
        topic_display = topic.replace("-", " ").title()
        return f"{feed_name} — {topic_display} (Scheda Istituzionale)"
    
    def _generate_minimal_fallback(self, topic: str, feed_name: str) -> str:
        """Genera contenuto di fallback minimale"""
        return (
            f"Informazioni istituzionali su {topic} da {feed_name}. "
            f"Risorsa autorevole contenente dati epidemiologici, linee guida cliniche "
            f"e raccomandazioni per la salute pubblica. "
            f"Consultare la fonte originale per dettagli completi."
        )
    
    def _create_emergency_fallback(self, topic: str) -> List[Dict]:
        """Crea fallback di emergenza quando tutto fallisce"""
        logger.warning(f"Creating emergency fallback for topic: {topic}")
        
        emergency_doc = {
            "source": "rss",
            "id": f"evergreen::emergency::{abs(hash(topic))}",
            "parent_id": None,
            "title": f"Informazioni Generali — {topic.replace('-', ' ').title()}",
            "text": (
                f"Informazioni di base su {topic} da fonti sanitarie ufficiali. "
                f"Le autorità sanitarie forniscono regolarmente aggiornamenti su prevenzione, "
                f"sintomi, trattamenti e misure di controllo. Consultare sempre fonti "
                f"mediche ufficiali come WHO, CDC, ISS per informazioni accurate e aggiornate."
            ),
            "url": "",
            "author_name": None,
            "author_handle": None,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "lang": "it",
            "platform_meta": {
                "feed": "Sistema Sanitario",
                "evergreen": True,
                "category": "emergency_fallback",
                "topic": topic,
                "is_fallback": True
            },
            "query": None,
            "processed": False,
            "campaign_id": None
        }
        
        return [emergency_doc]
    
    def refresh_topic_cache(self, topic: str) -> bool:
        """Forza il refresh della cache per un topic"""
        try:
            topic_normalized = topic.strip()
            
            success = self.content_indexer.invalidate_topic_cache(topic_normalized)
            
            if success:
                self.topic_analyzer.clear_topic_cache(topic_normalized)
                logger.info(f"Successfully refreshed cache for topic: {topic}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error refreshing cache for topic '{topic}': {e}")
            return False
    
    def get_service_statistics(self) -> Dict[str, any]:
        """Ottiene statistiche complete del servizio"""
        try:
            topic_stats = self.topic_analyzer.get_topic_statistics()
            index_stats = self.content_indexer.get_index_statistics()
            feeds_stats = self.feeds_collector.get_feed_statistics()
            
            service_stats = {
                "service_name": self.service_name,
                "components": {
                    "topic_analyzer": {
                        "total_topics": topic_stats.get("total_topics", 0),
                        "cache_size": topic_stats.get("cache_size", 0),
                        "top_topics": topic_stats.get("top_topics", [])
                    },
                    "content_indexer": {
                        "total_cached_topics": index_stats.get("total_topics", 0),
                        "fresh_topics": index_stats.get("fresh_topics", 0),
                        "freshness_ratio": index_stats.get("freshness_ratio", 0),
                        "index_size_mb": index_stats.get("index_size_mb", 0)
                    },
                    "feeds_collector": {
                        "total_feeds": feeds_stats.get("total_feeds", 0),
                        "content_cache_size": feeds_stats.get("content_cache_size", 0),
                        "feeds_by_category": feeds_stats.get("feeds_by_category", {})
                    }
                },
                "configuration": {
                    "fallback_enabled": self.enable_fallback,
                    "cache_ttl_hours": self.content_indexer.default_ttl / 3600
                }
            }
            
            return service_stats
            
        except Exception as e:
            logger.error(f"Error collecting service statistics: {e}")
            return {"error": str(e)}
    
    def health_check(self) -> Dict[str, any]:
        """Controlla lo stato di salute del servizio"""
        health_status = {
            "service": self.service_name,
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {}
        }
        
        try:
            try:
                test_profile = self.topic_analyzer.generate_topic_profile("test")
                health_status["components"]["topic_analyzer"] = {
                    "status": "healthy" if test_profile else "degraded"
                }
            except Exception as e:
                health_status["components"]["topic_analyzer"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
            
            try:
                test_entry = self.content_indexer.get_topic_entry("nonexistent")
                health_status["components"]["content_indexer"] = {"status": "healthy"}
            except Exception as e:
                health_status["components"]["content_indexer"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
            
            try:
                feeds_stats = self.feeds_collector.get_feed_statistics()
                health_status["components"]["feeds_collector"] = {
                    "status": "healthy" if feeds_stats.get("total_feeds", 0) > 0 else "degraded"
                }
            except Exception as e:
                health_status["components"]["feeds_collector"] = {
                    "status": "unhealthy", 
                    "error": str(e)
                }
            
            component_statuses = [comp.get("status") for comp in health_status["components"].values()]
            
            if any(status == "unhealthy" for status in component_statuses):
                health_status["status"] = "unhealthy"
            elif any(status == "degraded" for status in component_statuses):
                health_status["status"] = "degraded"
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status