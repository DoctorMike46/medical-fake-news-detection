import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from telethon import TelegramClient
from telethon.tl.functions.messages import SearchRequest
from telethon.tl.types import InputPeerEmpty
from app.core.config import Config
from app.nlp.preprocessing.language_detector import LanguageDetector
from app.nlp.preprocessing.text_cleaner import TextCleaner

logger = logging.getLogger(__name__)

class TelegramService():
    """
    Servizio per raccogliere messaggi da canali Telegram pubblici
    Nota: Richiede API ID e Hash di Telegram
    """
    
    def __init__(self):
        super().__init__()
        self.api_id = Config.TELEGRAM_API_ID
        self.api_hash = Config.TELEGRAM_API_HASH
        self.session_name = Config.TELEGRAM_SESSION_NAME or 'health_monitor'
        self.client = None
        
        # Canali sanitari italiani pubblici
        self.health_channels = [
            '@MinisteroSalute',
            '@istsupsan',
            '@who',
            '@aifa_ufficiale'
        ]
    
    async def _initialize_client(self):
        """Inizializza il client Telegram"""
        if not self.api_id or not self.api_hash:
            logger.error("Telegram API credentials not configured")
            return False
        
        try:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.start()
            logger.info("Telegram client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing Telegram client: {e}")
            return False
    
    async def search_telegram_messages(self, query: str, limit: int = 100,
                                     campaign_id: Optional[str] = None) -> List[dict]:
        """Cerca messaggi nei canali Telegram monitorati"""
        
        if not await self._initialize_client():
            return []
        
        messages = []
        
        for channel in self.health_channels:
            try:
                channel_messages = await self._search_in_channel(channel, query, limit // len(self.health_channels))
                messages.extend(channel_messages)
                
                if len(messages) >= limit:
                    break
                    
            except Exception as e:
                logger.warning(f"Error searching in channel {channel}: {e}")
                continue
        
        # Normalizza i messaggi
        normalized_messages = []
        for msg in messages[:limit]:
            normalized = self._normalize_telegram_message(msg, query, campaign_id)
            if normalized:
                normalized_messages.append(normalized)
        
        await self.client.disconnect()
        self.log_collection_stats(query, len(normalized_messages), limit)
        return normalized_messages
    
    async def _search_in_channel(self, channel_username: str, query: str, limit: int) -> List:
        """Cerca messaggi in un canale specifico"""
        try:
            entity = await self.client.get_entity(channel_username)
            
            # Cerca messaggi che contengono la query
            messages = []
            async for message in self.client.iter_messages(entity, limit=limit*2):  # Prendiamo più messaggi per filtrare
                if message.text and query.lower() in message.text.lower():
                    messages.append(message)
                    if len(messages) >= limit:
                        break
            
            return messages
            
        except Exception as e:
            logger.error(f"Error searching in channel {channel_username}: {e}")
            return []
    
    def _normalize_telegram_message(self, message, query: str, campaign_id: str) -> dict:
        """Normalizza un messaggio Telegram"""

        text_cleaner = TextCleaner()
        language_detector = LanguageDetector()
        
        text = text_cleaner.extract_clean_text_for_analysis(message.text or "")
        if not text:
            return None
        
        lang = language_detector.detect_language(text)
        
        return {
            "source": "telegram",
            "id": str(message.id),
            "parent_id": str(message.reply_to_msg_id) if message.reply_to_msg_id else None,
            "title": None,
            "text": text,
            "url": f"https://t.me/{message.chat.username}/{message.id}" if message.chat.username else "",
            "author_name": getattr(message.sender, 'first_name', None),
            "author_handle": f"@{message.sender.username}" if hasattr(message.sender, 'username') and message.sender.username else None,
            "created_utc": message.date.replace(tzinfo=timezone.utc).isoformat(),
            "lang": lang,
            "platform_meta": {
                "channel_id": message.chat.id,
                "channel_title": message.chat.title,
                "views": getattr(message, 'views', 0),
                "forwards": getattr(message, 'forwards', 0)
            },
            "query": query,
            "processed": False,
            "campaign_id": str(campaign_id) if campaign_id else None
        }
    
    def search(self, query: str, limit: int = 100, **kwargs) -> List[Dict[str, Any]]:
        """Implementazione sincrona per compatibilità"""
        import asyncio
        campaign_id = kwargs.get("campaign_id")
        return asyncio.run(self.search_telegram_messages(query, limit, campaign_id))