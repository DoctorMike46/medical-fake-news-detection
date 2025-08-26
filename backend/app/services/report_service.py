import logging
from datetime import datetime
from bson import ObjectId
from flask import current_app


class ReportService:
    
    @staticmethod
    def manage_report_note(user_id, campaign_id, method, note_content=None):
        """Gestisce le note dei report (GET/POST)"""
        report_notes_collection = current_app.mongo_manager.db.report_notes

        # Verifica che la campagna esista e appartenga all'utente
        campaign_doc = current_app.mongo_manager.db.campaigns.find_one({
            "_id": ObjectId(campaign_id), 
            "user_id": user_id
        })
        if not campaign_doc:
            return {"message": "Campagna non trovata per questo utente."}, 404

        if method == 'POST':
            if not isinstance(note_content, str):
                return {"message": "Il contenuto della nota deve essere una stringa."}, 400

            try:
                result = report_notes_collection.update_one(
                    {
                        "user_id": user_id,
                        "campaign_id": campaign_id
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
                    logging.info(f"Nota report creata per campagna {campaign_id}.")
                    return {
                        "message": "Nota report salvata con successo!", 
                        "note": note_content, 
                        "action": "created"
                    }, 201
                elif result.modified_count > 0:
                    logging.info(f"Nota report aggiornata per campagna {campaign_id}.")
                    return {
                        "message": "Nota report aggiornata con successo!", 
                        "note": note_content, 
                        "action": "updated"
                    }, 200
                else:
                    return {
                        "message": "Nessuna modifica apportata alla nota report.", 
                        "note": note_content, 
                        "action": "no_change"
                    }, 200

            except Exception as e:
                logging.error(f"Errore durante il salvataggio/aggiornamento nota report: {e}", exc_info=True)
                return {
                    "message": "Errore interno del server durante il salvataggio della nota report.", 
                    "details": str(e)
                }, 500

        elif method == 'GET':
            try:
                note_doc = report_notes_collection.find_one({
                    "user_id": user_id,
                    "campaign_id": campaign_id
                })
                if note_doc:
                    return {"note": note_doc.get("note_content", "")}, 200
                else:
                    return {"note": ""}, 200
            except Exception as e:
                logging.error(f"Errore durante il recupero nota report: {e}", exc_info=True)
                return {
                    "message": "Errore interno del server durante il recupero della nota report.", 
                    "details": str(e)
                }, 500

    @staticmethod
    def manage_ai_summary(user_id, campaign_id, method, summary_content=None):
        """Gestisce il riepilogo AI per una campagna (GET/POST)"""
        campaigns_collection = current_app.mongo_manager.db.campaigns

        # Verifica che la campagna esista e appartenga all'utente
        campaign_doc = campaigns_collection.find_one({
            "_id": ObjectId(campaign_id), 
            "user_id": user_id
        })
        if not campaign_doc:
            return {"message": "Campagna non trovata."}, 404

        if method == 'POST':
            if not isinstance(summary_content, str):
                return {"message": "Il contenuto del riepilogo deve essere una stringa."}, 400

            try:
                result = campaigns_collection.update_one(
                    {"_id": ObjectId(campaign_id)},
                    {"$set": {
                        "ai_report_summary": summary_content, 
                        "last_updated": datetime.now()
                    }}
                )
                
                if result.modified_count == 1:
                    logging.info(f"Riepilogo AI per campagna {campaign_id} salvato con successo.")
                    return {"message": "Riepilogo AI salvato con successo!"}, 200
                else:
                    return {"message": "Nessuna modifica apportata al riepilogo."}, 200
                    
            except Exception as e:
                logging.error(f"Errore durante il salvataggio del riepilogo AI: {e}", exc_info=True)
                return {"message": "Errore interno del server durante il salvataggio."}, 500

        elif method == 'GET':
            summary = campaign_doc.get("ai_report_summary", "")
            return {"summary": summary}, 200