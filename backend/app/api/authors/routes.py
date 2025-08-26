from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from app.services.author_service import AuthorService
from app.utils.auth_decorators import jwt_required

authors_bp = Blueprint('authors', __name__)


@authors_bp.route('/author_check', methods=['POST'])
@jwt_required
def save_author():
    """Salva o aggiorna un autore nel database"""
    user_id = request.current_user['user_id']
    data = request.get_json()
    
    result, status_code = AuthorService.save_author(user_id, data)
    return jsonify(result), status_code


@authors_bp.route('/campaigns/<campaign_id>/authors', methods=['GET'])
@jwt_required
def get_authors_by_campaign_id(campaign_id):
    """Recupera una lista di autori per una specifica campagna"""
    user_id = request.current_user['user_id']
    
    result, status_code = AuthorService.get_authors_by_campaign(user_id, campaign_id)
    return jsonify(result), status_code


@authors_bp.route('/campaigns/<campaign_id>/authors/<author_name_encoded>', methods=['GET'])
@jwt_required
def get_author_details_for_campaign(campaign_id, author_name_encoded):
    """Recupera i dettagli di un autore specifico per una data campagna"""
    user_id = request.current_user['user_id']
    
    result, status_code = AuthorService.get_author_details(user_id, campaign_id, author_name_encoded)
    return jsonify(result), status_code


@authors_bp.route('/campaigns/<campaign_id>/authors/id/<author_id>/notes', methods=['GET', 'POST', 'OPTIONS'])
@cross_origin(supports_credentials=True, headers=['Content-Type', 'Authorization'])
@jwt_required
def manage_author_notes(campaign_id, author_id):
    """Gestisce le note degli autori (GET/POST)"""
    user_id = request.current_user['user_id']
    
    if request.method == 'POST':
        data = request.get_json()
        note_content = data.get('note')
        result, status_code = AuthorService.manage_author_notes(
            user_id, campaign_id, author_id, 'POST', note_content
        )
    else:
        result, status_code = AuthorService.manage_author_notes(
            user_id, campaign_id, author_id, 'GET'
        )
    
    return jsonify(result), status_code


@authors_bp.route('/campaigns/<campaign_id>/authors/id/<author_id>/actions', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True, headers=['Content-Type', 'Authorization'])
@jwt_required
def perform_author_action(campaign_id, author_id):
    """Esegue un'azione specificata dall'analista su un autore"""
    user_id = request.current_user['user_id']
    data = request.get_json()
    action_type = data.get('action')
    
    result, status_code = AuthorService.perform_author_action(
        user_id, campaign_id, author_id, action_type
    )
    return jsonify(result), status_code