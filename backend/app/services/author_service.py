import logging
import urllib.parse
from datetime import datetime
from bson import ObjectId
from flask import current_app
from app.utils.helpers import normalize_is_fake


class AuthorService:
    
    @staticmethod
    def save_author(user_id, data):
        """Salva o aggiorna un autore nel database"""
        name = data.get('name')
        check = data.get('check')
        campaign_id_str = data.get('campaign_id')
        total_posts = data.get('total_posts', 0)
        real_posts = data.get('real_posts', 0)
        fake_posts = data.get('fake_posts', 0)
        unknown_posts = data.get('unknown_posts', 0)

        if not all([name, check, campaign_id_str]):
            return {"message": "I campi 'name', 'check' e 'campaign_id' sono obbligatori."}, 400

        try:
            authors_collection = current_app.mongo_manager.db.authors
            
            author_doc = {
                "name": name,
                "user_id": user_id,
                "campaign_id": campaign_id_str,
                "check": check,
                "total_posts": total_posts,
                "real_posts": real_posts,
                "fake_posts": fake_posts,
                "unknown_posts": unknown_posts,
                "last_updated": datetime.now()
            }

            query_filter = {"name": name, "campaign_id": campaign_id_str, "user_id": user_id}

            result = authors_collection.update_one(
                query_filter,
                {"$set": author_doc},
                upsert=True
            )

            is_new_author = result.upserted_id is not None
            author_mongo_id = None
            message = ""
            status_code = 200

            if is_new_author:
                author_mongo_id = result.upserted_id
                message = "Autore creato con successo!"
                status_code = 201
            elif result.modified_count > 0:
                existing_author = authors_collection.find_one(query_filter)
                if existing_author:
                    author_mongo_id = existing_author['_id']
                message = "Autore aggiornato con successo!"
                status_code = 200
            else:
                existing_author = authors_collection.find_one(query_filter)
                if existing_author:
                    author_mongo_id = existing_author['_id']
                message = "Nessuna modifica apportata all'autore."
                status_code = 200

            if author_mongo_id is None:
                logging.error(f"Impossibile recuperare l'ID dell'autore dopo il salvataggio/aggiornamento per '{name}'.")
                return {
                    "message": "Errore interno: impossibile recuperare l'ID dell'autore.", 
                    "status": "error"
                }, 500

            response_author_doc = author_doc.copy()
            response_author_doc['campaign_id'] = campaign_id_str
            response_author_doc['last_updated'] = str(response_author_doc['last_updated'])
            response_author_doc['id'] = str(author_mongo_id)

            logging.info(f"Autore '{name}' (ID: {author_mongo_id}) per campagna '{campaign_id_str}' salvato/aggiornato.")
            return {
                "message": message,
                "author_id": str(author_mongo_id),
                "author": response_author_doc
            }, status_code

        except Exception as e:
            logging.error(f"Errore durante il salvataggio dell'autore: {e}", exc_info=True)
            return {
                "message": "Errore interno del server durante il salvataggio dell'autore.", 
                "details": str(e)
            }, 500

    @staticmethod
    def get_authors_by_campaign(user_id, campaign_id):
        """Recupera tutti gli autori per una campagna specifica"""
        try:
            authors_collection = current_app.mongo_manager.db.authors
            authors_cursor = authors_collection.find({"campaign_id": campaign_id, "user_id": user_id})

            authors_list = []
            for author in authors_cursor:
                author_data = {
                    "id": str(author["_id"]),
                    "name": author["name"],
                    "campaign_id": author["campaign_id"],
                    "check": author.get("check", "pending"),
                    "total_posts": author.get("total_posts", 0),
                    "real_posts": author.get("real_posts", 0),
                    "fake_posts": author.get("fake_posts", 0),
                    "unknown_posts": author.get("unknown_posts", 0),
                    "last_updated": author["last_updated"].isoformat() if "last_updated" in author else None
                }
                authors_list.append(author_data)

            if authors_list:
                logging.info(f"Recuperati {len(authors_list)} autori monitorati per la campagna {campaign_id}.")
                return {"authors": authors_list}, 200
            else:
                logging.info(f"Nessun autore monitorato trovato per la campagna {campaign_id}.")
                return {"authors": []}, 200

        except Exception as e:
            logging.error(f"Errore nel recupero degli autori per la campagna {campaign_id}: {e}", exc_info=True)
            return {"message": "Errore interno del server."}, 500

    @staticmethod
    def get_author_details(user_id, campaign_id, author_name_encoded):
        """Recupera i dettagli completi di un autore con i suoi post"""
        author_name = urllib.parse.unquote(author_name_encoded)

        try:
            authors_collection = current_app.mongo_manager.db.authors
            social_posts_collection = current_app.mongo_manager.db.social_posts

            author_doc = authors_collection.find_one({
                "name": author_name,
                "campaign_id": campaign_id,
                "user_id": user_id
            })

            if not author_doc:
                return {"message": "Autore non trovato per questa campagna o non autorizzato."}, 404

            author_posts_cursor = social_posts_collection.find({
                "campaign_id": campaign_id,
                "author_name": author_name
            }).sort("created_utc", -1)

            posts_list = []
            for post in author_posts_cursor:
                content = f"{post.get('title', '')} - {post.get('text', '')}" if post.get('title') else post.get('text', '')

                posts_list.append({
                    "id": str(post["_id"]),
                    "platform": post.get("source", "N/A"),
                    "content": content,
                    "url": post.get("url"),
                    "sentiment": post.get("analysis_results", {}).get("sentiment", "da valutare"),
                    "is_fake": normalize_is_fake(post),
                    "created_at": post.get("created_utc", datetime.now().isoformat()),
                    "stato_post": post.get("stato_post", "da verificare")
                })

            sentiment_counts = {}
            for p in posts_list:
                sentiment = p.get("sentiment", "da valutare")
                sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1

            author_details = {
                "id": str(author_doc["_id"]),
                "name": author_doc["name"],
                "bio": author_doc.get("bio", "Nessuna biografia disponibile."),
                "metrics": {
                    "totalPosts": author_doc.get("total_posts", 0),
                    "fakeNewsDetected": author_doc.get("fake_posts", 0),
                    "realPosts": author_doc.get("real_posts", 0),
                    "unknownPosts": author_doc.get("unknown_posts", 0),
                    "postsFlagged": author_doc.get("check", "pending")
                },
                "sentiment_data_aggregated": [
                    {"name": "Positivo", "value": sentiment_counts.get("positivo", 0)},
                    {"name": "Neutro", "value": sentiment_counts.get("neutro", 0)},
                    {"name": "Negativo", "value": sentiment_counts.get("negativo", 0)},
                    {"name": "Da Valutare", "value": sentiment_counts.get("da valutare", 0)}
                ],
                "posts": posts_list
            }

            logging.info(f"Dettagli autore '{author_name}' per campagna {campaign_id} recuperati.")
            return author_details, 200

        except Exception as e:
            logging.error(f"Errore nel recupero dettagli autore '{author_name}' per campagna {campaign_id}: {e}", exc_info=True)
            return {"message": "Errore interno del server."}, 500

    @staticmethod
    def manage_author_notes(user_id, campaign_id, author_id, method, note_content=None):
        """Gestisce le note degli autori (GET/POST)"""
        notes_collection = current_app.mongo_manager.db.author_notes

        author_doc = current_app.mongo_manager.db.authors.find_one({
            "_id": ObjectId(author_id), 
            "user_id": user_id, 
            "campaign_id": campaign_id
        })
        if not author_doc:
            return {"message": "Autore o campagna non trovata per questo utente."}, 404

        if method == 'POST':
            if not isinstance(note_content, str):
                return {"message": "Il contenuto della nota deve essere una stringa."}, 400

            try:
                result = notes_collection.update_one(
                    {
                        "user_id": user_id,
                        "campaign_id": campaign_id,
                        "author_id": author_id
                    },
                    {
                        "$set": {
                            "note_content": note_content,
                            "last_updated": datetime.now()
                        },
                        "$setOnInsert": {
                            "created_at": datetime.now()
                        }
                    },
                    upsert=True
                )
                
                if result.upserted_id:
                    logging.info(f"Nota creata per autore {author_id} in campagna {campaign_id}.")
                    return {
                        "message": "Nota salvata con successo!", 
                        "note": note_content, 
                        "action": "created"
                    }, 201
                elif result.modified_count > 0:
                    logging.info(f"Nota aggiornata per autore {author_id} in campagna {campaign_id}.")
                    return {
                        "message": "Nota aggiornata con successo!", 
                        "note": note_content, 
                        "action": "updated"
                    }, 200
                else:
                    return {
                        "message": "Nessuna modifica apportata alla nota.", 
                        "note": note_content, 
                        "action": "no_change"
                    }, 200

            except Exception as e:
                logging.error(f"Errore durante il salvataggio/aggiornamento nota: {e}", exc_info=True)
                return {
                    "message": "Errore interno del server durante il salvataggio della nota.", 
                    "details": str(e)
                }, 500

        elif method == 'GET':
            try:
                note_doc = notes_collection.find_one({
                    "user_id": user_id,
                    "campaign_id": campaign_id,
                    "author_id": author_id
                })
                if note_doc:
                    return {"note": note_doc.get("note_content", "")}, 200
                else:
                    return {"note": ""}, 200
            except Exception as e:
                logging.error(f"Errore durante il recupero nota: {e}", exc_info=True)
                return {
                    "message": "Errore interno del server durante il recupero della nota.", 
                    "details": str(e)
                }, 500

    @staticmethod
    def perform_author_action(user_id, campaign_id, author_id, action_type):
        """Esegue un'azione su un autore (alert, flag, monitor, etc.)"""
        authors_collection = current_app.mongo_manager.db.authors

        if not action_type or not isinstance(action_type, str):
            return {"message": "Tipo di azione non specificato o non valido."}, 400

        allowed_actions = {
            'alert': 'alerted',
            'flag': 'flagged_suspicious',
            'monitor': 'monitoring_active',
            'resolve': 'resolved',
            'pending': 'pending'
        }

        new_check_status = allowed_actions.get(action_type)

        if not new_check_status:
            return {"message": f"Azione '{action_type}' non riconosciuta."}, 400

        try:
            result = authors_collection.update_one(
                {
                    "_id": ObjectId(author_id),
                    "user_id": user_id,
                    "campaign_id": campaign_id
                },
                {
                    "$set": {
                        "check": new_check_status,
                        "last_updated": datetime.now()
                    }
                }
            )

            if result.modified_count == 1:
                logging.info(f"Autore {author_id} in campagna {campaign_id} aggiornato con stato: {new_check_status}")
                return {
                    "message": f"Autore aggiornato a '{new_check_status}' con successo!",
                    "author_id": author_id,
                    "new_status": new_check_status
                }, 200
            else:
                return {"message": "Autore non trovato o stato già impostato."}, 404

        except Exception as e:
            logging.error(f"Errore durante l'azione '{action_type}' per autore {author_id}: {e}", exc_info=True)
            return {
                "message": "Errore interno del server durante l'esecuzione dell'azione.", 
                "details": str(e)
            }, 500