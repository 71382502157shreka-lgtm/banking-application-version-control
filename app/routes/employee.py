import csv
import io
from datetime import datetime, date, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, request, flash, redirect, url_for, Response, jsonify
from flask_login import login_required, current_user

from app import db
from app.utils.decorators import roles_required
from app.models.user import User, Role
from app.models.account import Account, AccountStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.version import EntityVersion, EntityType
from app.models.audit_log import AuditLog, AuditAction
from app.models.security_session import SecurityEvent, LoginSession
from app.models.workflow_risk import RiskAssessment, RiskDecision, RiskLevel, RollbackRequest, RollbackStatus
from app.models.complaint import Complaint, ComplaintStatus, ComplaintPriority
from app.models.service_request import ServiceRequest, ServiceRequestStatus
from app.services import (
    banking_service,
    approval_service,
    version_service,
    audit_service,
    security_service,
    auth_service,
)
from app.utils.validators import ValidationError

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")


@employee_bp.route("/")
@login_required
@roles_required(Role.EMPLOYEE)
def root():
    return redirect(url_for("employee.dashboard"))


@employee_bp.route("/dashboard")
@login_required
@roles_required(Role.EMPLOYEE)
def dashboard():
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())

    total_customers = User.query.filter_by(role=Role.CUSTOMER).count()
    total_accounts = Account.query.count()
    
    today_txns = Transaction.query.filter(Transaction.created_at >= today_start).all()
    today_deposits = sum((t.amount for t in today_txns if t.transaction_type == TransactionType.DEPOSIT), Decimal("0.00"))
    today_withdrawals = sum((t.amount for t in today_txns if t.transaction_type == TransactionType.WITHDRAWAL), Decimal("0.00"))
    today_transfers = sum((t.amount for t in today_txns if t.transaction_type == TransactionType.TRANSFER), Decimal("0.00"))

    pending_txns = Transaction.query.filter_by(status=TransactionStatus.PENDING).count()
    pending_approvals = RollbackRequest.query.filter_by(status=RollbackStatus.PENDING).count()
    open_complaints = Complaint.query.filter(Complaint.status.in_([ComplaintStatus.OPEN, ComplaintStatus.IN_PROGRESS])).count()
    high_risk_txns = RiskAssessment.query.filter(RiskAssessment.risk_score >= 60).count()
    failed_login_events = SecurityEvent.query.filter(
        SecurityEvent.event_type.in_(["FAILED_LOGIN", "ACCOUNT_LOCKED"])
    ).count()

    # Work Queue Items
    work_queue_approvals = RollbackRequest.query.filter_by(status=RollbackStatus.PENDING).all()
    work_queue_risk = RiskAssessment.query.filter(
        RiskAssessment.risk_score >= 60, RiskAssessment.reviewed_by.is_(None)
    ).all()
    work_queue_complaints = Complaint.query.filter(
        Complaint.status.in_([ComplaintStatus.OPEN, ComplaintStatus.IN_PROGRESS])
    ).all()

    recent_txns = Transaction.query.order_by(Transaction.created_at.desc()).limit(8).all()
    recent_versions = EntityVersion.query.order_by(EntityVersion.created_at.desc()).limit(8).all()

    return render_template(
        "employee/employee_dashboard.html",
        total_customers=total_customers,
        total_accounts=total_accounts,
        today_deposits=today_deposits,
        today_withdrawals=today_withdrawals,
        today_transfers=today_transfers,
        pending_txns=pending_txns,
        pending_approvals=pending_approvals,
        open_complaints=open_complaints,
        high_risk_txns=high_risk_txns,
        failed_login_events=failed_login_events,
        work_queue_approvals=work_queue_approvals,
        work_queue_risk=work_queue_risk,
        work_queue_complaints=work_queue_complaints,
        recent_txns=recent_txns,
        recent_versions=recent_versions,
    )


