import re
import anthropic
import logging
import json
from typing import Dict, List, Optional

from app.services.analysis.prompt_builder import PromptBuilder, SentimentAnalyzer
from ....core.config import Config
from ..llm_interface import LLMService

logging.basicConfig(level=logging.INFO)

class ClaudeService(LLMService):
    def __init__(self, model_name: str = "claude-3-haiku-20240307"):
        super().__init__()
        self.model_name = model_name
        
        if not hasattr(Config, 'CLAUDE_API_KEY') or not Config.CLAUDE_API_KEY:
            logging.error("Variabile d'ambiente 'CLAUDE_API_KEY' non trovata in Config. Impossibile usare Claude.")
            return

        try:
            self.client = anthropic.Anthropic(api_key=Config.CLAUDE_API_KEY)
            self.is_available = True
            logging.info(f"ClaudeService ({self.model_name}) inizializzato e disponibile.")
        except Exception as e:
            logging.error(f"Errore durante l'inizializzazione di ClaudeService: {e}")
            
    def evaluate_text_with_rag(self, post_text: str, retrieved_context: list, medical_concepts=None): 
        """
        Valuta il testo di un post usando il contesto recuperato dal RAG e i concetti medici con Claude.
        METODO ORIGINALE MANTENUTO PER COMPATIBILITÀ
        """
        if not self.is_available:
            logging.error("Chiamata a ClaudeService ma il servizio non è disponibile.")
            return {
                "grado_disinformazione": -1,
                "valutazione_testuale": "Servizio Claude non disponibile.",
                "motivazione": "Il servizio Claude non è stato inizializzato correttamente.",
                "fonti_utilizzate": [],
                "sentiment": "Errore del sentiment"
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

        prompt_messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""
                        Sei un assistente esperto nella verifica di notizie mediche. Il tuo compito è valutare la veridicità di un'affermazione medica trovata sui social media, basandoti su informazioni scientifiche e mediche autorevoli fornite e considerando i concetti medici specifici estratti.

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
                        5.  Indica quali "Fonti Utilizzate" dal contesto recuperato sono state più rilevanti per la tua valutazione.
                        6.  **Analisi del Sentiment:** Classifica il sentiment generale del post come "positivo", "negativo" o "neutro".

                        Fornisci la tua risposta esclusivamente in formato JSON, all'interno di un blocco di codice come il seguente:
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
                    }
                ]
            }
        ]

        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=2000,
                messages=prompt_messages,
                temperature=0.1
            )
            
            json_str = response.content[0].text
            
            json_start = json_str.find('{')
            json_end = json_str.rfind('}') + 1
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_data_str = json_str[json_start:json_end]
            else:
                raise ValueError(f"Nessun blocco JSON valido trovato nella risposta di Claude. Risposta completa: {json_str}")
            
            clean_json_str = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', json_data_str)
            result = json.loads(clean_json_str)

            return result

        except anthropic.APIError as e:
            logging.error(f"Errore API di Claude: {e}")
            raise 

        except json.JSONDecodeError as e:
            logging.error(f"Errore nel parsing JSON della risposta di Claude: {e}. Risposta completa: ```{json_data_str}```", exc_info=True)
            return {
                "grado_disinformazione": -1,
                "valutazione_testuale": "Errore nel parsing della risposta dell'LLM.",
                "motivazione": f"L'LLM ha generato una risposta con un formato JSON non valido. Errore: {e}",
                "fonti_utilizzate": [],
                "sentiment": "Errore del sentiment"
            }

        except Exception as e:
            logging.error(f"Errore generico nella valutazione con Claude: {e}", exc_info=True)
            return {
                "grado_disinformazione": -1,
                "valutazione_testuale": "Errore nella valutazione LLM.",
                "motivazione": f"Si è verificato un errore durante l'analisi: {str(e)}",
                "fonti_utilizzate": [],
                "sentiment": "Errore del sentiment"
            }

    def generate_text(self, prompt: str) -> str:
        """
        Genera testo libero basato su un prompt fornito con Claude.
        METODO ORIGINALE MANTENUTO PER COMPATIBILITÀ (CORRETTO)
        """
        if not self.is_available:
            logging.error("Chiamata a ClaudeService.generate_text ma il servizio non è disponibile.")
            return "Servizio Claude non disponibile."
        try:
            messages = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
            
            response = self.client.messages.create(
                model=self.model_name,
                messages=messages,
                max_tokens=2000,
                temperature=0.7 
            )
            return response.content[0].text
        except Exception as e:
            logging.error(f"Errore nella generazione del testo con Claude: {e}")
            return f"Errore nella generazione del riepilogo AI: {str(e)}"
    
    def factcheck_dual_claim_native(self, post_text: str, evidence_text: str, evidence_mapping: List[dict]) -> Optional[str]:
        """
        Implementazione nativa del fact-checking dual-claim con Claude
        """
        if not self.is_available:
            return None
        
        try:
            
            prompt_builder = PromptBuilder()
            messages = prompt_builder.build_claude_messages(post_text, evidence_text)
            
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=2000,
                messages=messages,
                temperature=0.1
            )
            
            return response.content[0].text if response.content else None
            
        except Exception as e:
            logging.error(f"Errore factcheck_dual_claim_native Claude: {e}")
            return None
    
    def analyze_sentiment_only(self, text: str) -> str:
        """
        Analizza solo il sentiment del testo con Claude
        """
        if not self.is_available:
            return "neutro"
        
        try:
            
            prompt_data = SentimentAnalyzer.build_sentiment_prompt(text)
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": f"{prompt_data['system']}\n\n{prompt_data['user']}"
                        }
                    ]
                }
            ]
            
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=500,
                messages=messages,
                temperature=0.1
            )
            
            if response.content:
                content = response.content[0].text
                
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = content[json_start:json_end]
                    try:
                        result = json.loads(json_str)
                        sentiment = result.get("sentiment", "neutro").lower()
                        return sentiment if sentiment in ["positivo", "negativo", "neutro"] else "neutro"
                    except json.JSONDecodeError:
                        pass
            
        except Exception as e:
            logging.warning(f"Errore analisi sentiment Claude: {e}")
        
        return "neutro"