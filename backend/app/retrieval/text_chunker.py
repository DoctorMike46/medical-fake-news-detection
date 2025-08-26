import re
import logging
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
from app.nlp.preprocessing.language_detector import LanguageDetector


logger = logging.getLogger(__name__)

class ChunkStrategy(Enum):
    """Strategie di chunking disponibili"""
    WORD_BASED = "word_based"
    SENTENCE_BASED = "sentence_based"
    PARAGRAPH_BASED = "paragraph_based"
    SEMANTIC_BASED = "semantic_based"
    FIXED_SIZE = "fixed_size"

@dataclass
class ChunkConfig:
    """Configurazione per il chunking"""
    strategy: ChunkStrategy = ChunkStrategy.WORD_BASED
    max_words: int = 350
    max_chars: int = 2000
    overlap_words: int = 40
    overlap_chars: int = 200
    min_chunk_words: int = 50
    preserve_sentences: bool = True
    preserve_paragraphs: bool = False

@dataclass
class TextChunk:
    """Rappresenta un chunk di testo"""
    content: str
    start_char: int
    end_char: int
    word_count: int
    char_count: int
    chunk_id: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class BaseChunker(ABC):
    """Classe base per tutte le strategie di chunking"""
    
    def __init__(self, config: ChunkConfig):
        self.config = config
    
    @abstractmethod
    def chunk(self, text: str) -> List[TextChunk]:
        """Implementa la strategia di chunking specifica"""
        pass
    
    def _validate_chunk_size(self, content: str) -> bool:
        """Valida se un chunk rispetta i requisiti minimi"""
        word_count = len(content.split())
        return word_count >= self.config.min_chunk_words
    
    def _generate_chunk_id(self, index: int, source_id: str = "") -> str:
        """Genera un ID univoco per il chunk"""
        return f"{source_id}_chunk_{index:04d}" if source_id else f"chunk_{index:04d}"

