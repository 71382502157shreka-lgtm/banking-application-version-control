import csv
import io
from decimal import Decimal
from flask import Blueprint, request, jsonify, Response
from flask_login import login_required, current_user

from app import db
from app.models.user import Role, User
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.beneficiary import Beneficiary
from app.models.version import EntityVersion
from app.models.audit_log import AuditLog, AuditAction
from app.models.security_session import LoginSession, SecurityEvent
from app.models.workflow_risk import RollbackRequest, RiskAssessment
from app.models.complaint import Complaint, ComplaintStatus, ComplaintPriority
from app.models.service_request import ServiceRequest, ServiceRequestStatus
from app.models.document_vault import CustomerDocument, DocumentStatus
from app.services import (
    banking_service, beneficiary_service, version_service,
    audit_service, mfa_service, session_service, approval_service,
    statement_service, risk_service, fraud_prevention_service
)
from app.utils.decorators import roles_required, json_errors
from app.utils.validators import ValidationError
from app.utils.security_utils import rate_limit
from datetime import datetime

api_bp = Blueprint("api", __name__)


# ---------------------------------------------------------------------------
# Health Check Endpoint
# ---------------------------------------------------------------------------
@api_bp.route("/health", methods=["GET"])
@api_bp.route("/v1/health", methods=["GET"])
def health_check():
    """Unauthenticated health check endpoint for load balancers and deployment probes."""
    try:
        db.session.execute(db.select(1))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return jsonify({
        "status": "healthy" if db_status == "connected" else "degraded",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "database": db_status,
        "version": "2.0.0",
        "application": "BankVCS"
    }), 200 if db_status == "connected" else 503


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
@api_bp.route("/accounts", methods=["GET"])
@api_bp.route("/v1/accounts", methods=["GET"])
@login_required
def list_accounts():
    if current_user.role == Role.CUSTOMER:
        accounts = Account.query.filter_by(user_id=current_user.id).all()
    else:
        accounts = Account.query.limit(200).all()
    return jsonify([a.to_dict() for a in accounts])


@api_bp.route("/accounts/<int:account_id>", methods=["GET"])
@api_bp.route("/v1/accounts/<int:account_id>", methods=["GET"])
@login_required
def get_account(account_id):
    account = _get_owned_account_or_403(account_id)
    return jsonify(account.to_dict())


@api_bp.route("/accounts", methods=["POST"])
@api_bp.route("/v1/accounts", methods=["POST"])
@login_required

@json_errors
def open_account():
    data = request.get_json(force=True) or {}
    account_type = data.get("account_type", "SAVINGS")
    account = banking_service.create_account(current_user.id, account_type)
    return jsonify(account.to_dict()), 201


# ---------------------------------------------------------------------------
# Transactions & Statements
# ---------------------------------------------------------------------------
@api_bp.route("/transactions", methods=["GET"])
@api_bp.route("/v1/transactions", methods=["GET"])
@login_required
def list_transactions():
    account_id = request.args.get("account_id", type=int)
    query = Transaction.query

    if account_id:
        _get_owned_account_or_403(account_id)
        query = query.filter_by(account_id=account_id)
    elif current_user.role == Role.CUSTOMER:
        owned_ids = [a.id for a in Account.query.filter_by(user_id=current_user.id).all()]
        query = query.filter(Transaction.account_id.in_(owned_ids))

    txn_type = request.args.get("type") or request.args.get("transaction_type")
    if txn_type and txn_type != "ALL":
        query = query.filter_by(transaction_type=txn_type)

    status = request.args.get("status")
    if status and status != "ALL":
        query = query.filter_by(status=status)

    mode = request.args.get("mode") or request.args.get("transaction_mode")
    if mode and mode != "ALL":
        query = query.filter_by(transaction_mode=mode)

    search = request.args.get("search")
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (Transaction.description.ilike(term)) |
            (Transaction.reference_number.ilike(term))
        )

    date_from = request.args.get("date_from") or request.args.get("start_date")
    if date_from:
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Transaction.created_at >= d_from)
        except ValueError:
            pass

    date_to = request.args.get("date_to") or request.args.get("end_date")
    if date_to:
        try:
            d_to = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(Transaction.created_at <= d_to)
        except ValueError:
            pass

    preset = request.args.get("preset")
    if preset:
        s_date, e_date = statement_service.resolve_date_preset(preset)
        if s_date:
            query = query.filter(Transaction.created_at >= datetime.combine(s_date, datetime.min.time()))
        if e_date:
            query = query.filter(Transaction.created_at <= datetime.combine(e_date, datetime.max.time()))

    sort_order = request.args.get("sort", "desc").lower()
    if sort_order == "asc":
        query = query.order_by(Transaction.created_at.asc())
    else:
        query = query.order_by(Transaction.created_at.desc())

    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 50, type=int)
    limit = min(max(limit, 1), 500)

    pagination = query.paginate(page=page, per_page=limit, error_out=False)
    txns = pagination.items

    return jsonify({
        "success": True,
        "items": [t.to_dict() for t in txns],
        "total": pagination.total,
        "page": page,
        "pages": pagination.pages,
        "limit": limit
    })


@api_bp.route("/transactions/mini-statement", methods=["GET"])
@login_required
def mini_statement():
    account_id = request.args.get("account_id", type=int)
    if account_id:
        _get_owned_account_or_403(account_id)
        txns = Transaction.query.filter_by(account_id=account_id).order_by(Transaction.created_at.desc()).limit(10).all()
    elif current_user.role == Role.CUSTOMER:
        owned_ids = [a.id for a in Account.query.filter_by(user_id=current_user.id).all()]
        txns = Transaction.query.filter(Transaction.account_id.in_(owned_ids)).order_by(Transaction.created_at.desc()).limit(10).all()
    else:
        txns = Transaction.query.order_by(Transaction.created_at.desc()).limit(10).all()

    return jsonify({
        "success": True,
        "count": len(txns),
        "transactions": [t.to_dict() for t in txns]
    })


@api_bp.route("/transactions/<int:transaction_id>", methods=["GET"])
@login_required
def get_transaction_detail(transaction_id):
    tx = Transaction.query.get_or_404(transaction_id)
    account = db.session.get(Account, tx.account_id)

    if current_user.role == Role.CUSTOMER:
        if not account or account.user_id != current_user.id:
            from flask import abort
            abort(403)

    return jsonify({
        "success": True,
        "transaction": tx.to_dict(),
        "account_number": statement_service.mask_account_number(account.account_number if account else ""),
        "account_type": account.account_type if account else "SAVINGS",
        "customer_name": current_user.full_name or current_user.username
    })


@api_bp.route("/transactions/<int:transaction_id>/receipt", methods=["GET"])
@login_required
def download_transaction_receipt(transaction_id):
    tx = Transaction.query.get_or_404(transaction_id)
    account = db.session.get(Account, tx.account_id)

    if current_user.role == Role.CUSTOMER:
        if not account or account.user_id != current_user.id:
            from flask import abort
            abort(403)

    pdf_bytes = statement_service.export_transaction_receipt_pdf(transaction_id)
    if not pdf_bytes:
        return jsonify({"success": False, "error": "Receipt generation failed"}), 500

    filename = f"transaction_receipt_{tx.reference_number}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@api_bp.route("/statements", methods=["GET"])
