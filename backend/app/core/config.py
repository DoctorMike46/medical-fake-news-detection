import os
import secrets
from dotenv import load_dotenv

load_dotenv()

class Config:

    # MONGO DB
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/'
    DB_NAME = os.environ.get('DB_NAME') or 'fake_news_db'

    # JWT Configuration - CRITICAL: Always set JWT_SECRET_KEY in production
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or secrets.token_urlsafe(32)
    
    @classmethod
    def validate_config(cls):
        """Validate critical configuration values"""
        if not os.environ.get('JWT_SECRET_KEY'):
            import warnings
            warnings.warn(
                "JWT_SECRET_KEY not set in environment! Using generated key. "
                "This is insecure for production!", 
                UserWarning
            )

    # SOCIAL
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')

    TWITTER_BEARER_TOKEN = os.environ.get('TWITTER_BEARER_TOKEN')
    TWITTER_EMAIL = os.environ.get('TWITTER_EMAIL')
    TWITTER_PASSWORD = os.environ.get('TWITTER_PASSWORD')

    FACEBOOK_EMAIL = os.environ.get('FACEBOOK_EMAIL')
    FACEBOOK_PASSWORD = os.environ.get('FACEBOOK_PASSWORD')

    REDDIT_CLIENT_ID = os.environ.get('REDDIT_CLIENT_ID')
    REDDIT_CLIENT_SECRET = os.environ.get('REDDIT_CLIENT_SECRET')
    REDDIT_USER_AGENT = os.environ.get('REDDIT_USER_AGENT') or 'medical_fake_news_detector_v1'

    CROWDTANGLE_API_TOKEN = os.environ.get('CROWDTANGLE_API_TOKEN')

    # LLM
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL')
    CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
    CLAUDE_MODEL = os.getenv('CLAUDE_MODEL')
    GLM4_API_KEY = os.getenv('GLM4_API_KEY')
    GLM4_MODEL = os.getenv('GLM4_MODEL')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL')

    # Elasticsearch
    ES_HOST = os.environ.get('ES_HOST') or 'localhost'
    ES_PORT = int(os.environ.get('ES_PORT', 9200))
    ES_CLOUD_ID = os.environ.get('ES_CLOUD_ID')
    ES_API_KEY = os.environ.get('ES_API_KEY')
    ELASTIC_API_KEY = os.environ.get('ELASTIC_API_KEY')

    # PubMed
    PUBMED_EMAIL = os.environ.get('PUBMED_EMAIL')
    ENTREZ_API_KEY = os.environ.get('ENTREZ_API_KEY')

    # MetaMap
    METAMAP_UTS_API_KEY = os.environ.get('METAMAP_UTS_API_KEY') 
    METAMAP_UTS_USERNAME = os.environ.get('METAMAP_UTS_USERNAME') 
    METAMAP_UTS_PASSWORD = os.environ.get('METAMAP_UTS_PASSWORD') 