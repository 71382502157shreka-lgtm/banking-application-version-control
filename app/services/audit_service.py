import hashlib
import json
from datetime import datetime
from flask import request
from flask_login import current_user

from app import db
from app.models.audit_log import AuditLog
from app.utils.security import get_client_ip

GENESIS_HASH = "GENESIS_0000000000000000000000000000000000000000000000000000000000000000"


def compute_audit_hash(user_id, role, action, entity_type, entity_id, old_data, new_data, ip_address, user_agent, description, previous_hash) -> str:
    payload = f"{user_id}|{role}|{action}|{entity_type}|{entity_id}|{json.dumps(old_data, sort_keys=True)}|{json.dumps(new_data, sort_keys=True)}|{ip_address}|{user_agent}|{description}|{previous_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def log_action(action, user_id=None, role=None, entity_type=None, entity_id=None,
               old_data=None, new_data=None, description=None, ip_address=None, user_agent=None):
    """
    Write one immutable, tamper-evident audit-log row using a SHA-256 hash chain.
    """
    if user_id is None and current_user and current_user.is_authenticated:
        user_id = current_user.id
    if role is None and current_user and current_user.is_authenticated:
        role = current_user.role

    client_ip = ip_address or _safe_get_ip()
    client_agent = user_agent or _safe_get_user_agent()

    last_entry = AuditLog.query.order_by(AuditLog.id.desc()).first()
    prev_hash = last_entry.current_hash if last_entry and last_entry.current_hash else GENESIS_HASH

    cur_hash = compute_audit_hash(
        user_id=user_id,
        role=role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_data=old_data,
        new_data=new_data,
        ip_address=client_ip,
        user_agent=client_agent,
        description=description,
        previous_hash=prev_hash,
    )

    entry = AuditLog(
        user_id=user_id,
        role=role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_data=old_data,
        new_data=new_data,
        ip_address=client_ip,
        user_agent=client_agent,
        description=description,
        previous_hash=prev_hash,
        current_hash=cur_hash,
    )
    db.session.add(entry)
    return entry


def verify_audit_integrity() -> dict:
    """
    Recalculate SHA-256 hashes across the entire AuditLog chain from genesis.
    Returns validation status, total count, and detail of broken link if tampered.
    """
    logs = AuditLog.query.order_by(AuditLog.id.asc()).all()
    if not logs:
        return {"valid": True, "total_records": 0, "message": "AUDIT CHAIN VALID ✓ (No records yet)"}

    expected_prev = GENESIS_HASH
    for log in logs:
        if log.previous_hash != expected_prev:
            return {
                "valid": False,
                "broken_at_id": log.id,
                "reason": f"Previous hash mismatch at Audit #{log.id}. Expected '{expected_prev[:16]}...', got '{log.previous_hash}'",
                "message": "AUDIT INTEGRITY VIOLATION ⚠",
            }

        recalculated = compute_audit_hash(
            user_id=log.user_id,
            role=log.role,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            old_data=log.old_data,
            new_data=log.new_data,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            description=log.description,
            previous_hash=log.previous_hash,
        )

        if log.current_hash and log.current_hash != recalculated:
            return {
                "valid": False,
                "broken_at_id": log.id,
                "reason": f"Current hash tampering detected at Audit #{log.id}. Stored '{log.current_hash[:16]}...', expected '{recalculated[:16]}...'",
                "message": "AUDIT INTEGRITY VIOLATION ⚠",
            }

        expected_prev = log.current_hash or recalculated

    return {
        "valid": True,
        "total_records": len(logs),
        "message": "AUDIT CHAIN VALID ✓",
    }


def _safe_get_ip():
    try:
        return get_client_ip()
    except Exception:
        return None


def _safe_get_user_agent():
    try:
        return request.headers.get("User-Agent") if request else None
    except Exception:
        return None

