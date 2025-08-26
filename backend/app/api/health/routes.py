"""
Health check endpoints for monitoring and Docker health checks
"""
from flask import Blueprint, jsonify, current_app
from datetime import datetime
import psutil
import os

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    try:
        # Check database connection
        current_app.mongo_manager.db.command('ping')
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Get system metrics
    memory_usage = psutil.virtual_memory().percent
    cpu_usage = psutil.cpu_percent(interval=1)
    disk_usage = psutil.disk_usage('/').percent
    
    health_data = {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "checks": {
            "database": db_status,
            "api": "healthy"
        },
        "metrics": {
            "memory_usage_percent": memory_usage,
            "cpu_usage_percent": cpu_usage,
            "disk_usage_percent": disk_usage,
            "uptime_seconds": psutil.boot_time()
        }
    }
    
    status_code = 200 if health_data["status"] == "healthy" else 503
    return jsonify(health_data), status_code


@health_bp.route('/health/detailed', methods=['GET'])
def detailed_health_check():
    """Detailed health check with component status"""
    checks = {}
    overall_status = "healthy"
    
    # Database check
    try:
        result = current_app.mongo_manager.db.command('ping')
        checks['database'] = {
            "status": "healthy",
            "response_time_ms": result.get('ok', 0) * 1000,
            "details": "MongoDB connection successful"
        }
    except Exception as e:
        checks['database'] = {
            "status": "unhealthy",
            "error": str(e),
            "details": "MongoDB connection failed"
        }
        overall_status = "unhealthy"
    
    # Check disk space
    disk_free_gb = psutil.disk_usage('/').free / (1024**3)
    if disk_free_gb < 1:  # Less than 1GB free
        checks['disk_space'] = {
            "status": "warning",
            "free_gb": round(disk_free_gb, 2),
            "details": "Low disk space"
        }
        if overall_status == "healthy":
            overall_status = "warning"
    else:
        checks['disk_space'] = {
            "status": "healthy",
            "free_gb": round(disk_free_gb, 2)
        }
    
    # Check memory usage
    memory_percent = psutil.virtual_memory().percent
    if memory_percent > 90:
        checks['memory'] = {
            "status": "warning",
            "usage_percent": memory_percent,
            "details": "High memory usage"
        }
        if overall_status == "healthy":
            overall_status = "warning"
    else:
        checks['memory'] = {
            "status": "healthy",
            "usage_percent": memory_percent
        }
    
    # Environment checks
    required_env_vars = ['JWT_SECRET_KEY', 'MONGO_URI']
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    
    if missing_vars:
        checks['environment'] = {
            "status": "unhealthy",
            "missing_variables": missing_vars,
            "details": "Required environment variables missing"
        }
        overall_status = "unhealthy"
    else:
        checks['environment'] = {
            "status": "healthy",
            "details": "All required environment variables present"
        }
    
    health_data = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
        "system_info": {
            "python_version": f"{psutil.version_info.major}.{psutil.version_info.minor}.{psutil.version_info.micro}",
            "platform": os.uname().sysname if hasattr(os, 'uname') else 'Unknown',
            "process_id": os.getpid()
        }
    }
    
    status_code = 200 if overall_status in ["healthy", "warning"] else 503
    return jsonify(health_data), status_code


@health_bp.route('/health/ready', methods=['GET'])
def readiness_check():
    """Kubernetes readiness probe endpoint"""
    try:
        # Check if app can handle requests
        current_app.mongo_manager.db.command('ping')
        
        return jsonify({
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "not_ready",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 503


@health_bp.route('/health/live', methods=['GET'])
def liveness_check():
    """Kubernetes liveness probe endpoint"""
    return jsonify({
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }), 200