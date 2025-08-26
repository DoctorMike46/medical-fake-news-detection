import logging
from Bio import Entrez
import time
from app.core.config import Config

logging.basicConfig(level=logging.INFO)

class PubMedService:
    def __init__(self, email=Config.PUBMED_EMAIL, api_key=Config.ENTREZ_API_KEY):
        Entrez.email = email
        
        if api_key:
            Entrez.api_key = api_key
            logging.info("Chiave API Entrez configurata.")
            
        if not email or email == "tua.email@esempio.com":
            logging.warning("EMAIL non configurata per Entrez (PubMedService). La ricerca potrebbe fallire.")
            self.is_available = False
        else:
            self.is_available = True
            logging.info("PubMedService inizializzato e disponibile.")
            if not api_key:
                logging.warning("Chiave API Entrez non configurata. Le richieste sono limitate a 3/s.")

    def search_pubmed(self, query: str, max_results: int = 5):
        """
        Cerca articoli su PubMed basandosi su una query.
        Restituisce una lista di dizionari con informazioni chiave degli articoli.
        """
        if not self.is_available:
            logging.error("PubMedService non disponibile a causa di configurazione mancante.")
            return []
        
        if not query:
            return []

        try:
            logging.info(f"Avvio ricerca PubMed per la query: '{query}'")
            
            handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results)
            record = Entrez.read(handle)
            handle.close()
            
            idlist = record["IdList"]
            if not idlist:
                logging.info(f"Nessun risultato trovato su PubMed per la query: '{query}'")
                return []
            
            logging.info(f"Trovati {len(idlist)} articoli, recupero i dettagli.")

            handle = Entrez.efetch(db="pubmed", id=idlist, retmode="xml")
            papers = Entrez.read(handle)
            handle.close()

            results = []
            for paper in papers['PubmedArticle']:
                article = paper['MedlineCitation']['Article']
                
                title = article.get('ArticleTitle', 'N/A')
                abstract = ""
                if 'Abstract' in article and 'AbstractText' in article['Abstract']:
                    abstract = " ".join(article['Abstract']['AbstractText'])
                
                pmid = paper['MedlineCitation']['PMID']
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                
                authors = []
                if 'AuthorList' in article:
                    for author in article['AuthorList']:
                        author_name_parts = []
                        if 'LastName' in author:
                            author_name_parts.append(author['LastName'])
                        if 'ForeName' in author:
                            author_name_parts.append(author['ForeName'])
                        elif 'Initials' in author:
                            author_name_parts.append(author['Initials'])
                        if author_name_parts:
                            authors.append(" ".join(author_name_parts))
                
                publication_date = "N/A"
                if 'Journal' in article and 'JournalIssue' in article['Journal'] and 'PubDate' in article['Journal']['JournalIssue']:
                    pub_date = article['Journal']['JournalIssue']['PubDate']
                    if 'Year' in pub_date:
                        publication_date = pub_date['Year']
                        if 'Month' in pub_date:
                            publication_date += f" {pub_date['Month']}"
                        if 'Day' in pub_date:
                            publication_date += f" {pub_date['Day']}"
                
                results.append({
                    "title": str(title), 
                    "abstract": str(abstract),
                    "url": url,
                    "pmid": str(pmid),
                    "authors": authors,
                    "publication_date": publication_date
                })
            
            logging.info(f"Trovati {len(results)} articoli su PubMed per la query: '{query}'")
            return results

        except Exception as e:
            logging.error(f"Errore nella ricerca PubMed per query '{query}': {e}", exc_info=True)
            return []