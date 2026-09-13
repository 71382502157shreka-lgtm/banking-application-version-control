import hashlib
import json
import random
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from app import db
from app.models.account import Account, AccountStatus
from app.models.audit_log import AuditAction, AuditLog
from app.models.behavioral_profile import UserBehavioralProfile
from app.models.fraud_alert import FraudAlert, FraudAlertSeverity, FraudAlertStatus
from app.models.notification import Notification
from app.models.security_incident import (
    AccountFreeze,
    FreezeType,
    IncidentEvent,
    IncidentSeverity,
    IncidentStatus,
    SecurityIncident,
)
from app.models.security_session import LoginSession, SecurityEvent
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import Role, User
from app.models.version import ChangeType, EntityType
from app.services import audit_service, banking_service
from app.services.version_service import create_version
from app.utils.validators import ValidationError


def _build_user_evidence_snapshot(user_id: Optional[int], incident_id: int) -> Dict:
    snapshot = {
        "incident_id": incident_id,
        "captured_at": datetime.utcnow().isoformat() + "Z",
        "user_id": user_id,
    }
    if not user_id:
        return snapshot

    user = db.session.get(User, user_id)
    if user:
        snapshot["user"] = {
            "username": user.username,
            "role": user.role,
            "is_locked": user.is_locked(),
        }

    profile = UserBehavioralProfile.get_or_create(user_id)
    if profile:
        snapshot["behavioral_profile"] = profile.to_dict()

    recent_sessions = LoginSession.query.filter_by(user_id=user_id).order_by(LoginSession.login_time.desc()).limit(5).all()
    snapshot["recent_sessions"] = [s.to_dict() for s in recent_sessions]

    recent_alerts = FraudAlert.query.filter_by(user_id=user_id).order_by(FraudAlert.created_at.desc()).limit(5).all()
    snapshot["recent_alerts"] = [a.to_dict() for a in recent_alerts]

    payload_str = json.dumps(snapshot, sort_keys=True)
    snapshot["digest_sha256"] = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    return snapshot


def generate_incident_number() -> str:
    timestamp_str = datetime.utcnow().strftime("%Y%m")
    random_digits = f"{random.randint(1000, 9999)}"
    return f"INC-{timestamp_str}-{random_digits}"


def create_incident(
    title: str,
    description: str,
    severity: str = IncidentSeverity.MEDIUM,
    user_id: Optional[int] = None,
    alert_ids: Optional[List[int]] = None,
    actor_id: Optional[int] = None,
) -> SecurityIncident:
    if not title or not description:
        raise ValidationError("Incident title and description are required")

    inc_num = generate_incident_number()
    incident = SecurityIncident(
        incident_number=inc_num,
        title=title.strip(),
        description=description.strip(),
        severity=severity,
        status=IncidentStatus.OPEN,
        user_id=user_id,
        assigned_admin_id=actor_id,
    )
    db.session.add(incident)
    db.session.flush()

    # Link alerts
    if alert_ids:
        alerts = FraudAlert.query.filter(FraudAlert.id.in_(alert_ids)).all()
        for alert in alerts:
            alert.incident_id = incident.id
            if alert.status == FraudAlertStatus.NEW:
                alert.status = FraudAlertStatus.UNDER_INVESTIGATION

    # Build initial evidence snapshot
    evidence = _build_user_evidence_snapshot(user_id, incident.id)
    incident.evidence_snapshot = evidence

    # Record IncidentEvent
    event = IncidentEvent(
        incident_id=incident.id,
        event_type="CREATED",
        actor_id=actor_id or user_id or 1,
        details={"title": title, "severity": severity, "linked_alerts_count": len(alert_ids or [])},
    )
    db.session.add(event)

    # Log Audit
    audit_service.log_action(
        user_id=actor_id or user_id or 1,
        action="INCIDENT_CREATED",
        description=f"Created Security Incident {inc_num} ({severity}): {title}",
    )
    db.session.commit()
    return incident


