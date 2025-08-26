from typing import List, Set, Optional, Iterable
import re
import logging
from collections import defaultdict
from Bio import Entrez

logger = logging.getLogger(__name__)

# Dizionario di seed per termini medici comuni (IT/EN)
_MEDICAL_SEED_TERMS = {
    "vaccino": {
        "vaccino", "vaccini", "#vaccino", "#vaccini", "vaccination", "vaccine", 
        "#vaccine", "immunizzazione", "immunization", "vaccinazione", "siero"
    },
    "chemioterapia": {
        "chemioterapia", "chemio", "chemioterapie", "chemotherapy", "#chemotherapy",
        "terapia antitumorale", "oncologia", "citotossico"
    },
    "vitamina c": {
        "vitamina c", "acido ascorbico", "ascorbato", "vitamin c", "#vitaminc",
        "vitamina", "integratore", "antiossidante"
    },
    "tumore": {
        "tumore", "tumori", "cancro", "neoplasia", "cancer", "#cancer",
        "oncologia", "carcinoma", "metastasi", "benigno", "maligno"
    },
    "diabete": {
        "diabete", "diabetico", "diabetici", "diabetes", "#diabetes",
        "glicemia", "insulina", "iperglicemia", "tipo 1", "tipo 2"
    },
    "antibiotico": {
        "antibiotico", "antibiotici", "antibiotic", "antibiotics", "#antibiotics",
        "resistenza", "batterio", "infezione", "antimicrobico"
    },
    "west nile": {
        "west nile", "west nile virus", "wnv", "#westnile",
        "virus del nilo occidentale", "nilo occidentale",
        "febbre del nilo occidentale", "arbovirosi", "culex", "zanzara"
    },
    "malattia west nile": {
        "west nile", "malattia west nile", "west nile virus", "wnv",
        "virus del nilo occidentale", "febbre del nilo occidentale",
        "nilo occidentale", "arbovirosi", "culex"
    },
    "covid": {
        "covid", "covid-19", "coronavirus", "sars-cov-2", "pandemia",
        "lockdown", "quarantena", "tampone", "vaccino covid", "long covid"
    },
    "influenza": {
        "influenza", "flu", "stagionale", "aviaria", "suina", "h1n1",
        "febbre", "sintomi influenzali", "vaccino antinfluenzale"
    }
}

