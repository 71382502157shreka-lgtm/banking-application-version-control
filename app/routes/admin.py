from decimal import Decimal
from flask import Blueprint, render_template
from flask_login import login_required

from app.utils.decorators import roles_required
from app.models.user import User, Role
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.version import EntityVersion
from app.models.audit_log import AuditLog
from app.models.workflow_risk import RollbackRequest, RiskAssessment
from app.models.security_session import SecurityEvent, LoginSession
from app.services.audit_service import verify_audit_integrity

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@login_required
@roles_required(Role.ADMIN)
def dashboard():
    total_users = User.query.count()
    total_customers = User.query.filter_by(role=Role.CUSTOMER).count()
    total_employees = User.query.filter_by(role=Role.EMPLOYEE).count()
    total_accounts = Account.query.count()
    total_txns = Transaction.query.count()
    total_versions = EntityVersion.query.count()
    total_audit_logs = AuditLog.query.count()
    failed_logins = AuditLog.query.filter_by(action="FAILED_LOGIN").count()

    txns = Transaction.query.all()
    total_volume = sum((Decimal(str(t.amount)) for t in txns if t.status == 'COMPLETED'), Decimal("0.00"))

    recent_txns = Transaction.query.order_by(Transaction.created_at.desc()).limit(6).all()
    recent_versions = EntityVersion.query.order_by(EntityVersion.created_at.desc()).limit(6).all()
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(6).all()

    audit_report = verify_audit_integrity()

    return render_template(
        "admin/admin_dashboard.html",
        total_users=total_users,
        total_customers=total_customers,
        total_employees=total_employees,
        total_accounts=total_accounts,
        total_txns=total_txns,
        total_volume=total_volume,
        total_versions=total_versions,
        total_audit_logs=total_audit_logs,
        failed_logins=failed_logins,
        recent_txns=recent_txns,
        recent_versions=recent_versions,
        recent_logs=recent_logs,
        audit_report=audit_report,
    )


@admin_bp.route("/users")
@login_required
@roles_required(Role.ADMIN)
def manage_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/manage_users.html", users=users)


@admin_bp.route("/audit-logs")
@login_required
@roles_required(Role.ADMIN)
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(150).all()
    audit_report = verify_audit_integrity()
    return render_template("admin/admin_audit_logs.html", logs=logs, audit_report=audit_report)


@admin_bp.route("/version-history")
@login_required
@roles_required(Role.ADMIN)
def version_history():
    versions = EntityVersion.query.order_by(EntityVersion.created_at.desc()).limit(150).all()
    return render_template("admin/admin_version_history.html", versions=versions)


@admin_bp.route("/security-center")
@login_required
@roles_required(Role.ADMIN)
def security_center():
    audit_report = verify_audit_integrity()
    security_events = SecurityEvent.query.order_by(SecurityEvent.created_at.desc()).limit(100).all()
    active_sessions = LoginSession.query.filter_by(is_active=True).all()
    locked_users = User.query.filter(User.locked_until != None).all()
    failed_logins_count = AuditLog.query.filter_by(action="FAILED_LOGIN").count()

    return render_template(
        "admin/security_center.html",
        audit_report=audit_report,
        security_events=security_events,
        active_sessions=active_sessions,
        locked_users=locked_users,
        failed_logins_count=failed_logins_count,
    )


@admin_bp.route("/rollback-requests")
@login_required
@roles_required(Role.ADMIN)
def rollback_requests():
    requests_list = RollbackRequest.query.order_by(RollbackRequest.created_at.desc()).all()
    return render_template("admin/rollback_requests.html", requests=requests_list)


@admin_bp.route("/risk-center")
@login_required
@roles_required(Role.ADMIN, Role.EMPLOYEE)
def risk_center():
    assessments = RiskAssessment.query.order_by(RiskAssessment.created_at.desc()).limit(150).all()
    pending_reviews = Transaction.query.filter_by(status="BLOCKED_FOR_REVIEW").all()
    return render_template("admin/risk_center.html", assessments=assessments, pending_reviews=pending_reviews)


@admin_bp.route("/settings")
@login_required
@roles_required(Role.ADMIN)
def settings():
    return render_template("admin/system_settings.html")
