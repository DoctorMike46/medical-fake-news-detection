import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from app.nlp.preprocessing.language_detector import LanguageDetector
from .text_chunker import TextChunker, ChunkConfig, ChunkStrategy

logger = logging.getLogger(__name__)

@dataclass
class ContextConfig:
    """Configurazione per il building del contesto RAG"""
    max_chunks: int = 6
    words_per_chunk: int = 350
    chunk_overlap: int = 40
    chunk_strategy: ChunkStrategy = ChunkStrategy.SENTENCE_BASED
    
    # Filtri qualità
    min_chunk_words: int = 50
    max_chunk_words: int = 500
    
    # Diversità e rilevanza
    ensure_diversity: bool = True
    max_chunks_per_source: int = 2
    prefer_recent: bool = True
    recent_days_threshold: int = 30
    
    # Filtri lingua
    language_filter: Optional[List[str]] = None
    
    # Metadati da includere
    include_source_metadata: bool = True
    include_chunk_metadata: bool = True

class RAGContextBuilder:
    """
    Costruttore di contesto per Retrieval-Augmented Generation
    """
    
    def __init__(self, config: Optional[ContextConfig] = None):
        self.config = config or ContextConfig()
        
        # Inizializzo chunker 
        chunk_config = ChunkConfig(
            strategy=self.config.chunk_strategy,
            max_words=self.config.words_per_chunk,
            overlap_words=self.config.chunk_overlap,
            min_chunk_words=self.config.min_chunk_words,
            preserve_sentences=True
        )
        self.chunker = TextChunker(chunk_config)
    
    def build_context(self, evidence_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Costruisce il contesto RAG da documenti di evidenza
        
        Args:
            evidence_docs: Lista di documenti con metadati
            
        Returns:
            Lista di chunk con metadati per RAG
        """
        if not evidence_docs:
            return []
        
        logger.debug(f"Building RAG context from {len(evidence_docs)} documents")
        
        # 1. Filtro documenti per qualità e lingua
        filtered_docs = self._filter_documents(evidence_docs)
        logger.debug(f"Filtered to {len(filtered_docs)} documents")
        
        # 2. Chunka i documenti
        chunks = self._chunk_documents(filtered_docs)
        logger.debug(f"Created {len(chunks)} total chunks")
        
        # 3. Applico filtri di qualità sui chunk
        quality_chunks = self._filter_chunks_by_quality(chunks)
        logger.debug(f"Quality filtered to {len(quality_chunks)} chunks")
        
        # 4. Assicuro diversità se richiesto
        if self.config.ensure_diversity:
            diverse_chunks = self._ensure_diversity(quality_chunks)
            logger.debug(f"Diversity filtered to {len(diverse_chunks)} chunks")
        else:
            diverse_chunks = quality_chunks
        
        # 5. Ordino per rilevanza e recency
        sorted_chunks = self._sort_chunks_by_relevance(diverse_chunks)
        
        # 6. Seleziono i migliori chunk
        final_chunks = sorted_chunks[:self.config.max_chunks]
        
        # 7. Preparo il formato finale
        context = self._format_context_chunks(final_chunks)
        
        logger.info(f"Built RAG context with {len(context)} chunks")
        return context
    
    def _filter_documents(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filtra documenti per qualità e criteri"""
        filtered = []

        language_detector = LanguageDetector()
        
        for doc in docs:
            # Filtro testo minimo
            text = doc.get("text", "")
            if not text or len(text.strip()) < 100:
                continue
            
            # Filtro lingua
            if self.config.language_filter:
                doc_lang = doc.get("lang") or language_detector.detect_language(text)
                if doc_lang not in self.config.language_filter:
                    continue
            
            # Filtro URL duplicati
            url = doc.get("url", "")
            if url and any(f.get("url") == url for f in filtered):
                continue
            
            filtered.append(doc)
        
        return filtered
    
    def _chunk_documents(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Chunka i documenti e mantiene metadati"""
        all_chunks = []

        language_detector = LanguageDetector()
        
        for doc_idx, doc in enumerate(docs):
            text = doc.get("text", "")
            if not text:
                continue
            
            # Normalizza il testo
            normalized_text = language_detector.normalize_spaces(text)
            
            # Crea chunk con metadati
            chunks = self.chunker.chunk_with_metadata(normalized_text)
            
            for chunk_idx, chunk in enumerate(chunks):
                chunk_data = {
                    "content": chunk.content,
                    "word_count": chunk.word_count,
                    "char_count": chunk.char_count,
                    "chunk_id": f"doc_{doc_idx}_chunk_{chunk_idx}",
                    
                    # Metadati documento originale
                    "source_doc": {
                        "title": doc.get("title", ""),
                        "url": doc.get("url", ""),
                        "source": doc.get("source", ""),
                        "created_utc": doc.get("created_utc", ""),
                        "lang": doc.get("lang", ""),
                        "platform_meta": doc.get("platform_meta", {})
                    },
                    
                    # Score di qualità iniziale
                    "quality_score": self._calculate_initial_quality_score(chunk, doc),
                    "recency_score": self._calculate_recency_score(doc),
                }
                
                all_chunks.append(chunk_data)
        
        return all_chunks
    
    def _calculate_initial_quality_score(self, chunk, doc: Dict[str, Any]) -> float:
        """Calcola score di qualità iniziale per un chunk"""
        score = 0.5  # Base score
        
        # Bonus per lunghezza ottimale
        optimal_length = self.config.words_per_chunk
        length_ratio = min(chunk.word_count / optimal_length, 1.0)
        score += 0.2 * length_ratio
        
        # Bonus per presenza di termini medici
        content_lower = chunk.content.lower()
        medical_terms = [
            'salute', 'medico', 'medicina', 'farmaco', 'terapia', 'diagnosi',
            'sintomo', 'malattia', 'virus', 'vaccino', 'cura', 'trattamento'
        ]
        medical_matches = sum(1 for term in medical_terms if term in content_lower)
        score += 0.1 * min(medical_matches / 3, 1.0)
        
        # Bonus per fonte affidabile
        source = doc.get("source", "").lower()
        if any(reliable in source for reliable in ["who", "cdc", "iss", "ministero", "ospedale"]):
            score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_recency_score(self, doc: Dict[str, Any]) -> float:
        """Calcola score di recency basato sulla data di creazione"""
        created_str = doc.get("created_utc", "")
        if not created_str:
            return 0.5
        
        try:
            created_date = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            days_ago = (datetime.now(created_date.tzinfo) - created_date).days
            
            if days_ago <= self.config.recent_days_threshold:
                return 1.0 - (days_ago / self.config.recent_days_threshold) * 0.5
            else:
                return 0.5 * (1.0 / (1.0 + (days_ago - self.config.recent_days_threshold) / 365))
        
        except Exception:
            return 0.5
    
    def _filter_chunks_by_quality(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filtra chunk per qualità"""
        filtered = []
        
        for chunk in chunks:
            # Filtro lunghezza
            if not (self.config.min_chunk_words <= chunk["word_count"] <= self.config.max_chunk_words):
                continue
            
            # Filtro qualità minima
            if chunk["quality_score"] < 0.3:
                continue
            
            # Filtro contenuto duplicato o quasi-duplicato
            content = chunk["content"].lower()
            if any(self._calculate_similarity(content, f["content"].lower()) > 0.8 for f in filtered):
                continue
            
            filtered.append(chunk)
        
        return filtered
    
    def _ensure_diversity(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Assicura diversità nelle fonti"""
        source_counts = {}
        diverse_chunks = []
        
        # Ordino per qualità decrescente
        sorted_chunks = sorted(chunks, key=lambda x: x["quality_score"], reverse=True)
        
        for chunk in sorted_chunks:
            source = chunk["source_doc"]["source"]
            current_count = source_counts.get(source, 0)
            
            if current_count < self.config.max_chunks_per_source:
                diverse_chunks.append(chunk)
                source_counts[source] = current_count + 1
            
            # Stop se abbiamo abbastanza chunk
            if len(diverse_chunks) >= self.config.max_chunks * 2: 
                break
        
        return diverse_chunks
    
    def _sort_chunks_by_relevance(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ordina chunk per rilevanza complessiva"""
        
        def calculate_final_score(chunk):
            quality_weight = 0.6
            recency_weight = 0.4 if self.config.prefer_recent else 0.2
            
            final_score = (
                quality_weight * chunk["quality_score"] +
                recency_weight * chunk["recency_score"]
            )
            
            return final_score
        
        # Calcolo score finale e ordina
        for chunk in chunks:
            chunk["final_score"] = calculate_final_score(chunk)
        
        return sorted(chunks, key=lambda x: x["final_score"], reverse=True)
    
    def _format_context_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Formatta i chunk nel formato finale per RAG"""
        context = []
        
        for chunk in chunks:
            source_doc = chunk["source_doc"]
            
            # Formato base
            formatted_chunk = {
                "content": chunk["content"],
                "meta": {
                    "title": source_doc["title"],
                    "url": source_doc["url"], 
                    "source": source_doc["source"],
                    "created_utc": source_doc["created_utc"],
                    "feed": source_doc["platform_meta"].get("feed", ""),
                    "lang": source_doc["lang"]
                }
            }
            
            # Aggiungo metadati aggiuntivi se richiesto
            if self.config.include_chunk_metadata:
                formatted_chunk["chunk_meta"] = {
                    "chunk_id": chunk["chunk_id"],
                    "word_count": chunk["word_count"],
                    "quality_score": chunk["quality_score"],
                    "recency_score": chunk["recency_score"],
                    "final_score": chunk["final_score"]
                }
            
            if self.config.include_source_metadata:
                formatted_chunk["meta"]["platform_meta"] = source_doc["platform_meta"]
            
            context.append(formatted_chunk)
        
        return context
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calcola similarità tra due testi (Jaccard semplificato)"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0


def build_rag_context(evidence_docs: List[dict], max_chunks: int = 6, 
                     words_per_chunk: int = 350) -> List[dict]:
    

    config = ContextConfig(
        max_chunks=max_chunks,
        words_per_chunk=words_per_chunk
    )
    
    builder = RAGContextBuilder(config)
    return builder.build_context(evidence_docs)

def build_rag_context_advanced(evidence_docs: List[dict], 
                              config: Optional[ContextConfig] = None) -> List[dict]:
    """
    Building avanzato del contesto RAG con configurazione personalizzata
    """
    builder = RAGContextBuilder(config)
    return builder.build_context(evidence_docs)

def optimize_context_for_query(evidence_docs: List[dict], query: str,
                              max_chunks: int = 6) -> List[dict]:
    """
    Ottimizza il contesto per una query specifica
    """

    language_detector = LanguageDetector()
    # Analizzo la query per estrarre caratteristiche
    query_lang = language_detector.detect_language(query)
    query_words = set(query.lower().split())
    
    # Creo config ottimizzata per la query
    config = ContextConfig(
        max_chunks=max_chunks,
        language_filter=[query_lang] if query_lang != 'und' else None,
        ensure_diversity=True,
        prefer_recent=True
    )
    
    builder = RAGContextBuilder(config)
    context = builder.build_context(evidence_docs)
    
    # Post-processing: riordino per rilevanza alla query
    def query_relevance_score(chunk):
        content_words = set(chunk["content"].lower().split())
        overlap = len(query_words & content_words)
        return overlap / len(query_words) if query_words else 0
    
    # Aggiungo score di rilevanza alla query
    for chunk in context:
        chunk["query_relevance"] = query_relevance_score(chunk)
    
    # Riordino considerando anche la rilevanza alla query
    context.sort(key=lambda x: (
        x.get("chunk_meta", {}).get("final_score", 0.5) * 0.7 + 
        x.get("query_relevance", 0) * 0.3
    ), reverse=True)
    
    return context

def get_context_statistics(context: List[dict]) -> Dict[str, Any]:
    """
    Calcola statistiche sui chunk del contesto
    """
    if not context:
        return {"total_chunks": 0}
    
    # Statistiche di base
    total_chunks = len(context)
    total_words = sum(chunk.get("chunk_meta", {}).get("word_count", 0) for chunk in context)
    
    # Distribuzione per fonte
    source_distribution = {}
    for chunk in context:
        source = chunk.get("meta", {}).get("source", "unknown")
        source_distribution[source] = source_distribution.get(source, 0) + 1
    
    # Distribuzione per lingua
    lang_distribution = {}
    for chunk in context:
        lang = chunk.get("meta", {}).get("lang", "unknown")
        lang_distribution[lang] = lang_distribution.get(lang, 0) + 1
    
    # Score qualità
    quality_scores = []
    for chunk in context:
        score = chunk.get("chunk_meta", {}).get("quality_score")
        if score is not None:
            quality_scores.append(score)
    
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
    
    return {
        "total_chunks": total_chunks,
        "total_words": total_words,
        "avg_words_per_chunk": total_words / total_chunks if total_chunks > 0 else 0,
        "source_distribution": source_distribution,
        "language_distribution": lang_distribution,
        "average_quality_score": avg_quality,
        "quality_range": {
            "min": min(quality_scores) if quality_scores else 0,
            "max": max(quality_scores) if quality_scores else 0
        }
    }