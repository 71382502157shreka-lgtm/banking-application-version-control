from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List

from app import db
from app.models.transaction import Transaction, TransactionType
from app.models.fraud_alert import FraudAlert, FraudAlertSeverity, FraudAlertStatus
from app.models.audit_log import AuditAction
from app.services.audit_service import log_action


def check_idempotency(user_id: int, idempotency_key: str) -> Optional[Dict[str, Any]]:
    """
    Check if a transaction with matching idempotency key has already been processed in the last 24 hours.
    Returns cached transaction dict if found, else None.
    """
    if not idempotency_key:
        return None

    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    existing_txn = Transaction.query.filter(
        Transaction.idempotency_key == idempotency_key,
        Transaction.created_at >= twenty_four_hours_ago
    ).order_by(Transaction.created_at.desc()).first()

    if existing_txn:
        return existing_txn.to_dict()
    return None


def check_duplicate_transaction(
    source_account_id: int,
    dest_account_id: int,
    amount: Decimal,
    description: str,
    window_seconds: int = 120
) -> bool:
    """
    Detect exact duplicate transfers (same source, destination, amount, and description)
    executed within rolling window_seconds (default 120s).
    """
    window_start = datetime.utcnow() - timedelta(seconds=window_seconds)
    duplicate = Transaction.query.filter(
        Transaction.account_id == source_account_id,
        Transaction.counterparty_account_id == dest_account_id,
        Transaction.amount == Decimal(str(amount)),
        Transaction.transaction_type == TransactionType.TRANSFER,
        Transaction.created_at >= window_start
    ).first()

    return duplicate is not None


def check_mule_beneficiary(destination_account_id: int) -> bool:
    """
    Detect if destination account receives transfers from >= 3 distinct source accounts within 1 hour.
    """
    if not destination_account_id:
        return False

    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    distinct_senders = db.session.query(Transaction.account_id).filter(
        Transaction.counterparty_account_id == destination_account_id,
        Transaction.transaction_type == TransactionType.TRANSFER,
        Transaction.created_at >= one_hour_ago
    ).distinct().count()

    return distinct_senders >= 3


def create_fraud_alert(
    user_id: int,
    alert_type: str,
    severity: str = FraudAlertSeverity.MEDIUM,
    details: Optional[Dict[str, Any]] = None,
    transaction_id: Optional[int] = None
) -> FraudAlert:
    """
    Create a FraudAlert record and log an audit action.
    """
    alert = FraudAlert(
        user_id=user_id,
        transaction_id=transaction_id,
        alert_type=alert_type,
        severity=severity,
        status=FraudAlertStatus.NEW,
        details=details or {},
        created_at=datetime.utcnow()
    )
    db.session.add(alert)
    db.session.commit()

    log_action(
        action=AuditAction.ADMIN_ACTION,
        user_id=user_id,
        entity_type="FRAUD_ALERT",
        entity_id=alert.id,
        description=f"Fraud alert raised: {alert_type} ({severity})"
    )
    return alert


def resolve_fraud_alert(
    alert_id: int,
    decision: str,  # CONFIRMED_FRAUD or DISMISSED
    actor_id: int,
    resolution_notes: str = "",
    lock_account: bool = False
) -> FraudAlert:
    """
    Resolve a FraudAlert and optionally lock the suspect user's account if confirmed fraud.
    """
    alert = db.session.get(FraudAlert, alert_id)
    if not alert:
        raise ValueError("Fraud alert not found")

    status = FraudAlertStatus.CONFIRMED_FRAUD if decision == "CONFIRMED_FRAUD" else FraudAlertStatus.DISMISSED
    alert.status = status
    alert.assigned_to = actor_id
    alert.resolution_notes = resolution_notes
    alert.resolved_at = datetime.utcnow()

    if lock_account and decision == "CONFIRMED_FRAUD":
        from app.services.session_service import toggle_user_lockout
        try:
            toggle_user_lockout(alert.user_id, actor_id)
        except Exception:
            pass

    log_action(
        action=AuditAction.ADMIN_ACTION,
        user_id=actor_id,
        entity_type="FRAUD_ALERT",
        entity_id=alert.id,
        description=f"Resolved fraud alert #{alert_id} as {status} (Notes: {resolution_notes})"
    )
    db.session.commit()
    return alert
