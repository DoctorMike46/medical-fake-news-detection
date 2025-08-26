import json
import re
import logging
from typing import Any, Dict, List, Optional


class ResultValidator:
    """Valida e normalizza le risposte degli LLM"""

    @staticmethod
    def parse_json_safe(content: str) -> Optional[dict]:
        """Parse JSON sicuro con gestione errori"""
        if not content:
            return None
            
        try:
            # Rimuovo markdown se presente
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            
            # Rimuovo caratteri di controllo
            clean_content = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', content)
            
            # Trovo il JSON nel contenuto
            json_start = clean_content.find('{')
            json_end = clean_content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_str = clean_content[json_start:json_end]
                return json.loads(json_str)
            
            return json.loads(clean_content)
            
        except (json.JSONDecodeError, ValueError) as e:
            logging.warning(f"JSON parse error: {e}")
            return None

    @staticmethod
    def extract_citation_indices(text: str) -> List[int]:
        """Estrae gli indici di citazione [n] dal testo"""
        indices = []
        for match in re.findall(r"\[(\d+)\]", text or ""):
            try:
                idx = int(match)
                if idx > 0:
                    indices.append(idx)
            except ValueError:
                continue
        return sorted(set(indices))

    @staticmethod
    def validate_dual_claim_schema(data: dict) -> bool:
        """Valida che la risposta abbia lo schema dual-claim corretto"""
        if not isinstance(data, dict):
            return False
        
        required_keys = ["general_claim", "local_claim", "overall_verdict", "confidence"]
        if not all(key in data for key in required_keys):
            return False
        
        # Valido ogni claim
        for claim_key in ["general_claim", "local_claim"]:
            claim = data.get(claim_key)
            if not isinstance(claim, dict):
                return False
            
            # Verifico presenza di citazioni nel reasoning
            reasoning = claim.get("reasoning", "")
            if not re.search(r"\[\d+\]", reasoning):
                return False
            
            # Verifico cited_evidence non vuoto
            cited_evidence = claim.get("cited_evidence", [])
            if not isinstance(cited_evidence, list) or len(cited_evidence) == 0:
                return False
        
        return True

    @staticmethod
    def normalize_dual_claim_result(data: Any, evidence_mapping: List[dict] = None) -> dict:
        """
        Normalizza il risultato al formato dual-claim standard
        """
        if evidence_mapping is None:
            evidence_mapping = []
        
        # Parse se è stringa
        if isinstance(data, str):
            data = ResultValidator.parse_json_safe(data) or {}
        
        if not isinstance(data, dict):
            data = {}

        def normalize_claim_section(section: Any) -> dict:
            """Normalizza una singola sezione (general_claim o local_claim)"""
            if not isinstance(section, dict):
                section = {}
            
            verdict = str(section.get("verdict", "UNCERTAIN")).upper()
            if verdict not in ["REAL", "FAKE", "UNCERTAIN"]:
                verdict = "UNCERTAIN"
            
            reasoning = section.get("reasoning", "") or ""
            cited_evidence = section.get("cited_evidence", []) or []
            
            # Normalizzo cited_evidence
            normalized_evidence = []
            for item in cited_evidence:
                if isinstance(item, dict):
                    normalized_evidence.append({
                        "idx": item.get("idx"),
                        "title": item.get("title", ""),
                        "url": item.get("url", "")
                    })
            
            return {
                "verdict": verdict,
                "reasoning": reasoning,
                "cited_evidence": normalized_evidence
            }

        # Normalizzo le sezioni
        general_claim = normalize_claim_section(data.get("general_claim"))
        local_claim = normalize_claim_section(data.get("local_claim"))
        
        # Normalizzo overall_verdict
        overall = str(data.get("overall_verdict", "UNCERTAIN")).upper()
        if overall not in ["REAL", "FAKE", "UNCERTAIN"]:
            overall = "UNCERTAIN"
        
        # Normalizzo confidence
        try:
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.5

        return {
            "general_claim": general_claim,
            "local_claim": local_claim,
            "overall_verdict": overall,
            "confidence": confidence
        }

    @staticmethod
    def backfill_missing_citations(claim: dict, evidence_mapping: List[dict]) -> dict:
        """
        Riempie citazioni mancanti usando l'evidence mapping
        """
        reasoning = claim.get("reasoning", "")
        cited_evidence = claim.get("cited_evidence", [])
        
        # Se già ha citazioni valide, lascia com'è
        if cited_evidence and re.search(r"\[\d+\]", reasoning):
            return claim
        
        # Estraggo indici dal reasoning o usa fallback
        indices = ResultValidator.extract_citation_indices(reasoning)
        if not indices:
            # Fallback: uso i primi 2-3 elementi
            indices = list(range(1, min(4, len(evidence_mapping) + 1)))
        
        # Costruisco cited_evidence
        new_cited_evidence = []
        for idx in indices:
            if 1 <= idx <= len(evidence_mapping):
                mapping_item = evidence_mapping[idx - 1]
                new_cited_evidence.append({
                    "idx": idx,
                    "title": mapping_item.get("title", ""),
                    "url": mapping_item.get("url", "")
                })
        
        # Aggiorno il claim
        claim["cited_evidence"] = new_cited_evidence
        
        if not re.search(r"\[\d+\]", reasoning) and new_cited_evidence:
            claim["reasoning"] = f"{reasoning} [{new_cited_evidence[0]['idx']}]".strip()
        
        return claim

    @staticmethod
    def derive_overall_verdict(general_verdict: str, local_verdict: str) -> str:
        """Deriva il verdetto complessivo dalle due sezioni"""
        general = (general_verdict or "UNCERTAIN").upper()
        local = (local_verdict or "UNCERTAIN").upper()
        
        if general == "FAKE" or local == "FAKE":
            return "FAKE"
        if general == "REAL" and local == "REAL":
            return "REAL"
        return "UNCERTAIN"


