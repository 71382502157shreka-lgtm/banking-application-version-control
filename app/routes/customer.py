import os
import uuid
from decimal import Decimal
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.utils.decorators import roles_required
from app.models.user import Role
from app.models.account import Account, AccountType, AccountStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.version import EntityVersion
from app.models.beneficiary import Beneficiary
from app.models.complaint import Complaint, ComplaintStatus
from app.models.service_request import ServiceRequest, ServiceRequestType, ServiceRequestStatus
from app.models.document_vault import CustomerDocument, DocumentStatus
from app.services import audit_service
from app.models.audit_log import AuditAction

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


@customer_bp.route("/e-passbook")
@login_required
@roles_required(Role.CUSTOMER)
def e_passbook():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template("customer/e_passbook.html", accounts=accounts)


@customer_bp.route("/mini-statement")
@login_required
@roles_required(Role.CUSTOMER)
def mini_statement():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template("customer/mini_statement.html", accounts=accounts)


@customer_bp.route("/account-details")
@login_required
@roles_required(Role.CUSTOMER)
def account_details():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template("customer/account_details.html", accounts=accounts)


@customer_bp.route("/banking-services")
@login_required
@roles_required(Role.CUSTOMER)
def banking_services():
    return render_template("customer/banking_services.html")


@customer_bp.route("/calculators", methods=["GET", "POST"])
@login_required
@roles_required(Role.CUSTOMER)
def calculators():
    calc_result = None
    calc_type = request.form.get("calc_type", "emi")

    if request.method == "POST":
        if calc_type == "emi":
            try:
                principal = float(request.form.get("principal", 0))
                rate = float(request.form.get("rate", 0)) / 12 / 100
                tenure_months = int(request.form.get("tenure_months", 0))

                if principal > 0 and tenure_months > 0 and rate > 0:
                    emi = principal * rate * ((1 + rate) ** tenure_months) / (((1 + rate) ** tenure_months) - 1)
                    total_payment = emi * tenure_months
                    total_interest = total_payment - principal
                    calc_result = {
                        "type": "emi",
                        "emi": round(emi, 2),
                        "total_payment": round(total_payment, 2),
                        "total_interest": round(total_interest, 2),
                        "principal": principal,
                        "tenure": tenure_months,
                    }
            except Exception as e:
                flash(f"Calculation error: {str(e)}", "danger")

        elif calc_type == "deposit":
            try:
                principal = float(request.form.get("principal", 0))
                rate = float(request.form.get("rate", 0)) / 100
                tenure_years = float(request.form.get("tenure_years", 0))
                compounding = int(request.form.get("compounding", 4))  # Quarterly default

                if principal > 0 and tenure_years > 0:
                    maturity_val = principal * ((1 + (rate / compounding)) ** (compounding * tenure_years))
                    interest_earned = maturity_val - principal
                    calc_result = {
                        "type": "deposit",
                        "principal": principal,
                        "maturity_val": round(maturity_val, 2),
                        "interest_earned": round(interest_earned, 2),
                        "tenure_years": tenure_years,
                    }
            except Exception as e:
                flash(f"Calculation error: {str(e)}", "danger")

    return render_template("customer/calculators.html", calc_result=calc_result, calc_type=calc_type)


