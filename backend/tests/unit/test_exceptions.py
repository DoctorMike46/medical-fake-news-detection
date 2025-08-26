"""
Unit tests for custom exceptions and validation functions
"""
import pytest
from app.core.exceptions import (
    BaseAPIException,
    ValidationError,
    AuthenticationError,
    ConflictError,
    validate_required_fields,
    validate_email,
    validate_password_strength
)


class TestCustomExceptions:
    """Test custom exception classes"""
    
    def test_base_api_exception_default(self):
        """Test BaseAPIException with default values"""
        exc = BaseAPIException()
        
        assert exc.status_code == 500
        assert exc.message == "Internal server error"
        assert exc.payload is None
        
        result = exc.to_dict()
        assert result == {"message": "Internal server error", "status": "error"}
    
    def test_base_api_exception_custom(self):
        """Test BaseAPIException with custom values"""
        exc = BaseAPIException(
            message="Custom error",
            status_code=400,
            payload={"field": "value"}
        )
        
        assert exc.status_code == 400
        assert exc.message == "Custom error"
        assert exc.payload == {"field": "value"}
        
        result = exc.to_dict()
        expected = {
            "message": "Custom error",
            "status": "error",
            "field": "value"
        }
        assert result == expected
    
    def test_validation_error_defaults(self):
        """Test ValidationError default values"""
        exc = ValidationError()
        
        assert exc.status_code == 400
        assert exc.message == "Validation error"
    
    def test_authentication_error_defaults(self):
        """Test AuthenticationError default values"""
        exc = AuthenticationError()
        
        assert exc.status_code == 401
        assert exc.message == "Authentication failed"
    
    def test_conflict_error_defaults(self):
        """Test ConflictError default values"""
        exc = ConflictError()
        
        assert exc.status_code == 409
        assert exc.message == "Resource conflict"


class TestValidationFunctions:
    """Test validation utility functions"""
    
    def test_validate_required_fields_success(self):
        """Test validate_required_fields with valid data"""
        data = {
            'field1': 'value1',
            'field2': 'value2',
            'field3': 'value3'
        }
        required = ['field1', 'field2']
        
        # Should not raise exception
        validate_required_fields(data, required)
    
    def test_validate_required_fields_missing_single(self):
        """Test validate_required_fields with single missing field"""
        data = {
            'field1': 'value1',
            'field2': ''  # Empty string should be considered missing
        }
        required = ['field1', 'field2']
        
        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, required)
        
        assert "Missing required fields: field2" in str(exc_info.value.message)
        assert exc_info.value.payload == {"missing_fields": ["field2"]}
    
    def test_validate_required_fields_missing_multiple(self):
        """Test validate_required_fields with multiple missing fields"""
        data = {
            'field1': 'value1'
        }
        required = ['field1', 'field2', 'field3']
        
        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, required)
        
        assert "field2" in str(exc_info.value.message)
        assert "field3" in str(exc_info.value.message)
        assert set(exc_info.value.payload["missing_fields"]) == {"field2", "field3"}
    
    def test_validate_email_valid_emails(self):
        """Test validate_email with valid email addresses"""
        valid_emails = [
            'user@example.com',
            'test.email@domain.co.uk',
            'user123@test-domain.org',
            'user+tag@example.com'
        ]
        
        for email in valid_emails:
            # Should not raise exception
            validate_email(email)
    
    def test_validate_email_invalid_emails(self):
        """Test validate_email with invalid email addresses"""
        invalid_emails = [
            'not-an-email',
            '@example.com',
            'user@',
            'user.example.com',
            'user@domain',
            '',
            'user spaces@example.com'
        ]
        
        for email in invalid_emails:
            with pytest.raises(ValidationError) as exc_info:
                validate_email(email)
            
            assert "Invalid email format" in str(exc_info.value.message)
    
    def test_validate_password_strength_valid_passwords(self):
        """Test validate_password_strength with valid passwords"""
        valid_passwords = [
            'Password123',
            'MySecurePass1',
            'ComplexP@ssw0rd',
            'Minimum8'
        ]
        
        for password in valid_passwords:
            # Should not raise exception
            validate_password_strength(password)
    
    def test_validate_password_strength_too_short(self):
        """Test password validation with too short password"""
        with pytest.raises(ValidationError) as exc_info:
            validate_password_strength('Short1')
        
        assert "at least 8 characters long" in str(exc_info.value.message)
    
    def test_validate_password_strength_no_uppercase(self):
        """Test password validation without uppercase letter"""
        with pytest.raises(ValidationError) as exc_info:
            validate_password_strength('password123')
        
        assert "uppercase letter" in str(exc_info.value.message)
    
    def test_validate_password_strength_no_lowercase(self):
        """Test password validation without lowercase letter"""
        with pytest.raises(ValidationError) as exc_info:
            validate_password_strength('PASSWORD123')
        
        assert "lowercase letter" in str(exc_info.value.message)
    
    def test_validate_password_strength_no_number(self):
        """Test password validation without number"""
        with pytest.raises(ValidationError) as exc_info:
            validate_password_strength('PasswordOnly')
        
        assert "number" in str(exc_info.value.message)
    
    def test_validate_password_strength_multiple_issues(self):
        """Test password with multiple validation issues"""
        with pytest.raises(ValidationError):
            validate_password_strength('short')  # Too short, no uppercase, no number