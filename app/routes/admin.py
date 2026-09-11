from decimal import Decimal
from datetime import datetime
from flask import Blueprint, render_template, request
from flask_login import login_required

from app import db
from app.utils.decorators import roles_required
from app.models.user import User, Role
from app.models.account import Account, AccountStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.beneficiary import Beneficiary, BeneficiaryStatus
from app.models.version import EntityVersion
from app.models.audit_log import AuditLog
from app.models.workflow_risk import RollbackRequest, RiskAssessment
from app.models.security_session import SecurityEvent, LoginSession
from app.services.audit_service import verify_audit_integrity
from app.services import statement_service

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@roles_required(Role.ADMIN)
def root():
    from flask import redirect, url_for
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/dashboard")
@login_required
@roles_required(Role.ADMIN)
def dashboard():
    total_users = User.query.count()
    total_customers = User.query.filter_by(role=Role.CUSTOMER).count()
    total_employees = User.query.filter_by(role=Role.EMPLOYEE).count()

    total_accounts = Account.query.count()
    total_active_accounts = Account.query.filter_by(status=AccountStatus.ACTIVE).count()
    total_inactive_accounts = Account.query.filter(Account.status != AccountStatus.ACTIVE).count()

    total_txns = Transaction.query.count()
    total_successful_txns = Transaction.query.filter_by(status=TransactionStatus.COMPLETED).count()
    total_failed_txns = Transaction.query.filter(Transaction.status.in_([TransactionStatus.FAILED, "BLOCKED_FOR_REVIEW"])).count()

    all_completed_transfers = Transaction.query.filter_by(
        transaction_type=TransactionType.TRANSFER, status=TransactionStatus.COMPLETED
    ).all()
    total_transfer_amount = sum((Decimal(str(t.amount)) for t in all_completed_transfers), Decimal("0.00"))

    total_active_beneficiaries = Beneficiary.query.filter_by(status=BeneficiaryStatus.ACTIVE).count()

    total_versions = EntityVersion.query.count()
    total_audit_logs = AuditLog.query.count()
    failed_logins = AuditLog.query.filter_by(action="FAILED_LOGIN").count()

    all_txns = Transaction.query.all()
    total_volume = sum((Decimal(str(t.amount)) for t in all_txns if t.status == TransactionStatus.COMPLETED), Decimal("0.00"))

    # Chart 1: Status Distribution
    chart_status = {
        "completed": Transaction.query.filter_by(status=TransactionStatus.COMPLETED).count(),
        "pending": Transaction.query.filter_by(status=TransactionStatus.PENDING).count(),
        "blocked": Transaction.query.filter_by(status="BLOCKED_FOR_REVIEW").count(),
        "failed": Transaction.query.filter_by(status=TransactionStatus.FAILED).count(),
        "reversed": Transaction.query.filter_by(status=TransactionStatus.REVERSED).count(),
    }

    # Chart 2: Type Volume & Amount Summary
    chart_volume = {
        "transfer": float(sum((Decimal(str(t.amount)) for t in all_txns if t.transaction_type == TransactionType.TRANSFER and t.status == TransactionStatus.COMPLETED), Decimal("0.00"))),
        "deposit": float(sum((Decimal(str(t.amount)) for t in all_txns if t.transaction_type == TransactionType.DEPOSIT and t.status == TransactionStatus.COMPLETED), Decimal("0.00"))),
        "withdrawal": float(sum((Decimal(str(t.amount)) for t in all_txns if t.transaction_type == TransactionType.WITHDRAWAL and t.status == TransactionStatus.COMPLETED), Decimal("0.00"))),
    }

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
        total_active_accounts=total_active_accounts,
        total_inactive_accounts=total_inactive_accounts,
        total_txns=total_txns,
        total_successful_txns=total_successful_txns,
        total_failed_txns=total_failed_txns,
        total_transfer_amount=total_transfer_amount,
        total_active_beneficiaries=total_active_beneficiaries,
        total_volume=total_volume,
        total_versions=total_versions,
        total_audit_logs=total_audit_logs,
        failed_logins=failed_logins,
        chart_status=chart_status,
        chart_volume=chart_volume,
        recent_txns=recent_txns,
        recent_versions=recent_versions,
        recent_logs=recent_logs,
        audit_report=audit_report,
    )