@employee_bp.route("/customers")
@login_required
@roles_required(Role.EMPLOYEE)
def customers():
    search = request.args.get("q", "").strip()
    query = User.query.filter_by(role=Role.CUSTOMER)
    if search:
        query = query.filter(
            (User.username.ilike(f"%{search}%")) |
            (User.full_name.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%")) |
            (User.phone.ilike(f"%{search}%")) |
            (User.id.like(f"%{search}%"))
        )
    customer_list = query.order_by(User.created_at.desc()).all()
    return render_template("employee/customers.html", customers=customer_list, search=search)


@employee_bp.route("/customers/<int:user_id>")
@login_required
@roles_required(Role.EMPLOYEE)
def customer_detail(user_id):
    customer = User.query.get_or_404(user_id)
    if customer.role != Role.CUSTOMER:
        flash("Can only view customer profiles.", "error")
        return redirect(url_for("employee.customers"))

    accounts = Account.query.filter_by(user_id=customer.id).all()
    account_ids = [a.id for a in accounts]
    txns = Transaction.query.filter(Transaction.account_id.in_(account_ids)).order_by(Transaction.created_at.desc()).limit(20).all() if account_ids else []
    versions = EntityVersion.query.filter_by(changed_by=customer.id).order_by(EntityVersion.created_at.desc()).limit(20).all()
    complaints = Complaint.query.filter_by(customer_id=customer.id).order_by(Complaint.created_at.desc()).all()
    security_events = SecurityEvent.query.filter_by(user_id=customer.id).order_by(SecurityEvent.created_at.desc()).limit(15).all()

    audit_service.log_action(
        action=AuditAction.CUSTOMER_LOOKUP,
        user_id=current_user.id,
        entity_type="USER",
        entity_id=customer.id,
        description=f"Staff {current_user.username} viewed customer profile for {customer.username}"
    )

    return render_template(
        "employee/customer_detail.html",
        customer=customer,
        accounts=accounts,
        txns=txns,
        versions=versions,
        complaints=complaints,
        security_events=security_events,
    )


@employee_bp.route("/accounts/search")
@login_required
@roles_required(Role.EMPLOYEE)
def account_search():
    q = request.args.get("q", "").strip()
    accounts = []
    if q:
        accounts = Account.query.filter(
            (Account.account_number.ilike(f"%{q}%")) |
            (Account.user_id.like(f"%{q}%"))
        ).all()
    return render_template("employee/account_search.html", accounts=accounts, query=q)


@employee_bp.route("/banking/deposit", methods=["GET", "POST"])
@login_required
@roles_required(Role.EMPLOYEE)
def banking_deposit():
    if request.method == "POST":
        account_number = request.form.get("account_number", "").strip()
        amount_str = request.form.get("amount", "0")
        description = request.form.get("description", "Staff Cash Deposit").strip()

        acc = Account.query.filter_by(account_number=account_number).first()
        if not acc:
            flash("Account not found.", "error")
            return redirect(url_for("employee.banking_deposit"))

        try:
            amt = Decimal(amount_str)
            if amt <= 0:
                raise ValueError("Amount must be positive.")
            txn = banking_service.deposit(acc, amt, description, current_user.id)
            flash(f"Deposit of ₹{amt} into account {acc.account_number} completed successfully! Ref #{txn.reference_number}", "success")
            return redirect(url_for("employee.banking_deposit"))
        except Exception as e:
            flash(f"Deposit failed: {str(e)}", "error")
            return redirect(url_for("employee.banking_deposit"))

    all_accounts = Account.query.all()
    return render_template("employee/deposit.html", accounts=all_accounts)


@employee_bp.route("/banking/withdraw", methods=["GET", "POST"])
@login_required
@roles_required(Role.EMPLOYEE)
def banking_withdraw():
    if request.method == "POST":
        account_number = request.form.get("account_number", "").strip()
        amount_str = request.form.get("amount", "0")
        description = request.form.get("description", "Staff Counter Withdrawal").strip()

        acc = Account.query.filter_by(account_number=account_number).first()
        if not acc:
            flash("Account not found.", "error")
            return redirect(url_for("employee.banking_withdraw"))

        try:
            amt = Decimal(amount_str)
            if amt <= 0:
                raise ValueError("Amount must be positive.")
            txn = banking_service.withdraw(acc, amt, description, current_user.id)
            flash(f"Withdrawal of ₹{amt} from account {acc.account_number} completed successfully! Ref #{txn.reference_number}", "success")
            return redirect(url_for("employee.banking_withdraw"))
        except Exception as e:
            flash(f"Withdrawal failed: {str(e)}", "error")
            return redirect(url_for("employee.banking_withdraw"))

    all_accounts = Account.query.all()
    return render_template("employee/withdraw.html", accounts=all_accounts)


@employee_bp.route("/banking/transfer", methods=["GET", "POST"])
@login_required
@roles_required(Role.EMPLOYEE)
def banking_transfer():
    if request.method == "POST":
        source_account = request.form.get("source_account", "").strip()
        dest_account = request.form.get("dest_account", "").strip()
        amount_str = request.form.get("amount", "0")
        description = request.form.get("description", "Staff Initiated Transfer").strip()

        src_acc = Account.query.filter_by(account_number=source_account).first()
        dest_acc = Account.query.filter_by(account_number=dest_account).first()

        if not src_acc or not dest_acc:
            flash("Source or Destination Account not found.", "error")
            return redirect(url_for("employee.banking_transfer"))

        try:
            amt = Decimal(amount_str)
            if amt <= 0:
                raise ValueError("Amount must be positive.")
            txn = banking_service.transfer(src_acc, dest_acc, amt, description, current_user.id)
            flash(f"Transfer of ₹{amt} from {src_acc.account_number} to {dest_acc.account_number} completed! Ref #{txn.reference_number}", "success")
            return redirect(url_for("employee.banking_transfer"))
        except Exception as e:
            flash(f"Transfer failed: {str(e)}", "error")
            return redirect(url_for("employee.banking_transfer"))

    all_accounts = Account.query.all()
    return render_template("employee/transfer.html", accounts=all_accounts)


@employee_bp.route("/transactions")
@login_required
@roles_required(Role.EMPLOYEE)
def transactions():
    txn_type = request.args.get("type", "").strip()
    status = request.args.get("status", "").strip()
    q = request.args.get("q", "").strip()

    query = Transaction.query
    if txn_type:
        query = query.filter_by(transaction_type=txn_type)
    if status:
        query = query.filter_by(status=status)
    if q:
        query = query.filter(
            (Transaction.reference_number.ilike(f"%{q}%")) |
            (Transaction.description.ilike(f"%{q}%"))
        )

    txn_list = query.order_by(Transaction.created_at.desc()).limit(200).all()
    return render_template(
        "employee/employee_transactions.html",
        transactions=txn_list,
        selected_type=txn_type,
        selected_status=status,
        query=q,
    )


@employee_bp.route("/transactions/export")
@login_required
@roles_required(Role.EMPLOYEE)
def transactions_export():
    txns = Transaction.query.order_by(Transaction.created_at.desc()).limit(1000).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Reference", "Account ID", "Type", "Amount", "Balance After", "Status", "Description", "Date"])
    for t in txns:
        writer.writerow([t.id, t.reference_number, t.account_id, t.transaction_type, t.amount, t.balance_after, t.status, t.description, t.created_at])

    audit_service.log_action(
        action=AuditAction.REPORT_EXPORTED,
        user_id=current_user.id,
        description="Employee exported transactions CSV report"
    )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=employee_transactions_report.csv"}
    )


