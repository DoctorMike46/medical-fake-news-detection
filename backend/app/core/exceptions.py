"""
Custom exceptions for the Medical Fake News Detection System
"""
from flask import jsonify
import logging


class BaseAPIException(Exception):
    """Base class for API exceptions"""
    status_code = 500
    message = "Internal server error"
    
    def __init__(self, message=None, status_code=None, payload=None):
        super().__init__()
        self.message = message or self.message
        self.status_code = status_code or self.status_code
        self.payload = payload

    def to_dict(self):
        result = {"message": self.message, "status": "error"}
        if self.payload:
            result.update(self.payload)
        return result


class ValidationError(BaseAPIException):
    """Raised when input validation fails"""
    status_code = 400
    message = "Validation error"


class AuthenticationError(BaseAPIException):
    """Raised when authentication fails"""
    status_code = 401
    message = "Authentication failed"


class AuthorizationError(BaseAPIException):
    """Raised when user lacks permissions"""
    status_code = 403
    message = "Access denied"


class NotFoundError(BaseAPIException):
    """Raised when resource is not found"""
    status_code = 404
    message = "Resource not found"


class ConflictError(BaseAPIException):
    """Raised when resource conflict occurs"""
    status_code = 409
    message = "Resource conflict"


class DatabaseError(BaseAPIException):
    """Raised when database operations fail"""
    status_code = 500
    message = "Database operation failed"


class ExternalAPIError(BaseAPIException):
    """Raised when external API calls fail"""
    status_code = 502
    message = "External service unavailable"


class RateLimitError(BaseAPIException):
    """Raised when rate limit is exceeded"""
    status_code = 429
    message = "Rate limit exceeded"


class ConfigurationError(BaseAPIException):
    """Raised when configuration is invalid"""
    status_code = 500
    message = "Configuration error"


def register_error_handlers(app):
    """Register global error handlers for the Flask app"""
    
    @app.errorhandler(BaseAPIException)
    def handle_api_exception(error):
        """Handle custom API exceptions"""
        logging.error(f"API Exception: {error.message}", exc_info=True)
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response
    
    @app.errorhandler(400)
    def handle_bad_request(error):
        """Handle 400 Bad Request"""
        return jsonify({
            "message": "Bad request",
            "status": "error"
        }), 400
    
    @app.errorhandler(401)
    def handle_unauthorized(error):
        """Handle 401 Unauthorized"""
        return jsonify({
            "message": "Unauthorized access",
            "status": "error"
        }), 401
    
    @app.errorhandler(403)
    def handle_forbidden(error):
        """Handle 403 Forbidden"""
        return jsonify({
            "message": "Access forbidden",
            "status": "error"
        }), 403
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 Not Found"""
        return jsonify({
            "message": "Resource not found",
            "status": "error"
        }), 404
    
    @app.errorhandler(429)
    def handle_rate_limit(error):
        """Handle 429 Too Many Requests"""
        return jsonify({
            "message": "Rate limit exceeded. Please try again later.",
            "status": "error"
        }), 429
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        """Handle 500 Internal Server Error"""
        logging.error(f"Internal server error: {str(error)}", exc_info=True)
        return jsonify({
            "message": "Internal server error",
            "status": "error"
        }), 500
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle any unexpected errors"""
        logging.error(f"Unexpected error: {str(error)}", exc_info=True)
        return jsonify({
            "message": "An unexpected error occurred",
            "status": "error"
        }), 500


# Utility functions for common validations
def validate_required_fields(data, required_fields):
    """Validate that all required fields are present in data"""
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            payload={"missing_fields": missing_fields}
        )


def validate_email(email):
    """Basic email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError("Invalid email format")


def validate_password_strength(password):
    """Validate password meets minimum requirements"""
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long")
    
    if not any(c.isupper() for c in password):
        raise ValidationError("Password must contain at least one uppercase letter")
    
    if not any(c.islower() for c in password):
        raise ValidationError("Password must contain at least one lowercase letter")
    
    if not any(c.isdigit() for c in password):
        raise ValidationError("Password must contain at least one number")