@login_required
def get_statement_summary():
    account_id = request.args.get("account_id", type=int)
    if not account_id:
        if current_user.role == Role.CUSTOMER:
            acc = Account.query.filter_by(user_id=current_user.id).first()
            if acc:
                account_id = acc.id
            else:
                return jsonify({"success": False, "error": "No accounts found"}), 404
        else:
            return jsonify({"success": False, "error": "account_id parameter required"}), 400

    _get_owned_account_or_403(account_id)

    preset = request.args.get("preset")
    s_date_str = request.args.get("date_from") or request.args.get("start_date")
    e_date_str = request.args.get("date_to") or request.args.get("end_date")

    s_date = datetime.strptime(s_date_str, "%Y-%m-%d").date() if s_date_str else None
    e_date = datetime.strptime(e_date_str, "%Y-%m-%d").date() if e_date_str else None

    statement_data = statement_service.generate_account_statement(
        account_id=account_id,
        start_date=s_date,
        end_date=e_date,
        transaction_type=request.args.get("type"),
        status=request.args.get("status"),
        mode=request.args.get("mode"),
        search=request.args.get("search"),
        preset=preset
    )
    # Exclude raw SQLAlchemy objects from JSON response
    if "transactions" in statement_data:
        statement_data["items"] = [t.to_dict() for t in statement_data["transactions"]]
        del statement_data["transactions"]

    return jsonify(statement_data)


@api_bp.route("/statements/download/pdf", methods=["GET"])
@login_required
def download_statement_pdf():
    account_id = request.args.get("account_id", type=int)
    if not account_id:
        acc = Account.query.filter_by(user_id=current_user.id).first()
        if acc:
            account_id = acc.id
        else:
            return jsonify({"success": False, "error": "No accounts found"}), 404

    _get_owned_account_or_403(account_id)

    preset = request.args.get("preset")
    s_date_str = request.args.get("date_from") or request.args.get("start_date")
    e_date_str = request.args.get("date_to") or request.args.get("end_date")

    s_date = datetime.strptime(s_date_str, "%Y-%m-%d").date() if s_date_str else None
    e_date = datetime.strptime(e_date_str, "%Y-%m-%d").date() if e_date_str else None

    pdf_bytes = statement_service.export_statement_pdf(
        account_id=account_id,
        start_date=s_date,
        end_date=e_date,
        transaction_type=request.args.get("type"),
        status=request.args.get("status"),
        mode=request.args.get("mode"),
        search=request.args.get("search"),
        preset=preset
    )

    filename = f"account_statement_{datetime.now().strftime('%Y_%m_%d')}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@api_bp.route("/statements/download/csv", methods=["GET"])
@login_required
def download_statement_csv():
    account_id = request.args.get("account_id", type=int)
    if not account_id:
        acc = Account.query.filter_by(user_id=current_user.id).first()
        if acc:
            account_id = acc.id
        else:
            return jsonify({"success": False, "error": "No accounts found"}), 404

    _get_owned_account_or_403(account_id)

    preset = request.args.get("preset")
    s_date_str = request.args.get("date_from") or request.args.get("start_date")
    e_date_str = request.args.get("date_to") or request.args.get("end_date")

    s_date = datetime.strptime(s_date_str, "%Y-%m-%d").date() if s_date_str else None
    e_date = datetime.strptime(e_date_str, "%Y-%m-%d").date() if e_date_str else None

    csv_data = statement_service.export_statement_csv(
        account_id=account_id,
        start_date=s_date,
        end_date=e_date,
        transaction_type=request.args.get("type"),
        status=request.args.get("status"),
        mode=request.args.get("mode"),
        search=request.args.get("search"),
        preset=preset
    )

    filename = f"transaction_history_{datetime.now().strftime('%Y_%m_%d')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@api_bp.route("/statements/download/excel", methods=["GET"])
@login_required
def download_statement_excel():
    account_id = request.args.get("account_id", type=int)
    if not account_id:
        acc = Account.query.filter_by(user_id=current_user.id).first()
        if acc:
            account_id = acc.id
        else:
            return jsonify({"success": False, "error": "No accounts found"}), 404

    _get_owned_account_or_403(account_id)

    preset = request.args.get("preset")
    s_date_str = request.args.get("date_from") or request.args.get("start_date")
    e_date_str = request.args.get("date_to") or request.args.get("end_date")

    s_date = datetime.strptime(s_date_str, "%Y-%m-%d").date() if s_date_str else None
    e_date = datetime.strptime(e_date_str, "%Y-%m-%d").date() if e_date_str else None

    xlsx_bytes = statement_service.export_statement_xlsx(
        account_id=account_id,
        start_date=s_date,
        end_date=e_date,
        transaction_type=request.args.get("type"),
        status=request.args.get("status"),
        mode=request.args.get("mode"),
        search=request.args.get("search"),
        preset=preset
    )

    filename = f"account_statement_{datetime.now().strftime('%Y_%m_%d')}.xlsx"
    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )



@api_bp.route("/transactions/deposit", methods=["POST"])
@api_bp.route("/v1/transactions/deposit", methods=["POST"])
@login_required
@json_errors
@rate_limit(limit=10, window_seconds=60, key_prefix="api_deposit")
def api_deposit():
    data = request.get_json(force=True) or {}
    account = _get_owned_account_or_403(data.get("account_id"))
    txn = banking_service.deposit(account, data.get("amount"), data.get("description", ""), current_user.id)
    return jsonify(txn.to_dict()), 201


@api_bp.route("/transactions/withdraw", methods=["POST"])
@api_bp.route("/v1/transactions/withdraw", methods=["POST"])
@login_required
@json_errors
@rate_limit(limit=10, window_seconds=60, key_prefix="api_withdraw")
def api_withdraw():
    data = request.get_json(force=True) or {}
    account = _get_owned_account_or_403(data.get("account_id"))
    try:
        txn = banking_service.withdraw(account, data.get("amount"), data.get("description", ""), current_user.id)
    except banking_service.InsufficientBalanceError as e:
        return jsonify(error=str(e)), 422
    return jsonify(txn.to_dict()), 201


