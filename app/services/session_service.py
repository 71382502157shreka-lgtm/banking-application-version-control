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


def revoke_session_by_id(session_id: int, actor_id: int) -> bool:
    sess = db.session.get(LoginSession, session_id)
    if not sess or not sess.is_active:
        return False
    sess.is_active = False

    log_action(
        action=AuditAction.SESSION_REVOKED,
        user_id=actor_id,
        entity_type="LOGIN_SESSION",
        entity_id=session_id,
        description=f"Revoked active login session #{session_id} for User #{sess.user_id}"
    )
    db.session.commit()
    return True


def toggle_user_lockout(user_id: int, actor_id: int) -> dict:
    from app.models.user import User
    from datetime import timedelta
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    if user.locked_until and user.locked_until > datetime.utcnow():
        user.locked_until = None
        user.failed_login_attempts = 0
        action_name = "UNLOCKED"
    else:
        user.locked_until = datetime.utcnow() + timedelta(days=365)
        action_name = "LOCKED"

    log_action(
        action=AuditAction.USER_LOCKED if action_name == "LOCKED" else AuditAction.USER_UNLOCKED,
        user_id=actor_id,
        entity_type="USER",
        entity_id=user_id,
        description=f"{action_name} user account #{user_id} ({user.username})"
    )
    db.session.commit()
    return {"user_id": user_id, "status": action_name, "username": user.username}


def _safe_get_ip():
    try:
        return get_client_ip()
    except RuntimeError:
        return "127.0.0.1"