class WordBasedChunker(BaseChunker):
    """Chunker basato su numero di parole"""
    
    def chunk(self, text: str) -> List[TextChunk]:
        if not text or not text.strip():
            return []
        
        language_detector = LanguageDetector()
        
        normalized_text = language_detector.normalize_spaces(text)
        words = normalized_text.split()
        
        if not words:
            return []
        
        chunks = []
        overlap = min(self.config.overlap_words, self.config.max_words // 2)
        step = max(1, self.config.max_words - overlap)
        
        i = 0
        chunk_index = 0
        
        while i < len(words):
            # Determino l'intervallo di parole per questo chunk
            end_word_idx = min(i + self.config.max_words, len(words))
            chunk_words = words[i:end_word_idx]
            
            if not chunk_words:
                break
            
            content = " ".join(chunk_words)
            
            if self.config.preserve_sentences and i + self.config.max_words < len(words):
                content = self._adjust_for_sentence_boundary(content, " ".join(words[end_word_idx:end_word_idx+10]))
            
            start_char = len(" ".join(words[:i]))
            if i > 0:
                start_char += 1  
            
            end_char = start_char + len(content)
            
            # Valido e creo il chunk
            if self._validate_chunk_size(content):
                chunk = TextChunk(
                    content=content.strip(),
                    start_char=start_char,
                    end_char=end_char,
                    word_count=len(chunk_words),
                    char_count=len(content),
                    chunk_id=self._generate_chunk_id(chunk_index)
                )
                chunks.append(chunk)
                chunk_index += 1
            
            i += step
        
        return chunks
    
    def _adjust_for_sentence_boundary(self, content: str, next_content: str) -> str:
        """Aggiusta il chunk per terminare su un confine di frase"""
        sentence_endings = ['.', '!', '?', '.\n', '!\n', '?\n']
        
        best_pos = -1
        for ending in sentence_endings:
            pos = content.rfind(ending)
            if pos > best_pos and pos > len(content) * 0.7: 
                best_pos = pos + len(ending)
        
        if best_pos > 0:
            return content[:best_pos]
        
        return content

class SentenceBasedChunker(BaseChunker):
    """Chunker basato su frasi"""
    
    def __init__(self, config: ChunkConfig):
        super().__init__(config)
        self.sentence_patterns = [
            r'[.!?]+\s+',
            r'[.!?]+$',
            r'\n\s*\n',
        ]
    
    def chunk(self, text: str) -> List[TextChunk]:
        if not text or not text.strip():
            return []
        
        language_detector = LanguageDetector()
        
        lang = language_detector.detect_language(text)
        sentences = self._split_into_sentences(text, lang)
        
        chunks = []
        current_chunk = []
        current_word_count = 0
        chunk_index = 0
        start_char = 0
        
        for sentence in sentences:
            sentence_words = len(sentence.split())
            
            if (current_word_count + sentence_words > self.config.max_words and 
                current_chunk and 
                current_word_count >= self.config.min_chunk_words):
                
                content = " ".join(current_chunk)
                end_char = start_char + len(content)
                
                chunk = TextChunk(
                    content=content.strip(),
                    start_char=start_char,
                    end_char=end_char,
                    word_count=current_word_count,
                    char_count=len(content),
                    chunk_id=self._generate_chunk_id(chunk_index)
                )
                chunks.append(chunk)
                chunk_index += 1
                
                overlap_sentences = self._get_overlap_sentences(current_chunk, self.config.overlap_words)
                current_chunk = overlap_sentences + [sentence]
                current_word_count = sum(len(s.split()) for s in current_chunk)
                start_char = end_char - sum(len(s + " ") for s in overlap_sentences)
            else:
                current_chunk.append(sentence)
                current_word_count += sentence_words
        
        if current_chunk and current_word_count >= self.config.min_chunk_words:
            content = " ".join(current_chunk)
            end_char = start_char + len(content)
            
            chunk = TextChunk(
                content=content.strip(),
                start_char=start_char,
                end_char=end_char,
                word_count=current_word_count,
                char_count=len(content),
                chunk_id=self._generate_chunk_id(chunk_index)
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_into_sentences(self, text: str, lang: str) -> List[str]:
        """Divide il testo in frasi"""
        # Pattern base per la divisione in frasi
        if lang == 'it':
            # Pattern per italiano
            pattern = r'(?<=[.!?])\s+(?=[A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ])'
        else:
            # Pattern per inglese e altre lingue
            pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _get_overlap_sentences(self, sentences: List[str], overlap_words: int) -> List[str]:
        """Ottiene le ultime frasi per l'overlap"""
        if not sentences or overlap_words <= 0:
            return []
        
        overlap_sentences = []
        word_count = 0
        
        for sentence in reversed(sentences):
            sentence_words = len(sentence.split())
            if word_count + sentence_words <= overlap_words:
                overlap_sentences.insert(0, sentence)
                word_count += sentence_words
            else:
                break
        
        return overlap_sentences

class TextChunker:
    """Classe principale per il chunking di testi"""
    
    def __init__(self, config: Optional[ChunkConfig] = None):
        self.config = config or ChunkConfig()
        self._chunkers = {
            ChunkStrategy.WORD_BASED: WordBasedChunker,
            ChunkStrategy.SENTENCE_BASED: SentenceBasedChunker,
        }
    
    def chunk_text(self, text: str, 
                   strategy: Optional[ChunkStrategy] = None,
                   max_words: Optional[int] = None,
                   overlap: Optional[int] = None) -> List[str]:
        """
        Funzione di compatibilità per il codice esistente
        
        Returns:
            Lista di stringhe (contenuto dei chunk)
        """
        if max_words is not None:
            self.config.max_words = max_words
        if overlap is not None:
            self.config.overlap_words = overlap
        
        strategy = strategy or self.config.strategy
        chunks = self.chunk_with_metadata(text, strategy)
        
        return [chunk.content for chunk in chunks]
    
    def chunk_with_metadata(self, text: str, 
                           strategy: Optional[ChunkStrategy] = None) -> List[TextChunk]:
        """
        Esegue il chunking con metadati completi
        
        Returns:
            Lista di TextChunk con metadati
        """
        if not text or not text.strip():
            return []
        
        strategy = strategy or self.config.strategy
        
        if strategy not in self._chunkers:
            logger.warning(f"Strategy {strategy} not implemented, using WORD_BASED")
            strategy = ChunkStrategy.WORD_BASED
        
        chunker_class = self._chunkers[strategy]
        chunker = chunker_class(self.config)
        
        try:
            chunks = chunker.chunk(text)
            logger.debug(f"Created {len(chunks)} chunks using {strategy.value} strategy")
            return chunks
        except Exception as e:
            logger.error(f"Error during chunking with {strategy.value}: {e}")
            fallback_chunker = WordBasedChunker(self.config)
            return fallback_chunker.chunk(text)
    
    def chunk_documents(self, documents: List[Dict[str, Any]], 
                       content_field: str = "text") -> List[Dict[str, Any]]:
        """
        Chunka una lista di documenti
        
        Args:
            documents: Lista di documenti con campo testo
            content_field: Nome del campo contenente il testo
            
        Returns:
            Lista di chunk con metadati del documento originale
        """
        all_chunks = []
        
        for doc_idx, doc in enumerate(documents):
            content = doc.get(content_field, "")
            if not content:
                continue
            
            chunks = self.chunk_with_metadata(content)
            
            for chunk in chunks:
                chunk.metadata.update({
                    "source_doc_id": doc.get("id", f"doc_{doc_idx}"),
                    "source_title": doc.get("title", ""),
                    "source_url": doc.get("url", ""),
                    "source_created": doc.get("created_utc", ""),
                    "source_lang": doc.get("lang", ""),
                    **doc.get("platform_meta", {})
                })
                
                all_chunks.append({
                    "content": chunk.content,
                    "meta": chunk.metadata,
                    "chunk_info": {
                        "chunk_id": chunk.chunk_id,
                        "word_count": chunk.word_count,
                        "char_count": chunk.char_count,
                        "start_char": chunk.start_char,
                        "end_char": chunk.end_char
                    }
                })
        
        logger.info(f"Created {len(all_chunks)} chunks from {len(documents)} documents")
        return all_chunks
    
    def get_optimal_chunk_size(self, texts: List[str], 
                              target_chunks_per_doc: int = 3) -> int:
        """
        Calcola la dimensione ottimale dei chunk basata sui testi forniti
        """
        if not texts:
            return self.config.max_words
        
        word_counts = [len(text.split()) for text in texts if text]
        if not word_counts:
            return self.config.max_words
        
        avg_doc_length = sum(word_counts) / len(word_counts)
        optimal_size = int(avg_doc_length / target_chunks_per_doc)
        
        optimal_size = max(100, min(optimal_size, 800))
        
        logger.info(f"Calculated optimal chunk size: {optimal_size} words")
        return optimal_size


_default_chunker = TextChunker()

def chunk_text(text: str, max_words: int = 350, overlap: int = 40) -> List[str]:
    """
    Funzione di compatibilità per il codice esistente
    """
    return _default_chunker.chunk_text(text, max_words=max_words, overlap=overlap)

def chunk_text_advanced(text: str, strategy: ChunkStrategy = ChunkStrategy.WORD_BASED,
                       config: Optional[ChunkConfig] = None) -> List[TextChunk]:
    """
    Chunking avanzato con metadati
    """
    chunker = TextChunker(config) if config else _default_chunker
    return chunker.chunk_with_metadata(text, strategy)

def get_chunk_statistics(chunks: List[TextChunk]) -> Dict[str, Any]:
    """
    Calcola statistiche sui chunk
    """
    if not chunks:
        return {}
    
    word_counts = [chunk.word_count for chunk in chunks]
    char_counts = [chunk.char_count for chunk in chunks]
    
    return {
        "total_chunks": len(chunks),
        "avg_words_per_chunk": sum(word_counts) / len(word_counts),
        "avg_chars_per_chunk": sum(char_counts) / len(char_counts),
        "min_words": min(word_counts),
        "max_words": max(word_counts),
        "total_words": sum(word_counts),
        "total_chars": sum(char_counts)
    }