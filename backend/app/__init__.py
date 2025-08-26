import os
import logging
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from .core.config import Config
from .core.database.mongoDB import MongoDBManager
from .core.exceptions import register_error_handlers

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

load_dotenv()

mongo_manager = MongoDBManager(Config.MONGO_URI, Config.DB_NAME)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Validate critical configuration
    Config.validate_config()
    
    # More secure CORS configuration
    allowed_origins = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
    CORS(app, 
         origins=allowed_origins,
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
         allow_headers=['Content-Type', 'Authorization'],
         supports_credentials=True)

    # Register error handlers
    register_error_handlers(app)
    
    # Register blueprints
    register_blueprints(app)
    
    app.mongo_manager = mongo_manager

    return app

def register_blueprints(app):
    """Registra tutti i blueprint dell'applicazione"""
    try:
        from .api.auth.routes import auth_bp
        from .api.campaigns.routes import campaigns_bp
        from .api.posts.routes import posts_bp
        from .api.data_collection.routes import data_collection_bp
        from .api.analysis.routes import analysis_bp
        from .api.authors.routes import authors_bp
        from .api.reports.routes import reports_bp
        from .api.health.routes import health_bp
        
        # Registrazione blueprint
        app.register_blueprint(auth_bp, url_prefix='/api')
        app.register_blueprint(campaigns_bp, url_prefix='/api/campaigns')
        app.register_blueprint(posts_bp, url_prefix='/api/posts')
        app.register_blueprint(data_collection_bp, url_prefix='/api')
        app.register_blueprint(analysis_bp, url_prefix='/api/analysis')
        app.register_blueprint(authors_bp, url_prefix='/api')
        app.register_blueprint(reports_bp, url_prefix='/api')
        app.register_blueprint(health_bp, url_prefix='/')
        
    except ImportError as e:
        logging.error(f"❌ Errore import blueprint: {e}")
        # Register at least health check for Docker
        try:
            from .api.health.routes import health_bp
            app.register_blueprint(health_bp, url_prefix='/')
        except ImportError:
            pass