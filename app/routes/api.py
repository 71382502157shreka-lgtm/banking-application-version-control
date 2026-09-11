import csv
import io
from flask import Blueprint, request, jsonify, Response
from flask_login import login_required, current_user

from app import db
from app.models.user import Role, User
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.beneficiary import Beneficiary
from app.models.version import EntityVersion
from app.models.audit_log import AuditLog
from app.models.security_session import LoginSession
from app.models.workflow_risk import RollbackRequest, RiskAssessment
from app.services import (
    banking_service, beneficiary_service, version_service,
    audit_service, mfa_service, session_service, approval_service
)
from app.utils.decorators import roles_required, json_errors
from app.utils.validators import ValidationError

api_bp = Blueprint("api", __name__)


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
# Transactions
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

    txn_type = request.args.get("type")
    if txn_type:
        query = query.filter_by(transaction_type=txn_type)

    txns = query.order_by(Transaction.created_at.desc()).limit(500).all()
    return jsonify([t.to_dict() for t in txns])


@api_bp.route("/transactions/deposit", methods=["POST"])
@api_bp.route("/v1/transactions/deposit", methods=["POST"])
@login_required
@json_errors
def api_deposit():
    data = request.get_json(force=True) or {}
    account = _get_owned_account_or_403(data.get("account_id"))
    txn = banking_service.deposit(account, data.get("amount"), data.get("description", ""), current_user.id)
    return jsonify(txn.to_dict()), 201


@api_bp.route("/transactions/withdraw", methods=["POST"])
@api_bp.route("/v1/transactions/withdraw", methods=["POST"])
@login_required
@json_errors
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
def api_transfer():
    data = request.get_json(force=True) or {}
    source = _get_owned_account_or_403(data.get("source_account_id"))

    dest_id = data.get("destination_account_id")
    destination = db.session.get(Account, dest_id)
    if not destination:
        return jsonify(error="Destination account not found"), 404

    try:
        debit, credit = banking_service.transfer(
            source, destination, data.get("amount"), data.get("description", ""), current_user.id
        )
    except banking_service.InsufficientBalanceError as e:
        return jsonify(error=str(e)), 422

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
    account = Account.query.get(txn.account_id)
    counterparty = Account.query.get(txn.counterparty_account_id) if txn.counterparty_account_id else None

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
def list_beneficiaries():
    beneficiaries = Beneficiary.query.filter_by(user_id=current_user.id).all()
    return jsonify([b.to_dict() for b in beneficiaries])


@api_bp.route("/beneficiaries", methods=["POST"])
@api_bp.route("/v1/beneficiaries", methods=["POST"])
@login_required
@json_errors
def api_add_beneficiary():
    data = request.get_json(force=True) or {}
    beneficiary = beneficiary_service.add_beneficiary(current_user.id, data)
    return jsonify(beneficiary.to_dict()), 201


@api_bp.route("/beneficiaries/<int:beneficiary_id>", methods=["PUT"])
@api_bp.route("/v1/beneficiaries/<int:beneficiary_id>", methods=["PUT"])
@login_required
@json_errors
def api_update_beneficiary(beneficiary_id):
    beneficiary = _get_owned_beneficiary_or_403(beneficiary_id)
    data = request.get_json(force=True) or {}
    beneficiary = beneficiary_service.update_beneficiary(beneficiary, data, current_user.id)
    return jsonify(beneficiary.to_dict())


@api_bp.route("/beneficiaries/<int:beneficiary_id>", methods=["DELETE"])
@api_bp.route("/v1/beneficiaries/<int:beneficiary_id>", methods=["DELETE"])
@login_required
@json_errors
def api_delete_beneficiary(beneficiary_id):
    beneficiary = _get_owned_beneficiary_or_403(beneficiary_id)
    beneficiary_service.deactivate_beneficiary(beneficiary, current_user.id)
    return jsonify(status="deactivated")


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