class TopicExpander:
    """
    Classe per l'espansione intelligente di topic medici usando:
    - Dizionario di seed terms
    - Varianti linguistiche
    - Termini MeSH da PubMed
    """
    
    def __init__(self, email_ncbi: Optional[str] = None, api_key_ncbi: Optional[str] = None):
        self.email_ncbi = email_ncbi
        self.api_key_ncbi = api_key_ncbi
        self._setup_entrez()
    
    def _setup_entrez(self):
        """Configura Entrez per accesso PubMed"""
        if self.email_ncbi:
            Entrez.email = self.email_ncbi
            if self.api_key_ncbi:
                Entrez.api_key = self.api_key_ncbi
            logger.info("Entrez configured for MeSH term expansion")
        else:
            logger.warning("No email configured for Entrez - MeSH expansion disabled")
    
    @staticmethod
    def _deaccent(text: str) -> str:
        """Rimuove gli accenti dai caratteri italiani"""
        accent_map = {
            "à": "a", "è": "e", "é": "e", "ì": "i", 
            "ò": "o", "ó": "o", "ù": "u"
        }
        return re.sub(
            r"[àèéìòóù]", 
            lambda m: accent_map.get(m.group(0), m.group(0)), 
            text
        )
    
    def generate_simple_variants(self, term: str) -> Set[str]:
        """
        Genera varianti semplici di un termine (case, hashtag, plurali, accenti)
        """
        if not term or not term.strip():
            return set()
        
        t = term.strip()
        variants = {t, t.lower(), t.capitalize(), t.title()}
        
        variants.update({f"#{t}", f"#{t.lower()}"})
        
        deaccented = self._deaccent(t)
        if deaccented != t:
            variants.add(deaccented)
            variants.add(f"#{deaccented}")
        
        if t.endswith("o"):
            variants.add(t[:-1] + "i")
        if t.endswith("a"):
            variants.add(t[:-1] + "e")
        
        if t.endswith("y") and len(t) > 2:
            variants.add(t[:-1] + "ies")
        if not t.endswith("s"):
            variants.add(t + "s")
        
        return {v for v in variants if len(v) >= 2}
    
    def get_mesh_terms(self, query: str, max_results: int = 40) -> Set[str]:
        """
        Recupera termini MeSH da PubMed per una query
        """
        if not self.email_ncbi:
            logger.debug("MeSH expansion skipped - no email configured")
            return set()
        
        if not query or not query.strip():
            return set()
        
        try:
            logger.debug(f"Fetching MeSH terms for: {query}")
            
            search_handle = Entrez.esearch(
                db="pubmed", 
                term=query, 
                retmax=max_results, 
                sort="relevance"
            )
            search_results = Entrez.read(search_handle)
            search_handle.close()
            
            id_list = search_results.get("IdList", [])
            if not id_list:
                logger.debug(f"No PubMed results for: {query}")
                return set()
            
            fetch_handle = Entrez.efetch(
                db="pubmed", 
                id=",".join(id_list), 
                rettype="medline", 
                retmode="text"
            )
            medline_text = fetch_handle.read()
            fetch_handle.close()
            
            mesh_terms = set()
            mesh_pattern = r"^MH\s*-\s*(.+)$"
            
            for line in re.findall(mesh_pattern, medline_text, flags=re.MULTILINE):
                term = line.split("/")[0].replace("*", "").strip()
                if term and len(term) >= 3:
                    mesh_terms.add(term)
            
            logger.debug(f"Found {len(mesh_terms)} MeSH terms for: {query}")
            return mesh_terms
            
        except Exception as e:
            logger.warning(f"Error fetching MeSH terms for '{query}': {e}")
            return set()
    
    def get_seed_terms(self, topic: str) -> Set[str]:
        """
        Recupera termini seed dal dizionario medico
        """
        topic_normalized = topic.lower().strip()
        
        if topic_normalized in _MEDICAL_SEED_TERMS:
            return _MEDICAL_SEED_TERMS[topic_normalized].copy()
        
        matching_terms = set()
        for seed_key, seed_terms in _MEDICAL_SEED_TERMS.items():
            if topic_normalized in seed_key or seed_key in topic_normalized:
                matching_terms.update(seed_terms)
            
            for seed_term in seed_terms:
                if topic_normalized in seed_term.lower() or seed_term.lower() in topic_normalized:
                    matching_terms.update(seed_terms)
                    break
        
        return matching_terms
    
    def expand_topic(self, topic: str, post_terms: Optional[Iterable[str]] = None, 
                    include_mesh: bool = True, max_mesh_results: int = 30) -> Set[str]:
        """
        Espande un topic medico combinando:
        - Termini seed dal dizionario
        - Varianti linguistiche del topic
        - Varianti dei termini estratti dal post
        - Termini MeSH da PubMed (opzionale)
        
        Args:
            topic: Topic principale da espandere
            post_terms: Termini estratti dal post (opzionale)
            include_mesh: Se includere termini MeSH
            max_mesh_results: Numero massimo di risultati MeSH
            
        Returns:
            Set di termini espansi
        """
        expanded_terms = set()
        
        if not topic or not topic.strip():
            logger.warning("Empty topic provided for expansion")
            return expanded_terms
        
        topic_normalized = topic.lower().strip()
        logger.debug(f"Expanding topic: {topic}")
        
        seed_terms = self.get_seed_terms(topic_normalized)
        expanded_terms.update(seed_terms)
        logger.debug(f"Added {len(seed_terms)} seed terms")
        
        topic_variants = self.generate_simple_variants(topic_normalized)
        expanded_terms.update(topic_variants)
        
        if post_terms:
            post_terms_list = list(post_terms)[:6]
            for term in post_terms_list:
                if term and isinstance(term, str):
                    term_variants = self.generate_simple_variants(term)
                    expanded_terms.update(term_variants)
        
        if include_mesh and self.email_ncbi:
            try:
                mesh_terms = self.get_mesh_terms(topic_normalized, max_mesh_results)
                
                if post_terms:
                    for term in list(post_terms)[:4]:
                        if term and isinstance(term, str) and len(term) > 3:
                            term_mesh = self.get_mesh_terms(term, max_results=20)
                            mesh_terms.update(term_mesh)
                
                for mesh_term in mesh_terms:
                    mesh_variants = self.generate_simple_variants(mesh_term)
                    expanded_terms.update(mesh_variants)
                
                logger.debug(f"Added {len(mesh_terms)} MeSH terms")
                
            except Exception as e:
                logger.warning(f"MeSH expansion failed: {e}")
        
        final_terms = {
            term for term in expanded_terms 
            if term and isinstance(term, str) and len(term.strip()) >= 2
        }
        
        logger.info(f"Topic '{topic}' expanded to {len(final_terms)} terms")
        return final_terms
    
    def add_custom_seed_terms(self, topic: str, terms: Set[str]):
        """
        Aggiunge termini personalizzati al dizionario seed
        """
        topic_normalized = topic.lower().strip()
        if topic_normalized not in _MEDICAL_SEED_TERMS:
            _MEDICAL_SEED_TERMS[topic_normalized] = set()
        
        _MEDICAL_SEED_TERMS[topic_normalized].update(terms)
        logger.info(f"Added {len(terms)} custom terms for topic '{topic}'")
    
    def get_available_topics(self) -> List[str]:
        """
        Ritorna la lista dei topic disponibili nel dizionario seed
        """
        return list(_MEDICAL_SEED_TERMS.keys())