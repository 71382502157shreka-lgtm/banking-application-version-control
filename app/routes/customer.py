from decimal import Decimal
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.utils.decorators import roles_required
from app.models.user import Role
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.version import EntityVersion
from app.models.beneficiary import Beneficiary

customer_bp = Blueprint("customer", __name__, url_prefix="/customer")


@customer_bp.route("/")
@login_required
@roles_required(Role.CUSTOMER)
def root():
    from flask import redirect, url_for
    return redirect(url_for("customer.dashboard"))


@customer_bp.route("/dashboard")
@login_required
@roles_required(Role.CUSTOMER)
def dashboard():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    total_balance = sum((a.balance for a in accounts), Decimal("0.00"))
    total_available = sum((a.available_balance for a in accounts), Decimal("0.00"))
    account_ids = [a.id for a in accounts]

    recent_transactions = []
    if account_ids:
        recent_transactions = (
            Transaction.query
            .filter(Transaction.account_id.in_(account_ids))
            .order_by(Transaction.created_at.desc())
            .limit(8)
            .all()
        )

    recent_versions = (
        EntityVersion.query
        .filter_by(changed_by=current_user.id)
        .order_by(EntityVersion.created_at.desc())
        .limit(5)
        .all()
    )

    beneficiaries = Beneficiary.query.filter_by(user_id=current_user.id).all()

    return render_template(
        "customer/dashboard.html",
        accounts=accounts,
        total_balance=total_balance,
        total_available=total_available,
        recent_transactions=recent_transactions,
        recent_versions=recent_versions,
        beneficiaries=beneficiaries,
    )


@customer_bp.route("/accounts")
@login_required
@roles_required(Role.CUSTOMER)
def accounts():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template("customer/account.html", accounts=accounts)


@customer_bp.route("/transactions")
@login_required
@roles_required(Role.CUSTOMER)
def transactions():
    return render_template("customer/transactions.html")


@customer_bp.route("/transfer")
@login_required
@roles_required(Role.CUSTOMER)
def transfer():
    return render_template("customer/transfer.html")


@customer_bp.route("/beneficiaries")
@login_required
@roles_required(Role.CUSTOMER)
def beneficiaries():
    return render_template("customer/beneficiaries.html")


@customer_bp.route("/profile")
@login_required
@roles_required(Role.CUSTOMER)
def profile():
    return render_template("customer/profile.html")


@customer_bp.route("/version-history")
@login_required
@roles_required(Role.CUSTOMER)
def version_history():
    return render_template("customer/version_history.html")


@customer_bp.route("/deposit")
@login_required
@roles_required(Role.CUSTOMER)
def deposit():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template("customer/deposit.html", accounts=accounts)


@customer_bp.route("/withdraw")
@login_required
@roles_required(Role.CUSTOMER)
def withdraw():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template("customer/withdraw.html", accounts=accounts)


@customer_bp.route("/statements")
@login_required
@roles_required(Role.CUSTOMER)
def statements():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template("customer/statements.html", accounts=accounts)


@customer_bp.route("/notifications")
@login_required
@roles_required(Role.CUSTOMER)
def notifications():
    return render_template("customer/notifications.html")


@customer_bp.route("/security")
@login_required
@roles_required(Role.CUSTOMER)
def security():
    return render_template("customer/security.html")


@customer_bp.route("/complaints", methods=["GET", "POST"])
@login_required
@roles_required(Role.CUSTOMER)
def complaints():
    from flask import request, flash, redirect, url_for
    from app import db
    from app.models.complaint import Complaint, ComplaintStatus, ComplaintPriority

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "GENERAL").strip()

        if not subject or not description:
            flash("Subject and description are required", "error")
            return redirect(url_for("customer.complaints"))

        import uuid
        ticket_num = f"TICK-{uuid.uuid4().hex[:6].upper()}"
        comp = Complaint(
            ticket_number=ticket_num,
            customer_id=current_user.id,
            subject=subject,
            description=description,
            category=category,
            priority=ComplaintPriority.MEDIUM,
            status=ComplaintStatus.OPEN,
        )
        db.session.add(comp)
        db.session.commit()
        flash(f"Complaint submitted successfully! Ticket #{ticket_num}", "success")
        return redirect(url_for("customer.complaints"))

    customer_complaints = Complaint.query.filter_by(customer_id=current_user.id).order_by(Complaint.created_at.desc()).all()
    return render_template("customer/complaints.html", complaints=customer_complaints)

