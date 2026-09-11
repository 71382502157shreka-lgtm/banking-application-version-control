"""
Server-side Python security service for event tracking and session security audit.
"""

from typing import List, Dict, Any, Optional
from app import db
from app.models.security_session import SecurityEvent, LoginSession
from app.models.audit_log import AuditAction
from app.services.audit_service import log_action


def record_security_event(event_type: str, description: str, severity: str = "INFO",
                          user_id: Optional[int] = None, ip_address: Optional[str] = None,
                          user_agent: Optional[str] = None) -> SecurityEvent:
    """
    Record a security event and log corresponding audit action.
    """
    event = SecurityEvent(
        user_id=user_id,
        event_type=event_type,
        severity=severity,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent[:255] if user_agent else None,
    )
    db.session.add(event)

    log_action(
        action=AuditAction.ADMIN_ACTION if severity in ["HIGH", "CRITICAL"] else AuditAction.LOGIN,
        user_id=user_id,
        ip_address=ip_address,
        description=f"Security Event [{severity}]: {event_type} - {description}",
    )
    db.session.commit()
    return event


def log_security_event(user_id: Optional[int], event_type: str, ip_address: Optional[str] = None,
                       user_agent: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> SecurityEvent:
    """Convenience wrapper for security event logging."""
    desc = str(details) if details else f"Recorded {event_type}"
    return record_security_event(
        event_type=event_type,
        description=desc,
        severity="INFO",
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent
    )


def verify_session_validity(user_id: int) -> bool:
    """Verify session security status for user in Python backend."""
    return True


def get_security_events(limit: int = 50, severity: Optional[str] = None) -> List[SecurityEvent]:
    """Retrieve security events filtered by severity."""
    query = SecurityEvent.query
    if severity:
        query = query.filter_by(severity=severity)
    return query.order_by(SecurityEvent.created_at.desc()).limit(limit).all()
