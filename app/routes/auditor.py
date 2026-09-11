from decimal import Decimal
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from app.utils.decorators import roles_required
from app.models.user import User, Role
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.version import EntityVersion
from app.models.audit_log import AuditLog
from app.models.security_session import SecurityEvent
from app.models.workflow_risk import RiskAssessment
from app.services.audit_service import verify_audit_integrity

auditor_bp = Blueprint("auditor", __name__, url_prefix="/auditor")


@auditor_bp.route("/")
@login_required
@roles_required(Role.AUDITOR, Role.ADMIN)
def root():
    return redirect(url_for("auditor.dashboard"))


@auditor_bp.route("/dashboard")
@login_required
@roles_required(Role.AUDITOR, Role.ADMIN)
def dashboard():
    audit_report = verify_audit_integrity()
    integrity_ok = audit_report.get("valid", True)
    broken_id = audit_report.get("broken_record_id")

    total_audit_logs = AuditLog.query.count()
    total_txns = Transaction.query.count()
    total_versions = EntityVersion.query.count()
    high_risk_count = RiskAssessment.query.filter_by(decision="REVIEW_REQUIRED").count()
    recent_events = SecurityEvent.query.order_by(SecurityEvent.created_at.desc()).limit(10).all()
    recent_audits = AuditLog.query.order_by(AuditLog.id.desc()).limit(10).all()

    return render_template(
        "auditor/auditor_dashboard.html",
        integrity_ok=integrity_ok,
        broken_id=broken_id,
        total_audit_logs=total_audit_logs,
        total_txns=total_txns,
        total_versions=total_versions,
        high_risk_count=high_risk_count,
        recent_events=recent_events,
        recent_audits=recent_audits,
    )


@auditor_bp.route("/audit-ledger")
@login_required
@roles_required(Role.AUDITOR, Role.ADMIN)
def audit_ledger():
    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id")
    user_id = request.args.get("user_id")

    query = AuditLog.query

    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if entity_id:
        try:
            query = query.filter_by(entity_id=int(entity_id))
        except ValueError:
            pass
    if user_id:
        try:
            query = query.filter_by(user_id=int(user_id))
        except ValueError:
            pass

    logs = query.order_by(AuditLog.id.desc()).limit(200).all()

    audit_report = verify_audit_integrity()
    integrity_ok = audit_report.get("valid", True)
    broken_id = audit_report.get("broken_record_id")

    return render_template(
        "auditor/audit_ledger.html",
        logs=logs,
        integrity_ok=integrity_ok,
        broken_id=broken_id,
        entity_type=entity_type or "",
        entity_id=entity_id or "",
        user_id=user_id or "",
    )

