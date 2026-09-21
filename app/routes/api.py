from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app import db
from app.models.user import Role
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.beneficiary import Beneficiary
from app.models.version import EntityVersion
from app.models.audit_log import AuditLog
from app.services import banking_service, beneficiary_service, version_service
from app.utils.decorators import roles_required, json_errors
from app.utils.validators import ValidationError

api_bp = Blueprint("api", __name__)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
@api_bp.route("/accounts", methods=["GET"])
@login_required
def list_accounts():
    user_id = request.args.get("user_id", type=int)
    if user_id and current_user.role in [Role.EMPLOYEE, Role.ADMIN]:
        accounts = Account.query.filter_by(user_id=user_id).all()
    elif current_user.role == Role.CUSTOMER:
        accounts = Account.query.filter_by(user_id=current_user.id).all()
    else:
        accounts = Account.query.limit(200).all()
    return jsonify([a.to_dict() for a in accounts])


@api_bp.route("/accounts/<int:account_id>", methods=["GET"])
@login_required
def get_account(account_id):
    account = _get_owned_account_or_403(account_id)
    return jsonify(account.to_dict())


@api_bp.route("/accounts", methods=["POST"])
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
@login_required
@json_errors
def api_deposit():
    data = request.get_json(force=True) or {}
    account = _get_owned_account_or_403(data.get("account_id"))
    txn = banking_service.deposit(account, data.get("amount"), data.get("description", ""), current_user.id)
    return jsonify(txn.to_dict()), 201


@api_bp.route("/transactions/withdraw", methods=["POST"])
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
@login_required
@json_errors
def api_transfer():
    data = request.get_json(force=True) or {}
    source_id = data.get("source_account_id")
    source = _get_owned_account_or_403(source_id)

    dest_val = data.get("destination_account_id")
    destination = None
    if dest_val is not None:
        if isinstance(dest_val, int) or (isinstance(dest_val, str) and dest_val.isdigit()):
            destination = db.session.get(Account, int(dest_val))
        if not destination:
            destination = Account.query.filter_by(account_number=str(dest_val)).first()
        if not destination and isinstance(dest_val, str):
            destination = Account.query.filter(Account.account_number.ilike(f"%{dest_val}%")).first()

    if not destination:
        return jsonify(error=f"Destination account '{dest_val}' not found. Please select a valid destination account."), 404

    try:
        debit, credit = banking_service.transfer(
            source, destination, data.get("amount"), data.get("description", ""), current_user.id
        )
    except banking_service.InsufficientBalanceError as e:
        return jsonify(error=str(e)), 422
    except Exception as e:
        return jsonify(error=str(e)), 400

    return jsonify(debit=debit.to_dict(), credit=credit.to_dict()), 201


@api_bp.route("/transactions/<int:txn_id>/reverse", methods=["POST"])
@login_required
@roles_required(Role.EMPLOYEE, Role.ADMIN)
@json_errors
def api_reverse(txn_id):
    original = Transaction.query.get_or_404(txn_id)
    reason = (request.get_json(silent=True) or {}).get("reason", "Manual correction")
    reversal = banking_service.reverse_transaction(original, current_user.id, reason)
    return jsonify(reversal.to_dict()), 201


# ---------------------------------------------------------------------------
# Beneficiaries
# ---------------------------------------------------------------------------
@api_bp.route("/beneficiaries", methods=["GET"])
@login_required
def list_beneficiaries():
    beneficiaries = Beneficiary.query.filter_by(user_id=current_user.id).all()
    return jsonify([b.to_dict() for b in beneficiaries])


@api_bp.route("/beneficiaries", methods=["POST"])
@login_required
@json_errors
def api_add_beneficiary():
    data = request.get_json(force=True) or {}
    beneficiary = beneficiary_service.add_beneficiary(current_user.id, data)
    return jsonify(beneficiary.to_dict()), 201


@api_bp.route("/beneficiaries/<int:beneficiary_id>", methods=["PUT"])
@login_required
@json_errors
def api_update_beneficiary(beneficiary_id):
    beneficiary = _get_owned_beneficiary_or_403(beneficiary_id)
    data = request.get_json(force=True) or {}
    beneficiary = beneficiary_service.update_beneficiary(beneficiary, data, current_user.id)
    return jsonify(beneficiary.to_dict())


@api_bp.route("/beneficiaries/<int:beneficiary_id>", methods=["DELETE"])
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

    # Customers only ever see their own history
    if current_user.role == Role.CUSTOMER:
        query = query.filter_by(changed_by=current_user.id)

    versions = query.order_by(EntityVersion.created_at.desc()).limit(500).all()
    return jsonify([v.to_dict() for v in versions])


@api_bp.route("/versions/<entity_type>/<int:entity_id>", methods=["GET"])
@login_required
def entity_version_history(entity_type, entity_id):
    history = version_service.get_history(entity_type.upper(), entity_id)
    return jsonify([v.to_dict() for v in history])


