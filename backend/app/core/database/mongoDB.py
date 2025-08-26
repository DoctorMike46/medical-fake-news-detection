from pymongo import MongoClient
import logging
from pymongo import ASCENDING, TEXT
from pymongo import UpdateOne

logging.basicConfig(level=logging.INFO)

class MongoDBManager:
    def __init__(self, uri, db_name):
        try:
            self.client = MongoClient(uri)
            self.db = self.client[db_name]
            logging.info(f"Connesso a MongoDB: {db_name}")
        except Exception as e:
            logging.error(f"Errore nella connessione a MongoDB: {e}")
            raise

    def insert_posts(self, collection_name, posts):
        if not posts:
            return 0
        try:
            result = self.db[collection_name].insert_many(posts)
            logging.info(f"Inseriti {len(result.inserted_ids)} documenti nella collezione '{collection_name}'.")
            return len(result.inserted_ids)
        except Exception as e:
            logging.error(f"Errore nell'inserimento dei post in MongoDB: {e}")
            return 0

    def get_unprocessed_posts(self, collection_name, limit=100):
        try:
            return list(self.db[collection_name].find({"processed": False}).sort("created_at", 1).limit(limit))
        except Exception as e:
            logging.error(f"Errore nel recupero dei post non processati: {e}")
            return []

    def update_post_status(self, collection_name, post_original_id, updates):
        """Aggiorna lo stato di un post usando l'ID originale del social (non l'ObjectId di Mongo)."""
        try:
            result = self.db[collection_name].update_one({'id': post_original_id}, {'$set': updates})
            if result.modified_count > 0:
                logging.info(f"Post con ID '{post_original_id}' aggiornato.")
            else:
                logging.warning(f"Nessun documento trovato/modificato per ID '{post_original_id}'.")
            return result.modified_count
        except Exception as e:
            logging.error(f"Errore nell'aggiornamento del post {post_original_id}: {e}")
            return 0

    def get_analyzed_posts(self, collection_name, limit=20, offset=0):
        """Recupera i post analizzati per la visualizzazione."""
        try:
            return list(self.db[collection_name].find({"processed": True, "analysis_status": "completed"})
                            .sort("last_processed_at", -1)
                            .skip(offset).limit(limit))
        except Exception as e:
            logging.error(f"Errore nel recupero dei post analizzati: {e}")
            return []

    def close(self):
        self.client.close()
        logging.info("Connessione MongoDB chiusa.")