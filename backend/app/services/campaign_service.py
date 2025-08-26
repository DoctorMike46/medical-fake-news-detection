import logging
from datetime import datetime, timedelta
from bson import ObjectId
from flask import current_app
from app.api.validators.campaign_validation import validate_and_prepare_campaign_inputs
from app.services.data_collection.data_collection_service import DataCollectionService
from app.utils.helpers import normalize_is_fake


class CampaignService:
    
    @staticmethod
    def create_campaign(user_id, data):
        """Crea una nuova campagna di monitoraggio"""
        validation = validate_and_prepare_campaign_inputs(
            name=data.get("name"),
            keywords=data.get("keywords"),
            platforms=data.get("social_platforms")
        )
        
        if "errors" in validation:
            return {"status": "error", "errors": validation["errors"]}, 400
        
        name = validation["name"]
        keywords = validation["keywords"]
        platforms = validation["platforms"]

        try:
            start_date = datetime.now()
            campaign = {
                "user_id": user_id,
                "name": name,
                "start_date": start_date,
                "social_platforms": platforms,
                "keywords": keywords,
                "status": "active",
                "created_at": datetime.now(),
                "last_updated": datetime.now()
            }

            campaign_id = current_app.mongo_manager.db.campaigns.insert_one(campaign).inserted_id
            logging.info(f"Campagna '{name}' (ID: {campaign_id}) creata. Avvio raccolta per {platforms} con keywords: {keywords}.")

            try:
                for keyword in keywords:
                    for platform in platforms:
                        added = DataCollectionService.collect_posts_for_campaign(
                            query=keyword,
                            source=platform,
                            num_posts=50,
                            campaign_id=campaign_id,
                            mongo_manager=current_app.mongo_manager
                        )
                        logging.info(f"[collect] {platform} '{keyword}': inseriti {added} post")
                
                DataCollectionService.trigger_analysis_for_campaign(current_app.mongo_manager)
                logging.info("Raccolta e analisi avviate con successo.")
            except Exception as e:
                logging.error(f"Errore durante raccolta/analisi iniziale: {e}", exc_info=True)

            return {
                "message": "Campagna creata con successo! Raccolta e analisi avviate.",
                "campaign_id": str(campaign_id),
                "campaign": {
                    "name": name,
                    "start_date": start_date.isoformat(),
                    "social_platforms": platforms,
                    "keywords": keywords
                }
            }, 201

        except Exception as e:
            logging.error(f"Errore durante la creazione della campagna: {e}", exc_info=True)
            return {
                "message": "Errore interno del server durante la creazione della campagna.", 
                "details": str(e)
            }, 500

    @staticmethod
    def get_user_campaigns(user_id):
        """Recupera tutte le campagne di un utente"""
        try:
            campaigns_cursor = current_app.mongo_manager.db.campaigns.find({"user_id": user_id})
            
            campaigns_list = []
            for campaign in campaigns_cursor:
                campaign_data = {
                    "id": str(campaign["_id"]),
                    "name": campaign["name"],
                    "start_date": campaign["start_date"].isoformat(),
                    "social_platforms": campaign["social_platforms"],
                    "keywords": campaign["keywords"],
                    "status": campaign["status"],
                    "created_at": campaign["created_at"].isoformat(),
                    "last_updated": campaign["last_updated"].isoformat()
                }
                campaigns_list.append(campaign_data)
            
            logging.info(f"Recuperate {len(campaigns_list)} campagne per l'utente {user_id}.")
            return {"campaigns": campaigns_list}, 200

        except Exception as e:
            logging.error(f"Errore durante il recupero delle campagne utente: {e}", exc_info=True)
            return {
                "message": "Errore interno del server durante il recupero delle campagne.", 
                "details": str(e)
            }, 500

    @staticmethod
    def update_campaign(user_id, campaign_id, data):
        """Aggiorna una campagna esistente"""
        campaigns_collection = current_app.mongo_manager.db.campaigns

        if not data:
            return {"message": "Dati non forniti per l'aggiornamento."}, 400

        try:
            campaign = campaigns_collection.find_one({"_id": ObjectId(campaign_id)})
            
            if not campaign:
                return {"message": "Campagna non trovata."}, 404

            if str(campaign.get('user_id')) != user_id:
                return {"message": "Non autorizzato a modificare questa campagna."}, 403

            update_data = {"last_updated": datetime.now()}

            if 'name' in data:
                update_data['name'] = data['name']
            if 'duration' in data:
                update_data['duration_days'] = data['duration']
                update_data['end_date'] = campaign['start_date'] + timedelta(days=data['duration'])
            if 'social_platforms' in data:
                update_data['social_platforms'] = data['social_platforms']
            if 'keywords' in data:
                update_data['keywords'] = data['keywords']
            
            result = campaigns_collection.update_one(
                {"_id": ObjectId(campaign_id)},
                {"$set": update_data}
            )

            if result.modified_count == 1:
                return {
                    "message": "Campagna aggiornata con successo!", 
                    "updated_fields": update_data
                }, 200
            else:
                return {
                    "message": "Nessuna modifica apportata alla campagna o campagna non trovata."
                }, 200
                
        except Exception as e:
            logging.error(f"Errore durante la modifica della campagna: {e}", exc_info=True)
            return {
                "message": "Errore interno del server durante la modifica della campagna.", 
                "details": str(e)
            }, 500

    @staticmethod
    def delete_campaign(user_id, campaign_id):
        """Elimina una campagna e tutti i suoi post associati"""
        campaigns_collection = current_app.mongo_manager.db.campaigns
        
        try:
            campaign = campaigns_collection.find_one({"_id": ObjectId(campaign_id)})

            if not campaign:
                return {"message": "Campagna non trovata."}, 404
            
            if str(campaign.get('user_id')) != user_id:
                return {"message": "Non autorizzato a eliminare questa campagna."}, 403

            # Elimina i post associati
            social_posts_collection = current_app.mongo_manager.db.social_posts
            social_posts_collection.delete_many({"campaign_id": campaign_id})

            # Elimina la campagna
            result = campaigns_collection.delete_one({"_id": ObjectId(campaign_id)})

            if result.deleted_count == 1:
                return {"message": "Campagna eliminata con successo!"}, 200
            else:
                return {"message": "Campagna non trovata."}, 404
                
        except Exception as e:
            logging.error(f"Errore durante l'eliminazione della campagna: {e}", exc_info=True)
            return {
                "message": "Errore interno del server durante l'eliminazione della campagna.", 
                "details": str(e)
            }, 500

    @staticmethod
    def close_campaign(user_id, campaign_id):
        """Chiude una campagna impostando lo stato su 'closed'"""
        campaigns_collection = current_app.mongo_manager.db.campaigns

        try:
            campaign = campaigns_collection.find_one({"_id": ObjectId(campaign_id)})

            if not campaign:
                return {"message": "Campagna non trovata."}, 404
            
            if str(campaign.get('user_id')) != user_id:
                return {"message": "Non autorizzato a chiudere questa campagna."}, 403

            if campaign.get('status') == 'closed':
                return {"message": "La campagna è già chiusa."}, 200

            result = campaigns_collection.update_one(
                {"_id": ObjectId(campaign_id)},
                {"$set": {"status": "closed", "last_updated": datetime.now()}}
            )

            if result.modified_count == 1:
                logging.info(f"Campagna {campaign_id} chiusa con successo.")
                return {"message": "Campagna chiusa con successo!", "new_status": "closed"}, 200
            else:
                return {"message": "Impossibile chiudere la campagna."}, 500
                
        except Exception as e:
            logging.error(f"Errore durante la chiusura della campagna {campaign_id}: {e}", exc_info=True)
            return {
                "message": "Errore interno del server durante la chiusura della campagna.", 
                "details": str(e)
            }, 500

    @staticmethod
    def activate_campaign(user_id, campaign_id):
        """Attiva una campagna impostando lo stato su 'active'"""
        campaigns_collection = current_app.mongo_manager.db.campaigns

        try:
            campaign = campaigns_collection.find_one({"_id": ObjectId(campaign_id)})

            if not campaign:
                return {"message": "Campagna non trovata."}, 404
            
            if str(campaign.get('user_id')) != user_id:
                return {"message": "Non autorizzato a modificare questa campagna."}, 403

            if campaign.get('status') == 'active':
                return {"message": "La campagna è già attiva."}, 200

            result = campaigns_collection.update_one(
                {"_id": ObjectId(campaign_id)},
                {"$set": {"status": "active", "last_updated": datetime.now()}}
            )

            if result.modified_count == 1:
                logging.info(f"Campagna {campaign_id} attivata con successo.")
                return {"message": "Campagna attivata con successo!", "new_status": "active"}, 200
            else:
                return {"message": "Impossibile attivare la campagna."}, 500
                
        except Exception as e:
            logging.error(f"Errore durante l'attivazione della campagna {campaign_id}: {e}", exc_info=True)
            return {
                "message": "Errore interno del server durante l'attivazione della campagna.", 
                "details": str(e)
            }, 500

    @staticmethod
    def get_analyzed_posts_for_campaign(campaign_id):
        """Recupera tutti i post analizzati per una campagna specifica"""
        try:
            campaign = current_app.mongo_manager.db.campaigns.find_one({"_id": ObjectId(campaign_id)})
            if not campaign:
                return {"message": "Campagna non trovata."}, 404

            posts_query = {"campaign_id": campaign_id}
            posts = current_app.mongo_manager.db.social_posts.find(posts_query)
            
            posts_list = []
            for post in posts:
                content = f"{post.get('title', '')} - {post.get('text', '')}" if post.get('title') else post.get('text', '')

                post_data = {
                    "id": str(post["_id"]),
                    "platform": post.get("source", "N/A"),
                    "author": {
                        "name": post.get("author_name", "Anonimo"),
                        "is_verified": False 
                    },
                    "sentiment": post.get("analysis_results", {}).get("sentiment", 0),
                    "url": post.get("url"),
                    "score": post.get("score"),
                    "num_comments": post.get("num_comments"),
                    "analysis_results": post.get("analysis_results"),
                    "content": content,
                    "is_fake": normalize_is_fake(post),
                    "keyword": post.get("query", "N/A"),
                    "created_at": post.get("created_utc", datetime.now().isoformat()),
                    "stato_post": post.get("stato_post", "da verificare"),
                    "medical_concepts": post.get("medical_concepts", []), 
                    "pubmed_validation_results": post.get("analysis_results", {}).get("pubmed_validation", []) 
                }
                posts_list.append(post_data)
            
            return {
                "campaign": {
                    "id": str(campaign["_id"]),
                    "name": campaign["name"],
                    "keywords": campaign["keywords"],
                    "social_platforms": campaign["social_platforms"],
                    "status": campaign["status"],
                    "start_date": campaign["start_date"].isoformat() if "start_date" in campaign else None,
                },
                "posts": posts_list
            }, 200

        except Exception as e:
            logging.error(f"Errore durante il recupero dei post analizzati per la campagna {campaign_id}: {e}", exc_info=True)
            return {"message": "Errore interno del server."}, 500