@customer_bp.route("/deposits-loans", methods=["GET", "POST"])
@login_required
@roles_required(Role.CUSTOMER)
def deposits_loans():
    accounts = Account.query.filter_by(user_id=current_user.id).all()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "open_deposit":
            source_acc_id = request.form.get("source_account_id")
            dep_type = request.form.get("deposit_type", AccountType.FIXED_DEPOSIT)
            amount_str = request.form.get("amount", "0")
            tenure_months = request.form.get("tenure_months", "12")

            try:
                amount = Decimal(amount_str)
                source_acc = Account.query.filter_by(id=int(source_acc_id) if source_acc_id else 0, user_id=current_user.id).first()

                if not source_acc:
                    flash("Invalid source account.", "danger")
                elif source_acc.available_balance < amount:
                    flash("Insufficient available balance for deposit principal.", "danger")
                else:
                    # Deduct from source account
                    source_acc.balance -= amount
                    source_acc.available_balance -= amount

                    # Create new FD/RD account
                    acc_num = f"FD{uuid.uuid4().hex[:8].upper()}"
                    new_dep = Account(
                        account_number=acc_num,
                        user_id=current_user.id,
                        account_type=dep_type,
                        balance=amount,
                        available_balance=amount,
                        status=AccountStatus.ACTIVE,
                    )
                    db.session.add(new_dep)
                    db.session.flush()

                    # Record transaction
                    txn = Transaction(
                        account_id=source_acc.id,
                        counterparty_account_id=new_dep.id,
                        transaction_type=TransactionType.TRANSFER,
                        amount=amount,
                        description=f"Opened {dep_type} Account #{acc_num} for {tenure_months} months",
                        status=TransactionStatus.COMPLETED,
                        balance_after=source_acc.balance,
                    )
                    db.session.add(txn)
                    db.session.commit()

                    audit_service.log_action(
                        action=AuditAction.ACCOUNT_CREATED,
                        user_id=current_user.id,
                        entity_type="ACCOUNT",
                        entity_id=new_dep.id,
                        description=f"Created {dep_type} deposit account #{acc_num} with initial principal {amount}"
                    )
                    flash(f"Deposit Account #{acc_num} opened successfully with amount ₹{amount:,.2f}!", "success")
                    return redirect(url_for("customer.deposits_loans"))

            except Exception as e:
                db.session.rollback()
                flash(f"Failed to open deposit: {str(e)}", "danger")

        elif action == "apply_loan":
            loan_type = request.form.get("loan_type", "PERSONAL_LOAN")
            requested_amount = request.form.get("amount", "0")
            tenure_years = request.form.get("tenure_years", "3")
            income = request.form.get("monthly_income", "0")

            ticket_num = f"LN-{uuid.uuid4().hex[:8].upper()}"
            details_str = f"Loan Type: {loan_type} | Amount: ₹{requested_amount} | Tenure: {tenure_years} years | Monthly Income: ₹{income}"

            sr = ServiceRequest(
                ticket_number=ticket_num,
                user_id=current_user.id,
                request_type=f"LOAN_APPLICATION_{loan_type}",
                details=details_str,
                status=ServiceRequestStatus.PENDING,
            )
            db.session.add(sr)
            db.session.commit()

            audit_service.log_action(
                action=AuditAction.SERVICE_REQUEST,
                user_id=current_user.id,
                entity_type="SERVICE_REQUEST",
                entity_id=sr.id,
                description=f"Submitted Loan application ticket #{ticket_num}"
            )
            flash(f"Loan application submitted successfully! Ticket #{ticket_num}", "success")
            return redirect(url_for("customer.deposits_loans"))

    # Fetch customer active deposits
    deposits = [a for a in accounts if a.account_type in [AccountType.FIXED_DEPOSIT, AccountType.RECURRING_DEPOSIT]]
    return render_template("customer/deposits_loans.html", accounts=accounts, deposits=deposits)


@customer_bp.route("/quick-pay", methods=["GET", "POST"])
@login_required
@roles_required(Role.CUSTOMER)
def quick_pay():
    accounts = Account.query.filter_by(user_id=current_user.id, status=AccountStatus.ACTIVE).all()

    if request.method == "POST":
        source_acc_id = request.form.get("account_id")
        pay_category = request.form.get("category", "RECHARGE")
        biller_name = request.form.get("biller_name", "Utility Provider")
        consumer_number = request.form.get("consumer_number", "")
        amount_str = request.form.get("amount", "0")

        try:
            amount = Decimal(amount_str)
            acc = Account.query.filter_by(id=int(source_acc_id) if source_acc_id else 0, user_id=current_user.id).first()

            if not acc:
                flash("Invalid payment account selected.", "danger")
            elif amount <= Decimal("0.00"):
                flash("Payment amount must be greater than zero.", "danger")
            elif acc.available_balance < amount:
                flash("Insufficient available balance for bill payment.", "danger")
            else:
                acc.balance -= amount
                acc.available_balance -= amount

                txn = Transaction(
                    account_id=acc.id,
                    transaction_type=TransactionType.WITHDRAWAL,
                    amount=amount,
                    description=f"Quick Pay: {pay_category} - {biller_name} ({consumer_number})",
                    status=TransactionStatus.COMPLETED,
                    balance_after=acc.balance,
                )
                db.session.add(txn)
                db.session.commit()

                audit_service.log_action(
                    action=AuditAction.TRANSFER,
                    user_id=current_user.id,
                    entity_type="TRANSACTION",
                    entity_id=txn.id,
                    description=f"Quick Pay payment of ₹{amount:,.2f} for {biller_name}"
                )
                flash(f"Payment of ₹{amount:,.2f} to {biller_name} completed successfully!", "success")
                return redirect(url_for("customer.quick_pay"))

        except Exception as e:
            db.session.rollback()
            flash(f"Payment failed: {str(e)}", "danger")

    return render_template("customer/quick_pay.html", accounts=accounts)


