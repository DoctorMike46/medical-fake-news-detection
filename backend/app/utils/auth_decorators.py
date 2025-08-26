from functools import wraps
from flask import request, jsonify, current_app
import jwt

def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            return jsonify({"message": "Token JWT mancante", "status": "error"}), 401

        try:
            data = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            current_user = data

            request.current_user = current_user

        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token JWT scaduto", "status": "error"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Token JWT non valido", "status": "error"}), 401
        except Exception as e:
            return jsonify({"message": f"Errore di autenticazione: {str(e)}", "status": "error"}), 401

        return f(*args, **kwargs)
    return decorated