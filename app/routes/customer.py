import csv
io_import = True
import io
from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, request, Response, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.utils.decorators import roles_required
from app.models.user import Role
from app.models.account import Account
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.version import EntityVersion
from app.models.beneficiary import Beneficiary

customer_bp = Blueprint("customer", __name__, url_prefix="/customer")


def _calculate_statement_data(account, start_date=None, end_date=None, txn_type=None, search=None):
    query = Transaction.query.filter(
        or_(
            Transaction.account_id == account.id,
            Transaction.counterparty_account_id == account.id
        )
    )

    if start_date:
        query = query.filter(Transaction.created_at >= start_date)
    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.filter(Transaction.created_at <= end_datetime)

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Transaction.reference_number.ilike(pattern),
                Transaction.description.ilike(pattern)
            )
        )

    all_txns = query.order_by(Transaction.created_at.asc()).all()

    records = []
    total_credit = Decimal("0.00")
    total_debit = Decimal("0.00")

    for tx in all_txns:
        is_credit = (
            tx.transaction_type == TransactionType.DEPOSIT or
            (tx.transaction_type == TransactionType.TRANSFER and tx.counterparty_account_id == account.id)
        )

        entry_type = "CREDIT" if is_credit else "DEBIT"
        if txn_type and txn_type.upper() in ["CREDIT", "DEBIT"] and entry_type != txn_type.upper():
            continue

        credit_amt = tx.amount if is_credit else Decimal("0.00")
        debit_amt = tx.amount if not is_credit else Decimal("0.00")

        total_credit += credit_amt
        total_debit += debit_amt

        records.append({
            "id": tx.id,
            "created_at": tx.created_at,
            "reference_number": tx.reference_number,
            "transaction_type": tx.transaction_type,
            "entry_type": entry_type,
            "description": tx.description or f"{tx.transaction_type} transaction",
            "debit_amount": debit_amt,
            "credit_amount": credit_amt,
            "amount": tx.amount,
            "balance_after": tx.balance_after if tx.balance_after is not None else account.balance,
            "status": tx.status
        })

    opening_balance = account.balance - total_credit + total_debit
    closing_balance = account.balance

    return {
        "records": list(reversed(records)),
        "chronological": records,
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "total_credit": total_credit,
        "total_debit": total_debit
    }


@customer_bp.route("/dashboard")
@login_required
@roles_required(Role.CUSTOMER)
def dashboard():
    accounts = _get_user_accounts(current_user.id)
    total_balance = sum((a.balance for a in accounts), Decimal("0.00"))
    total_available = sum((a.available_balance for a in accounts), Decimal("0.00"))
    account_ids = [a.id for a in accounts]

    recent_transactions = []
    monthly_sent = Decimal("0.00")
    monthly_received = Decimal("0.00")

    if account_ids:
        recent_transactions = (
            Transaction.query
            .filter(Transaction.account_id.in_(account_ids))
            .order_by(Transaction.created_at.desc())
            .limit(8)
            .all()
        )

        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_30d_txns = (
            Transaction.query
            .filter(
                or_(
                    Transaction.account_id.in_(account_ids),
                    Transaction.counterparty_account_id.in_(account_ids)
                ),
                Transaction.created_at >= thirty_days_ago,
                Transaction.status == TransactionStatus.COMPLETED
            ).all()
        )

        for tx in recent_30d_txns:
            if tx.transaction_type in [TransactionType.WITHDRAWAL, TransactionType.TRANSFER] and tx.account_id in account_ids:
                monthly_sent += tx.amount
            if tx.transaction_type in [TransactionType.DEPOSIT] or (tx.transaction_type == TransactionType.TRANSFER and tx.counterparty_account_id in account_ids):
                monthly_received += tx.amount

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
        monthly_sent=monthly_sent,
        monthly_received=monthly_received,
    )


