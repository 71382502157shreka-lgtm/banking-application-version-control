from app import db
from app.models.audit_log import AuditLog
from app.utils.security import get_client_ip


def log_action(action, user_id=None, entity_type=None, entity_id=None,
                old_data=None, new_data=None, description=None, ip_address=None):
    """
    Write one immutable audit-log row. Called by the version service, the
    banking service, and the auth service whenever a trackable event occurs.
    This function only adds to the session — callers control the commit so
    the audit row lands in the same database transaction as the operation
    it describes.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_data=old_data,
        new_data=new_data,
        ip_address=ip_address or _safe_get_ip(),
        description=description,
    )
    db.session.add(entry)
    return entry


def _safe_get_ip():
    try:
        return get_client_ip()
    except RuntimeError:
        # Outside of a request context (e.g. seed script) — no IP to record
        return None