@employee_bp.route("/approvals", methods=["GET", "POST"])
@login_required
@roles_required(Role.EMPLOYEE)
def approvals():
    if request.method == "POST":
        request_id = request.form.get("request_id", type=int)
        action = request.form.get("action", "").strip()  # approve or reject
        notes = request.form.get("notes", "Reviewed by Staff").strip()

        try:
            req = RollbackRequest.query.get(request_id)
            if not req:
                flash("Rollback request not found.", "error")
                return redirect(url_for("employee.approvals"))

            if req.requested_by == current_user.id:
                flash("Maker-Checker Policy: You cannot approve or reject your own request.", "error")
                return redirect(url_for("employee.approvals"))

            if action == "approve":
                approval_service.approve_rollback_request(request_id, current_user.id, notes)
                flash(f"Rollback Request #{request_id} APPROVED and executed forwardly!", "success")
            elif action == "reject":
                approval_service.reject_rollback_request(request_id, current_user.id, notes)
                flash(f"Rollback Request #{request_id} REJECTED.", "info")
        except Exception as e:
            flash(f"Approval action failed: {str(e)}", "error")

        return redirect(url_for("employee.approvals"))

    pending_requests = RollbackRequest.query.filter_by(status=RollbackStatus.PENDING).all()
    history_requests = RollbackRequest.query.filter(RollbackRequest.status != RollbackStatus.PENDING).order_by(RollbackRequest.created_at.desc()).limit(50).all()

    return render_template(
        "employee/approvals.html",
        pending_requests=pending_requests,
        history_requests=history_requests,
    )


