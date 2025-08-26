import logging
from typing import List, Dict, Optional
import numpy as np
from dataclasses import dataclass
from app.nlp.embeddings.embedding_service import encode_texts
from app.nlp.embeddings.vector_store import VectorStore
from app.nlp.preprocessing.language_detector import LanguageDetector

logger = logging.getLogger(__name__)

# Fonti istituzionali affidabili per boosting
INSTITUTIONAL_SOURCES = {
    "WHO", "CDC", "ISS", "MINISTERO", "AIFA", "EMA", "FDA", 
    "ECDC", "WORLD HEALTH", "CENTERS FOR DISEASE", "ISTITUTO SUPERIORE",
    "MINISTRY OF HEALTH", "HEALTH MINISTRY", "PUBMED", "NEJM", "LANCET"
}

@dataclass
class IndexConfig:
    """Configurazione per l'indicizzazione vettoriale"""
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    max_text_length: int = 10000
    normalize_embeddings: bool = True
    include_metadata: bool = True
    min_text_length: int = 50

class VectorIndexer:
    """
    Classe per la creazione e gestione di indici vettoriali
    """
    
    def __init__(self, config: Optional[IndexConfig] = None):
        self.config = config or IndexConfig()
    
    def build_vector_index(self, documents: List[dict]) -> VectorStore:
        """
        Crea un indice vettoriale da una lista di documenti
        
        Args:
            documents: Lista di documenti con campi 'title', 'text', etc.
            
        Returns:
            VectorStore con indice costruito
        """
        if not documents:
            logger.warning("No documents provided for indexing")
            return self._create_empty_index()
        
        logger.info(f"Building vector index for {len(documents)} documents")
        
        # 1. Estraggo e preprocesso i testi
        texts, valid_docs = self._extract_and_preprocess_texts(documents)
        
        if not texts:
            logger.warning("No valid texts found for indexing")
            return self._create_empty_index()
        
        # 2. Genero embeddings
        try:
            embeddings = encode_texts(
                texts, 
                normalize=self.config.normalize_embeddings
            )
            logger.info(f"Generated embeddings: {embeddings.shape}")
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return self._create_empty_index()
        
        # 3. Creo e popolo VectorStore
        vector_store = VectorStore(dim=embeddings.shape[1])
        vector_store.build(embeddings.astype("float32"), valid_docs)
        
        logger.info(f"Vector index built successfully with {len(valid_docs)} documents")
        return vector_store
    
    def _extract_and_preprocess_texts(self, documents: List[dict]) -> tuple[List[str], List[dict]]:
        """Estrae e preprocessa i testi dai documenti"""
        texts = []
        valid_docs = []
        
        for doc in documents:
            # Estraggo testo per indicizzazione
            text = self._extract_document_text(doc)
            
            # Filtro per lunghezza minima
            if len(text.strip()) < self.config.min_text_length:
                continue
            
            # Preprocesso il testo
            processed_text = self._preprocess_text(text)
            
            if processed_text:
                texts.append(processed_text)
                valid_docs.append(doc)
        
        logger.debug(f"Preprocessed {len(texts)} valid texts from {len(documents)} documents")
        return texts, valid_docs
    
    def _extract_document_text(self, doc: Dict) -> str:
        """
        Estrae il testo di un documento per l'indicizzazione
        Combina titolo e contenuto con troncamento intelligente
        """
        title = doc.get("title", "").strip()
        body = doc.get("text", "").strip()
        
        # Combino titolo e corpo
        if title and body:
            combined = f"{title}. {body}"
        else:
            combined = title or body
        
        # Tronco se troppo lungo
        if len(combined) > self.config.max_text_length:
            truncated = combined[:self.config.max_text_length]
            
            last_period = truncated.rfind('.')
            if last_period > len(truncated) * 0.8: 
                truncated = truncated[:last_period + 1]
            
            return truncated
        
        return combined
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocessa il testo per l'indicizzazione"""
        if not text:
            return ""
        
        language_detector = LanguageDetector()

        normalized = language_detector.normalize_spaces(text)
        
        cleaned = ''.join(char for char in normalized if ord(char) >= 32 or char in '\n\t')
        
        return cleaned.strip()
    
    def _create_empty_index(self) -> VectorStore:
        """Crea un indice vuoto"""
        default_dim = 384  # Dimensione per paraphrase-multilingual-MiniLM-L12-v2
        
        vector_store = VectorStore(dim=default_dim)
        vector_store.build(np.zeros((0, default_dim), dtype="float32"), [])
        
        return vector_store
    
    def update_index(self, vector_store: VectorStore, new_documents: List[dict]) -> VectorStore:
        """
        Aggiorna un indice esistente con nuovi documenti
        """
        if not new_documents:
            return vector_store
        
        logger.info(f"Updating index with {len(new_documents)} new documents")
        
        texts, valid_docs = self._extract_and_preprocess_texts(new_documents)
        
        if not texts:
            logger.warning("No valid new documents to add to index")
            return vector_store
        
        try:
            new_embeddings = encode_texts(texts, normalize=self.config.normalize_embeddings)
        except Exception as e:
            logger.error(f"Error generating embeddings for new documents: {e}")
            return vector_store
        
        try:
            vector_store.add(new_embeddings.astype("float32"), valid_docs)
            logger.info(f"Added {len(valid_docs)} documents to existing index")
        except Exception as e:
            logger.error(f"Error updating vector store: {e}")
        
        return vector_store
    
    def get_index_statistics(self, vector_store: VectorStore) -> Dict[str, any]:
        """Ottiene statistiche sull'indice"""
        try:
            total_docs = vector_store.size() if hasattr(vector_store, 'size') else 0
            
            # Analizzo le fonti presenti
            source_stats = {}
            institutional_count = 0
            
            if hasattr(vector_store, 'metadata') and vector_store.metadata:
                for doc in vector_store.metadata:
                    source = doc.get("source", "unknown")
                    source_stats[source] = source_stats.get(source, 0) + 1
                    
                    if self._is_institutional_source(doc):
                        institutional_count += 1
            
            return {
                "total_documents": total_docs,
                "institutional_documents": institutional_count,
                "sources": source_stats,
                "index_dimension": vector_store.dim if hasattr(vector_store, 'dim') else None
            }
            
        except Exception as e:
            logger.error(f"Error calculating index statistics: {e}")
            return {"error": str(e)}
    
    def _is_institutional_source(self, doc: Dict) -> bool:
        """Verifica se un documento proviene da fonte istituzionale"""
        source_name = self._get_source_name(doc).upper()
        return any(inst in source_name for inst in INSTITUTIONAL_SOURCES)
    
    def _get_source_name(self, doc: Dict) -> str:
        """Estrae il nome della fonte da un documento"""
        platform_meta = doc.get("platform_meta", {})
        feed = platform_meta.get("feed", "")
        source = doc.get("source", "")
        return (feed or source or "").strip()
