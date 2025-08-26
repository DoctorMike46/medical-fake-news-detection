import time
import json
import logging
from typing import Any, Optional, Dict, Callable
from functools import wraps
from pathlib import Path

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Manager centralizzato per caching con TTL e persistenza
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path("app/data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str, ttl_seconds: int = 3600) -> Optional[Any]:
        """Recupera valore dalla cache con controllo TTL"""
        
        # Controlla cache in memoria
        if key in self._memory_cache:
            cache_data = self._memory_cache[key]
            if time.time() - cache_data['timestamp'] < ttl_seconds:
                return cache_data['value']
            else:
                del self._memory_cache[key]
        
        # Controlla cache su disco
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                if time.time() - cache_data['timestamp'] < ttl_seconds:
                    # Ricarica in memoria
                    self._memory_cache[key] = cache_data
                    return cache_data['value']
                else:
                    cache_file.unlink()
            except Exception as e:
                logger.warning(f"Error reading cache file {cache_file}: {e}")
        
        return None
    
    def set(self, key: str, value: Any, persist: bool = True) -> None:
        """Salva valore in cache"""
        cache_data = {
            'value': value,
            'timestamp': time.time()
        }
        
        # Cache in memoria
        self._memory_cache[key] = cache_data
        
        # Cache su disco (opzionale)
        if persist:
            try:
                cache_file = self.cache_dir / f"{key}.json"
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, default=str)
            except Exception as e:
                logger.warning(f"Error writing cache file: {e}")
    
    def clear(self, pattern: Optional[str] = None) -> None:
        """Pulisce cache con pattern opzionale"""
        if pattern:
            # Pulisci chiavi che matchano il pattern
            keys_to_remove = [k for k in self._memory_cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._memory_cache[key]
                cache_file = self.cache_dir / f"{key}.json"
                if cache_file.exists():
                    cache_file.unlink()
        else:
            # Pulisci tutto
            self._memory_cache.clear()
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()

# Istanza globale
cache_manager = CacheManager()

def cached(ttl_seconds: int = 3600, key_func: Optional[Callable] = None):
    """
    Decorator per caching automatico delle funzioni
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Genera chiave cache
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Chiave di default basata su nome funzione e parametri
                key_parts = [func.__name__]
                for arg in args:
                    if isinstance(arg, (str, int, float, bool)):
                        key_parts.append(str(arg))
                for k, v in kwargs.items():
                    if isinstance(v, (str, int, float, bool)):
                        key_parts.append(f"{k}={v}")
                cache_key = "_".join(key_parts)
            
            # Controlla cache
            cached_result = cache_manager.get(cache_key, ttl_seconds)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Esegui funzione e cache il risultato
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result)
            logger.debug(f"Cache miss for {func.__name__}, result cached")
            
            return result
        return wrapper
    return decorator