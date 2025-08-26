from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from app.services.report_service import ReportService
from app.utils.auth_decorators import jwt_required

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/campaigns/<campaign_id>/report_note', methods=['GET', 'POST', 'OPTIONS'])
@cross_origin(supports_credentials=True, headers=['Content-Type', 'Authorization'])
@jwt_required
def manage_report_note(campaign_id):
    """Gestisce le note dei report (GET/POST)"""
    user_id = request.current_user['user_id']
    
    if request.method == 'POST':
        data = request.get_json()
        note_content = data.get('note')
        result, status_code = ReportService.manage_report_note(
            user_id, campaign_id, 'POST', note_content
        )
    else:  # GET
        result, status_code = ReportService.manage_report_note(
            user_id, campaign_id, 'GET'
        )
    
    return jsonify(result), status_code


@reports_bp.route('/campaigns/<campaign_id>/ai_summary', methods=['GET', 'POST', 'OPTIONS'])
@cross_origin(supports_credentials=True, headers=['Content-Type', 'Authorization'])
@jwt_required
def manage_ai_summary(campaign_id):
    """Gestisce il salvataggio e il recupero del riepilogo AI per una campagna"""
    user_id = request.current_user['user_id']
    
    if request.method == 'POST':
        data = request.get_json()
        summary_content = data.get('summary')
        result, status_code = ReportService.manage_ai_summary(
            user_id, campaign_id, 'POST', summary_content
        )
    else:  # GET
        result, status_code = ReportService.manage_ai_summary(
            user_id, campaign_id, 'GET'
        )
    
    return jsonify(result), status_code