@customer_bp.route("/accounts")
@login_required
@roles_required(Role.CUSTOMER)
def accounts():
    accounts = _get_user_accounts(current_user.id)
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
    accounts = _get_user_accounts(current_user.id)
    beneficiaries = Beneficiary.query.filter_by(user_id=current_user.id).all()
    all_accounts = Account.query.filter(Account.user_id != current_user.id).limit(50).all()
    return render_template(
        "customer/transfer.html",
        accounts=accounts,
        beneficiaries=beneficiaries,
        all_accounts=all_accounts
    )


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
    accounts = _get_user_accounts(current_user.id)
    return render_template("customer/deposit.html", accounts=accounts)


@customer_bp.route("/withdraw")
@login_required
@roles_required(Role.CUSTOMER)
def withdraw():
    accounts = _get_user_accounts(current_user.id)
    return render_template("customer/withdraw.html", accounts=accounts)


def _get_user_accounts(user_id):
    accounts = Account.query.filter_by(user_id=user_id).all()
    if not accounts:
        from app.services.banking_service import create_account
        create_account(user_id, "Savings")
        accounts = Account.query.filter_by(user_id=user_id).all()
    return accounts


@customer_bp.route("/statements")
@login_required
@roles_required(Role.CUSTOMER)
def statements():
    accounts = _get_user_accounts(current_user.id)
    selected_account_id = request.args.get("account_id", type=int)
    preset = request.args.get("preset", "30days")
    txn_type = request.args.get("txn_type", "ALL")
    search_query = request.args.get("search", "")

    start_date = None
    end_date = None

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    today = datetime.now().date()

    if preset == "7days":
        start_date = today - timedelta(days=7)
        end_date = today
    elif preset == "30days":
        start_date = today - timedelta(days=30)
        end_date = today
    elif preset == "3months":
        start_date = today - timedelta(days=90)
        end_date = today
    elif preset == "custom":
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

    selected_account = None
    statement_data = None

    if accounts:
        if selected_account_id:
            selected_account = next((a for a in accounts if a.id == selected_account_id), accounts[0])
        else:
            selected_account = accounts[0]

        statement_data = _calculate_statement_data(
            selected_account,
            start_date=start_date,
            end_date=end_date,
            txn_type=txn_type,
            search=search_query
        )

    return render_template(
        "customer/statements.html",
        accounts=accounts,
        selected_account=selected_account,
        statement_data=statement_data,
        preset=preset,
        txn_type=txn_type,
        search_query=search_query,
        start_date_str=start_date_str or (start_date.strftime("%Y-%m-%d") if start_date else ""),
        end_date_str=end_date_str or (end_date.strftime("%Y-%m-%d") if end_date else "")
    )