class GradeCalculator:
    """Calcola il grado di disinformazione basato sui verdetti"""
    
    @staticmethod
    def verdict_to_grade(verdict: str, confidence: float = 0.5) -> int:
        """
        Converte verdetto in grado numerico:
        0 = REAL (nessuna disinformazione)
        1 = UNCERTAIN (da valutare)
        2 = FAKE (moderata disinformazione)
        3 = FAKE (grave disinformazione, alta confidence)
        """
        verdict = (verdict or "").upper()
        
        if verdict == "REAL":
            return 0
        elif verdict == "FAKE":
            return 3 if confidence >= 0.75 else 2
        else:  # UNCERTAIN
            return 1

    @staticmethod
    def build_reasoning_summary(result: dict) -> str:
        """Costruisce un riassunto della motivazione"""
        if not result:
            return "Nessuna motivazione disponibile."
        
        general_reasoning = (result.get("general_claim", {}) or {}).get("reasoning", "")
        local_reasoning = (result.get("local_claim", {}) or {}).get("reasoning", "")
        
        parts = []
        if general_reasoning:
            parts.append(f"Generale: {general_reasoning}")
        if local_reasoning:
            parts.append(f"Locale/Temporale: {local_reasoning}")
        
        summary = " | ".join(parts)
        return summary[:1500] if summary else "Nessuna motivazione disponibile."


class ResponseBuilder:
    """Costruisce risposte standardizzate"""
    
    @staticmethod
    def build_success_response(
        factcheck_result: dict,
        sentiment: str,
        evidence_mapping: List[dict],
        post_text: str
    ) -> dict:
        """Costruisce risposta di successo standardizzata"""
        
        overall_verdict = factcheck_result.get("overall_verdict", "UNCERTAIN")
        confidence = factcheck_result.get("confidence", 0.5)
        
        grade = GradeCalculator.verdict_to_grade(overall_verdict, confidence)
        
        # Estraggo URL delle fonti
        urls = []
        for claim_key in ["general_claim", "local_claim"]:
            claim = factcheck_result.get(claim_key, {}) or {}
            for evidence in claim.get("cited_evidence", []):
                url = evidence.get("url")
                if url and url not in urls:
                    urls.append(url)
        
        return {
            "status": "ok",
            "factcheck": factcheck_result,
            "grado_disinformazione": grade,
            "valutazione_testuale": f"Verdetto complessivo: {overall_verdict}",
            "motivazione": GradeCalculator.build_reasoning_summary(factcheck_result),
            "fonti_utilizzate": urls,
            "evidence_count": len(evidence_mapping),
            "sentiment": sentiment,
        }

    @staticmethod
    def build_error_response(reason: str, details: str = "") -> dict:
        """Costruisce risposta di errore standardizzata"""
        message = f"Errore durante il fact-check: {reason}"
        if details:
            message = f"{message} — {details}"
        
        return {
            "status": "error",
            "error": reason,
            "message": message,
            "grado_disinformazione": -1,
            "sentiment": "neutro",
            "factcheck": {
                "general_claim": {"verdict": "UNCERTAIN", "reasoning": "", "cited_evidence": []},
                "local_claim": {"verdict": "UNCERTAIN", "reasoning": "", "cited_evidence": []},
                "overall_verdict": "UNCERTAIN",
                "confidence": 0.5
            },
            "fonti_utilizzate": [],
            "evidence_count": 0,
            "valutazione_testuale": "Verdetto complessivo: UNCERTAIN",
            "motivazione": "Nessuna motivazione disponibile."
        }