@api_bp.route("/transactions/transfer", methods=["POST"])
@api_bp.route("/v1/transactions/transfer", methods=["POST"])
@login_required
@json_errors
@rate_limit(limit=10, window_seconds=60, key_prefix="api_transfer")
def api_transfer():
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    amount_raw = data.get("amount")
    try:
        amount_num = float(amount_raw) if amount_raw is not None else 0.0
    except (ValueError, TypeError):
        amount_num = 0.0

    # 1. Idempotency Check (24-Hour Cache Lookup)
    idempotency_key = request.headers.get("X-Idempotency-Key") or data.get("idempotency_key")
    if idempotency_key:
        cached_txn = fraud_prevention_service.check_idempotency(current_user.id, idempotency_key)
        if cached_txn:
            return jsonify(cached_txn), 200

    source = _get_owned_account_or_403(data.get("source_account_id"))

    dest_val = data.get("destination_account_id") or data.get("destination_account_number")
    beneficiary_id = data.get("beneficiary_id")
    destination = None

    if beneficiary_id:
        from app.models.beneficiary import Beneficiary, BeneficiaryStatus
        bene = Beneficiary.query.filter_by(id=beneficiary_id, user_id=current_user.id).first()
        if not bene:
            return jsonify(error="Beneficiary not found or unauthorized"), 404
        if bene.status != BeneficiaryStatus.ACTIVE:
            return jsonify(error="Selected beneficiary is inactive"), 400
        destination = Account.query.filter_by(account_number=bene.account_number).first()
    elif dest_val:
        dest_str = str(dest_val).strip()
        if dest_str.isdigit() and len(dest_str) < 9:
            destination = db.session.get(Account, int(dest_str))
        if not destination:
            destination = Account.query.filter_by(account_number=dest_str).first()

    if not destination:
        return jsonify(error="Destination account not found"), 404

    if destination.status != "ACTIVE":
        return jsonify(error="Destination account is inactive"), 400

    # 2. Behavioral Anomaly Risk Engine & Step-Up MFA Evaluation
    risk_res = risk_service.evaluate_transaction_risk(source, Decimal(str(amount_num)), destination.id if destination else None)
    step_up_token = request.headers.get("X-Step-Up-Token") or data.get("step_up_token")
    current_token = request.cookies.get("session_token")

    requires_step_up = (amount_num >= 50000.0) or (risk_res.get("action_taken") in ("STEP_UP_ENFORCED", "HOLD_AND_REVOKE")) or (risk_res.get("risk_score", 0) >= 60)

    if requires_step_up:
        if not step_up_token or not mfa_service.validate_and_consume_step_up_token(current_user.id, step_up_token, current_token):
            return jsonify({
                "error": "Step-Up Authentication Required",
                "message": "Transactions of ₹50,000 or greater or elevated behavioral risk require step-up MFA verification.",
                "step_up_required": True,
                "risk_score": risk_res.get("risk_score", 0),
                "risk_factors": risk_res.get("risk_factors", [])
            }), 403

    # 3. 120-Second Duplicate Transaction Suppression
    if not idempotency_key and amount_num > 0:
        if fraud_prevention_service.check_duplicate_transaction(source.id, destination.id, Decimal(str(amount_num)), data.get("description", "Funds Transfer")):
            fraud_prevention_service.create_fraud_alert(
                current_user.id, "DUPLICATE_ATTEMPT", "MEDIUM",
                {"source_account_id": source.id, "destination_account_id": destination.id, "amount": amount_num}
            )
            return jsonify({
                "error": "Duplicate Transaction Detected",
                "message": "An identical transfer was executed within the last 120 seconds. Provide an X-Idempotency-Key header to confirm intentional retries.",
                "duplicate": True
            }), 409

    # 4. Mule Account Intelligence Check
    if destination and fraud_prevention_service.check_mule_beneficiary(destination.id):
        fraud_prevention_service.create_fraud_alert(
            current_user.id, "MULE_ACCOUNT_SUSPECT", "HIGH",
            {"destination_account_id": destination.id, "amount": amount_num}
        )

    try:
        debit, credit = banking_service.transfer(
            source, destination, data.get("amount"), data.get("description", "Funds Transfer"), current_user.id,
            idempotency_key=idempotency_key
        )
    except banking_service.InsufficientBalanceError as e:
        return jsonify(error=str(e)), 422
    except ValidationError as e:
        return jsonify(error=str(e)), 400
    except Exception:
        return jsonify(error="Transaction failed to process securely"), 500

    if credit is None:
        # High risk transaction flagged for review
        return jsonify(
            message="Transfer flagged by risk security engine and pending admin approval",
            debit=debit.to_dict(),
            status="BLOCKED_FOR_REVIEW"
        ), 202

    return jsonify(debit=debit.to_dict(), credit=credit.to_dict()), 201



@api_bp.route("/transactions/<int:txn_id>/reverse", methods=["POST"])
@api_bp.route("/v1/transactions/<int:txn_id>/reverse", methods=["POST"])
@login_required
@roles_required(Role.EMPLOYEE, Role.ADMIN)
@json_errors
def api_reverse(txn_id):
    original = Transaction.query.get_or_404(txn_id)
    reason = (request.get_json(silent=True) or {}).get("reason", "Manual correction")
    reversal = banking_service.reverse_transaction(original, current_user.id, reason)
    return jsonify(reversal.to_dict()), 201


@api_bp.route("/transactions/<int:txn_id>/receipt", methods=["GET"])
@api_bp.route("/v1/transactions/<int:txn_id>/receipt", methods=["GET"])
@login_required
def get_transaction_receipt(txn_id):
    txn = Transaction.query.get_or_404(txn_id)
    if current_user.role == Role.CUSTOMER:
        owned_ids = [a.id for a in Account.query.filter_by(user_id=current_user.id).all()]
        if txn.account_id not in owned_ids and txn.counterparty_account_id not in owned_ids:
            from flask import abort
            abort(403)
    account = db.session.get(Account, txn.account_id)
    counterparty = db.session.get(Account, txn.counterparty_account_id) if txn.counterparty_account_id else None

    return jsonify({
        "reference_number": txn.reference_number,
        "transaction_type": txn.transaction_type,
        "amount": str(txn.amount),
        "status": txn.status,
        "description": txn.description,
        "created_at": txn.created_at.isoformat() if txn.created_at else None,
        "account_number": account.account_number,
        "account_type": account.account_type,
        "balance_after": str(txn.balance_after) if txn.balance_after else None,
        "counterparty_account": counterparty.account_number if counterparty else None,
    })


# ---------------------------------------------------------------------------
# Beneficiaries
# ---------------------------------------------------------------------------
@api_bp.route("/beneficiaries", methods=["GET"])
@api_bp.route("/v1/beneficiaries", methods=["GET"])
@login_required
@json_errors
def list_beneficiaries():
    q = request.args.get("q", "").strip().lower()
    query = Beneficiary.query.filter_by(user_id=current_user.id)
    if q:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                Beneficiary.name.ilike(f"%{q}%"),
                Beneficiary.bank_name.ilike(f"%{q}%"),
                Beneficiary.account_number.ilike(f"%{q}%"),
                Beneficiary.ifsc.ilike(f"%{q}%"),
            )
        )
    beneficiaries = query.order_by(Beneficiary.created_at.desc()).all()
    return jsonify([b.to_dict() for b in beneficiaries])


@api_bp.route("/beneficiaries/<int:beneficiary_id>", methods=["GET"])
@api_bp.route("/v1/beneficiaries/<int:beneficiary_id>", methods=["GET"])
@login_required
@json_errors
def get_beneficiary(beneficiary_id):
    beneficiary = _get_owned_beneficiary_or_403(beneficiary_id)
    return jsonify(beneficiary.to_dict())


@api_bp.route("/beneficiaries", methods=["POST"])
@api_bp.route("/v1/beneficiaries", methods=["POST"])
@login_required
@json_errors
def api_add_beneficiary():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    beneficiary = beneficiary_service.add_beneficiary(current_user.id, data)
    return jsonify(beneficiary.to_dict()), 201


@api_bp.route("/beneficiaries/<int:beneficiary_id>", methods=["PUT", "PATCH"])
@api_bp.route("/v1/beneficiaries/<int:beneficiary_id>", methods=["PUT", "PATCH"])
@login_required
@json_errors
def api_update_beneficiary(beneficiary_id):
    beneficiary = _get_owned_beneficiary_or_403(beneficiary_id)
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    updated = beneficiary_service.update_beneficiary(beneficiary, data, current_user.id)
    return jsonify(updated.to_dict())


@api_bp.route("/beneficiaries/<int:beneficiary_id>", methods=["DELETE"])
@api_bp.route("/v1/beneficiaries/<int:beneficiary_id>", methods=["DELETE"])
@login_required
@json_errors
def api_delete_beneficiary(beneficiary_id):
    beneficiary = _get_owned_beneficiary_or_403(beneficiary_id)
    deactivated = beneficiary_service.deactivate_beneficiary(beneficiary, current_user.id)
    return jsonify({"message": "Beneficiary deleted successfully", "beneficiary": deactivated.to_dict()})



# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------
@api_bp.route("/versions", methods=["GET"])
@api_bp.route("/v1/versions", methods=["GET"])
@login_required
def list_versions():
    query = EntityVersion.query
    entity_type = request.args.get("entity_type")
    changed_by = request.args.get("changed_by", type=int)
    action = request.args.get("change_type")

    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if changed_by:
        query = query.filter_by(changed_by=changed_by)
    if action:
        query = query.filter_by(change_type=action)

    if current_user.role == Role.CUSTOMER:
        query = query.filter_by(changed_by=current_user.id)

    versions = query.order_by(EntityVersion.created_at.desc()).limit(500).all()
    return jsonify([v.to_dict() for v in versions])


@api_bp.route("/versions/<entity_type>/<int:entity_id>", methods=["GET"])
@api_bp.route("/v1/versions/<entity_type>/<int:entity_id>", methods=["GET"])
@login_required
def entity_version_history(entity_type, entity_id):
    _validate_entity_ownership_for_customer(entity_type, entity_id)
    history = version_service.get_history(entity_type.upper(), entity_id)
    return jsonify([v.to_dict() for v in history])


@api_bp.route("/versions/compare", methods=["GET"])
@api_bp.route("/v1/versions/compare", methods=["GET"])
@login_required
@json_errors
def compare_versions():
    entity_type = request.args.get("entity_type", "").upper()
    entity_id = request.args.get("entity_id", type=int)
    v1 = request.args.get("v1", type=int)
    v2 = request.args.get("v2", type=int)

    if not all([entity_type, entity_id, v1, v2]):
        raise ValidationError("entity_type, entity_id, v1, and v2 are all required")

    _validate_entity_ownership_for_customer(entity_type, entity_id)

    try:
        result = version_service.diff_versions(entity_type, entity_id, v1, v2)
    except ValueError as e:
        return jsonify(error=str(e)), 404
    return jsonify(result)


