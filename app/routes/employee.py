from flask import Blueprint, render_template
from flask_login import login_required

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
