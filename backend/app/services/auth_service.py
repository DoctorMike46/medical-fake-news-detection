import jwt
import logging
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from ..core.exceptions import (
    ValidationError, 
    ConflictError, 
    AuthenticationError,
    validate_required_fields,
    validate_email,
    validate_password_strength
)


class AuthService:
    
    @staticmethod
    def register_user(data):
        """Registra un nuovo utente"""
        try:
            # Validazione dei campi obbligatori
            validate_required_fields(data, ['username', 'email', 'password'])
            
            username = data.get('username').strip()
            email = data.get('email').strip().lower()
            password = data.get('password')
            
            # Validazione email
            validate_email(email)
            
            # Validazione forza password
            validate_password_strength(password)
            
            # Validazione username
            if len(username) < 3:
                raise ValidationError("Username must be at least 3 characters long")
            
            users_collection = current_app.mongo_manager.db.users

            # Verifica esistenza utente
            existing_user = users_collection.find_one({
                "$or": [{"username": username}, {"email": email}]
            })
            if existing_user:
                if existing_user.get('email') == email:
                    raise ConflictError("Email già registrata")
                else:
                    raise ConflictError("Username già registrato")

            # Crea utente
            hashed_password = generate_password_hash(password)
            user_id = users_collection.insert_one({
                "username": username,
                "email": email,
                "password": hashed_password,
                "created_at": datetime.now(),
                "is_active": True
            }).inserted_id

            return {
                "message": "Registrazione avvenuta con successo!", 
                "status": "success", 
                "user_id": str(user_id)
            }, 201
            
        except (ValidationError, ConflictError) as e:
            return {"message": e.message, "status": "error"}, e.status_code
        except Exception as e:
            logging.error(f"Error in register_user: {str(e)}", exc_info=True)
            return {
                "message": "Errore interno del server durante la registrazione",
                "status": "error"
            }, 500

    @staticmethod
    def login_user(data):
        """Autentica un utente esistente"""
        email_or_username = data.get('email')
        password = data.get('password')

        if not email_or_username or not password:
            return {
                "message": "Email/Username e password sono obbligatori", 
                "status": "error"
            }, 400

        users_collection = current_app.mongo_manager.db.users
        user = users_collection.find_one({
            "$or": [{"email": email_or_username}, {"username": email_or_username}]
        })

        if user and check_password_hash(user['password'], password):
            token_payload = {
                'user_id': str(user['_id']),
                'username': user['username'],
                'exp': datetime.now() + timedelta(hours=24)
            }
            token = jwt.encode(
                token_payload, 
                current_app.config['JWT_SECRET_KEY'], 
                algorithm='HS256'
            )

            return {
                "message": "Login avvenuto con successo!",
                "status": "success",
                "token": token,
                "user": {
                    "id": str(user['_id']),
                    "username": user['username'],
                    "email": user['email']
                }
            }, 200
        else:
            return {
                "message": "Credenziali non valide", 
                "status": "error"
            }, 401