@employee_bp.route("/complaints", methods=["GET", "POST"])
@login_required
@roles_required(Role.EMPLOYEE)
def complaints():
    if request.method == "POST":
        complaint_id = request.form.get("complaint_id", type=int)
        status = request.form.get("status", "").strip()
        notes = request.form.get("internal_notes", "").strip()
        resolution = request.form.get("resolution", "").strip()

        comp = Complaint.query.get(complaint_id)
        if comp:
            if status:
                comp.status = status
            if notes:
                comp.internal_notes = (comp.internal_notes or "") + f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {current_user.username}: {notes}"
            if resolution:
                comp.resolution = resolution
            comp.assigned_employee_id = current_user.id
            db.session.commit()

            audit_service.log_action(
                action=AuditAction.ADMIN_ACTION,
                user_id=current_user.id,
                entity_type="COMPLAINT",
                entity_id=comp.id,
                description=f"Updated complaint #{comp.ticket_number} to {comp.status}"
            )
            flash(f"Complaint #{comp.ticket_number} updated.", "success")
        return redirect(url_for("employee.complaints"))

    status_filter = request.args.get("status", "")
    query = Complaint.query
    if status_filter:
        query = query.filter_by(status=status_filter)

    complaint_list = query.order_by(Complaint.created_at.desc()).all()
    return render_template("employee/complaints.html", complaints=complaint_list, selected_status=status_filter)


@employee_bp.route("/risk-alerts", methods=["GET", "POST"])
@login_required
@roles_required(Role.EMPLOYEE)
def risk_alerts():
    if request.method == "POST":
        assessment_id = request.form.get("assessment_id", type=int)
        action = request.form.get("action", "").strip()  # approve or block
        notes = request.form.get("review_notes", "").strip()

        try:
            approval_service.review_risk_assessment(assessment_id, current_user.id, approve=(action == "approve"), review_notes=notes)
            flash(f"Risk Assessment #{assessment_id} marked as {action.upper()}!", "success")
        except Exception as e:
            flash(f"Action failed: {str(e)}", "error")
        return redirect(url_for("employee.risk_alerts"))

    assessments = RiskAssessment.query.order_by(RiskAssessment.created_at.desc()).all()
    security_events = SecurityEvent.query.order_by(SecurityEvent.created_at.desc()).limit(50).all()
    return render_template("employee/risk_alerts.html", assessments=assessments, security_events=security_events)


@employee_bp.route("/audit-logs")
@login_required
@roles_required(Role.EMPLOYEE)
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return render_template("employee/audit_logs.html", logs=logs)


@employee_bp.route("/versions")
@login_required
@roles_required(Role.EMPLOYEE)
def versions():
    all_versions = EntityVersion.query.order_by(EntityVersion.created_at.desc()).limit(100).all()
    return render_template("employee/employee_versions.html", versions=all_versions)