def get_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    user_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> Dict:
    query = SecurityIncident.query

    if status:
        query = query.filter(SecurityIncident.status == status)
    if severity:
        query = query.filter(SecurityIncident.severity == severity)
    if user_id:
        query = query.filter(SecurityIncident.user_id == user_id)
    if search:
        pat = f"%{search.strip()}%"
        query = query.filter(
            (SecurityIncident.incident_number.ilike(pat))
            | (SecurityIncident.title.ilike(pat))
            | (SecurityIncident.description.ilike(pat))
        )

    pagination = query.order_by(SecurityIncident.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return {
        "items": [inc.to_dict() for inc in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "per_page": pagination.per_page,
    }


def get_incident_detail(incident_id: int) -> Dict:
    incident = db.session.get(SecurityIncident, incident_id)
    if not incident:
        raise ValidationError(f"Security Incident ID {incident_id} not found")

    alerts = [a.to_dict() for a in incident.alerts.all()]
    events = [e.to_dict() for e in incident.events.order_by(IncidentEvent.created_at.asc()).all()]

    res = incident.to_dict()
    res["alerts"] = alerts
    res["timeline"] = events
    return res


def update_incident_status(
    incident_id: int, status: str, resolution_notes: str, actor_id: int
) -> SecurityIncident:
    incident = db.session.get(SecurityIncident, incident_id)
    if not incident:
        raise ValidationError(f"Security Incident ID {incident_id} not found")

    old_status = incident.status
    incident.status = status
    if status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED_FALSE_POSITIVE):
        incident.resolved_at = datetime.utcnow()

    event = IncidentEvent(
        incident_id=incident.id,
        event_type="STATUS_CHANGED",
        actor_id=actor_id,
        details={"old_status": old_status, "new_status": status, "notes": resolution_notes},
    )
    db.session.add(event)

    audit_service.log_action(
        user_id=actor_id,
        action="INCIDENT_STATUS_CHANGED",
        description=f"Incident {incident.incident_number} status changed from {old_status} to {status}. Notes: {resolution_notes}",
    )
    db.session.commit()
    return incident


def assign_incident(incident_id: int, assigned_admin_id: int, actor_id: int) -> SecurityIncident:
    incident = db.session.get(SecurityIncident, incident_id)
    if not incident:
        raise ValidationError(f"Security Incident ID {incident_id} not found")

    admin_user = db.session.get(User, assigned_admin_id)
    if not admin_user or admin_user.role != Role.ADMIN:
        raise ValidationError("Assigned user must be a valid administrator")

    old_assignee = incident.assigned_admin_id
    incident.assigned_admin_id = assigned_admin_id

    event = IncidentEvent(
        incident_id=incident.id,
        event_type="ASSIGNED",
        actor_id=actor_id,
        details={"old_assignee": old_assignee, "new_assignee": assigned_admin_id},
    )
    db.session.add(event)

    audit_service.log_action(
        user_id=actor_id,
        action="INCIDENT_ASSIGNED",
        description=f"Incident {incident.incident_number} assigned to admin {admin_user.username}",
    )
    db.session.commit()
    return incident


def freeze_account(account_id: int, freeze_type: str, reason: str, admin_id: int) -> AccountFreeze:
    if not reason or len(reason.strip()) < 5:
        raise ValidationError("A detailed freeze reason (at least 5 characters) is required")

    # Pessimistic row locking
    locked_acc = Account.query.filter_by(id=account_id).with_for_update().first()
    if not locked_acc:
        raise ValidationError(f"Account ID {account_id} not found")

    # Deactivate existing freezes
    existing_freezes = AccountFreeze.query.filter_by(account_id=account_id, is_active=True).all()
    for ef in existing_freezes:
        ef.is_active = False
        ef.unfrozen_at = datetime.utcnow()
        ef.unfrozen_by_admin_id = admin_id
        ef.unfreeze_reason = "Replaced by new freeze policy"

    freeze = AccountFreeze(
        account_id=account_id,
        freeze_type=freeze_type or FreezeType.TOTAL_FREEZE,
        reason=reason.strip(),
        frozen_by_admin_id=admin_id,
        is_active=True,
    )
    db.session.add(freeze)

    old_status = locked_acc.status
    locked_acc.status = AccountStatus.FROZEN
    create_version(
        EntityType.ACCOUNT, locked_acc.id, ChangeType.UPDATE,
        {"status": old_status}, locked_acc.to_dict(),
        admin_id, f"Account status set to FROZEN ({freeze_type}): {reason}", AuditAction.ACCOUNT_UPDATED
    )

    # Revoke active user sessions
    user_sessions = LoginSession.query.filter_by(user_id=locked_acc.user_id, is_active=True).all()
    for sess in user_sessions:
        sess.is_active = False

    db.session.add(Notification(
        user_id=locked_acc.user_id,
        title="Account Frozen",
        message=f"Account {locked_acc.account_number} has been placed under {freeze_type} by Bank VCS Security.",
        notification_type="SECURITY"
    ))

    audit_service.log_action(
        user_id=admin_id,
        action="ACCOUNT_FROZEN",
        description=f"Account {locked_acc.account_number} frozen ({freeze_type}). Reason: {reason}",
    )
    db.session.commit()
    return freeze


def unfreeze_account(account_id: int, reason: str, admin_id: int) -> Account:
    if not reason or len(reason.strip()) < 5:
        raise ValidationError("A detailed unfreeze reason (at least 5 characters) is required")

    locked_acc = Account.query.filter_by(id=account_id).with_for_update().first()
    if not locked_acc:
        raise ValidationError(f"Account ID {account_id} not found")

    existing_freezes = AccountFreeze.query.filter_by(account_id=account_id, is_active=True).all()
    for ef in existing_freezes:
        ef.is_active = False
        ef.unfrozen_at = datetime.utcnow()
        ef.unfrozen_by_admin_id = admin_id
        ef.unfreeze_reason = reason.strip()

    old_status = locked_acc.status
    locked_acc.status = AccountStatus.ACTIVE
    create_version(
        EntityType.ACCOUNT, locked_acc.id, ChangeType.UPDATE,
        {"status": old_status}, locked_acc.to_dict(),
        admin_id, f"Account status unfrozen to ACTIVE: {reason}", AuditAction.ACCOUNT_UPDATED
    )

    db.session.add(Notification(
        user_id=locked_acc.user_id,
        title="Account Unfrozen",
        message=f"Account {locked_acc.account_number} has been unfrozen and restored to active status.",
        notification_type="SECURITY"
    ))

    audit_service.log_action(
        user_id=admin_id,
        action="ACCOUNT_UNFROZEN",
        description=f"Account {locked_acc.account_number} unfrozen. Reason: {reason}",
    )
    db.session.commit()
    return locked_acc


def release_held_transaction(transaction_id: int, admin_id: int, notes: Optional[str] = None) -> Tuple[Transaction, Optional[Transaction]]:
    debit_txn = Transaction.query.filter_by(id=transaction_id).with_for_update().first()
    if not debit_txn:
        raise ValidationError(f"Transaction ID {transaction_id} not found")
    if debit_txn.status != "BLOCKED_FOR_REVIEW":
        raise ValidationError(f"Transaction ID {transaction_id} is not pending review (current status: {debit_txn.status})")

    source = Account.query.filter_by(id=debit_txn.account_id).with_for_update().first()
    destination = Account.query.filter_by(id=debit_txn.counterparty_account_id).with_for_update().first()

    if Decimal(source.available_balance) < Decimal(str(debit_txn.amount)):
        raise ValidationError("Source account has insufficient balance to complete released transfer")

    # Perform balance transfer
    source.balance = Decimal(source.balance) - Decimal(str(debit_txn.amount))
    source.available_balance = Decimal(source.available_balance) - Decimal(str(debit_txn.amount))

    destination.balance = Decimal(destination.balance) + Decimal(str(debit_txn.amount))
    destination.available_balance = Decimal(destination.available_balance) + Decimal(str(debit_txn.amount))

    debit_txn.status = TransactionStatus.COMPLETED
    debit_txn.description = f"[RELEASED] {debit_txn.description.replace('[REVIEW REQUIRED] ', '')}"
    debit_txn.balance_after = source.balance

    credit_txn = Transaction(
        account_id=destination.id,
        transaction_type=debit_txn.transaction_type,
        transaction_mode=debit_txn.transaction_mode,
        amount=debit_txn.amount,
        description=debit_txn.description,
        status=TransactionStatus.COMPLETED,
        counterparty_account_id=source.id,
        balance_after=destination.balance,
    )
    db.session.add(credit_txn)

    audit_service.log_action(
        user_id=admin_id,
        action="TRANSACTION_RELEASED",
        description=f"Admin released held transaction #{debit_txn.id} (₹{debit_txn.amount}). Notes: {notes or 'None'}",
    )
    db.session.commit()
    return debit_txn, credit_txn


def reject_held_transaction(transaction_id: int, admin_id: int, reason: str) -> Transaction:
    if not reason or len(reason.strip()) < 5:
        raise ValidationError("A detailed rejection reason is required")

    debit_txn = Transaction.query.filter_by(id=transaction_id).with_for_update().first()
    if not debit_txn:
        raise ValidationError(f"Transaction ID {transaction_id} not found")
    if debit_txn.status != "BLOCKED_FOR_REVIEW":
        raise ValidationError(f"Transaction ID {transaction_id} is not pending review (current status: {debit_txn.status})")

    debit_txn.status = TransactionStatus.FAILED
    debit_txn.description = f"[REJECTED: {reason}] {debit_txn.description}"

    audit_service.log_action(
        user_id=admin_id,
        action="TRANSACTION_REJECTED",
        description=f"Admin rejected held transaction #{debit_txn.id} (₹{debit_txn.amount}). Reason: {reason}",
    )
    db.session.commit()
    return debit_txn


def mark_false_positive(alert_id: int, admin_id: int, notes: str) -> FraudAlert:
    if not notes or len(notes.strip()) < 5:
        raise ValidationError("Detailed notes explaining the false positive classification are required")

    alert = db.session.get(FraudAlert, alert_id)
    if not alert:
        raise ValidationError(f"Fraud Alert ID {alert_id} not found")

    alert.status = FraudAlertStatus.DISMISSED
    alert.resolution_notes = f"[FALSE POSITIVE] {notes.strip()}"
    alert.resolved_at = datetime.utcnow()

    # Log Audit
    audit_service.log_action(
        user_id=admin_id,
        action="FALSE_POSITIVE_FLAGGED",
        description=f"Fraud alert #{alert.id} marked as false positive. Notes: {notes}",
    )
    db.session.commit()
    return alert


def get_user_timeline(user_id: int) -> List[Dict]:
    user = db.session.get(User, user_id)
    if not user:
        raise ValidationError(f"User ID {user_id} not found")

    timeline = []

    # 1. Login Sessions
    sessions = LoginSession.query.filter_by(user_id=user_id).all()
    for s in sessions:
        timeline.append({
            "timestamp": s.login_time.isoformat() if s.login_time else None,
            "type": "LOGIN_SESSION",
            "title": f"Login Session from {s.ip_address}",
            "severity": "LOW" if s.is_active else "MEDIUM",
            "details": s.to_dict()
        })

    # 2. Security Events
    events = SecurityEvent.query.filter_by(user_id=user_id).all()
    for e in events:
        timeline.append({
            "timestamp": e.created_at.isoformat() if e.created_at else None,
            "type": "SECURITY_EVENT",
            "title": f"Security Event: {e.event_type}",
            "severity": e.severity,
            "details": e.to_dict()
        })

    # 3. Fraud Alerts
    alerts = FraudAlert.query.filter_by(user_id=user_id).all()
    for a in alerts:
        timeline.append({
            "timestamp": a.created_at.isoformat() if a.created_at else None,
            "type": "FRAUD_ALERT",
            "title": f"Fraud Alert: {a.alert_type}",
            "severity": a.severity,
            "details": a.to_dict()
        })

    # 4. Security Incidents
    incidents = SecurityIncident.query.filter_by(user_id=user_id).all()
    for inc in incidents:
        timeline.append({
            "timestamp": inc.created_at.isoformat() if inc.created_at else None,
            "type": "SECURITY_INCIDENT",
            "title": f"Incident {inc.incident_number}: {inc.title}",
            "severity": inc.severity,
            "details": inc.to_dict()
        })

    # Sort descending by timestamp
    timeline.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    return timeline


def export_evidence_bundle(incident_id: int) -> Dict:
    detail = get_incident_detail(incident_id)
    bundle_str = json.dumps(detail, sort_keys=True)
    digest = hashlib.sha256(bundle_str.encode("utf-8")).hexdigest()

    return {
        "incident_id": incident_id,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "digest_sha256": digest,
        "evidence_bundle": detail
    }


def get_soc_dashboard_metrics() -> Dict:
    open_incidents_count = SecurityIncident.query.filter(SecurityIncident.status.in_([IncidentStatus.OPEN, IncidentStatus.INVESTIGATING])).count()
    critical_incidents_count = SecurityIncident.query.filter_by(severity=IncidentSeverity.CRITICAL, status=IncidentStatus.OPEN).count()

    new_alerts_count = FraudAlert.query.filter_by(status=FraudAlertStatus.NEW).count()
    high_risk_alerts_count = FraudAlert.query.filter(FraudAlert.severity.in_([FraudAlertSeverity.HIGH, FraudAlertSeverity.CRITICAL])).count()

    active_freezes_count = AccountFreeze.query.filter_by(is_active=True).count()
    held_transactions_count = Transaction.query.filter_by(status="BLOCKED_FOR_REVIEW").count()

    recent_incidents = [inc.to_dict() for inc in SecurityIncident.query.order_by(SecurityIncident.created_at.desc()).limit(5).all()]
    recent_alerts = [alt.to_dict() for alt in FraudAlert.query.order_by(FraudAlert.created_at.desc()).limit(5).all()]

    return {
        "open_incidents": open_incidents_count,
        "critical_incidents": critical_incidents_count,
        "new_fraud_alerts": new_alerts_count,
        "high_risk_alerts": high_risk_alerts_count,
        "active_account_freezes": active_freezes_count,
        "held_transactions": held_transactions_count,
        "recent_incidents": recent_incidents,
        "recent_alerts": recent_alerts,
        "system_health": "HEALTHY",
    }