@api_bp.route("/versions/compare", methods=["GET"])
@login_required
@json_errors
def compare_versions():
    entity_type = request.args.get("entity_type", "").upper()
    entity_id = request.args.get("entity_id", type=int)
    v1 = request.args.get("v1", type=int)
    v2 = request.args.get("v2", type=int)

    if not all([entity_type, entity_id, v1, v2]):
        raise ValidationError("entity_type, entity_id, v1, and v2 are all required")

    try:
        result = version_service.diff_versions(entity_type, entity_id, v1, v2)
    except ValueError as e:
        return jsonify(error=str(e)), 404
    return jsonify(result)


@api_bp.route("/versions/<entity_type>/<int:entity_id>/restore/<int:version_number>", methods=["POST"])
@login_required
@roles_required(Role.ADMIN)
@json_errors
def restore_entity_version(entity_type, entity_id, version_number):
    entity_type = entity_type.upper()

    def apply_beneficiary(snapshot):
        beneficiary = Beneficiary.query.get_or_404(entity_id)
        beneficiary.name = snapshot["name"]
        beneficiary.account_number = snapshot["account_number"]
        beneficiary.bank_name = snapshot["bank_name"]
        beneficiary.ifsc = snapshot["ifsc"]
        beneficiary.status = snapshot["status"]
        beneficiary.version_number += 1
        db.session.flush()
        return beneficiary.to_dict()

    appliers = {"BENEFICIARY": apply_beneficiary}
    apply_fn = appliers.get(entity_type)
    if not apply_fn:
        return jsonify(error=f"Restoration is not supported for entity type {entity_type}"), 400

    try:
        result = version_service.restore_version(entity_type, entity_id, version_number, current_user.id, apply_fn)
    except ValueError as e:
        return jsonify(error=str(e)), 404
    db.session.commit()
    return jsonify(result)


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------
@api_bp.route("/audit-logs", methods=["GET"])
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


# ---------------------------------------------------------------------------
# Admin dashboard stats
# ---------------------------------------------------------------------------
@api_bp.route("/admin/dashboard", methods=["GET"])
@login_required
@roles_required(Role.ADMIN)
def admin_dashboard_stats():
    from app.models.user import User

    return jsonify({
        "total_users": User.query.count(),
        "active_users": User.query.filter_by(status="active").count(),
        "total_accounts": Account.query.count(),
        "total_transactions": Transaction.query.count(),
        "total_versions": EntityVersion.query.count(),
        "total_audit_logs": AuditLog.query.count(),
        "failed_logins": AuditLog.query.filter_by(action="FAILED_LOGIN").count(),
    })


# ---------------------------------------------------------------------------
# Profile & Security
# ---------------------------------------------------------------------------
@api_bp.route("/profile", methods=["GET"])
@login_required
def get_current_profile():
    data = current_user.to_dict(include_email=True)
    data["phone"] = current_user.phone
    data["failed_login_attempts"] = current_user.failed_login_attempts
    data["last_login_at"] = current_user.last_login_at.isoformat() if current_user.last_login_at else None
    return jsonify(data)


@api_bp.route("/profile", methods=["PUT"])
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


@api_bp.route("/account/delete", methods=["POST"])
@login_required
@json_errors
def api_delete_account():
    from app.services import auth_service
    from flask_login import logout_user
    user_id = current_user.id
    username = current_user.username
    logout_user()
    try:
        auth_service.delete_user_account(user_id)
        return jsonify(message=f"Account '{username}' deleted successfully.")
    except Exception as e:
        return jsonify(error=str(e)), 400


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
@api_bp.route("/notifications", methods=["GET"])
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
@login_required
def mark_notification_read(note_id):
    from app.models.notification import Notification
    note = Notification.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    note.is_read = True
    db.session.commit()
    return jsonify(status="marked as read")


@api_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_notifications_read():
    from app.models.notification import Notification
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify(status="all marked as read")


# ---------------------------------------------------------------------------
# Spending Analytics & Statement
# ---------------------------------------------------------------------------
@api_bp.route("/analytics", methods=["GET"])
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

    # Group by month string (e.g. "Sep 2026")
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
            # If counterparty is within customer's own accounts vs outbound
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
    if account_id is None:
        from flask import abort
        abort(404)

    account = None
    if isinstance(account_id, int) or (isinstance(account_id, str) and account_id.isdigit()):
        account = db.session.get(Account, int(account_id))
    if not account:
        account = Account.query.filter_by(account_number=str(account_id)).first()

    if not account:
        from flask import abort
        abort(404)

    if current_user.role == Role.CUSTOMER and account.user_id != current_user.id:
        from flask import abort
        abort(403)
    return account


def _get_owned_beneficiary_or_403(beneficiary_id):
    beneficiary = Beneficiary.query.get_or_404(beneficiary_id)
    if beneficiary.user_id != current_user.id:
        from flask import abort
        abort(403)
    return beneficiary
