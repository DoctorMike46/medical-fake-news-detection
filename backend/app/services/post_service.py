import logging
from datetime import datetime
from bson import ObjectId
from flask import current_app
from app.services.analysis.analysis_orchestrator import AnalysisOrchestrator


class PostService:
    
    @staticmethod
    def get_post_by_id(post_id):
        """Recupera un singolo post dal database"""
        try:
            post_id_obj = ObjectId(post_id)
        except:
            return {"message": "ID del post non valido."}, 400

        try:
            posts_collection = current_app.mongo_manager.db.social_posts
            post = posts_collection.find_one({"_id": post_id_obj})

            if post:
                post['id'] = str(post.pop('_id'))
                post['stato_post'] = post.get('stato_post', 'da verificare')
                post['medical_concepts'] = post.get('medical_concepts', [])
                post['pubmed_validation_results'] = post.get('analysis_results', {}).get('pubmed_validation', [])
                return post, 200
            else:
                return {"message": "Post non trovato."}, 404

        except Exception as e:
            logging.error(f"Errore nel recupero del post con ID {post_id}: {e}", exc_info=True)
            return {"message": "Errore interno del server."}, 500

    @staticmethod
    def get_analyzed_posts(limit=20, offset=0):
        """Recupera post analizzati con paginazione"""
        try:
            posts = current_app.mongo_manager.get_analyzed_posts('social_posts', limit, offset)
            return posts, 200
        except Exception as e:
            logging.error(f"Errore nel recupero post analizzati: {e}", exc_info=True)
            return {"message": "Errore interno del server."}, 500

    @staticmethod
    def verify_post(user_id, post_id):
        """Marca un post come verificato"""
        posts_collection = current_app.mongo_manager.db.social_posts

        try:
            result = posts_collection.update_one(
                {"_id": ObjectId(post_id)},
                {"$set": {
                    "stato_post": "verificato", 
                    "last_verified_by": user_id, 
                    "verified_at": datetime.now()
                }}
            )

            if result.modified_count == 1:
                logging.info(f"Post {post_id} marcato come 'verificato' da utente {user_id}.")
                return {
                    "message": "Post marcato come verificato con successo!", 
                    "new_status": "verificato"
                }, 200
            else:
                return {
                    "message": "Impossibile marcare il post come verificato. Potrebbe non esistere o essere già verificato."
                }, 404
        except Exception as e:
            logging.error(f"Errore durante la verifica del post {post_id}: {e}", exc_info=True)
            return {
                "message": "Errore interno del server durante la verifica del post.", 
                "details": str(e)
            }, 500

    @staticmethod
    def classify_post(user_id, post_id, is_fake_value):
        """Classifica un post come fake/non fake"""
        posts_collection = current_app.mongo_manager.db.social_posts

        if is_fake_value not in [0, 2, 3]:
            return {"message": "Valore di classificazione non valido."}, 400

        try:
            result = posts_collection.update_one(
                {"_id": ObjectId(post_id)},
                {"$set": {
                    "analysis_results.grado_disinformazione": is_fake_value,
                    "stato_post": "verificato",
                    "last_classified_by": user_id,
                    "classified_at": datetime.now()
                }}
            )

            if result.modified_count == 1:
                logging.info(f"Post {post_id} classificato come '{is_fake_value}' e verificato da utente {user_id}.")
                return {
                    "message": "Post classificato e marcato come verificato con successo!", 
                    "new_is_fake_status": is_fake_value,
                    "new_verification_status": "verificato"
                }, 200
            else:
                return {
                    "message": "Impossibile classificare il post. Potrebbe non esistere o essere già classificato."
                }, 404
        except Exception as e:
            logging.error(f"Errore durante la classificazione del post {post_id}: {e}", exc_info=True)
            return {
                "message": "Errore interno del server durante la classificazione del post.", 
                "details": str(e)
            }, 500

    @staticmethod
    def classify_and_verify_post(user_id, post_id, is_fake_value, valutazione_testuale=None, motivazione=None):
        """Classifica un post con valutazione e motivazione dettagliate"""
        posts_collection = current_app.mongo_manager.db.social_posts

        if is_fake_value not in [0, 2, 3]:
            return {"message": "Valore di classificazione non valido."}, 400

        try:
            update_fields = {
                "analysis_results.grado_disinformazione": is_fake_value,
                "stato_post": "verificato",
                "last_classified_by": user_id,
                "classified_at": datetime.now(),
            }
            
            if valutazione_testuale is not None:
                update_fields["analysis_results.valutazione_testuale"] = valutazione_testuale
            if motivazione is not None:
                update_fields["analysis_results.motivazione"] = motivazione

            result = posts_collection.update_one(
                {"_id": ObjectId(post_id)},
                {"$set": update_fields}
            )

            if result.modified_count == 1:
                logging.info(f"Post {post_id} classificato come '{is_fake_value}' e verificato da utente {user_id}. Valutazione e motivazione aggiornate.")
                return {
                    "message": "Post classificato e marcato come verificato con successo!",
                    "new_is_fake_status": is_fake_value,
                    "new_verification_status": "verificato",
                    "new_valutazione_testuale": valutazione_testuale,
                    "new_motivazione": motivazione
                }, 200
            else:
                return {
                    "message": "Impossibile classificare il post. Potrebbe non esistere o essere già classificato."
                }, 404
        except Exception as e:
            logging.error(f"Errore durante la classificazione e verifica del post {post_id}: {e}", exc_info=True)
            return {
                "message": "Errore interno del server durante la classificazione del post.", 
                "details": str(e)
            }, 500

    @staticmethod
    def reanalyze_post(post_id):
        """Rilancia l'analisi completa di un singolo post"""
        try:
            try:
                post_id_obj = ObjectId(post_id)
            except:
                return {"message": "ID del post non valido."}, 400

            posts_collection = current_app.mongo_manager.db.social_posts
            post = posts_collection.find_one({"_id": post_id_obj})
            if not post:
                return {"message": "Post non trovato."}, 404

            # Esegui una nuova analisi sul singolo post
            orchestrator_instance = AnalysisOrchestrator(current_app.mongo_manager)
            orchestrator_instance.process_single_post(post)

            # Ricarica la versione aggiornata dal DB
            post_updated = posts_collection.find_one({"_id": post_id_obj})
            if not post_updated:
                return {"message": "Post non trovato dopo l'analisi."}, 404

            # Normalizza campi per output
            post_updated['id'] = str(post_updated.pop('_id'))
            post_updated['stato_post'] = post_updated.get('stato_post', 'da verificare')
            post_updated['medical_concepts'] = post_updated.get('medical_concepts', [])
            post_updated['pubmed_validation_results'] = post_updated.get('analysis_results', {}).get('pubmed_validation', [])

            return {
                "message": "Rianalisi completata.",
                "post": post_updated
            }, 200

        except Exception as e:
            logging.error(f"Errore nella rianalisi del post {post_id}: {e}", exc_info=True)
            return {
                "message": "Errore interno del server durante la rianalisi del post.", 
                "details": str(e)
            }, 500