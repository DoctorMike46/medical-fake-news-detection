"""
Pytest configuration and shared fixtures for the test suite
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from app import create_app
from app.core.config import Config


@pytest.fixture
def app():
    """Create and configure a test app instance."""
    # Use in-memory MongoDB for testing
    test_config = {
        'TESTING': True,
        'MONGO_URI': 'mongodb://localhost:27017/',
        'DB_NAME': 'test_fake_news_db',
        'JWT_SECRET_KEY': 'test-secret-key-for-testing-only'
    }
    
    # Patch environment variables for testing
    with patch.dict(os.environ, test_config, clear=False):
        app = create_app()
        app.config.update(test_config)
        
        with app.app_context():
            yield app


@pytest.fixture
def client(app):
    """Create a test client for the Flask app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test runner for the Flask CLI."""
    return app.test_cli_runner()


@pytest.fixture
def auth_headers():
    """Create mock JWT token for authenticated requests."""
    import jwt
    from datetime import datetime, timedelta
    
    payload = {
        'user_id': 'test-user-123',
        'username': 'testuser',
        'exp': datetime.utcnow() + timedelta(hours=1)
    }
    token = jwt.encode(payload, 'test-secret-key-for-testing-only', algorithm='HS256')
    
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def mock_mongo_manager():
    """Mock MongoDB manager for unit tests."""
    mock_manager = MagicMock()
    mock_db = MagicMock()
    mock_manager.db = mock_db
    
    # Mock collections
    mock_db.users = MagicMock()
    mock_db.campaigns = MagicMock()
    mock_db.social_posts = MagicMock()
    
    return mock_manager


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'TestPassword123'
    }


@pytest.fixture
def sample_campaign_data():
    """Sample campaign data for testing."""
    return {
        'name': 'Test Campaign',
        'keywords': ['covid', 'vaccine'],
        'social_platforms': ['twitter', 'reddit'],
        'start_date': '2024-01-01',
        'end_date': '2024-12-31'
    }


@pytest.fixture
def sample_post_data():
    """Sample social media post for testing."""
    return {
        'id': 'test-post-123',
        'text': 'This is a test post about medical information',
        'platform': 'twitter',
        'author': 'testauthor',
        'created_at': '2024-01-01T12:00:00Z',
        'processed': False
    }


@pytest.fixture(autouse=True)
def cleanup_test_db(app):
    """Automatically cleanup test database after each test."""
    yield
    # Cleanup logic here if needed
    with app.app_context():
        # Clean up test data
        pass


class TestDataFactory:
    """Factory class for creating test data."""
    
    @staticmethod
    def create_user(**kwargs):
        """Create a test user with default values."""
        default_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'TestPassword123'
        }
        default_data.update(kwargs)
        return default_data
    
    @staticmethod
    def create_campaign(**kwargs):
        """Create a test campaign with default values."""
        default_data = {
            'name': 'Test Campaign',
            'keywords': ['test', 'medical'],
            'social_platforms': ['twitter'],
            'status': 'active'
        }
        default_data.update(kwargs)
        return default_data
    
    @staticmethod
    def create_post(**kwargs):
        """Create a test post with default values."""
        default_data = {
            'id': 'test-post-123',
            'text': 'Test medical post content',
            'platform': 'twitter',
            'author': 'testauthor',
            'processed': False
        }
        default_data.update(kwargs)
        return default_data


# Make factory available as fixture
@pytest.fixture
def factory():
    """Provide test data factory."""
    return TestDataFactory