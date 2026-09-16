from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.utils.decorators import roles_required
from app.models.user import User, Role
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.version import EntityVersion
from app.models.audit_log import AuditLog

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")


@employee_bp.route("/dashboard")
@login_required
@roles_required(Role.EMPLOYEE, Role.ADMIN)
def dashboard():
    total_customers = User.query.filter_by(role=Role.CUSTOMER).count()
    total_accounts = Account.query.count()
    total_txns = Transaction.query.count()
    recent_txns = Transaction.query.order_by(Transaction.created_at.desc()).limit(8).all()
    recent_versions = EntityVersion.query.order_by(EntityVersion.created_at.desc()).limit(8).all()
    return render_template(
        "employee/employee_dashboard.html",
        total_customers=total_customers,
        total_accounts=total_accounts,
        total_txns=total_txns,
        recent_txns=recent_txns,
        recent_versions=recent_versions,
    )


@employee_bp.route("/customers")
@login_required
@roles_required(Role.EMPLOYEE, Role.ADMIN)
def customers():
    customer_list = User.query.filter_by(role=Role.CUSTOMER).order_by(User.created_at.desc()).all()
    return render_template("employee/customers.html", customers=customer_list)


@employee_bp.route("/versions")
@login_required
@roles_required(Role.EMPLOYEE, Role.ADMIN)
def versions():
    all_versions = EntityVersion.query.order_by(EntityVersion.created_at.desc()).limit(100).all()
    return render_template("employee/employee_versions.html", versions=all_versions)


@employee_bp.route("/audit-logs")
@login_required
@roles_required(Role.EMPLOYEE, Role.ADMIN)
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return render_template("employee/audit_logs.html", logs=logs)


@employee_bp.route("/transactions/export/csv")
@login_required
@roles_required(Role.EMPLOYEE, Role.ADMIN)
def export_transactions_csv():
    import csv, io
    from datetime import datetime
    from flask import Response

    txns = Transaction.query.order_by(Transaction.created_at.desc()).limit(500).all()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["BankVCS 2.0 - Staff Operational Transaction Ledger"])
    writer.writerow(["Exported By", f"{current_user.full_name} ({current_user.role.upper()})"])
    writer.writerow(["Generated At", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")])
    writer.writerow([])
    writer.writerow(["Txn ID", "Date & Time", "Reference Number", "Account ID", "Type", "Amount (INR)", "Status", "Description"])

    for tx in txns:
        writer.writerow([
            tx.id,
            tx.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            tx.reference_number,
            tx.account_id,
            tx.transaction_type,
            f"{tx.amount:.2f}",
            tx.status,
            tx.description or ""
        ])

    csv_data = output.getvalue()
    filename = f"BankVCS_Branch_Ledger_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
