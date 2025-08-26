from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from app.services.campaign_service import CampaignService
from app.utils.auth_decorators import jwt_required

campaigns_bp = Blueprint('campaigns', __name__)


@campaigns_bp.route('', methods=['POST'])
@jwt_required
def create_campaign():
    """Crea una nuova campagna di monitoraggio"""
    user_id = request.current_user['user_id']
    data = request.get_json(force=True)
    
    result, status_code = CampaignService.create_campaign(user_id, data)
    return jsonify(result), status_code


@campaigns_bp.route('', methods=['GET'])
@jwt_required
def get_user_campaigns():
    """Recupera tutte le campagne dell'utente"""
    user_id = request.current_user['user_id']
    
    result, status_code = CampaignService.get_user_campaigns(user_id)
    return jsonify(result), status_code


@campaigns_bp.route('/<campaign_id>', methods=['PUT'])
@cross_origin(supports_credentials=True, headers=['Content-Type', 'Authorization'])
@jwt_required
def update_campaign(campaign_id):
    """Aggiorna una campagna esistente"""
    user_id = request.current_user['user_id']
    data = request.get_json()
    
    result, status_code = CampaignService.update_campaign(user_id, campaign_id, data)
    return jsonify(result), status_code


@campaigns_bp.route('/<campaign_id>', methods=['DELETE'])
@cross_origin(supports_credentials=True, headers=['Content-Type', 'Authorization'])
@jwt_required
def delete_campaign(campaign_id):
    """Elimina una campagna"""
    user_id = request.current_user['user_id']
    
    result, status_code = CampaignService.delete_campaign(user_id, campaign_id)
    return jsonify(result), status_code


@campaigns_bp.route('/<campaign_id>/close', methods=['POST'])
@jwt_required
def close_campaign(campaign_id):
    """Chiude una campagna"""
    user_id = request.current_user['user_id']
    
    result, status_code = CampaignService.close_campaign(user_id, campaign_id)
    return jsonify(result), status_code


@campaigns_bp.route('/<campaign_id>/activate', methods=['POST'])
@jwt_required
def activate_campaign(campaign_id):
    """Attiva una campagna"""
    user_id = request.current_user['user_id']
    
    result, status_code = CampaignService.activate_campaign(user_id, campaign_id)
    return jsonify(result), status_code


@campaigns_bp.route('/<campaign_id>/analyzed_posts', methods=['GET'])
@jwt_required
def get_analyzed_posts_for_campaign(campaign_id):
    """Recupera tutti i post analizzati per una campagna"""
    result, status_code = CampaignService.get_analyzed_posts_for_campaign(campaign_id)
    return jsonify(result), status_code