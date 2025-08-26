import logging
from typing import List, Dict, Optional, Any
from app.core.config import Config
from app.services.analysis.prompt_builder import EvidenceFormatter, PromptBuilder
from app.services.analysis.result_validator import ResultValidator
from .providers.openai_service import OpenAIService
from .providers.claude_service import ClaudeService
from .providers.gemini_service import GeminiService
from .pubmed_service import PubMedService



class LLMManager:
    """
    Gestisce l'inizializzazione e la distribuzione delle richieste tra i vari servizi LLM.
    """
    
    def __init__(self):
        self.llm_services = {}
        self.failed_llms = set()
        self.logger = logging.getLogger(__name__)
        
        self.prompt_builder = PromptBuilder()
        self.evidence_formatter = EvidenceFormatter()
        self.result_validator = ResultValidator()

        # self.gemini_model = getattr(Config, 'GEMINI_MODEL', 'gemini-2.5-pro')
        # self.claude_model = getattr(Config, 'CLAUDE_MODEL', 'claude-3-haiku-20240307')
        self.openai_model = getattr(Config, 'OPENAI_MODEL', 'gpt-mini')
        
        self._initialize_llm_services()
        
        self._initialize_pubmed_service()
        
        if not self.llm_services:
            self.logger.error("Nessun servizio LLM inizializzato con successo!")
        else:
            self.logger.info(f"LLMManager inizializzato con {len(self.llm_services)} servizi")
        
        self.service_index = 0
    
    def _initialize_llm_services(self):
        """Inizializza tutti i servizi LLM disponibili"""
        
        # try:
        #     gemini_service = GeminiService(model_name=self.gemini_model)
        #     if gemini_service.is_available:
        #         self.llm_services['gemini'] = gemini_service
        #         self.logger.info(f"GeminiService ({gemini_service.model_name}) inizializzato")
        #     else:
        #         self.logger.warning(f"GeminiService ({self.gemini_model}) non disponibile")
        # except Exception as e:
        #     self.logger.error(f"Errore inizializzazione GeminiService: {e}")
            
        # try:
        #     claude_service = ClaudeService(model_name=self.claude_model)
        #     if claude_service.is_available:
        #         self.llm_services['claude'] = claude_service
        #         self.logger.info(f"ClaudeService ({claude_service.model_name}) inizializzato")
        #     else:
        #         self.logger.warning(f"ClaudeService ({self.claude_model}) non disponibile")
        # except Exception as e:
        #     self.logger.error(f"Errore inizializzazione ClaudeService: {e}")

        try:
            openai_service = OpenAIService(model_name=self.openai_model)
            if openai_service.is_available:
                self.llm_services['openai'] = openai_service
                self.logger.info(f"OpenAIService ({openai_service.model_name}) inizializzato")
            else:
                self.logger.warning(f"OpenAIService ({self.openai_model}) non disponibile")
        except Exception as e:
            self.logger.error(f"Errore inizializzazione OpenAIService: {e}")
    
    def _initialize_pubmed_service(self):
        """Inizializza il servizio PubMed"""
        self.pubmed_service = None 
        try:
            self.pubmed_service = PubMedService(
                email=Config.PUBMED_EMAIL, 
                api_key=Config.ENTREZ_API_KEY
            ) 
            if not self.pubmed_service.is_available:
                self.logger.warning("PubMedService non completamente disponibile")
        except Exception as e:
            self.logger.error(f"Errore inizializzazione PubMedService: {e}")
            self.pubmed_service = None
    
    def get_all_services(self):
        """
        Restituisce una lista di tutti i servizi LLM disponibili e non marcati come falliti
        nel batch corrente.
        """
        available_services = [
            service for name, service in self.llm_services.items()
            if service.is_available and name not in self.failed_llms
        ]
        self.logger.info(f"Servizi disponibili: {[s.model_name for s in available_services]}")
        return available_services

    def mark_as_failed(self, service_name: str):
        """Marca un servizio LLM come fallito per il batch corrente."""
        self.failed_llms.add(service_name)
        self.logger.warning(f"Servizio '{service_name}' marcato come fallito per il batch")

    def reset_failed_services(self):
        """Resetta la lista dei servizi falliti all'inizio di un nuovo batch."""
        self.failed_llms.clear()
        self.logger.info("Lista servizi falliti resettata per il nuovo batch")

    def get_next_service(self):
        """
        Restituisce il prossimo servizio LLM disponibile in modo ciclico,
        saltando quelli marcati come falliti nel batch corrente.
        """
        services_to_check = self.get_all_services()
        
        if not services_to_check:
            self.logger.error("Nessun servizio LLM disponibile")
            return None
            
        service_names = list(self.llm_services.keys())
        current_service_name = service_names[self.service_index]
        current_service = self.llm_services[current_service_name]

        if not current_service.is_available or current_service_name in self.failed_llms:
            for _ in range(len(service_names)):
                self.service_index = (self.service_index + 1) % len(service_names)
                next_service_name = service_names[self.service_index]
                next_service = self.llm_services[next_service_name]
                if next_service.is_available and next_service_name not in self.failed_llms:
                    self.logger.info(f"Passaggio al servizio: {next_service.model_name}")
                    return next_service
            
            self.logger.error("Nessun servizio LLM disponibile per la prossima richiesta")
            return None
        
        self.service_index = (self.service_index + 1) % len(service_names)
        return current_service
    
    
    def factcheck_with_retry(
        self, 
        post_text: str, 
        evidence_chunks: List[dict], 
        max_retries: int = 2
    ) -> Dict:
        """
        Esegue fact-checking con retry automatico su più servizi LLM
        
        Args:
            post_text: Testo del post da verificare
            evidence_chunks: Lista di chunk di evidenze  
            max_retries: Numero massimo di retry per servizio
            
        Returns:
            Risultato fact-check nel formato dual-claim
        """
        evidence_text, evidence_mapping = self.evidence_formatter.format_evidence_for_prompt(
            evidence_chunks
        )
        
        attempted_services = set()
        
        while len(attempted_services) < len(self.llm_services):
            service = self.get_next_service()
            
            if not service:
                break
                
            service_name = self._get_service_name(service)
            
            if service_name in attempted_services:
                continue
                
            attempted_services.add(service_name)
            
            self.logger.info(f"Tentativo fact-checking con {service_name}")
            
            try:
                result = self. _try_factcheck_with_service(
                    service, post_text, evidence_text, evidence_mapping, max_retries
                )
                
                if result and self._is_valid_factcheck_result(result):
                    self.logger.info(f"Fact-checking completato con {service_name}")
                    return result
                else:
                    self.logger.warning(f"Risultato non valido da {service_name}")
                    self.mark_as_failed(service_name)
                    
            except Exception as e:
                self.logger.error(f"Errore con {service_name}: {e}")
                self.mark_as_failed(service_name)
                continue
        
        self.logger.warning("Tutti i servizi LLM falliti, usando fallback")
        return self._get_fallback_factcheck_result(evidence_mapping)
    
    def _try_factcheck_with_service(
        self, 
        service, 
        post_text: str, 
        evidence_text: str, 
        evidence_mapping: List[dict], 
        max_retries: int
    ) -> Optional[Dict]:
        """
        Tenta fact-checking con un singolo servizio
        """
        if hasattr(service, 'factcheck_dual_claim_native'):
            for attempt in range(max_retries + 1):
                try:
                    raw_result = service.factcheck_dual_claim_native(
                        post_text, evidence_text, evidence_mapping
                    )
                    
                    if raw_result:
                        parsed_result = self.result_validator.parse_json_safe(raw_result)
                        if parsed_result and self.result_validator.validate_dual_claim_schema(parsed_result):
                            return self.result_validator.normalize_dual_claim_result(
                                parsed_result, evidence_mapping
                            )
                except Exception as e:
                    self.logger.warning(f"Tentativo {attempt + 1} fallito: {e}")
                    
        try:
            result = service.factcheck_dual_claim(
                post_text, 
                [{"content": evidence_text, "meta": {"mapping": evidence_mapping}}]
            )
            
            if result:
                return self.result_validator.normalize_dual_claim_result(result, evidence_mapping)
                
        except Exception as e:
            self.logger.warning(f"Fallback dual-claim fallito: {e}")
        
        return None
    
    def analyze_sentiment(self, text: str) -> str:
        """
        Analizza sentiment usando il primo servizio disponibile
        """
        for service_name, service in self.llm_services.items():
            if service.is_available and service_name not in self.failed_llms:
                try:
                    return service.analyze_sentiment_only(text)
                except Exception as e:
                    self.logger.warning(f"Errore sentiment con {service_name}: {e}")
                    continue
        
        return "neutro"  
    
    def _get_service_name(self, service) -> str:
        """Ottiene il nome del servizio dall'istanza"""
        for name, svc in self.llm_services.items():
            if svc is service:
                return name
        return "unknown"
    
    def _is_valid_factcheck_result(self, result: Dict) -> bool:
        """Verifica se il risultato del fact-checking è valido"""
        return (
            isinstance(result, dict) and
            "overall_verdict" in result and
            "confidence" in result and
            result.get("overall_verdict") in ["REAL", "FAKE", "UNCERTAIN"]
        )
    
    def _get_fallback_factcheck_result(self, evidence_mapping: List[dict]) -> Dict:
        """Genera risultato di fallback quando tutti i servizi falliscono"""
        fallback_evidence = []
        
        for i, mapping in enumerate(evidence_mapping[:2], 1):
            fallback_evidence.append({
                "idx": i,
                "title": mapping.get("title", ""),
                "url": mapping.get("url", "")
            })
        
        return {
            "general_claim": {
                "verdict": "UNCERTAIN",
                "reasoning": "Servizi LLM non disponibili per l'analisi. [1]",
                "cited_evidence": fallback_evidence
            },
            "local_claim": {
                "verdict": "UNCERTAIN",
                "reasoning": "Servizi LLM non disponibili per l'analisi. [1]",
                "cited_evidence": fallback_evidence
            },
            "overall_verdict": "UNCERTAIN",
            "confidence": 0.2
        }
    
    def get_service_for_analysis(self, post_id: str = None):
        return self.get_next_service()