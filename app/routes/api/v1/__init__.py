from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db
from app.models import (
    Account, Transaction, Beneficiary, EntityVersion, AuditLog,
    LoginSession, RiskAssessment, RollbackRequest, RollbackStatus, Role
)
from app.services.audit_service import verify_audit_integrity, log_action
from app.services.version_service import search_versions, diff_versions, get_history
from app.services.fraud_service import evaluate_transaction_risk

api_v1_bp = Blueprint("api_v1", __name__)


@api_v1_bp.route("/status", methods=["GET"])
def status():
    return jsonify({
        "status": "online",
        "system": "BankVCS 2.0 – Secure Intelligent Banking & Database Version Control System",
        "api_version": "v1",
        "features": {
            "version_control": "Git-like snapshotting & side-by-side diffing",
            "audit_trail": "Tamper-evident SHA-256 hash chain",
            "risk_engine": "Transparent rule-based scoring (0-100)",
            "mfa_security": "OTP verification & active session tracking",
            "rbac": "Role-based portal isolation (Customer/Employee/Admin)"
        }
    })


# --- SESSION SECURITY ENDPOINTS ---
@api_v1_bp.route("/auth/sessions", methods=["GET"])
@login_required
def list_sessions():
    sessions = LoginSession.query.filter_by(user_id=current_user.id).order_by(LoginSession.login_at.desc()).all()
    return jsonify({"sessions": [s.to_dict() for s in sessions]})


@api_v1_bp.route("/auth/sessions/<int:session_id>/revoke", methods=["POST"])
@login_required
def revoke_session(session_id):
    sess = db.session.get(LoginSession, session_id)
    if not sess or sess.user_id != current_user.id:
        return jsonify({"error": "Session not found or unauthorized"}), 404
    sess.status = "REVOKED"
    db.session.commit()
    return jsonify({"message": "Session revoked successfully", "session_id": session_id})


# --- AUDIT HASH CHAIN VERIFICATION ---
@api_v1_bp.route("/audit/verify", methods=["GET", "POST"])
@login_required
def verify_audit():
    if current_user.role not in (Role.ADMIN, Role.EMPLOYEE):
        return jsonify({"error": "Unauthorized access to audit chain verification"}), 403

    result = verify_audit_integrity()
    log_action(
        action="ADMIN_ACTION",
        description=f"Audit chain verification executed by {current_user.username}: {result['message']}",
    )
    db.session.commit()
    return jsonify(result)


@api_v1_bp.route("/audit/logs", methods=["GET"])
@login_required
def get_audit_logs():
    if current_user.role not in (Role.ADMIN, Role.EMPLOYEE):
        return jsonify({"error": "Unauthorized"}), 403

    action = request.args.get("action")
    user_id = request.args.get("user_id", type=int)
    
    q = AuditLog.query
    if action:
        q = q.filter(AuditLog.action == action)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)

    logs = q.order_by(AuditLog.id.desc()).limit(100).all()
    return jsonify({"logs": [l.to_dict() for l in logs]})


# --- VERSION CONTROL ENDPOINTS ---
@api_v1_bp.route("/versions/history", methods=["GET"])
@login_required
def get_version_history():
    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id", type=int)

    if not entity_type or not entity_id:
        return jsonify({"error": "entity_type and entity_id parameters are required"}), 400

    history = get_history(entity_type, entity_id)
    return jsonify({"entity_type": entity_type, "entity_id": entity_id, "versions": [v.to_dict() for v in history]})


@api_v1_bp.route("/versions/diff", methods=["GET"])
@login_required
def get_version_diff():
    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id", type=int)
    va = request.args.get("version_a", type=int)
    vb = request.args.get("version_b", type=int)

    if not entity_type or not entity_id or not va or not vb:
        return jsonify({"error": "entity_type, entity_id, version_a, and version_b are required"}), 400

    try:
        diff = diff_versions(entity_type, entity_id, va, vb)
        return jsonify(diff)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@api_v1_bp.route("/versions/rollback/request", methods=["POST"])
@login_required
def create_rollback_request():
    data = request.get_json() or {}
    entity_type = data.get("entity_type")
    entity_id = data.get("entity_id")
    target_version = data.get("target_version_number")
    reason = data.get("reason")

    if not entity_type or not entity_id or not target_version or not reason:
        return jsonify({"error": "entity_type, entity_id, target_version_number, and reason are required"}), 400

    req = RollbackRequest(
        requested_by_id=current_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        target_version_number=target_version,
        reason=reason,
        status=RollbackStatus.PENDING,
    )
    db.session.add(req)
    log_action("ROLLBACK_REQUESTED", description=f"Rollback requested for {entity_type} #{entity_id} to v{target_version}: {reason}")
    db.session.commit()

    return jsonify({"message": "Rollback request submitted for Maker-Checker approval", "rollback_request": req.to_dict()}), 201


# --- RISK ENGINE ENDPOINTS ---
@api_v1_bp.route("/risk/assessments", methods=["GET"])
@login_required
def get_risk_assessments():
    if current_user.role not in (Role.ADMIN, Role.EMPLOYEE):
        return jsonify({"error": "Unauthorized"}), 403

    assessments = RiskAssessment.query.order_by(RiskAssessment.assessed_at.desc()).limit(50).all()
    return jsonify({"assessments": [a.to_dict() for a in assessments]})
