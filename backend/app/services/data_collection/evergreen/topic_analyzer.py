from __future__ import annotations
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

class TopicAnalyzer:
    """
    Analyzer intelligente per topic medici con cache e normalizzazione avanzata
    """
    
    def __init__(self, profiles_path: Optional[str] = None):
        """
        Inizializza l'analyzer con gestione automatica dei paths
        
        Args:
            profiles_path: Path personalizzato per il file dei profili
        """
        self.base_dir = Path(__file__).resolve().parents[4]
        self.data_dir = self.base_dir / "app" / "data" / "evergreen"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.profiles_path = profiles_path or str(self.data_dir / "topic_profiles.json")
        
        self._profiles_cache: Optional[Dict] = None
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl = 3600  # 1 ora
        
        # Pattern precompilati per performance
        self._slug_pattern = re.compile(r"[^a-zA-Z0-9]+")
        
        self._ensure_profiles_store()
        logger.info(f"TopicAnalyzer initialized with profiles at: {self.profiles_path}")
    
    def _ensure_profiles_store(self) -> None:
        """Crea il file dei profili se mancante"""
        try:
            profiles_path = Path(self.profiles_path)
            profiles_path.parent.mkdir(parents=True, exist_ok=True)
            
            if not profiles_path.exists():
                with open(profiles_path, "w", encoding="utf-8") as f:
                    json.dump({}, f, ensure_ascii=False, indent=2)
                logger.info(f"Created topic profiles store: {profiles_path}")
        except Exception as e:
            logger.error(f"Error creating profiles store: {e}")
    
    def _load_profiles_with_cache(self) -> Dict:
        """Carica profili con cache intelligente"""
        import time
        
        now = time.time()
        
        if (self._profiles_cache is not None and 
            self._cache_timestamp is not None and 
            (now - self._cache_timestamp) < self._cache_ttl):
            return self._profiles_cache
        
        try:
            with open(self.profiles_path, "r", encoding="utf-8") as f:
                profiles = json.load(f)
            
            self._profiles_cache = profiles
            self._cache_timestamp = now
            
            logger.debug(f"Loaded {len(profiles)} topic profiles from file")
            return profiles
            
        except Exception as e:
            logger.warning(f"Error loading profiles from {self.profiles_path}: {e}")
            

            self._profiles_cache = {}
            self._cache_timestamp = now
            return {}
    
    def _save_profiles(self, profiles: Dict) -> None:
        """Salva profili con aggiornamento cache"""
        try:
            with open(self.profiles_path, "w", encoding="utf-8") as f:
                json.dump(profiles, f, ensure_ascii=False, indent=2)
            
            import time
            self._profiles_cache = profiles
            self._cache_timestamp = time.time()
            
            logger.debug(f"Saved {len(profiles)} topic profiles to file")
            
        except Exception as e:
            logger.error(f"Error saving profiles to {self.profiles_path}: {e}")
    
    @lru_cache(maxsize=200)
    def normalize_topic_key(self, topic: str) -> str:
        """
        Normalizza un topic in una chiave standardizzata
        Cache LRU per performance su topic ripetuti
        
        Args:
            topic: Topic da normalizzare
            
        Returns:
            Topic normalizzato
        """
        if not topic or not isinstance(topic, str):
            return ""
        
        normalized = topic.strip().lower()
        
        topic_mappings = {
            frozenset(["botulino", "botulismo"]): "botulino",
            frozenset(["west nile", "virus del nilo occidentale", "nilo occidentale", "wnv"]): "west nile",
            frozenset(["covid lungo", "post covid", "post-covid", "long covid"]): "long covid",
            frozenset(["antibiotico", "antimicrob", "amr", "resistenza antimicrobica"]): "antibiotico-resistenza",
            frozenset(["influenza aviaria", "aviaria", "h5n1"]): "influenza aviaria"
        }
        
        for topic_set, canonical in topic_mappings.items():
            if any(variant in normalized for variant in topic_set):
                return canonical
        
        return normalized
    
    def generate_topic_profile(self, topic: str, force_refresh: bool = False) -> Dict[str, any]:
        """
        Genera o recupera il profilo completo di un topic
        
        Args:
            topic: Topic da analizzare
            force_refresh: Se forzare la rigenerazione anche se cached
            
        Returns:
            Dizionario con topic_key, aliases, sources
        """
        if not topic:
            return {"topic_key": "", "aliases": {"it": [], "en": []}, "sources": []}
        
        topic_key = self.normalize_topic_key(topic)
        
        if not force_refresh:
            profiles = self._load_profiles_with_cache()
            if topic_key in profiles:
                cached_profile = profiles[topic_key]
                
                it_aliases = cached_profile.get("aliases_it", [])
                en_aliases = cached_profile.get("aliases_en", [])
                
                return {
                    "topic_key": topic_key,
                    "aliases": {"it": it_aliases, "en": en_aliases},
                    "sources": self._build_institutional_sources(topic_key, it_aliases, en_aliases),
                    "cached": True,
                    "last_updated": cached_profile.get("created_utc")
                }
        
        logger.info(f"Generating new profile for topic: {topic}")
        
        it_aliases = self._generate_italian_aliases(topic_key)
        en_aliases = self._generate_english_aliases(topic_key, it_aliases)
        
        profiles = self._load_profiles_with_cache()
        profiles[topic_key] = {
            "aliases_it": it_aliases,
            "aliases_en": en_aliases,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "last_used": datetime.now(timezone.utc).isoformat(),
            "usage_count": profiles.get(topic_key, {}).get("usage_count", 0) + 1
        }
        self._save_profiles(profiles)
        
        return {
            "topic_key": topic_key,
            "aliases": {"it": it_aliases, "en": en_aliases},
            "sources": self._build_institutional_sources(topic_key, it_aliases, en_aliases),
            "cached": False,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _generate_italian_aliases(self, topic_key: str) -> List[str]:
        """Genera alias italiani con regole specifiche per dominio medico"""
        aliases = {topic_key}
        
        # Dizionario alias specifici per medicina
        medical_aliases = {
            "west nile": {
                "virus del nilo occidentale", "wnv", "febbre del nilo occidentale",
                "west nile virus", "nilo occidentale", "arbovirosi", "culex"
            },
            "morbillo": {"morbillo", "measles", "virus del morbillo"},
            "dengue": {"dengue", "febbre dengue", "aedes", "virus dengue"},
            "long covid": {"long covid", "post covid", "post-covid", "sindrome post-covid"},
            "antibiotico-resistenza": {
                "antibiotico resistenza", "resistenza antimicrobica", "amr",
                "antimicrobial resistance", "superbatteri"
            },
            "botulino": {"botulismo", "clostridium botulinum", "tossina botulinica"},
            "influenza aviaria": {
                "influenza aviaria", "influenza degli uccelli", "aviaria",
                "influenza h5n1", "virus h5n1", "pandemia aviaria"
            }
        }
        
        for key, values in medical_aliases.items():
            if key == topic_key or any(part in topic_key for part in key.split()):
                aliases.update(values)
        
        hashtag_aliases = {f"#{self._slugify(alias)}" for alias in aliases if alias}
        aliases.update(hashtag_aliases)
        
        return sorted([alias for alias in aliases if alias]) 
    
    def _generate_english_aliases(self, topic_key: str, it_aliases: List[str]) -> List[str]:
        """Genera alias inglesi con mappings e traduzioni automatiche"""
        
        direct_translations = {
            "west nile": {"west nile virus", "west nile fever", "wnv"},
            "morbillo": {"measles", "measles virus", "rubeola"},
            "dengue": {"dengue fever", "dengue virus", "breakbone fever"},
            "long covid": {"post-covid-19 condition", "post-acute covid-19", "long-haul covid"},
            "antibiotico-resistenza": {"antimicrobial resistance", "antibiotic resistance", "drug resistance"},
            "botulino": {"botulism", "botulinum toxin", "clostridium botulinum"},
            "influenza aviaria": {"avian influenza", "bird flu", "avian flu", "h5n1 influenza"}
        }
        
        aliases = set()
        
        if topic_key in direct_translations:
            aliases.update(direct_translations[topic_key])
        else:
            english_version = topic_key
            
            substitutions = {
                "virus del nilo occidentale": "west nile virus",
                "botulismo": "botulism",
                "morbillo": "measles",
                "antibiotico-resistenza": "antimicrobial resistance",
                "influenza aviaria": "avian influenza",
                "febbre": "fever",
                "virus": "virus",
                "malattia": "disease"
            }
            
            for it_term, en_term in substitutions.items():
                english_version = english_version.replace(it_term, en_term)
            
            aliases.add(english_version)
            
            aliases.add(self._slugify(english_version).replace("-", " "))
        
        if any("h5n1" in alias.lower() for alias in it_aliases):
            aliases.update({"h5n1", "h5n1 virus", "avian h5n1"})
        
        hashtag_aliases = {f"#{self._slugify(alias)}" for alias in aliases if alias}
        aliases.update(hashtag_aliases)
        
        return sorted([alias for alias in aliases if alias])
    
    def _build_institutional_sources(self, topic_key: str, it_aliases: List[str], en_aliases: List[str]) -> List[Tuple[str, str]]:
        """Costruisce URL per fonti istituzionali autorevoli"""
        
        en_slug = self._select_best_slug(en_aliases)
        it_slug = self._select_best_slug(it_aliases)
        
        it_query = self._select_best_query_term(it_aliases)
        it_query_encoded = it_query.replace(" ", "%20")
        
        institutional_urls = [
            # CDC (US) - Inglese
            ("CDC", f"https://www.cdc.gov/{en_slug}/"),
            ("CDC", f"https://www.cdc.gov/{en_slug}/symptoms/"),
            ("CDC", f"https://www.cdc.gov/{en_slug}/prevention/"),
            
            # ECDC (EU) - Inglese
            ("ECDC", f"https://www.ecdc.europa.eu/en/{en_slug}"),
            ("ECDC", f"https://www.ecdc.europa.eu/en/{en_slug}/surveillance-and-disease-data"),
            
            # WHO - Inglese
            ("WHO", f"https://www.who.int/news-room/fact-sheets/detail/{en_slug}"),
            ("WHO", f"https://www.who.int/health-topics/{en_slug}"),
            
            # ISS (IT) - Italiano
            ("ISS", f"https://www.iss.it/{it_slug}"),
            ("ISS", f"https://www.epicentro.iss.it/{it_slug}"),
            
            # Ministero Salute (IT) - Italiano
            ("Ministero della Salute", 
             f"https://www.salute.gov.it/portale/news/p3_2_1_1_1.jsp?"
             f"lingua=italiano&menu=notizie&p=dalministero&parolaChiave={it_query_encoded}"),
            
            # AIFA (IT) - per farmaci e vaccini
            ("AIFA", f"https://www.aifa.gov.it/ricerca-contenuti?q={it_query_encoded}"),
        ]
        
        return institutional_urls
    
    def _select_best_slug(self, aliases: List[str]) -> str:
        """Seleziona il miglior slug da una lista di alias"""
        if not aliases:
            return "health"
        
        for alias in aliases:
            if alias.startswith("#"):
                continue
            if "-" in alias and " " not in alias and len(alias) > 3:
                return alias
        
        for alias in aliases:
            if not alias.startswith("#") and len(alias) > 2:
                return self._slugify(alias)
        
        return self._slugify(aliases[0]) if aliases else "health"
    
    def _select_best_query_term(self, aliases: List[str]) -> str:
        """Seleziona il miglior termine per query di ricerca"""
        if not aliases:
            return "salute"
        
        for alias in aliases:
            if not alias.startswith("#") and len(alias) > 3:
                return alias
        
        return aliases[0] if aliases else "salute"
    
    def _slugify(self, text: str) -> str:
        """
        Converte testo in slug URL-friendly
        Ottimizzato per performance con pattern precompilato
        """
        if not text:
            return ""
        
        normalized = unicodedata.normalize("NFKD", text)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        
        slug = self._slug_pattern.sub("-", ascii_text.lower()).strip("-")
        
        return slug
    
    def get_topic_statistics(self) -> Dict[str, any]:
        """Ottiene statistiche sui topic salvati"""
        try:
            profiles = self._load_profiles_with_cache()
            
            if not profiles:
                return {"total_topics": 0}
            
            total_topics = len(profiles)
            topics_with_usage = sum(1 for p in profiles.values() if p.get("usage_count", 0) > 0)
            
            top_topics = sorted(
                [(k, v.get("usage_count", 0)) for k, v in profiles.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            total_it_aliases = sum(len(p.get("aliases_it", [])) for p in profiles.values())
            total_en_aliases = sum(len(p.get("aliases_en", [])) for p in profiles.values())
            
            return {
                "total_topics": total_topics,
                "topics_with_usage": topics_with_usage,
                "avg_it_aliases": total_it_aliases / total_topics if total_topics > 0 else 0,
                "avg_en_aliases": total_en_aliases / total_topics if total_topics > 0 else 0,
                "top_topics": [{"topic": t[0], "usage": t[1]} for t in top_topics],
                "cache_size": len(self._profiles_cache) if self._profiles_cache else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating topic statistics: {e}")
            return {"error": str(e)}
    
    def clear_topic_cache(self, topic: Optional[str] = None) -> bool:
        """
        Pulisce cache per un topic specifico o tutti
        
        Args:
            topic: Topic specifico da rimuovere, None per pulire tutto
            
        Returns:
            True se operazione riuscita
        """
        try:
            if topic:
                topic_key = self.normalize_topic_key(topic)
                profiles = self._load_profiles_with_cache()
                
                if topic_key in profiles:
                    del profiles[topic_key]
                    self._save_profiles(profiles)
                    logger.info(f"Cleared cache for topic: {topic}")
                else:
                    logger.warning(f"Topic not found in cache: {topic}")
            else:
                self._save_profiles({})
                logger.info("Cleared all topic cache")
            
            self.normalize_topic_key.cache_clear()
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing topic cache: {e}")
            return False