@employee_bp.route("/reports")
@login_required
@roles_required(Role.EMPLOYEE)
def reports():
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())

    total_deposits = sum((t.amount for t in Transaction.query.filter(Transaction.transaction_type == TransactionType.DEPOSIT).all()), Decimal("0.00"))
    total_withdrawals = sum((t.amount for t in Transaction.query.filter(Transaction.transaction_type == TransactionType.WITHDRAWAL).all()), Decimal("0.00"))
    total_transfers = sum((t.amount for t in Transaction.query.filter(Transaction.transaction_type == TransactionType.TRANSFER).all()), Decimal("0.00"))
    total_txns = Transaction.query.count()

    recent_txns = Transaction.query.order_by(Transaction.created_at.desc()).limit(25).all()

    return render_template(
        "employee/reports.html",
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        total_transfers=total_transfers,
        total_txns=total_txns,
        recent_txns=recent_txns,
    )


@employee_bp.route("/reports/export")
@login_required
@roles_required(Role.EMPLOYEE)
def reports_export():
    txns = Transaction.query.order_by(Transaction.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Transaction ID", "Reference", "Account ID", "Type", "Amount", "Balance After", "Status", "Date"])
    for t in txns:
        writer.writerow([t.id, t.reference_number, t.account_id, t.transaction_type, t.amount, t.balance_after, t.status, t.created_at])

    audit_service.log_action(
        action=AuditAction.REPORT_EXPORTED,
        user_id=current_user.id,
        description="Employee downloaded full summary audit report"
    )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=bankvcs_employee_report.csv"}
    )


@employee_bp.route("/profile", methods=["GET", "POST"])
@login_required
@roles_required(Role.EMPLOYEE)
def profile():
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        
        if not auth_service.check_user_password(current_user, current_pw):
            flash("Current password incorrect.", "error")
            return redirect(url_for("employee.profile"))

        if len(new_pw) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return redirect(url_for("employee.profile"))

        current_user.set_password(new_pw)
        db.session.commit()

        audit_service.log_action(
            action=AuditAction.PASSWORD_CHANGED,
            user_id=current_user.id,
            entity_type="USER",
            entity_id=current_user.id,
            description="Employee changed profile password"
        )
        flash("Password updated successfully!", "success")
        return redirect(url_for("employee.profile"))

    sessions = LoginSession.query.filter_by(user_id=current_user.id).order_by(LoginSession.login_time.desc()).all()
    return render_template("employee/profile.html", sessions=sessions)


@employee_bp.route("/help")
@login_required
@roles_required(Role.EMPLOYEE)
def help():
    return render_template("employee/help.html")


@employee_bp.route("/service-requests", methods=["GET", "POST"])
@login_required
@roles_required(Role.EMPLOYEE)
def service_requests():
    if request.method == "POST":
        ticket_id = request.form.get("ticket_id")
        new_status = request.form.get("status")
        notes = request.form.get("notes", "").strip()

        sr = db.session.get(ServiceRequest, int(ticket_id)) if ticket_id else None

        if not sr:
            flash("Service request ticket not found.", "danger")
        else:
            sr.status = new_status
            sr.admin_notes = notes
            db.session.commit()

            audit_service.log_action(
                action=AuditAction.SERVICE_REQUEST,
                user_id=current_user.id,
                entity_type="SERVICE_REQUEST",
                entity_id=sr.id,
                description=f"Employee updated service request #{sr.ticket_number} status to {new_status}"
            )
            flash(f"Service Request #{sr.ticket_number} updated to {new_status}.", "success")
            return redirect(url_for("employee.service_requests"))

    status_filter = request.args.get("status")
    if status_filter:
        requests_list = ServiceRequest.query.filter_by(status=status_filter).order_by(ServiceRequest.created_at.desc()).all()
    else:
        requests_list = ServiceRequest.query.order_by(ServiceRequest.created_at.desc()).all()

    return render_template("employee/service_requests.html", requests_list=requests_list, status_filter=status_filter or "")