@customer_bp.route("/service-requests", methods=["GET", "POST"])
@login_required
@roles_required(Role.CUSTOMER)
def service_requests():
    accounts = Account.query.filter_by(user_id=current_user.id).all()

    if request.method == "POST":
        req_type = request.form.get("request_type")
        account_id = request.form.get("account_id")
        details = request.form.get("details", "").strip()

        ticket_num = f"SR-{uuid.uuid4().hex[:8].upper()}"

        sr = ServiceRequest(
            ticket_number=ticket_num,
            user_id=current_user.id,
            account_id=int(account_id) if account_id else None,
            request_type=req_type,
            details=details,
            status=ServiceRequestStatus.PENDING,
        )
        db.session.add(sr)
        db.session.commit()

        audit_service.log_action(
            action=AuditAction.SERVICE_REQUEST,
            user_id=current_user.id,
            entity_type="SERVICE_REQUEST",
            entity_id=sr.id,
            description=f"Created Service Request #{ticket_num} ({req_type})"
        )
        flash(f"Service Request submitted! Ticket #{ticket_num}", "success")
        return redirect(url_for("customer.service_requests"))

    requests_list = ServiceRequest.query.filter_by(user_id=current_user.id).order_by(ServiceRequest.created_at.desc()).all()
    return render_template("customer/service_requests.html", accounts=accounts, requests_list=requests_list)


@customer_bp.route("/document-vault", methods=["GET", "POST"])
@login_required
@roles_required(Role.CUSTOMER)
def document_vault():
    if request.method == "POST":
        doc_type = request.form.get("document_type", "OTHER")
        doc_name = request.form.get("document_name", "").strip()

        if not doc_name:
            flash("Document title/name is required.", "danger")
        else:
            file_obj = request.files.get("document_file")
            saved_filename = None

            if file_obj and file_obj.filename:
                sec_filename = secure_filename(file_obj.filename)
                ext = os.path.splitext(sec_filename)[1]
                unique_name = f"user_{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
                upload_dir = os.path.join(current_app.instance_path, "uploads", "documents")
                os.makedirs(upload_dir, exist_ok=True)
                file_obj.save(os.path.join(upload_dir, unique_name))
                saved_filename = unique_name

            doc = CustomerDocument(
                user_id=current_user.id,
                document_type=doc_type,
                document_name=doc_name,
                file_path=saved_filename,
                status=DocumentStatus.PENDING_VERIFICATION,
            )
            db.session.add(doc)
            db.session.commit()

            audit_service.log_action(
                action=AuditAction.DOCUMENT_UPLOAD,
                user_id=current_user.id,
                entity_type="DOCUMENT",
                entity_id=doc.id,
                description=f"Uploaded document '{doc_name}' ({doc_type})"
            )
            flash(f"Document '{doc_name}' uploaded to vault successfully!", "success")
            return redirect(url_for("customer.document_vault"))

    documents = CustomerDocument.query.filter_by(user_id=current_user.id).order_by(CustomerDocument.created_at.desc()).all()
    return render_template("customer/document_vault.html", documents=documents)
