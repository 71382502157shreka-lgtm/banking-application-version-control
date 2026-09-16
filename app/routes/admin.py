from decimal import Decimal
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app import db
from app.utils.decorators import roles_required
from app.models.user import User, Role
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.version import EntityVersion
from app.models.audit_log import AuditLog

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
    return render_template("admin/admin_audit_logs.html", logs=logs)


@admin_bp.route("/version-history")
@login_required
@roles_required(Role.ADMIN)
def version_history():
    versions = EntityVersion.query.order_by(EntityVersion.created_at.desc()).limit(150).all()
    return render_template("admin/admin_version_history.html", versions=versions)


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@roles_required(Role.ADMIN)
def settings():
    from flask import request, flash, current_app, redirect, url_for
    from app.services.audit_service import log_action

    if request.method == "POST":
        institution_name = request.form.get("institution_name", "BankVCS Digital Core").strip()
        daily_transfer_limit = request.form.get("daily_transfer_limit", "500000").strip()
        max_failed_logins = request.form.get("max_failed_logins", "5").strip()
        session_timeout = request.form.get("session_timeout", "30").strip()
        diff_engine = request.form.get("diff_engine", "Deep JSON State Diff")

        try:
            current_app.config["INSTITUTION_NAME"] = institution_name
            current_app.config["DAILY_TRANSFER_LIMIT"] = Decimal(daily_transfer_limit)
            current_app.config["MAX_FAILED_LOGIN_ATTEMPTS"] = int(max_failed_logins)
            current_app.config["SESSION_TIMEOUT_MINUTES"] = int(session_timeout)
            current_app.config["VERSION_DIFF_ENGINE"] = diff_engine

            log_action(
                "ADMIN_CONFIG_UPDATED",
                description=f"Admin {current_user.username} updated system config: limit=₹{daily_transfer_limit}, max_logins={max_failed_logins}, engine={diff_engine}"
            )
            db.session.commit()
            flash("System configuration updated and administrative audit logged successfully!", "success")
        except Exception as e:
            flash(f"Error saving system configuration: {str(e)}", "danger")

        return redirect(url_for("admin.settings"))

    return render_template("admin/system_settings.html")