@customer_bp.route("/statements/download/csv")
@login_required
@roles_required(Role.CUSTOMER)
def download_statement_csv():
    accounts = _get_user_accounts(current_user.id)
    account_id = request.args.get("account_id", type=int)
    if account_id:
        account = next((a for a in accounts if a.id == account_id), accounts[0] if accounts else None)
    else:
        account = accounts[0] if accounts else None

    if not account:
        flash("No account available for statement export.", "error")
        return redirect(url_for("customer.statements"))

    preset = request.args.get("preset", "30days")
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    txn_type = request.args.get("txn_type", "ALL")
    search_query = request.args.get("search", "")

    today = datetime.now().date()
    start_date = None
    end_date = None

    if preset == "7days":
        start_date = today - timedelta(days=7)
        end_date = today
    elif preset == "30days":
        start_date = today - timedelta(days=30)
        end_date = today
    elif preset == "3months":
        start_date = today - timedelta(days=90)
        end_date = today
    elif preset == "custom":
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

    stmt = _calculate_statement_data(account, start_date, end_date, txn_type, search_query)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["BankVCS 2.0 Digital Banking - Account Statement"])
    writer.writerow(["Customer Name", current_user.full_name])
    writer.writerow(["Account Number", account.account_number])
    writer.writerow(["Account Type", account.account_type])
    writer.writerow(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow(["Opening Balance", f"INR {stmt['opening_balance']:.2f}"])
    writer.writerow(["Closing Balance", f"INR {stmt['closing_balance']:.2f}"])
    writer.writerow([])
    writer.writerow(["Date & Time", "UTR Reference", "Type", "Entry", "Description", "Debit (INR)", "Credit (INR)", "Running Balance (INR)", "Status"])

    for rec in stmt["chronological"]:
        writer.writerow([
            rec["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
            rec["reference_number"],
            rec["transaction_type"],
            rec["entry_type"],
            rec["description"],
            f"{rec['debit_amount']:.2f}",
            f"{rec['credit_amount']:.2f}",
            f"{rec['balance_after']:.2f}",
            rec["status"]
        ])

    csv_data = output.getvalue()
    filename = f"BankVCS_Statement_{account.account_number}_{today.strftime('%Y%m%d')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@customer_bp.route("/statements/print")
@login_required
@roles_required(Role.CUSTOMER)
def print_statement():
    accounts = _get_user_accounts(current_user.id)
    account_id = request.args.get("account_id", type=int)
    if account_id:
        account = next((a for a in accounts if a.id == account_id), accounts[0] if accounts else None)
    else:
        account = accounts[0] if accounts else None

    if not account:
        flash("No account available for statement printing.", "error")
        return redirect(url_for("customer.statements"))

    preset = request.args.get("preset", "30days")
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    txn_type = request.args.get("txn_type", "ALL")
    search_query = request.args.get("search", "")

    today = datetime.now().date()
    start_date = None
    end_date = None

    if preset == "7days":
        start_date = today - timedelta(days=7)
        end_date = today
    elif preset == "30days":
        start_date = today - timedelta(days=30)
        end_date = today
    elif preset == "3months":
        start_date = today - timedelta(days=90)
        end_date = today
    elif preset == "custom":
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

    stmt = _calculate_statement_data(account, start_date, end_date, txn_type, search_query)

    return render_template(
        "customer/statement_print.html",
        account=account,
        stmt=stmt,
        generated_at=datetime.now(),
        preset=preset
    )


@customer_bp.route("/transaction/<int:tx_id>/receipt")
@login_required
@roles_required(Role.CUSTOMER)
def transaction_receipt(tx_id):
    user_account_ids = [a.id for a in Account.query.filter_by(user_id=current_user.id).all()]
    tx = Transaction.query.filter(
        Transaction.id == tx_id,
        or_(
            Transaction.account_id.in_(user_account_ids),
            Transaction.counterparty_account_id.in_(user_account_ids)
        )
    ).first_or_404()

    account = Account.query.get(tx.account_id)
    counterparty = Account.query.get(tx.counterparty_account_id) if tx.counterparty_account_id else None

    return render_template(
        "customer/receipt.html",
        tx=tx,
        account=account,
        counterparty=counterparty
    )


@customer_bp.route("/transactions/export/csv")
@login_required
@roles_required(Role.CUSTOMER)
def download_transactions_csv():
    accounts = _get_user_accounts(current_user.id)
    account_ids = [a.id for a in accounts]
    if not account_ids:
        flash("No accounts found for export.", "error")
        return redirect(url_for("customer.transactions"))

    txns = Transaction.query.filter(
        or_(
            Transaction.account_id.in_(account_ids),
            Transaction.counterparty_account_id.in_(account_ids)
        )
    ).order_by(Transaction.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["BankVCS 2.0 - Customer Transaction History Ledger"])
    writer.writerow(["Customer Name", current_user.full_name])
    writer.writerow(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])
    writer.writerow(["Date & Time", "UTR Reference", "Type", "Amount (INR)", "Status", "Description", "Balance After (INR)"])

    for tx in txns:
        writer.writerow([
            tx.created_at.strftime("%Y-%m-%d %H:%M:%S") if tx.created_at else "",
            tx.reference_number,
            tx.transaction_type,
            f"{tx.amount:.2f}",
            tx.status,
            tx.description or "",
            f"{tx.balance_after:.2f}" if tx.balance_after is not None else "N/A"
        ])

    csv_data = output.getvalue()
    filename = f"BankVCS_Transaction_History_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@customer_bp.route("/epassbook")
@login_required
@roles_required(Role.CUSTOMER)
def epassbook():
    accounts = _get_user_accounts(current_user.id)
    selected_account_id = request.args.get("account_id", type=int)
    selected_account = next((a for a in accounts if a.id == selected_account_id), accounts[0] if accounts else None)

    statement_data = None
    if selected_account:
        statement_data = _calculate_statement_data(selected_account)

    return render_template(
        "customer/epassbook.html",
        accounts=accounts,
        selected_account=selected_account,
        statement_data=statement_data
    )


@customer_bp.route("/epassbook/download/csv")
@login_required
@roles_required(Role.CUSTOMER)
def download_epassbook_csv():
    accounts = _get_user_accounts(current_user.id)
    account_id = request.args.get("account_id", type=int)
    account = next((a for a in accounts if a.id == account_id), accounts[0] if accounts else None)

    if not account:
        flash("No account available for e-Passbook export.", "error")
        return redirect(url_for("customer.epassbook"))

    stmt = _calculate_statement_data(account)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["BankVCS 2.0 - Digital e-Passbook Ledger"])
    writer.writerow(["Customer Name", current_user.full_name])
    writer.writerow(["Account Number", account.account_number])
    writer.writerow(["Account Type", account.account_type])
    writer.writerow(["IFSC Code", "BVCS0001092"])
    writer.writerow(["Branch", "Headquarters Financial Center"])
    writer.writerow(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow(["Current Balance", f"INR {account.balance:.2f}"])
    writer.writerow([])
    writer.writerow(["Date & Time", "UTR Reference", "Type", "Entry", "Description", "Debit (INR)", "Credit (INR)", "Running Balance (INR)", "Status"])

    for rec in stmt["chronological"]:
        writer.writerow([
            rec["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
            rec["reference_number"],
            rec["transaction_type"],
            rec["entry_type"],
            rec["description"],
            f"{rec['debit_amount']:.2f}",
            f"{rec['credit_amount']:.2f}",
            f"{rec['balance_after']:.2f}",
            rec["status"]
        ])

    csv_data = output.getvalue()
    filename = f"BankVCS_ePassbook_{account.account_number}_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@customer_bp.route("/epassbook/print")
@login_required
@roles_required(Role.CUSTOMER)
def print_epassbook():
    accounts = _get_user_accounts(current_user.id)
    account_id = request.args.get("account_id", type=int)
    account = next((a for a in accounts if a.id == account_id), accounts[0] if accounts else None)

    if not account:
        flash("No account available for e-Passbook printing.", "error")
        return redirect(url_for("customer.epassbook"))

    stmt = _calculate_statement_data(account)

    return render_template(
        "customer/epassbook_print.html",
        account=account,
        stmt=stmt,
        generated_at=datetime.now()
    )


@customer_bp.route("/transaction/<int:tx_id>/export/csv")
@login_required
@roles_required(Role.CUSTOMER)
def export_receipt_csv(tx_id):
    user_account_ids = [a.id for a in Account.query.filter_by(user_id=current_user.id).all()]
    tx = Transaction.query.filter(
        Transaction.id == tx_id,
        or_(
            Transaction.account_id.in_(user_account_ids),
            Transaction.counterparty_account_id.in_(user_account_ids)
        )
    ).first_or_404()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["BankVCS 2.0 - Official Transaction Receipt Invoice"])
    writer.writerow(["Customer Name", current_user.full_name])
    writer.writerow(["UTR Reference Number", tx.reference_number])
    writer.writerow(["Transaction Type", tx.transaction_type])
    writer.writerow(["Amount (INR)", f"{tx.amount:.2f}"])
    writer.writerow(["Status", tx.status])
    writer.writerow(["Timestamp", tx.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")])
    writer.writerow(["Description", tx.description or tx.transaction_type])
    writer.writerow(["Cryptographic Integrity", "SHA-256 Verified Append-Only Entry"])

    csv_data = output.getvalue()
    filename = f"BankVCS_Invoice_Receipt_{tx.reference_number}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


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

