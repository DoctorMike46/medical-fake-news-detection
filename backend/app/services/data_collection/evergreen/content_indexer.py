import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class ContentIndexer:
    """
    Indexer thread-safe per contenuti evergreen con TTL intelligente
    """
    
    def __init__(self, 
                 index_path: Optional[str] = None,
                 default_ttl_seconds: int = 86400,  # 24 ore
                 backup_enabled: bool = True):
        """
        Inizializza il Content Indexer
        
        Args:
            index_path: Path personalizzato per l'index file
            default_ttl_seconds: TTL di default in secondi
            backup_enabled: Se abilitare backup automatici
        """
        self.base_dir = Path(__file__).resolve().parents[4]
        self.data_dir = self.base_dir / "app" / "data" / "evergreen"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_path = index_path or str(self.data_dir / "evergreen_index.json")
        self.backup_dir = self.data_dir / "backups"
        self.backup_enabled = backup_enabled
        
        if self.backup_enabled:
            self.backup_dir.mkdir(exist_ok=True)
        
        self.default_ttl = default_ttl_seconds
        
        # Thread safety
        self._lock = threading.RLock()
        self._index_cache: Optional[Dict] = None
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl = 300  # 5 minuti per cache in memoria
        
        logger.info(f"ContentIndexer initialized with index at: {self.index_path}")
    
    def _now_timestamp(self) -> float:
        """Timestamp corrente thread-safe"""
        return time.time()
    
    def _load_index_safe(self) -> Dict[str, Any]:
        """Carica index con cache thread-safe"""
        with self._lock:
            now = self._now_timestamp()
            
            if (self._index_cache is not None and 
                self._cache_timestamp is not None and
                (now - self._cache_timestamp) < self._cache_ttl):
                return self._index_cache.copy()
            
            try:
                index_path = Path(self.index_path)
                if not index_path.exists():
                    empty_index = {}
                    self._save_index_safe(empty_index)
                    return empty_index
                
                with open(index_path, "r", encoding="utf-8") as f:
                    index_data = json.load(f) or {}
                
                # Aggiorna cache
                self._index_cache = index_data.copy()
                self._cache_timestamp = now
                
                logger.debug(f"Loaded index with {len(index_data)} entries")
                return index_data
                
            except Exception as e:
                logger.error(f"Error loading index from {self.index_path}: {e}")
                
                # Fallback a index vuoto
                empty_index = {}
                self._index_cache = empty_index
                self._cache_timestamp = now
                return empty_index
    
    def _save_index_safe(self, index_data: Dict[str, Any]) -> bool:
        """Salva index con backup automatico e thread safety"""
        with self._lock:
            try:
                index_path = Path(self.index_path)
                
                if self.backup_enabled and index_path.exists():
                    self._create_backup()
                
                temp_path = index_path.with_suffix('.tmp')
                
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(index_data, f, ensure_ascii=False, indent=2)
                
                temp_path.replace(index_path)
                
                self._index_cache = index_data.copy()
                self._cache_timestamp = self._now_timestamp()
                
                logger.debug(f"Saved index with {len(index_data)} entries")
                return True
                
            except Exception as e:
                logger.error(f"Error saving index to {self.index_path}: {e}")
                return False
    
    def _create_backup(self) -> bool:
        """Crea backup dell'index corrente"""
        if not self.backup_enabled:
            return True
        
        try:
            index_path = Path(self.index_path)
            if not index_path.exists():
                return True
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_name = f"evergreen_index_backup_{timestamp}.json"
            backup_path = self.backup_dir / backup_name
            
            import shutil
            shutil.copy2(index_path, backup_path)
            
            # Mantieni solo gli ultimi 10 backup
            self._cleanup_old_backups()
            
            logger.debug(f"Created backup: {backup_name}")
            return True
            
        except Exception as e:
            logger.warning(f"Error creating backup: {e}")
            return False
    
    def _cleanup_old_backups(self, keep_count: int = 10):
        """Rimuove backup vecchi mantenendo solo i più recenti"""
        if not self.backup_enabled:
            return
        
        try:
            backup_files = list(self.backup_dir.glob("evergreen_index_backup_*.json"))
            
            if len(backup_files) <= keep_count:
                return
            
            # Ordino per data di modifica (più recenti prima)
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Rimuovo i backup più vecchi
            for old_backup in backup_files[keep_count:]:
                old_backup.unlink()
                logger.debug(f"Removed old backup: {old_backup.name}")
                
        except Exception as e:
            logger.warning(f"Error cleaning up old backups: {e}")
    
    def get_topic_entry(self, topic: str) -> Optional[Dict[str, Any]]:
        """
        Recupera entry per un topic specifico
        
        Args:
            topic: Nome del topic
            
        Returns:
            Dictionary con i dati del topic o None se non trovato
        """
        if not topic or not topic.strip():
            return None
        
        topic_key = topic.strip().lower()
        index = self._load_index_safe()
        
        return index.get(topic_key)
    
    def is_entry_fresh(self, entry: Dict[str, Any], max_age_seconds: Optional[int] = None) -> bool:
        """
        Verifica se un'entry è ancora fresca (non scaduta)
        
        Args:
            entry: Entry da verificare
            max_age_seconds: Età massima in secondi (default usa TTL configurato)
            
        Returns:
            True se l'entry è fresca
        """
        if not entry or not isinstance(entry, dict):
            return False
        
        timestamp = entry.get("updated_at_ts")
        if timestamp is None:
            return False
        
        try:
            entry_time = float(timestamp)
            current_time = self._now_timestamp()
            max_age = max_age_seconds or self.default_ttl
            
            age = current_time - entry_time
            is_fresh = age <= max_age
            
            if not is_fresh:
                logger.debug(f"Entry expired: age={age:.1f}s, max_age={max_age}s")
            
            return is_fresh
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid timestamp in entry: {timestamp}, error: {e}")
            return False
    
    def upsert_topic_content(self, 
                           topic: str, 
                           sources: List[Tuple[str, str]], 
                           aliases_it: List[str], 
                           aliases_en: List[str],
                           metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Inserisce o aggiorna contenuto per un topic
        
        Args:
            topic: Nome del topic
            sources: Lista di tuple (feed_name, url)
            aliases_it: Lista alias italiani
            aliases_en: Lista alias inglesi
            metadata: Metadati aggiuntivi opzionali
            
        Returns:
            Entry aggiornata
        """
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty")
        
        topic_key = topic.strip().lower()
        
        now = self._now_timestamp()
        entry = {
            "topic": topic_key,
            "sources": [[str(feed), str(url)] for feed, url in (sources or [])],
            "aliases": {
                "it": list(aliases_it) if aliases_it else [],
                "en": list(aliases_en) if aliases_en else []
            },
            "updated_at_ts": now,
            "updated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "version": 1
        }
        
        if metadata and isinstance(metadata, dict):
            entry["metadata"] = metadata.copy()
        
        index = self._load_index_safe()
        
        if topic_key in index:
            old_version = index[topic_key].get("version", 0)
            entry["version"] = old_version + 1
            entry["created_at_ts"] = index[topic_key].get("created_at_ts", now)
        else:
            entry["created_at_ts"] = now
        
        index[topic_key] = entry
        
        if self._save_index_safe(index):
            logger.info(f"Updated topic '{topic}' with {len(sources)} sources (v{entry['version']})")
            return entry
        else:
            logger.error(f"Failed to save updated topic '{topic}'")
            raise RuntimeError(f"Failed to save topic '{topic}' to index")
    
    def get_cached_content(self, topic: str) -> Optional[Dict[str, Any]]:
        """
        Recupera contenuto cachato per un topic se ancora fresco
        
        Args:
            topic: Nome del topic
            
        Returns:
            Contenuto cachato o None se non trovato/scaduto
        """
        entry = self.get_topic_entry(topic)
        
        if entry and self.is_entry_fresh(entry):
            logger.debug(f"Cache hit for topic '{topic}'")
            return entry
        
        if entry:
            logger.debug(f"Cache expired for topic '{topic}'")
        else:
            logger.debug(f"Cache miss for topic '{topic}'")
        
        return None
    
    def cache_topic_content(self, topic: str, topic_analysis: Dict[str, Any]) -> bool:
        """
        Caching di risultati di analisi topic
        
        Args:
            topic: Nome del topic
            topic_analysis: Risultato dell'analisi (da TopicAnalyzer)
            
        Returns:
            True se caching riuscito
        """
        try:
            aliases = topic_analysis.get("aliases", {})
            sources = topic_analysis.get("sources", [])
            

            metadata = {
                "analysis_cached": topic_analysis.get("cached", False),
                "generated_at": topic_analysis.get("generated_at"),
                "topic_key": topic_analysis.get("topic_key", topic)
            }
            
            self.upsert_topic_content(
                topic=topic,
                sources=sources,
                aliases_it=aliases.get("it", []),
                aliases_en=aliases.get("en", []),
                metadata=metadata
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error caching topic content for '{topic}': {e}")
            return False
    
    def invalidate_topic_cache(self, topic: str) -> bool:
        """
        Invalida cache per un topic specifico rimuovendolo dall'index
        
        Args:
            topic: Nome del topic
            
        Returns:
            True se invalidazione riuscita
        """
        if not topic or not topic.strip():
            return False
        
        topic_key = topic.strip().lower()
        
        try:
            index = self._load_index_safe()
            
            if topic_key in index:
                del index[topic_key]
                
                if self._save_index_safe(index):
                    logger.info(f"Invalidated cache for topic '{topic}'")
                    return True
                else:
                    logger.error(f"Failed to save index after invalidating '{topic}'")
                    return False
            else:
                logger.debug(f"Topic '{topic}' not found in cache for invalidation")
                return True
                
        except Exception as e:
            logger.error(f"Error invalidating cache for topic '{topic}': {e}")
            return False
    
    def get_index_statistics(self) -> Dict[str, Any]:
        """Ottiene statistiche sull'index"""
        try:
            index = self._load_index_safe()
            
            if not index:
                return {
                    "total_topics": 0,
                    "index_size_mb": 0,
                    "cache_hit_ratio": 0
                }
            
            total_topics = len(index)
            fresh_topics = sum(1 for entry in index.values() if self.is_entry_fresh(entry))
            
            now = self._now_timestamp()
            ages = []
            for entry in index.values():
                timestamp = entry.get("updated_at_ts")
                if timestamp:
                    try:
                        age_hours = (now - float(timestamp)) / 3600
                        ages.append(age_hours)
                    except (ValueError, TypeError):
                        pass
            
            try:
                file_size_mb = Path(self.index_path).stat().st_size / (1024 * 1024)
            except:
                file_size_mb = 0
            
            total_sources = sum(len(entry.get("sources", [])) for entry in index.values())
            
            stats = {
                "total_topics": total_topics,
                "fresh_topics": fresh_topics,
                "expired_topics": total_topics - fresh_topics,
                "freshness_ratio": fresh_topics / total_topics if total_topics > 0 else 0,
                "total_sources": total_sources,
                "avg_sources_per_topic": total_sources / total_topics if total_topics > 0 else 0,
                "index_size_mb": round(file_size_mb, 2),
                "default_ttl_hours": self.default_ttl / 3600,
                "cache_enabled": self._index_cache is not None
            }
            
            if ages:
                stats.update({
                    "avg_age_hours": sum(ages) / len(ages),
                    "oldest_entry_hours": max(ages),
                    "newest_entry_hours": min(ages)
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating index statistics: {e}")
            return {"error": str(e)}
    
    def cleanup_expired_entries(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Rimuove entries scadute dall'index
        
        Args:
            dry_run: Se True, simula la pulizia senza modificare l'index
            
        Returns:
            Statistiche della pulizia
        """
        try:
            index = self._load_index_safe()
            
            expired_topics = []
            for topic_key, entry in index.items():
                if not self.is_entry_fresh(entry):
                    expired_topics.append(topic_key)
            
            if not expired_topics:
                return {
                    "expired_found": 0,
                    "removed": 0,
                    "dry_run": dry_run
                }
            
            if not dry_run:
                for topic_key in expired_topics:
                    del index[topic_key]
                
                if self._save_index_safe(index):
                    logger.info(f"Cleaned up {len(expired_topics)} expired entries")
                else:
                    logger.error("Failed to save index after cleanup")
                    return {"error": "Failed to save cleaned index"}
            
            return {
                "expired_found": len(expired_topics),
                "removed": len(expired_topics) if not dry_run else 0,
                "expired_topics": expired_topics,
                "dry_run": dry_run
            }
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {"error": str(e)}
    
    def load_overrides(self) -> Dict[str, Any]:
        """
        Carica overrides manuali da file separato
        
        Returns:
            Dictionary con overrides o vuoto se non trovato
        """
        try:
            overrides_path = self.data_dir / "evergreen_overrides.json"
            
            if not overrides_path.exists():
                return {}
            
            with open(overrides_path, "r", encoding="utf-8") as f:
                overrides = json.load(f)
            
            logger.debug(f"Loaded {len(overrides)} manual overrides")
            return overrides or {}
            
        except Exception as e:
            logger.warning(f"Error loading overrides: {e}")
            return {}