@admin_bp.route("/users/<int:user_id>/toggle-status", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
def toggle_user_status(user_id):
    from flask import flash, redirect, url_for
    from app.services.audit_service import log_action
    from app.services.version_service import create_version, EntityType, ChangeType

    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin.manage_users"))

    if user.id == current_user.id:
        flash("You cannot disable your own admin account.", "warning")
        return redirect(url_for("admin.manage_users"))

    old_data = user.to_dict()
    user.status = "disabled" if user.status == "active" else "active"
    new_data = user.to_dict()

    action_name = "ADMIN_USER_DEACTIVATED" if user.status == "disabled" else "ADMIN_USER_ACTIVATED"
    log_action(action_name, description=f"Admin {current_user.username} changed status for user #{user.id} (@{user.username}) to {user.status.upper()}")
    
    create_version(
        entity_type=EntityType.USER_PROFILE,
        entity_id=user.id,
        change_type=ChangeType.UPDATE,
        old_data=old_data,
        new_data=new_data,
        changed_by=current_user.id,
        change_summary=f"User @{user.username} status set to {user.status.upper()}",
        audit_action=action_name
    )

    db.session.commit()

    flash(f"User @{user.username} status updated to '{user.status.upper()}' and version snapshot recorded.", "success")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route("/users/<int:user_id>/unlock", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
def unlock_user(user_id):
    from flask import flash, redirect, url_for
    from app.services.audit_service import log_action
    from app.services.version_service import create_version, EntityType, ChangeType

    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin.manage_users"))

    old_data = user.to_dict()
    user.locked_until = None
    user.failed_login_attempts = 0
    new_data = user.to_dict()

    log_action("ADMIN_USER_UNLOCKED", description=f"Admin {current_user.username} unlocked account for user #{user.id} (@{user.username})")
    
    create_version(
        entity_type=EntityType.USER_PROFILE,
        entity_id=user.id,
        change_type=ChangeType.UPDATE,
        old_data=old_data,
        new_data=new_data,
        changed_by=current_user.id,
        change_summary=f"User @{user.username} account unlocked by Admin",
        audit_action="ADMIN_USER_UNLOCKED"
    )

    db.session.commit()

    flash(f"User @{user.username} account unlocked successfully!", "success")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route("/security")
@login_required
@roles_required(Role.ADMIN)
def security_center():
    from app.services.audit_service import verify_audit_integrity
    audit_verification = verify_audit_integrity()
    failed_logins = AuditLog.query.filter_by(action="FAILED_LOGIN").count()
    locked_users = User.query.filter(User.locked_until.isnot(None)).count()
    recent_events = AuditLog.query.filter(AuditLog.action.in_(["SECURITY_EVENT", "FAILED_LOGIN", "LOGIN", "OTP_FAILED", "RISK_EVALUATED"])).order_by(AuditLog.created_at.desc()).limit(20).all()

    return render_template(
        "admin/security_center.html",
        audit_verification=audit_verification,
        failed_logins=failed_logins,
        locked_users=locked_users,
        recent_events=recent_events,
    )


@admin_bp.route("/analytics")
@login_required
@roles_required(Role.ADMIN)
def analytics():
    from app.models.risk_assessment import RiskAssessment
    total_users = User.query.count()
    total_txns = Transaction.query.count()
    risk_evals = RiskAssessment.query.count()
    high_risk_count = RiskAssessment.query.filter(RiskAssessment.risk_score >= 60).count()

    return render_template(
        "admin/analytics.html",
        total_users=total_users,
        total_txns=total_txns,
        risk_evals=risk_evals,
        high_risk_count=high_risk_count,
    )


@admin_bp.route("/rollback-requests")
@login_required
@roles_required(Role.ADMIN)
def rollback_requests():
    from app.models.rollback_request import RollbackRequest
    requests_list = RollbackRequest.query.order_by(RollbackRequest.created_at.desc()).all()
    return render_template("admin/rollback_requests.html", rollback_requests=requests_list)


@admin_bp.route("/rollback-requests/<int:req_id>/approve", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
def approve_rollback(req_id):
    from flask import redirect, url_for, flash
    from datetime import datetime
    from app.models.rollback_request import RollbackRequest, RollbackStatus
    from app.services.version_service import get_version, create_version, ChangeType
    from app.models.account import Account
    from app.models.beneficiary import Beneficiary
    from app.models.version import EntityType
    from app.services.audit_service import log_action

    req = db.session.get(RollbackRequest, req_id)
    if not req or req.status != RollbackStatus.PENDING:
        flash("Rollback request is invalid or already processed.", "danger")
        return redirect(url_for("admin.rollback_requests"))

    target_ver = get_version(req.entity_type, req.entity_id, req.target_version_number)
    if not target_ver or not target_ver.new_data:
        flash("Target snapshot data not found.", "danger")
        return redirect(url_for("admin.rollback_requests"))

    # Apply restore to entity
    if req.entity_type == EntityType.ACCOUNT:
        acc = db.session.get(Account, req.entity_id)
        if acc:
            old_data = acc.to_dict()
            acc.account_type = target_ver.new_data.get("account_type", acc.account_type)
            acc.status = target_ver.new_data.get("status", acc.status)
            create_version(EntityType.ACCOUNT, acc.id, ChangeType.RESTORE, old_data, acc.to_dict(), current_user.id, f"Maker-Checker Restored to v{target_ver.version_number}", reason=req.reason, restored_from_version=target_ver.version_number)
    elif req.entity_type == EntityType.BENEFICIARY:
        ben = db.session.get(Beneficiary, req.entity_id)
        if ben:
            old_data = ben.to_dict()
            ben.nickname = target_ver.new_data.get("nickname", ben.nickname)
            ben.bank_name = target_ver.new_data.get("bank_name", ben.bank_name)
            create_version(EntityType.BENEFICIARY, ben.id, ChangeType.RESTORE, old_data, ben.to_dict(), current_user.id, f"Maker-Checker Restored to v{target_ver.version_number}", reason=req.reason, restored_from_version=target_ver.version_number)

    req.status = RollbackStatus.EXECUTED
    req.reviewed_by_id = current_user.id
    req.reviewed_at = datetime.utcnow()
    log_action("ROLLBACK_APPROVED", description=f"Admin {current_user.username} approved rollback request #{req.id}")
    db.session.commit()

    flash(f"Rollback request #{req.id} approved and executed successfully as a NEW version!", "success")
    return redirect(url_for("admin.rollback_requests"))


@admin_bp.route("/audit-logs/export/csv")
@login_required
@roles_required(Role.ADMIN)
def export_audit_logs_csv():
    import csv, io
    from datetime import datetime
    from flask import Response

    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(1000).all()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["BankVCS 2.0 - System Cryptographic Audit Trail Export"])
    writer.writerow(["Exported By Admin", f"{current_user.full_name} ({current_user.username})"])
    writer.writerow(["Generated At", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")])
    writer.writerow([])
    writer.writerow(["Audit ID", "Timestamp", "Action", "User ID", "Entity Type", "Entity ID", "Description", "IP Address", "Prev Hash", "Current Hash"])

    for l in logs:
        writer.writerow([
            l.id,
            l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else "",
            l.action,
            l.user_id or "System",
            l.entity_type or "",
            l.entity_id or "",
            l.description or "",
            l.ip_address or "127.0.0.1",
            l.previous_hash or "",
            l.current_hash or ""
        ])

    csv_data = output.getvalue()
    filename = f"BankVCS_System_Audit_Trail_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

