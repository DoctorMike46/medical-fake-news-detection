# app/services/analysis/llm_interface.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class LLMService(ABC):
    """
    Classe base astratta per i servizi LLM. Tutti i servizi LLM devono ereditare da questa classe.
    """
    
    def __init__(self):
        self.is_available = False
        self.model_name = ""
    
    @abstractmethod
    def evaluate_text_with_rag(self, text, retrieved_context, medical_concepts=None):
        """
        Analizza un testo utilizzando il contesto RAG.
        :param text: Il testo da analizzare.
        :param retrieved_context: Il contesto recuperato da una fonte esterna (es. Elasticsearch).
        :param medical_concepts: Lista opzionale di concetti medici estratti.
        :return: Un dizionario con i risultati dell'analisi.
        """
        pass

    @abstractmethod
    def generate_text(self, prompt: str) -> str:
        """
        Genera testo libero basato su un prompt fornito.
        :param prompt: Il prompt di testo per la generazione.
        :return: Una stringa di testo generato.
        """
        pass

    def extract_medical_concepts_prova(self, text: str):
        """Estrazione concetti medici - implementazione base"""
        return []
    
    def factcheck_dual_claim(self, post_text: str, evidence_chunks: List[dict], **kwargs) -> Optional[Dict]:
        """
        Esegue fact-checking con approccio dual-claim (generale + locale/temporale)
        
        Args:
            post_text: Testo del post da verificare
            evidence_chunks: Lista di chunk di evidenze con metadati
            **kwargs: Parametri aggiuntivi (max_retries, temperature, etc.)
        
        Returns:
            Dict con risultato fact-check nel formato standard o None se fallisce
        """
        try:
            retrieved_context = []
            for chunk in evidence_chunks:
                meta = chunk.get("meta", {})
                retrieved_context.append({
                    "text": chunk.get("content", ""),
                    "source_url": meta.get("url", ""),
                    "source": meta.get("source", "")
                })
            
            legacy_result = self.evaluate_text_with_rag(post_text, retrieved_context)
            
            return self._convert_legacy_to_dual_claim(legacy_result, evidence_chunks)
            
        except Exception as e:
            return None
    
    def analyze_sentiment_only(self, text: str) -> str:
        """
        Analizza solo il sentiment del testo
        
        Returns:
            Sentiment come stringa: "positivo", "negativo", "neutro"
        """
        try:
            result = self.evaluate_text_with_rag(text, [])
            return result.get("sentiment", "neutro")
        except Exception:
            return "neutro"
    
    def _convert_legacy_to_dual_claim(self, legacy_result: Dict, evidence_chunks: List[dict]) -> Dict:
        """
        Converte risultato legacy nel formato dual-claim
        """
        if not legacy_result:
            return self._get_default_dual_claim_result()
        
        grado = legacy_result.get("grado_disinformazione", 1)
        motivazione = legacy_result.get("motivazione", "")
        fonti = legacy_result.get("fonti_utilizzate", [])
        
        if grado == 0:
            verdict = "REAL"
            confidence = 0.9
        elif grado >= 3:
            verdict = "FAKE"
            confidence = 0.8
        elif grado == 2:
            verdict = "FAKE"
            confidence = 0.6
        else:
            verdict = "UNCERTAIN"
            confidence = 0.5
        
        cited_evidence = []
        for i, chunk in enumerate(evidence_chunks[:3], 1):
            meta = chunk.get("meta", {})
            cited_evidence.append({
                "idx": i,
                "title": meta.get("title", ""),
                "url": meta.get("url", "")
            })
        
        return {
            "general_claim": {
                "verdict": verdict,
                "reasoning": motivazione,
                "cited_evidence": cited_evidence
            },
            "local_claim": {
                "verdict": "UNCERTAIN",
                "reasoning": "Analisi locale/temporale non disponibile nel formato legacy.",
                "cited_evidence": []
            },
            "overall_verdict": verdict,
            "confidence": confidence
        }
    
    def _get_default_dual_claim_result(self) -> Dict:
        """Ritorna risultato dual-claim di default in caso di errore"""
        return {
            "general_claim": {
                "verdict": "UNCERTAIN",
                "reasoning": "Errore nell'analisi del servizio LLM.",
                "cited_evidence": []
            },
            "local_claim": {
                "verdict": "UNCERTAIN",
                "reasoning": "Errore nell'analisi del servizio LLM.",
                "cited_evidence": []
            },
            "overall_verdict": "UNCERTAIN",
            "confidence": 0.3
        }


class FactCheckCapableLLMService(LLMService):
    
    @abstractmethod
    def factcheck_dual_claim_native(self, post_text: str, evidence_text: str, evidence_mapping: List[dict]) -> Optional[str]:
        """
        Implementazione nativa del fact-checking dual-claim
        
        Args:
            post_text: Testo da verificare
            evidence_text: Evidenze formattate come testo con indici [1], [2], etc.
            evidence_mapping: Mapping degli indici con metadati
        
        Returns:
            JSON string con risultato o None se fallisce
        """
        pass