from openai import OpenAI
import logging
import json
from typing import Dict, List, Optional

from app.services.analysis.prompt_builder import PromptBuilder
from ....core.config import Config
from ..llm_interface import LLMService

logging.basicConfig(level=logging.INFO)

class OpenAIService(LLMService):
    def __init__(self, model_name: str = "gpt-4o-mini"):
        super().__init__()
        self.model_name = model_name

        if not hasattr(Config, 'OPENAI_API_KEY') or not Config.OPENAI_API_KEY:
            logging.error("Variabile d'ambiente 'OPENAI_API_KEY' non trovata in Config. Impossibile usare OpenAI.")
            return

        try:
            self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
            self.is_available = True
            logging.info(f"OpenAIService ({self.model_name}) inizializzato e disponibile.")
        except Exception as e:
            logging.error(f"Errore durante l'inizializzazione di OpenAIService: {e}")

    def evaluate_text_with_rag(self, post_text: str, retrieved_context: list, medical_concepts=None):
        """
        Valuta il testo di un post usando il contesto recuperato dal RAG e i concetti medici con OpenAI GPT.
        """
        if not self.is_available:
            logging.error("Chiamata a OpenAIService ma il servizio non è disponibile.")
            return {
                "grado_disinformazione": -1,
                "valutazione_testuale": "Servizio OpenAI non disponibile.",
                "motivazione": "Il servizio OpenAI non è stato inizializzato correttamente.",
                "fonti_utilizzate": [],
                "sentiment": "Errore del sentiment",
                "pubmed_validation": []
            }
        
        context_str = "\n".join([f"Fonte: {c.get('source_url', 'N/A')}\nContenuto: {c.get('text', '')}" for c in retrieved_context])

        medical_concepts_section = ""
        if medical_concepts:
            concepts_detail = "\n".join([f"- '{concept}'" for concept in medical_concepts])
            medical_concepts_section = f"""
            **Concetti Medici Dettagliati Estratti dal Post:**
            ---
            {concepts_detail}
            ---
            """

        messages = [
            {"role": "system", "content": f"""
            Sei un assistente esperto nella verifica di notizie mediche. Il tuo compito è valutare la veridicità di un'affermazione medica trovata sui social media, basandoti su informazioni scientifiche e mediche autorevoli fornite e considerando i concetti medici specifici estratti. Rispondi in modo conciso e professionale.
            Fornisci la tua risposta ESCLUSIVAMENTE in formato JSON.
            """},
            {"role": "user", "content": f"""
            **Testo del Post Social:**
            "{post_text}"

            {medical_concepts_section}

            **Informazioni Mediche Affidabili (Contesto Recuperato da PubMed):**
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
            """}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            logging.error(f"Errore nella valutazione con OpenAI: {e}", exc_info=True)
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
        Genera testo libero basato su un prompt fornito con OpenAI GPT.
        """
        if not self.is_available:
            logging.error("Chiamata a OpenAIService.generate_text ma il servizio non è disponibile.")
            return "Servizio OpenAI non disponibile."
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7 
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Errore nella generazione del testo con OpenAI: {e}")
            return f"Errore nella generazione del riepilogo AI: {str(e)}"
    
    def factcheck_dual_claim_native(self, post_text: str, evidence_text: str, evidence_mapping: List[dict]) -> Optional[str]:
        """
        Implementazione nativa del fact-checking dual-claim con OpenAI
        """
        if not self.is_available:
            return None
        
        try:
            
            prompt_builder = PromptBuilder()
            messages = prompt_builder.build_openai_messages(post_text, evidence_text)
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            return response.choices[0].message.content if response.choices else None
            
        except Exception as e:
            logging.error(f"Errore factcheck_dual_claim_native OpenAI: {e}")
            return None
    
    def analyze_sentiment_only(self, text: str) -> str:
        """
        Analizza solo il sentiment del testo con OpenAI
        """
        if not self.is_available:
            return "neutro"
        
        try:
            messages = [
                {"role": "system", "content": "Classifica il sentiment come 'positivo', 'negativo' o 'neutro'. Rispondi SOLO con JSON."},
                {"role": "user", "content": f"""
                Testo: {text}
                
                Restituisci:
                {{
                  "sentiment": "positivo|negativo|neutro"
                }}
                """}
            ]
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            if response.choices:
                result = json.loads(response.choices[0].message.content)
                sentiment = result.get("sentiment", "neutro").lower()
                return sentiment if sentiment in ["positivo", "negativo", "neutro"] else "neutro"
            
        except Exception as e:
            logging.warning(f"Errore analisi sentiment OpenAI: {e}")
        
        return "neutro"

    def extract_medical_concepts_prova(self, text: str):
        """
        Estrae fino a 3 concetti medici
        
        """
        if not self.is_available:
            logging.error("OpenAIService non disponibile per extract_medical_concepts_prova.")
            return []

        messages = [
            {"role": "system", "content": (
                "Sei un assistente specializzato nell'estrazione di concetti medici. "
                "Estrai i concetti medici principali da un testo. Rispondi SOLO con JSON."
            )},
            {"role": "user", "content": f"""
                Estrai al massimo 3 concetti medici dal seguente testo:

                {text}

                Rispondi solo con un oggetto JSON con una chiave "medical_concepts" lista di stringhe.
                Esempio:
                {{
                  "medical_concepts": ["Diabete", "Insulina", "Glicemia alta"]
                }}
            """}
        ]

        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            if not hasattr(resp, "choices") or not resp.choices:
                return []
            content = getattr(resp.choices[0].message, "content", None)
            if not content:
                return []

            try:
                result = json.loads(content)
            except Exception:
                logging.warning("extract_medical_concepts_prova: JSON non valido, ritorno lista vuota.")
                return []

            mc = result.get("medical_concepts", [])
            if isinstance(mc, str):
                mc = [mc.strip()] if mc.strip() else []
            elif isinstance(mc, list):
                mc = [str(x).strip() for x in mc if isinstance(x, (str, int, float)) and str(x).strip()]
            else:
                mc = []
            return mc

        except Exception as e:
            logging.error(f"Errore in extract_medical_concepts_prova: {e}", exc_info=True)
            return []