from typing import List, Dict, Tuple


class PromptBuilder:
    """Costruisce prompt strutturati per diversi tipi di LLM"""
    
    def __init__(self):
        self.base_instructions = {
            "system": (
                "Sei un fact-checker medico. Valuta con rigore evidence-based.\n"
                "Analizza DUE aspetti distinti del post:\n"
                " - CLAIM GENERALE (validità scientifica generale)\n"
                " - CLAIM LOCALE/TEMPORALE (es. paese/anno affermati)\n"
                "Usa SOLO le evidenze fornite e cita SEMPRE gli indici [n].\n"
                "Se le evidenze sono insufficienti, rispondi 'UNCERTAIN' ma cita comunque le evidenze più pertinenti."
            ),
            "rules": (
                "REGOLE:\n"
                "- Ogni 'reasoning' deve contenere almeno una citazione [n].\n"
                "- Ogni sezione deve avere 'cited_evidence' NON vuoto (coerente con gli indici citati).\n"
                "- 'overall_verdict' = REAL solo se general e local sono entrambi REAL; FAKE se almeno uno è FAKE; altrimenti UNCERTAIN.\n"
                "- Non aggiungere testo fuori dal JSON."
            ),
            "json_schema": (
                '{\n'
                '  "general_claim": {"verdict":"REAL|FAKE|UNCERTAIN","reasoning":"... [n]","cited_evidence":[{"idx":n,"title":"...","url":"..."}]},\n'
                '  "local_claim":   {"verdict":"REAL|FAKE|UNCERTAIN","reasoning":"... [n]","cited_evidence":[{"idx":n,"title":"...","url":"..."}]},\n'
                '  "overall_verdict":"REAL|FAKE|UNCERTAIN",\n'
                '  "confidence": 0.0-1.0\n'
                '}'
            )
        }

    def build_dual_claim_prompt(self, post_text: str, evidence_text: str) -> Dict[str, str]:
        """
        Costruisce prompt per analisi dual-claim (generale + locale/temporale)
        
        Returns:
            Dict con chiavi 'system' e 'user' per i diversi ruoli
        """
        user_prompt = (
            "POST DA VALUTARE (IT/EN):\n"
            f"{post_text}\n\n"
            "EVIDENZE (usa indici [1], [2], ... nelle citazioni):\n"
            f"{evidence_text}\n\n"
            "Compito: restituisci SOLO JSON con esattamente questi campi:\n"
            f"{self.base_instructions['json_schema']}\n"
            f"{self.base_instructions['rules']}"
        )
        
        return {
            "system": self.base_instructions["system"],
            "user": user_prompt
        }

    def build_openai_messages(self, post_text: str, evidence_text: str) -> List[Dict[str, str]]:
        """Formato specifico per OpenAI Chat API"""
        prompts = self.build_dual_claim_prompt(post_text, evidence_text)
        return [
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": prompts["user"]}
        ]

    def build_claude_messages(self, post_text: str, evidence_text: str) -> List[Dict]:
        """Formato specifico per Claude API"""
        prompts = self.build_dual_claim_prompt(post_text, evidence_text)
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"{prompts['system']}\n\n{prompts['user']}"
                    }
                ]
            }
        ]

    def build_gemini_prompt(self, post_text: str, evidence_text: str) -> str:
        """Formato specifico per Gemini (prompt singolo)"""
        prompts = self.build_dual_claim_prompt(post_text, evidence_text)
        return f"{prompts['system']}\n\n{prompts['user']}"

    def build_retry_prompt(self, original_user_prompt: str, attempt: int) -> str:
        """Costruisce prompt per retry con istruzioni aggiuntive"""
        retry_instructions = (
            "\n\nATTENZIONE: La risposta precedente non rispettava lo schema o mancavano citazioni. "
            "Rigenera il JSON assicurandoti che in ENTRAMBI 'general_claim' e 'local_claim': "
            "1) il 'reasoning' contenga almeno una citazione [n]; "
            "2) 'cited_evidence' elenchi gli [n] citati con titolo e URL."
        )
        return original_user_prompt + retry_instructions


class EvidenceFormatter:
    """Formatta le evidenze per i prompt"""
    
    @staticmethod
    def format_evidence_for_prompt(chunks: List[dict]) -> Tuple[str, List[dict]]:
        """
        Formatta chunks di evidenze in testo leggibile con indici numerati
        
        Returns:
            Tuple[str, List[dict]]: (testo_formattato, mapping_indici)
        """
        lines = []
        mapping = []
        
        for i, chunk in enumerate(chunks, 1):
            meta = chunk.get("meta") or {}
            title = meta.get("title") or "Senza titolo"
            url = meta.get("url") or ""
            source = meta.get("source") or meta.get("feed") or "sconosciuta"
            excerpt = (chunk.get("content") or "")[:900]
            
            lines.append(
                f"[{i}] TITOLO: {title}\n"
                f"FONTE: {source}\n"
                f"URL: {url}\n"
                f"ESTRATTO: {excerpt}"
            )
            
            mapping.append({
                "idx": i,
                "title": title,
                "url": url,
                "source": source
            })
        
        return "\n\n".join(lines), mapping

    @staticmethod
    def extract_urls_from_evidence(mapping: List[dict]) -> List[str]:
        """Estrae lista URL dalle evidenze"""
        urls = []
        for item in mapping:
            url = item.get("url")
            if url and url not in urls:
                urls.append(url)
        return urls


class SentimentAnalyzer:
    """Analizza il sentiment dei post"""
    
    @staticmethod
    def build_sentiment_prompt(text: str) -> Dict[str, str]:
        """Costruisce prompt per analisi sentiment"""
        return {
            "system": "Classifica il sentiment di questo testo come 'positivo', 'negativo' o 'neutro'. Rispondi SOLO con JSON.",
            "user": f"""
                Testo:
                ---
                {text}
                ---
                Restituisci:
                {{
                  "sentiment": "positivo|negativo|neutro"
                }}
            """
        }