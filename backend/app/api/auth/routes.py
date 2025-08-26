from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from app.services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST', 'OPTIONS'])
@cross_origin()
def register():
    """Endpoint per la registrazione di un nuovo utente"""
    if request.method == 'OPTIONS':
        return '', 200
        
    data = request.get_json()
    result, status_code = AuthService.register_user(data)
    return jsonify(result), status_code

@auth_bp.route('/login', methods=['POST', 'OPTIONS'])
@cross_origin()
def login():
    """Endpoint per il login di un utente esistente"""
    if request.method == 'OPTIONS':
        return '', 200
        
    data = request.get_json()
    result, status_code = AuthService.login_user(data)
    return jsonify(result), status_code