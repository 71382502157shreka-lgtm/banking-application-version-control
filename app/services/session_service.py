from datetime import datetime
from flask import request, session, has_request_context
from app import db
from app.models.security_session import LoginSession, SecurityEvent
from app.models.audit_log import AuditAction
from app.services.audit_service import log_action
from app.utils.security import get_client_ip


def create_user_session(user_id: int) -> LoginSession:
    ip_addr = _safe_get_ip()
    ua = request.headers.get("User-Agent", "") if has_request_context() else ""

    sess = LoginSession.create_session(user_id, ip_addr, ua)
    if has_request_context():
        session["session_token"] = sess.session_token

    db.session.add(SecurityEvent(
        user_id=user_id,
        event_type="LOGIN_SESSION_CREATED",
        severity="INFO",
        description=f"Logged in from {sess.browser} on {sess.operating_system} ({ip_addr})",
        ip_address=ip_addr,
        user_agent=ua[:255] if ua else "",
    ))
    db.session.commit()
    return sess


def touch_session(token: str):
    if not token:
        return
    sess = LoginSession.query.filter_by(session_token=token, is_active=True).first()
    if sess:
        sess.last_activity = datetime.utcnow()
        db.session.commit()


def revoke_other_sessions(user_id: int, current_token: str) -> int:
    other_sessions = LoginSession.query.filter(
        LoginSession.user_id == user_id,
        LoginSession.session_token != current_token,
        LoginSession.is_active == True
    ).all()

    count = len(other_sessions)
    for s in other_sessions:
        s.is_active = False

    log_action(
        action=AuditAction.SESSION_REVOKED,
        user_id=user_id,
        description=f"Revoked {count} other active login session(s)",
    )
    db.session.commit()
    return count


def _safe_get_ip():
    try:
        return get_client_ip()
    except RuntimeError:
        return "127.0.0.1"
