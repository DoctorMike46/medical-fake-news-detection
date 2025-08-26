from app import create_app, mongo_manager
import logging

logging.basicConfig(level=logging.INFO)

app = create_app()

if __name__ == '__main__':
    try:
        app.mongo_manager.db.command('ping') 
        logging.info("Connessione a MongoDB verificata con successo.")
    except Exception as e:
        logging.error(f"Errore critico: Impossibile connettersi a MongoDB all'avvio: {e}")
        exit(1)

    logging.info("Avvio del server Flask...")
    app.run(debug=True, port=5000)