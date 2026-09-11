from datetime import datetime
from app import db
from app.models.audit_log import AuditLog
from app.utils.security import get_client_ip


def log_action(action, user_id=None, entity_type=None, entity_id=None,
               old_data=None, new_data=None, description=None, ip_address=None):
    """
    Write one tamper-evident audit-log row with SHA-256 hash chaining.
    """
    last_log = AuditLog.query.order_by(AuditLog.id.desc()).first()
    prev_hash = last_log.current_hash if (last_log and last_log.current_hash) else "GENESIS"

    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_data=old_data,
        new_data=new_data,
        ip_address=ip_address or _safe_get_ip(),
        description=description,
        previous_hash=prev_hash,
        created_at=datetime.utcnow(),
    )
    entry.current_hash = entry.calculate_hash(prev_hash)
    db.session.add(entry)
    return entry


def verify_audit_integrity() -> dict:
    """
    Traverse the audit chain sequentially from genesis to tip, re-computing
    the SHA-256 hash for each entry and verifying that:
      1. entry.previous_hash matches the previous record's current_hash
      2. entry.current_hash matches calculate_hash(entry.previous_hash)
    Returns detailed audit integrity report.
    """
    logs = AuditLog.query.order_by(AuditLog.id.asc()).all()
    if not logs:
        return {
            "valid": True,
            "status": "AUDIT CHAIN VALID [OK]",
            "message": "No audit records found. Chain is empty and intact.",
            "total_records": 0,
            "broken_record_id": None,
        }

    expected_prev = "GENESIS"
    for idx, entry in enumerate(logs):
        if entry.previous_hash != expected_prev:
            return {
                "valid": False,
                "status": "AUDIT INTEGRITY VIOLATION [ALERT]",
                "message": f"Broken chain link at Audit ID #{entry.id}: previous_hash mismatch.",
                "total_records": len(logs),
                "broken_record_id": entry.id,
                "details": {
                    "expected_previous_hash": expected_prev,
                    "found_previous_hash": entry.previous_hash,
                }
            }

        recalculated = entry.calculate_hash(expected_prev)
        if entry.current_hash != recalculated:
            return {
                "valid": False,
                "status": "AUDIT INTEGRITY VIOLATION [ALERT]",
                "message": f"Tampered data detected at Audit ID #{entry.id}: hash mismatch.",
                "total_records": len(logs),
                "broken_record_id": entry.id,
                "details": {
                    "stored_hash": entry.current_hash,
                    "recalculated_hash": recalculated,
                }
            }
        expected_prev = entry.current_hash

    return {
        "valid": True,
        "status": "AUDIT CHAIN VALID [OK]",
        "message": f"All {len(logs)} audit records verified successfully. Chain is unbroken.",
        "total_records": len(logs),
        "broken_record_id": None,
    }


def _safe_get_ip():
    try:
        return get_client_ip()
    except RuntimeError:
        return None
