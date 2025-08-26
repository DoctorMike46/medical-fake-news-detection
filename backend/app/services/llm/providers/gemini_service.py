import google.generativeai as genai
import logging
import json
from typing import Dict, List, Optional

from app.services.analysis.prompt_builder import PromptBuilder, SentimentAnalyzer
from ....core.config import Config
from ..llm_interface import LLMService

logging.basicConfig(level=logging.INFO)

class GeminiService(LLMService):
    def __init__(self, model_name: str = 'gemini-2.5-pro'):
        super().__init__() 
        self.model_name = model_name 
        
        if not Config.GEMINI_API_KEY:
            logging.error("Variabile d'ambiente 'GEMINI_API_KEY' non trovata in Config. Impossibile usare Gemini.")
            return 

        try:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(self.model_name)
            self.is_available = True
            logging.info(f"GeminiService ({self.model_name}) inizializzato e disponibile.")
        except Exception as e:
            logging.error(f"Errore durante l'inizializzazione del modello Gemini: {e}")
            
    def evaluate_text_with_rag(self, post_text: str, retrieved_context: list, medical_concepts=None):
        """
        Valuta il testo di un post usando il contesto recuperato dal RAG e i concetti medici.
        Restituisce un dizionario JSON strutturato.
        METODO ORIGINALE MANTENUTO PER COMPATIBILITÀ
        """
        if not self.is_available:
            logging.error("Chiamata a GeminiService ma il servizio non è disponibile.")
            return {
                "grado_disinformazione": -1,
                "valutazione_testuale": "Servizio Gemini non disponibile.",
                "motivazione": "Il servizio Gemini non è stato inizializzato correttamente.",
                "fonti_utilizzate": [],
                "sentiment": "Errore del sentiment",
                "pubmed_validation": []
            }

        context_str = "\n".join([f"Fonte: {c.get('source_url', 'N/A')}\nContenuto: {c.get('text', '')}" for c in retrieved_context])

        medical_concepts_section = ""
        if medical_concepts:
            concepts_detail = "\n".join([
                f"- Termine: '{mc.get('text', 'N/A')}' (Concetto standard: '{mc.get('preferred_name', 'N/A')}', CUI: {mc.get('cui', 'N/A')}, Tipi: {', '.join(mc.get('sem_types', []))})"
                for mc in medical_concepts
            ])
            medical_concepts_section = f"""
            **Concetti Medici Dettagliati Estratti dal Post (MetaMap):**
            ---
            {concepts_detail}
            ---
            """

        prompt = f"""
        Sei un assistente esperto nella verifica di notizie mediche. Il tuo compito è valutare la veridicità di un'affermazione medica trovata sui social media, basandoti su informazioni scientifiche e mediche autorevoli fornite, e considerando i concetti medici specifici estratti.

        **Testo del Post Social:**
        "{post_text}"

        {medical_concepts_section}

        **Informazioni Mediche Affidabili (Contesto Recuperato):**
        ---
        {context_str if context_str else "Nessuna informazione affidabile rilevante trovata nel contesto."}
        ---

        **Istruzioni per la Valutazione:**
        1.  Compara attentamente le affermazioni nel "Testo del Post Social" con le "Informazioni Mediche Affidabili" e i "Concetti Medici Dettagliati".
        2.  Identifica se il post contiene disinformazione, affermazioni fuorvianti, non supportate scientificamente, o in diretto contrasto con il contesto fornito. Presta particolare attenzione ai concetti medici identificati.
        3.  Assegna un "Grado di Disinformazione" su una scala da 0 a 3:
            * **0: Nessuna Disinformazione:** Il post è accurato o non contiene affermazioni mediche significative.
            * **1: Lieve Disinformazione/Ambiguità:** Contiene affermazioni leggermente fuorvianti, incomplete o che richiedono chiarimenti, ma non gravemente false.
            * **2: Moderata Disinformazione:** Contiene affermazioni false o non supportate che potrebbero portare a conclusioni errate, ma non rappresentano un rischio immediato grave.
            * **3: Grave Disinformazione/Fake News:** Contiene affermazioni palesemente false, dannose, pericolose o teorie del complotto che potrebbero causare grave danno alla salute pubblica.
        4.  Fornisci una "Motivazione" concisa che spieghi perché hai assegnato quel grado, evidenziando le discrepanze o le affermazioni non veritiere e facendo riferimento, se possibile, alle fonti fornite. Fai riferimento esplicitamente ai concetti medici se pertinenti.
        5.  Indica quali "Fonti Utilizzate" dal contesto recuperato sono state più rilevanti per la tua valutazione (lista di URL o identificativi).
        6.  **Analisi del Sentiment:** Classifica il sentiment generale del post come "positivo", "negativo" o "neutro".

        **Formato della Risposta (JSON):**
        ```json
        {{
            "grado_disinformazione": [0-3],
            "valutazione_testuale": "Breve riassunto della tua valutazione (es. 'Il post è una grave fake news.', 'Il post è accurato.', 'Il post contiene alcune imprecisioni minori.')",
            "motivazione": "Spiegazione dettagliata delle ragioni della valutazione, con riferimenti alle informazioni affidabili e ai concetti medici rilevanti.",
            "fonti_utilizzate": ["URL_Fonte_1", "URL_Fonte_2", ...],
            "sentiment": "positivo" | "negativo" | "neutro"
        }}
        ```
        """
        try:
            response = self.model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.1))
            
            json_response_str = response.text.strip()
            if json_response_str.startswith('```json'):
                json_response_str = json_response_str.replace('```json', '').replace('```', '').strip()
            
            result = json.loads(json_response_str)
            return result
        
        except ValueError as e:
            logging.error(f"Errore di parsing o di risposta da Gemini. Dettagli: {e}", exc_info=True)
            return {
                "grado_disinformazione": -1,
                "valutazione_testuale": "Errore di formato nella risposta AI o risposta vuota.",
                "motivazione": f"La risposta AI non era in formato JSON valido o vuota. Dettagli: {str(e)}",
                "fonti_utilizzate": [],
                "sentiment": "Errore del sentiment"
            }
        
        except json.JSONDecodeError as e:
            logging.error(f"Errore di parsing JSON dalla risposta Gemini RAG: {e}. Risposta RAW: {response.text}")
            return {
                "grado_disinformazione": -1,
                "valutazione_testuale": "Errore di formato nella risposta AI.",
                "motivazione": f"La risposta AI non era in formato JSON valido: {str(e)}",
                "fonti_utilizzate": [],
                "sentiment": "Errore del sentiment",
                "pubmed_validation": []
            }
        except Exception as e:
            logging.error(f"Errore nella valutazione con Gemini RAG: {e}", exc_info=True)
            return {
                "grado_disinformazione": -1,
                "valutazione_testuale": "Errore nella valutazione LLM.",
                "motivazione": f"Si è verificato un errore durante l'analisi: {str(e)}",
                "fonti_utilizzate": [],
                "sentiment": "Errore del sentiment",
                "pubmed_validation": []
            }
        
    def generate_text(self, prompt: str) -> str:
        """
        Genera testo libero basato su un prompt fornito, per il riepilogo della campagna.
        METODO ORIGINALE MANTENUTO PER COMPATIBILITÀ
        """
        if not self.is_available:
            logging.error("Chiamata a GeminiService.generate_text ma il servizio non è disponibile.")
            return "Servizio Gemini non disponibile."
        try:
            response = self.model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.7))
            return response.text
        except Exception as e:
            logging.error(f"Errore nella generazione del testo con Gemini: {e}", exc_info=True)
            return f"Errore nella generazione del riepilogo AI: {str(e)}"
    
    def factcheck_dual_claim_native(self, post_text: str, evidence_text: str, evidence_mapping: List[dict]) -> Optional[str]:
        """
        Implementazione nativa del fact-checking dual-claim con Gemini
        """
        if not self.is_available:
            return None
        
        try:
            # Import del prompt builder
            
            prompt_builder = PromptBuilder()
            prompt = prompt_builder.build_gemini_prompt(post_text, evidence_text)
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(temperature=0.1)
            )
            
            return response.text if response else None
            
        except Exception as e:
            logging.error(f"Errore factcheck_dual_claim_native Gemini: {e}")
            return None
    
    def analyze_sentiment_only(self, text: str) -> str:
        """
        Analizza solo il sentiment del testo con Gemini
        """
        if not self.is_available:
            return "neutro"
        
        try:
            
            prompt_data = SentimentAnalyzer.build_sentiment_prompt(text)
            prompt = f"{prompt_data['system']}\n\n{prompt_data['user']}"
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(temperature=0.1)
            )
            
            if response and response.text:
                content = response.text.strip()
                
                if content.startswith('```json'):
                    content = content.replace('```json', '').replace('```', '').strip()
                
                try:
                    result = json.loads(content)
                    sentiment = result.get("sentiment", "neutro").lower()
                    return sentiment if sentiment in ["positivo", "negativo", "neutro"] else "neutro"
                except json.JSONDecodeError:
                    content_lower = content.lower()
                    if "positivo" in content_lower:
                        return "positivo"
                    elif "negativo" in content_lower:
                        return "negativo"
                    else:
                        return "neutro"
            
        except Exception as e:
            logging.warning(f"Errore analisi sentiment Gemini: {e}")
        
        return "neutro"