@api_bp.route("/versions/restore", methods=["POST"])
@api_bp.route("/v1/versions/restore", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def restore_version_api():
    data = request.get_json(force=True) or {}
    entity_type = data.get("entity_type", "").upper()
    entity_id = int(data.get("entity_id", 0))
    version_number = int(data.get("version_number", 0))

    if entity_type == "TRANSACTION":
        return jsonify({"error": "Transactions cannot be restored; use a reversal transaction instead"}), 400

    if entity_type == "BENEFICIARY":
        b = db.session.get(Beneficiary, entity_id)
        if not b:
            return jsonify({"error": "Beneficiary not found"}), 404
        def apply_fn(snap):
            if not snap: return {}
            b.name = snap.get("name", b.name)
            b.account_number = snap.get("account_number", b.account_number)
            b.bank_name = snap.get("bank_name", b.bank_name)
            b.ifsc_code = snap.get("ifsc_code", b.ifsc_code)
            b.status = snap.get("status", b.status)
            return snap
    elif entity_type in ["USER_PROFILE", "USER"]:
        u = db.session.get(User, entity_id)
        if not u:
            return jsonify({"error": "User not found"}), 404
        def apply_fn(snap):
            if not snap: return {}
            u.full_name = snap.get("full_name", u.full_name)
            u.email = snap.get("email", u.email)
            u.phone = snap.get("phone", u.phone)
            return snap
    else:
        return jsonify({"error": f"Restoration for entity type '{entity_type}' is not supported"}), 400

    try:
        new_version = version_service.restore_version(
            entity_type=entity_type,
            entity_id=entity_id,
            version_number=version_number,
            changed_by=current_user.id,
            apply_fn=apply_fn
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

    return jsonify({"success": True, "new_version": new_version.to_dict()})


# ---------------------------------------------------------------------------
# Audit Logs & Integrity Verification
# ---------------------------------------------------------------------------
@api_bp.route("/audit-logs", methods=["GET"])
@api_bp.route("/v1/audit-logs", methods=["GET"])
@login_required
@roles_required(Role.EMPLOYEE, Role.ADMIN)
def list_audit_logs():
    query = AuditLog.query
    action = request.args.get("action")
    user_id = request.args.get("user_id", type=int)
    if action:
        query = query.filter_by(action=action)
    if user_id:
        query = query.filter_by(user_id=user_id)
    logs = query.order_by(AuditLog.created_at.desc()).limit(500).all()
    return jsonify([l.to_dict() for l in logs])


@api_bp.route("/audit/verify-integrity", methods=["POST", "GET"])
@api_bp.route("/v1/audit/verify-integrity", methods=["POST", "GET"])
@api_bp.route("/audit/verify", methods=["POST", "GET"])
@api_bp.route("/v1/audit/verify", methods=["POST", "GET"])
@login_required
@roles_required(Role.ADMIN)
def verify_audit_chain():
    report = audit_service.verify_audit_integrity()
    return jsonify(report)


# ---------------------------------------------------------------------------
# Maker-Checker Rollback Requests & Risk Management
# ---------------------------------------------------------------------------
@api_bp.route("/rollback-requests", methods=["GET"])
@api_bp.route("/v1/rollback-requests", methods=["GET"])
@login_required
def list_rollback_requests():
    query = RollbackRequest.query
    if current_user.role == Role.CUSTOMER:
        query = query.filter_by(requested_by=current_user.id)
    requests_list = query.order_by(RollbackRequest.created_at.desc()).all()
    return jsonify([r.to_dict() for r in requests_list])


@api_bp.route("/rollback-requests", methods=["POST"])
@api_bp.route("/v1/rollback-requests", methods=["POST"])
@login_required
@json_errors
def create_rollback_request():
    data = request.get_json(force=True) or {}
    entity_type = data.get("entity_type")
    entity_id = int(data["entity_id"]) if data.get("entity_id") is not None else None
    target_version = int(data["target_version"]) if data.get("target_version") is not None else None
    reason = data.get("reason", "Requested via API")

    _validate_entity_ownership_for_customer(entity_type, entity_id)

    req = approval_service.request_rollback(
        user_id=current_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        target_version=target_version,
        reason=reason
    )
    return jsonify(req.to_dict()), 201


@api_bp.route("/rollback-requests/<int:req_id>/approve", methods=["POST"])
@api_bp.route("/v1/rollback-requests/<int:req_id>/approve", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def approve_rollback(req_id):
    data = request.get_json(silent=True) or {}
    notes = data.get("review_notes", "Approved by Admin")
    req = approval_service.approve_rollback_request(req_id, current_user.id, notes)
    return jsonify(req.to_dict())


@api_bp.route("/rollback-requests/<int:req_id>/reject", methods=["POST"])
@api_bp.route("/v1/rollback-requests/<int:req_id>/reject", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def reject_rollback(req_id):
    data = request.get_json(silent=True) or {}
    notes = data.get("review_notes", "Rejected by Admin")
    req = approval_service.reject_rollback_request(req_id, current_user.id, notes)
    return jsonify(req.to_dict())


@api_bp.route("/risk/assessments", methods=["GET"])
@api_bp.route("/v1/risk/assessments", methods=["GET"])
@login_required
@roles_required(Role.EMPLOYEE, Role.ADMIN)
def list_risk_assessments():
    assessments = RiskAssessment.query.order_by(RiskAssessment.created_at.desc()).limit(200).all()
    return jsonify([a.to_dict() for a in assessments])


@api_bp.route("/risk/assessments/<int:assessment_id>/review", methods=["POST"])
@api_bp.route("/v1/risk/assessments/<int:assessment_id>/review", methods=["POST"])
@login_required
@roles_required(Role.EMPLOYEE, Role.ADMIN)
@json_errors
def review_risk(assessment_id):
    data = request.get_json(force=True) or {}
    approve = data.get("approve", True)
    notes = data.get("notes", "")
    res = approval_service.review_risk_assessment(assessment_id, current_user.id, approve, notes)
    return jsonify(res.to_dict())


# ---------------------------------------------------------------------------
# Sessions & MFA / OTP Security
# ---------------------------------------------------------------------------
@api_bp.route("/sessions", methods=["GET"])
@api_bp.route("/v1/sessions", methods=["GET"])
@login_required
def list_user_sessions():
    sessions_list = LoginSession.query.filter_by(user_id=current_user.id, is_active=True).all()
    return jsonify([s.to_dict() for s in sessions_list])


@api_bp.route("/sessions/revoke-others", methods=["POST"])
@api_bp.route("/v1/sessions/revoke-others", methods=["POST"])
@login_required
def revoke_other_user_sessions():
    current_token = request.cookies.get("session_token", "")
    count = session_service.revoke_other_sessions(current_user.id, current_token)
    return jsonify(message=f"Revoked {count} other active session(s)", count=count)


@api_bp.route("/sessions/<int:session_id>/revoke", methods=["POST"])
@api_bp.route("/v1/sessions/<int:session_id>/revoke", methods=["POST"])
@login_required
@json_errors
def revoke_specific_session(session_id):
    sess = db.session.get(LoginSession, session_id)
    if not sess:
        return jsonify(error="Session not found"), 404
    if current_user.role != Role.ADMIN and sess.user_id != current_user.id:
        return jsonify(error="Forbidden: Cannot revoke another user's session"), 403

    success = session_service.revoke_session_by_id(session_id, current_user.id)
    if not success:
        return jsonify(error="Session is already inactive or invalid"), 400
    return jsonify(message=f"Session #{session_id} successfully revoked", session_id=session_id)


@api_bp.route("/users/<int:user_id>/toggle-lockout", methods=["POST"])
@api_bp.route("/v1/users/<int:user_id>/toggle-lockout", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def toggle_user_lockout_api(user_id):
    try:
        res = session_service.toggle_user_lockout(user_id, current_user.id)
    except ValueError as e:
        return jsonify(error=str(e)), 404
    return jsonify(res)


@api_bp.route("/security/events", methods=["GET"])
@api_bp.route("/v1/security/events", methods=["GET"])
@login_required
@roles_required(Role.ADMIN)
def get_security_events():
    severity = request.args.get("severity")
    query = SecurityEvent.query
    if severity and severity.upper() != "ALL":
        query = query.filter_by(severity=severity.upper())
    events = query.order_by(SecurityEvent.created_at.desc()).limit(200).all()
    return jsonify([e.to_dict() for e in events])


@api_bp.route("/mfa/generate", methods=["POST"])
@api_bp.route("/v1/mfa/generate", methods=["POST"])
@login_required
@json_errors
def generate_mfa_otp():
    data = request.get_json(silent=True) or {}
    action_type = data.get("action_type", "BENEFICIARY_ADD")
    code = mfa_service.generate_otp(current_user.id, action_type)
    return jsonify(message=f"OTP generated for {action_type}", demo_otp=code)


@api_bp.route("/mfa/verify", methods=["POST"])
@api_bp.route("/v1/mfa/verify", methods=["POST"])
@login_required
@json_errors
def verify_mfa_otp():
    data = request.get_json(force=True) or {}
    action_type = data.get("action_type", "BENEFICIARY_ADD")
    code = data.get("otp_code", "")
    try:
        mfa_service.verify_otp(current_user.id, action_type, code)
    except mfa_service.OTPError as e:
        return jsonify(error=str(e)), 400
    return jsonify(status="OTP verified successfully")


@api_bp.route("/mfa/step-up-challenge", methods=["POST"])
@api_bp.route("/v1/mfa/step-up-challenge", methods=["POST"])
@login_required
@json_errors
def step_up_challenge():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    action_type = data.get("action_type", "HIGH_VALUE_TRANSFER")
    code = mfa_service.generate_otp(current_user.id, action_type)
    return jsonify({
        "message": f"Step-Up OTP generated for {action_type}",
        "action_type": action_type,
        "demo_otp": code
    })


@api_bp.route("/mfa/verify-step-up", methods=["POST"])
@api_bp.route("/v1/mfa/verify-step-up", methods=["POST"])
@login_required
@json_errors
def verify_step_up_otp():
    data = request.get_json(force=True) or {}
    action_type = data.get("action_type", "HIGH_VALUE_TRANSFER")
    code = data.get("otp_code", "")
    try:
        mfa_service.verify_otp(current_user.id, action_type, code)
    except mfa_service.OTPError as e:
        return jsonify(error=str(e)), 400

    current_sess_token = request.cookies.get("session_token")
    step_up_token = mfa_service.issue_step_up_token_for_user(current_user.id, session_token=current_sess_token, ttl_minutes=5)
    return jsonify({
        "status": "Step-Up verification successful",
        "step_up_token": step_up_token,
        "expires_in_seconds": 300
    })


@api_bp.route("/sessions/active", methods=["GET"])
@api_bp.route("/v1/sessions/active", methods=["GET"])
@login_required
def active_sessions_api():
    sessions_list = session_service.get_user_active_sessions(current_user.id)
    return jsonify({"success": True, "sessions": sessions_list})


@api_bp.route("/sessions/revoke", methods=["POST"])
@api_bp.route("/v1/sessions/revoke", methods=["POST"])
@login_required
@json_errors
def revoke_session_by_token_or_id():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    token = data.get("session_token")
    sess_id = data.get("session_id")

    if token:
        success = session_service.revoke_session_by_token(token, current_user.id)
    elif sess_id:
        success = session_service.revoke_session_by_id(int(sess_id), current_user.id)
    else:
        return jsonify(error="session_token or session_id is required"), 400

    if not success:
        return jsonify(error="Session not found or already inactive"), 404
    return jsonify(message="Session successfully revoked")


@api_bp.route("/security/risk-profile", methods=["GET"])
@api_bp.route("/v1/security/risk-profile", methods=["GET"])
@login_required
def get_user_risk_profile():
    from app.models.behavioral_profile import UserBehavioralProfile
    profile = UserBehavioralProfile.get_or_create(current_user.id)
    return jsonify({"success": True, "profile": profile.to_dict()})


@api_bp.route("/admin/behavioral-anomalies", methods=["GET"])
@api_bp.route("/v1/admin/behavioral-anomalies", methods=["GET"])
@login_required
def get_admin_behavioral_anomalies():
    if current_user.role != Role.ADMIN:
        return jsonify(error="Forbidden: Admin access required"), 403
    from app.models.workflow_risk import RiskAssessment, RiskLevel
    assessments = RiskAssessment.query.filter(
        RiskAssessment.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL])
    ).order_by(RiskAssessment.created_at.desc()).limit(50).all()
    return jsonify({"success": True, "anomalies": [a.to_dict() for a in assessments]})


@api_bp.route("/admin/fraud/alerts", methods=["GET"])
@api_bp.route("/v1/admin/fraud/alerts", methods=["GET"])
@login_required
def get_admin_fraud_alerts():
    if current_user.role != Role.ADMIN:
        return jsonify(error="Forbidden: Admin access required"), 403

    from app.models.fraud_alert import FraudAlert
    status_filter = request.args.get("status")
    severity_filter = request.args.get("severity")

    query = FraudAlert.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if severity_filter:
        query = query.filter_by(severity=severity_filter)

    alerts = query.order_by(FraudAlert.created_at.desc()).limit(100).all()
    return jsonify({"success": True, "alerts": [a.to_dict() for a in alerts]})


@api_bp.route("/admin/fraud/alerts/<int:alert_id>/resolve", methods=["POST"])
@api_bp.route("/v1/admin/fraud/alerts/<int:alert_id>/resolve", methods=["POST"])
@login_required
@json_errors
def resolve_admin_fraud_alert(alert_id):
    if current_user.role != Role.ADMIN:
        return jsonify(error="Forbidden: Admin access required"), 403

    data = request.get_json(force=True) or {}
    decision = data.get("decision", "DISMISSED")  # CONFIRMED_FRAUD or DISMISSED
    resolution_notes = data.get("resolution_notes", "")
    lock_account = bool(data.get("lock_account", False))

    try:
        alert = fraud_prevention_service.resolve_fraud_alert(
            alert_id=alert_id,
            decision=decision,
            actor_id=current_user.id,
            resolution_notes=resolution_notes,
            lock_account=lock_account
        )
    except ValueError as e:
        return jsonify(error=str(e)), 404

    return jsonify({"success": True, "message": f"Fraud alert #{alert_id} resolved as {alert.status}", "alert": alert.to_dict()})


# ---------------------------------------------------------------------------
# Smart Statements CSV Export
# ---------------------------------------------------------------------------
@api_bp.route("/statements/export", methods=["GET"])
@api_bp.route("/v1/statements/export", methods=["GET"])
@login_required
def export_statement_csv():
    account_id = request.args.get("account_id", type=int)
    if account_id:
        account = _get_owned_account_or_403(account_id)
        txns = Transaction.query.filter_by(account_id=account.id).order_by(Transaction.created_at.asc()).all()
    else:
        owned_ids = [a.id for a in Account.query.filter_by(user_id=current_user.id).all()]
        txns = Transaction.query.filter(Transaction.account_id.in_(owned_ids)).order_by(Transaction.created_at.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Reference Number", "Date", "Type", "Amount", "Status", "Description", "Balance After"])

    for t in txns:
        writer.writerow([
            t.reference_number,
            t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
            t.transaction_type,
            str(t.amount),
            t.status,
            t.description,
            str(t.balance_after) if t.balance_after else ""
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=account_statement.csv"}
    )


# ---------------------------------------------------------------------------
# Profile & Security
# ---------------------------------------------------------------------------
@api_bp.route("/profile", methods=["GET"])
@api_bp.route("/v1/profile", methods=["GET"])
@login_required
def get_current_profile():
    data = current_user.to_dict(include_email=True)
    data["phone"] = current_user.phone
    data["failed_login_attempts"] = current_user.failed_login_attempts
    data["last_login_at"] = current_user.last_login_at.isoformat() if current_user.last_login_at else None
    return jsonify(data)


@api_bp.route("/profile", methods=["PUT"])
@api_bp.route("/v1/profile", methods=["PUT"])
@login_required
@json_errors
def update_current_profile():
    from app.services import auth_service
    data = request.get_json(force=True) or {}
    user = auth_service.update_profile(
        current_user,
        full_name=data.get("full_name"),
        phone=data.get("phone"),
        email=data.get("email"),
    )
    res = user.to_dict(include_email=True)
    res["phone"] = user.phone
    return jsonify(res)


@api_bp.route("/security/change-password", methods=["POST"])
@api_bp.route("/v1/security/change-password", methods=["POST"])
@login_required
@json_errors
def api_change_password():
    from app.services import auth_service
    data = request.get_json(force=True) or {}
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")
    try:
        auth_service.change_password(current_user, old_password, new_password)
    except auth_service.AuthError as e:
        return jsonify(error=str(e)), 400
    return jsonify(status="Password changed successfully")


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
@api_bp.route("/notifications", methods=["GET"])
@api_bp.route("/v1/notifications", methods=["GET"])
@login_required
def get_notifications():
    from app.models.notification import Notification
    notes = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({
        "notifications": [n.to_dict() for n in notes],
        "unread_count": unread_count,
    })


@api_bp.route("/notifications/<int:note_id>/read", methods=["POST"])
@api_bp.route("/v1/notifications/<int:note_id>/read", methods=["POST"])
@login_required
def mark_notification_read(note_id):
    from app.models.notification import Notification
    note = Notification.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    note.is_read = True
    db.session.commit()
    return jsonify(status="marked as read")


@api_bp.route("/notifications/read-all", methods=["POST"])
@api_bp.route("/v1/notifications/read-all", methods=["POST"])
@login_required
def mark_all_notifications_read():
    from app.models.notification import Notification
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify(status="all marked as read")


# ---------------------------------------------------------------------------
# Spending Analytics
# ---------------------------------------------------------------------------
@api_bp.route("/analytics", methods=["GET"])
@api_bp.route("/v1/analytics", methods=["GET"])
@login_required
def get_analytics():
    from decimal import Decimal
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    account_ids = [a.id for a in accounts]

    if not account_ids:
        return jsonify({
            "total_income": "0.00",
            "total_expenses": "0.00",
            "transfers_volume": "0.00",
            "net_balance_change": "0.00",
            "monthly_labels": [],
            "monthly_income": [],
            "monthly_expenses": [],
            "breakdown": {"DEPOSIT": 0, "WITHDRAWAL": 0, "TRANSFER": 0},
            "recent_activity_count": 0,
        })

    txns = (
        Transaction.query
        .filter(Transaction.account_id.in_(account_ids))
        .filter(Transaction.status == "COMPLETED")
        .order_by(Transaction.created_at.asc())
        .all()
    )

    income = Decimal("0.00")
    expenses = Decimal("0.00")
    transfers = Decimal("0.00")
    type_counts = {"DEPOSIT": 0, "WITHDRAWAL": 0, "TRANSFER": 0, "REVERSAL": 0}

    monthly_data = {}

    for t in txns:
        amt = Decimal(str(t.amount))
        t_type = t.transaction_type
        type_counts[t_type] = type_counts.get(t_type, 0) + 1

        m_key = t.created_at.strftime("%b %Y") if t.created_at else "Recent"
        if m_key not in monthly_data:
            monthly_data[m_key] = {"income": Decimal("0.00"), "expenses": Decimal("0.00")}

        if t_type == "DEPOSIT":
            income += amt
            monthly_data[m_key]["income"] += amt
        elif t_type == "WITHDRAWAL":
            expenses += amt
            monthly_data[m_key]["expenses"] += amt
        elif t_type == "TRANSFER":
            expenses += amt
            transfers += amt
            monthly_data[m_key]["expenses"] += amt
        elif t_type == "REVERSAL":
            income += amt

    monthly_labels = list(monthly_data.keys())[-6:] if monthly_data else ["Current"]
    monthly_inc = [float(monthly_data[k]["income"]) for k in monthly_labels] if monthly_data else [float(income)]
    monthly_exp = [float(monthly_data[k]["expenses"]) for k in monthly_labels] if monthly_data else [float(expenses)]

    return jsonify({
        "total_income": str(income),
        "total_expenses": str(expenses),
        "transfers_volume": str(transfers),
        "net_balance_change": str(income - expenses),
        "monthly_labels": monthly_labels,
        "monthly_income": monthly_inc,
        "monthly_expenses": monthly_exp,
        "breakdown": type_counts,
        "recent_activity_count": len(txns),
    })


# ---------------------------------------------------------------------------
# Ownership helpers
# ---------------------------------------------------------------------------
def _get_owned_account_or_403(account_id):
    account = Account.query.get_or_404(account_id)
    if current_user.role == Role.CUSTOMER and account.user_id != current_user.id:
        try:
            from app.services import audit_service
            from app.models.audit_log import AuditAction
            audit_service.log_action(
                action=AuditAction.ACCESS_DENIED,
                user_id=current_user.id,
                description=f"IDOR attempt by '{current_user.username}' on Account #{account_id}"
            )
        except Exception:
            pass
        from flask import abort
        abort(403)
    return account


def _get_owned_beneficiary_or_403(beneficiary_id):
    beneficiary = Beneficiary.query.get_or_404(beneficiary_id)
    if beneficiary.user_id != current_user.id:
        try:
            from app.services import audit_service
            from app.models.audit_log import AuditAction
            audit_service.log_action(
                action=AuditAction.ACCESS_DENIED,
                user_id=current_user.id,
                description=f"IDOR attempt by '{current_user.username}' on Beneficiary #{beneficiary_id}"
            )
        except Exception:
            pass
        from flask import abort
        abort(403)
    return beneficiary


def _validate_entity_ownership_for_customer(entity_type, entity_id):
    if current_user.role == Role.CUSTOMER:
        et = (entity_type or "").upper()
        if et in ("USER_PROFILE", "CUSTOMER", "USER"):
            if entity_id != current_user.id:
                try:
                    from app.services import audit_service
                    from app.models.audit_log import AuditAction
                    audit_service.log_action(
                        action=AuditAction.ACCESS_DENIED,
                        user_id=current_user.id,
                        description=f"IDOR attempt by '{current_user.username}' on Profile #{entity_id}"
                    )
                except Exception:
                    pass
                from flask import abort
                abort(403)
        elif et == "ACCOUNT":
            _get_owned_account_or_403(entity_id)
        elif et == "BENEFICIARY":
            _get_owned_beneficiary_or_403(entity_id)
        else:
            from flask import abort
            abort(403)


# ---------------------------------------------------------------------------
# AI Banking Assistant Chat Endpoint
# ---------------------------------------------------------------------------
@api_bp.route("/ai/chat", methods=["POST"])
@login_required
def ai_chat():
    from app.services import ai_service
    
    # Verify request payload
    if request.is_json:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({
                "success": False,
                "error": "Invalid JSON format"
            }), 400
    else:
        data = request.form.to_dict()

    if not isinstance(data, dict) or "message" not in data:
        return jsonify({
            "success": False,
            "error": "Message content is required"
        }), 400

    raw_message = data.get("message")
    if raw_message is None or not str(raw_message).strip():
        return jsonify({
            "success": False,
            "error": "Message content is required"
        }), 400

    message = str(raw_message).strip()

    if len(message) > 500:
        return jsonify({
            "success": False,
            "error": "Message exceeds maximum allowed length of 500 characters"
        }), 400

    context = {
        "username": getattr(current_user, "username", "Customer"),
        "user_id": getattr(current_user, "id", None),
        "role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    }

    try:
        result = ai_service.generate_ai_response(message, user_context=context)
        return jsonify({
            "success": True,
            "reply": result.get("reply", ""),
            "mode": result.get("mode", "rule_engine")
        }), 200
    except Exception as err:
        return jsonify({
            "success": False,
            "error": "An error occurred while processing your request"
        }), 500


# ---------------------------------------------------------------------------
# Helpdesk Complaints, Service Requests & Documents API
# ---------------------------------------------------------------------------
@api_bp.route("/complaints", methods=["GET"])
@api_bp.route("/v1/complaints", methods=["GET"])
@login_required
def list_api_complaints():
    if current_user.role == Role.CUSTOMER:
        items = Complaint.query.filter_by(customer_id=current_user.id).order_by(Complaint.created_at.desc()).all()
    else:
        status_filter = request.args.get("status")
        query = Complaint.query
        if status_filter:
            query = query.filter_by(status=status_filter)
        items = query.order_by(Complaint.created_at.desc()).limit(200).all()
    return jsonify([c.to_dict() for c in items])


@api_bp.route("/complaints", methods=["POST"])
@api_bp.route("/v1/complaints", methods=["POST"])
@login_required
@json_errors
def create_api_complaint():
    import uuid
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    subject = data.get("subject", "").strip()
    description = data.get("description", "").strip()
    category = data.get("category", "GENERAL").strip()

    if not subject or not description:
        raise ValidationError("Subject and description are required")

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

    audit_service.log_action(
        action=AuditAction.ADMIN_ACTION,
        user_id=current_user.id,
        entity_type="COMPLAINT",
        entity_id=comp.id,
        description=f"Submitted complaint ticket #{ticket_num}"
    )

    return jsonify(comp.to_dict()), 201


@api_bp.route("/service-requests", methods=["GET"])
@api_bp.route("/v1/service-requests", methods=["GET"])
@login_required
def list_api_service_requests():
    if current_user.role == Role.CUSTOMER:
        items = ServiceRequest.query.filter_by(user_id=current_user.id).order_by(ServiceRequest.created_at.desc()).all()
    else:
        status_filter = request.args.get("status")
        query = ServiceRequest.query
        if status_filter:
            query = query.filter_by(status=status_filter)
        items = query.order_by(ServiceRequest.created_at.desc()).limit(200).all()
    return jsonify([s.to_dict() for s in items])


@api_bp.route("/service-requests/<int:req_id>/process", methods=["POST"])
@api_bp.route("/v1/service-requests/<int:req_id>/process", methods=["POST"])
@login_required
@roles_required(Role.EMPLOYEE, Role.ADMIN)
@json_errors
def process_api_service_request(req_id):
    data = request.get_json(force=True) or {}
    new_status = data.get("status", "").strip()
    notes = data.get("notes", "").strip()

    sr = db.session.get(ServiceRequest, req_id)
    if not sr:
        return jsonify(error="Service request ticket not found"), 404

    sr.status = new_status
    if notes:
        sr.admin_notes = notes
    db.session.commit()

    audit_service.log_action(
        action=AuditAction.SERVICE_REQUEST,
        user_id=current_user.id,
        entity_type="SERVICE_REQUEST",
        entity_id=sr.id,
        description=f"Processed service request #{sr.ticket_number} to {new_status}"
    )
    return jsonify(sr.to_dict())


@api_bp.route("/documents", methods=["GET"])
@api_bp.route("/v1/documents", methods=["GET"])
@login_required
def list_api_documents():
    if current_user.role == Role.CUSTOMER:
        docs = CustomerDocument.query.filter_by(user_id=current_user.id).order_by(CustomerDocument.created_at.desc()).all()
    else:
        status_filter = request.args.get("status")
        query = CustomerDocument.query
        if status_filter:
            query = query.filter_by(status=status_filter)
        docs = query.order_by(CustomerDocument.created_at.desc()).limit(200).all()
    return jsonify([d.to_dict() for d in docs])


@api_bp.route("/documents/<int:doc_id>/verify", methods=["POST"])
@api_bp.route("/v1/documents/<int:doc_id>/verify", methods=["POST"])
@login_required
@roles_required(Role.EMPLOYEE, Role.ADMIN)
@json_errors
def verify_api_document(doc_id):
    data = request.get_json(force=True) or {}
    new_status = data.get("status", DocumentStatus.VERIFIED).strip()
    notes = data.get("notes", "").strip()

    doc = db.session.get(CustomerDocument, doc_id)
    if not doc:
        return jsonify(error="Document not found"), 404

    doc.status = new_status
    if notes:
        doc.verification_notes = notes
    db.session.commit()

    audit_service.log_action(
        action=AuditAction.ADMIN_ACTION,
        user_id=current_user.id,
        entity_type="DOCUMENT",
        entity_id=doc.id,
        description=f"Verified document #{doc.id} status to {new_status}"
    )
    return jsonify(doc.to_dict())


# =========================================================================
# SOC & FRAUD INVESTIGATION REST API ENDPOINTS
# =========================================================================

@api_bp.route("/v1/admin/soc/dashboard", methods=["GET"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_soc_dashboard():
    from app.services import soc_service
    return jsonify(soc_service.get_soc_dashboard_metrics())


@api_bp.route("/v1/admin/soc/incidents", methods=["GET"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_list_incidents():
    from app.services import soc_service
    status_filter = request.args.get("status")
    severity_filter = request.args.get("severity")
    user_id = request.args.get("user_id", type=int)
    search = request.args.get("search")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    return jsonify(soc_service.get_incidents(
        status=status_filter,
        severity=severity_filter,
        user_id=user_id,
        search=search,
        page=page,
        per_page=per_page
    ))


@api_bp.route("/v1/admin/soc/incidents", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_create_incident():
    from app.services import soc_service
    data = request.get_json(force=True) or {}
    title = data.get("title")
    description = data.get("description")
    severity = data.get("severity", "MEDIUM")
    user_id = data.get("user_id")
    alert_ids = data.get("alert_ids")

    incident = soc_service.create_incident(
        title=title,
        description=description,
        severity=severity,
        user_id=user_id,
        alert_ids=alert_ids,
        actor_id=current_user.id
    )
    return jsonify(incident.to_dict()), 201


@api_bp.route("/v1/admin/soc/incidents/<int:inc_id>", methods=["GET"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_get_incident(inc_id):
    from app.services import soc_service
    return jsonify(soc_service.get_incident_detail(inc_id))


@api_bp.route("/v1/admin/soc/incidents/<int:inc_id>/update-status", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_update_incident_status(inc_id):
    from app.services import soc_service
    data = request.get_json(force=True) or {}
    new_status = data.get("status")
    notes = data.get("resolution_notes", data.get("notes", "Status updated by admin"))

    incident = soc_service.update_incident_status(inc_id, new_status, notes, current_user.id)
    return jsonify(incident.to_dict())


@api_bp.route("/v1/admin/soc/incidents/<int:inc_id>/assign", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_assign_incident(inc_id):
    from app.services import soc_service
    data = request.get_json(force=True) or {}
    admin_id = data.get("assigned_admin_id", current_user.id)

    incident = soc_service.assign_incident(inc_id, admin_id, current_user.id)
    return jsonify(incident.to_dict())


@api_bp.route("/v1/admin/soc/user-timeline/<int:user_id>", methods=["GET"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_get_user_timeline(user_id):
    from app.services import soc_service
    return jsonify(soc_service.get_user_timeline(user_id))


@api_bp.route("/v1/admin/soc/accounts/<int:account_id>/freeze", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_freeze_account(account_id):
    from app.services import mfa_service, soc_service

    step_up_token = request.headers.get("X-Step-Up-Token") or (request.get_json(silent=True) or {}).get("step_up_token")
    session_token = request.cookies.get("session_token")
    if not step_up_token or not mfa_service.validate_and_consume_step_up_token(current_user.id, step_up_token, session_token):
        return jsonify({
            "error": "Step-Up Authentication Required",
            "message": "Freezing an account requires Step-Up MFA verification.",
            "step_up_required": True
        }), 403

    data = request.get_json(force=True) or {}
    freeze_type = data.get("freeze_type", "TOTAL_FREEZE")
    reason = data.get("reason", "Administrative Security Freeze")

    freeze = soc_service.freeze_account(account_id, freeze_type, reason, current_user.id)
    return jsonify(freeze.to_dict()), 200


@api_bp.route("/v1/admin/soc/accounts/<int:account_id>/unfreeze", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_unfreeze_account(account_id):
    from app.services import mfa_service, soc_service

    step_up_token = request.headers.get("X-Step-Up-Token") or (request.get_json(silent=True) or {}).get("step_up_token")
    session_token = request.cookies.get("session_token")
    if not step_up_token or not mfa_service.validate_and_consume_step_up_token(current_user.id, step_up_token, session_token):
        return jsonify({
            "error": "Step-Up Authentication Required",
            "message": "Unfreezing an account requires Step-Up MFA verification.",
            "step_up_required": True
        }), 403

    data = request.get_json(force=True) or {}
    reason = data.get("reason", "Administrative Security Unfreeze")

    acc = soc_service.unfreeze_account(account_id, reason, current_user.id)
    return jsonify(acc.to_dict()), 200


@api_bp.route("/v1/admin/soc/transactions/<int:txn_id>/release", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_release_held_transaction(txn_id):
    from app.services import mfa_service, soc_service

    step_up_token = request.headers.get("X-Step-Up-Token") or (request.get_json(silent=True) or {}).get("step_up_token")
    session_token = request.cookies.get("session_token")
    if not step_up_token or not mfa_service.validate_and_consume_step_up_token(current_user.id, step_up_token, session_token):
        return jsonify({
            "error": "Step-Up Authentication Required",
            "message": "Releasing a held high-risk transaction requires Step-Up MFA verification.",
            "step_up_required": True
        }), 403

    data = request.get_json(force=True) or {}
    notes = data.get("notes", "Released by Security Operations")

    debit, credit = soc_service.release_held_transaction(txn_id, current_user.id, notes)
    return jsonify(debit=debit.to_dict(), credit=credit.to_dict() if credit else None), 200


@api_bp.route("/v1/admin/soc/transactions/<int:txn_id>/reject", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_reject_held_transaction(txn_id):
    from app.services import soc_service

    data = request.get_json(force=True) or {}
    reason = data.get("reason", "Transaction rejected by Security Operations")

    txn = soc_service.reject_held_transaction(txn_id, current_user.id, reason)
    return jsonify(txn.to_dict()), 200


@api_bp.route("/v1/admin/soc/alerts/<int:alert_id>/mark-false-positive", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_mark_false_positive(alert_id):
    from app.services import soc_service

    data = request.get_json(force=True) or {}
    notes = data.get("notes", "Dismissed as false positive after review")

    alert = soc_service.mark_false_positive(alert_id, current_user.id, notes)
    return jsonify(alert.to_dict()), 200


@api_bp.route("/v1/admin/soc/evidence/<int:inc_id>/export", methods=["GET"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def api_export_evidence(inc_id):
    from app.services import soc_service
    return jsonify(soc_service.export_evidence_bundle(inc_id))