@admin_bp.route("/users")
@login_required
@roles_required(Role.ADMIN)
def manage_users():
    search = request.args.get("search", "").strip()
    query = User.query

    if search:
        s_pattern = f"%{search}%"
        query = query.filter(
            (User.username.ilike(s_pattern)) |
            (User.email.ilike(s_pattern)) |
            (User.full_name.ilike(s_pattern)) |
            (User.phone.ilike(s_pattern))
        )

    users = query.order_by(User.created_at.desc()).all()
    return render_template("admin/manage_users.html", users=users, search=search)


@admin_bp.route("/transactions")
@login_required
@roles_required(Role.ADMIN)
def transactions():
    search = request.args.get("search", "").strip() or request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    type_filter = request.args.get("type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    page = request.args.get("page", 1, type=int)
    per_page = 15

    query = Transaction.query

    if search:
        s_pat = f"%{search}%"
        query = query.filter((Transaction.reference_number.ilike(s_pat)) | (Transaction.description.ilike(s_pat)))

    if status_filter:
        query = query.filter(Transaction.status == status_filter)

    if type_filter:
        query = query.filter(Transaction.transaction_type == type_filter)

    if date_from:
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Transaction.created_at >= d_from)
        except ValueError:
            pass

    if date_to:
        try:
            d_to = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(Transaction.created_at <= d_to)
        except ValueError:
            pass

    pagination = query.order_by(Transaction.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    # Attach account details and masked account numbers
    acc_cache = {}
    for tx in pagination.items:
        if tx.account_id not in acc_cache:
            acc_cache[tx.account_id] = db.session.get(Account, tx.account_id)
        if tx.counterparty_account_id and tx.counterparty_account_id not in acc_cache:
            acc_cache[tx.counterparty_account_id] = db.session.get(Account, tx.counterparty_account_id)

    txn_items = []
    for tx in pagination.items:
        sender_acc = acc_cache.get(tx.account_id)
        receiver_acc = acc_cache.get(tx.counterparty_account_id)

        sender_masked = statement_service.mask_account_number(sender_acc.account_number) if sender_acc else "N/A"
        receiver_masked = statement_service.mask_account_number(receiver_acc.account_number) if receiver_acc else "-"

        txn_items.append({
            "model": tx,
            "sender_masked": sender_masked,
            "receiver_masked": receiver_masked
        })

    return render_template(
        "admin/admin_transactions.html",
        txn_items=txn_items,
        pagination=pagination,
        search=search,
        status_filter=status_filter,
        type_filter=type_filter,
        date_from=date_from,
        date_to=date_to,
    )


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
@roles_required(Role.ADMIN)
def risk_center():
    assessments = RiskAssessment.query.order_by(RiskAssessment.created_at.desc()).limit(150).all()
    pending_reviews = Transaction.query.filter_by(status="BLOCKED_FOR_REVIEW").all()
    return render_template("admin/risk_center.html", assessments=assessments, pending_reviews=pending_reviews)


@admin_bp.route("/settings")
@login_required
@roles_required(Role.ADMIN)
def settings():
    return render_template("admin/system_settings.html")


@admin_bp.route("/customer-management")
@login_required
@roles_required(Role.ADMIN)
def customer_management():
    search = request.args.get("search", "").strip()
    query = User.query.filter_by(role=Role.CUSTOMER)

    if search:
        s_pattern = f"%{search}%"
        query = query.filter(
            (User.username.ilike(s_pattern)) |
            (User.email.ilike(s_pattern)) |
            (User.full_name.ilike(s_pattern)) |
            (User.phone.ilike(s_pattern))
        )

    customers = query.order_by(User.created_at.desc()).all()
    return render_template("admin/manage_users.html", users=customers, search=search)


@admin_bp.route("/approvals")
@login_required
@roles_required(Role.ADMIN)
def approvals():
    requests_list = RollbackRequest.query.order_by(RollbackRequest.created_at.desc()).all()
    return render_template("admin/rollback_requests.html", requests=requests_list)
