from flask import Blueprint, request, jsonify
from app.services.post_service import PostService
from app.utils.auth_decorators import jwt_required

posts_bp = Blueprint('posts', __name__)


@posts_bp.route('/<post_id>', methods=['GET'])
@jwt_required
def get_post_by_id(post_id):
    """Recupera un singolo post dal database"""
    result, status_code = PostService.get_post_by_id(post_id)
    return jsonify(result), status_code


@posts_bp.route('/analyzed', methods=['GET'])
@jwt_required
def get_analyzed_posts():
    """Recupera post analizzati con paginazione"""
    limit = int(request.args.get('limit', 20))
    offset = int(request.args.get('offset', 0))
    
    result, status_code = PostService.get_analyzed_posts(limit, offset)
    return jsonify(result), status_code


@posts_bp.route('/<post_id>/verify', methods=['POST'])
@jwt_required
def verify_post(post_id):
    """Marca un post come verificato"""
    user_id = request.current_user['user_id']
    
    result, status_code = PostService.verify_post(user_id, post_id)
    return jsonify(result), status_code


@posts_bp.route('/<post_id>/classify', methods=['POST'])
@jwt_required
def classify_post(post_id):
    """Classifica un post come fake/non fake"""
    user_id = request.current_user['user_id']
    data = request.get_json()
    is_fake_value = data.get('is_fake_value')
    
    result, status_code = PostService.classify_post(user_id, post_id, is_fake_value)
    return jsonify(result), status_code


@posts_bp.route('/<post_id>/classify_and_verify', methods=['POST'])
@jwt_required
def classify_and_verify_post(post_id):
    """Classifica un post con valutazione e motivazione dettagliate"""
    user_id = request.current_user['user_id']
    data = request.get_json()
    
    is_fake_value = data.get('is_fake_value')
    valutazione_testuale = data.get('valutazione_testuale')
    motivazione = data.get('motivazione')
    
    result, status_code = PostService.classify_and_verify_post(
        user_id, post_id, is_fake_value, valutazione_testuale, motivazione
    )
    return jsonify(result), status_code


@posts_bp.route('/<post_id>/reanalyze', methods=['POST'])
@jwt_required
def reanalyze_post(post_id):
    """Rilancia l'analisi completa di un singolo post"""
    result, status_code = PostService.reanalyze_post(post_id)
    return jsonify(result), status_code