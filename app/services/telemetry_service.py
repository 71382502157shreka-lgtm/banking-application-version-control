"""
Security Telemetry & System Risk Monitoring Service for BankVCS 2.0.
Provides pure Python analytics for active user sessions, failed login tracking,
IP address velocity telemetry, and threat detection summaries.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

from app import db
from app.models.user import User, Role
from app.models.security_session import LoginSession, SecurityEvent
from app.models.audit_log import AuditLog, AuditAction

logger = logging.getLogger(__name__)


def generate_security_telemetry_summary() -> Dict[str, Any]:
    """
    Generates system-wide security telemetry analytics including session health,
    failed authentication attempts, security event counts, and high-activity IP addresses.
    """
    total_sessions = LoginSession.query.count()
    active_sessions = LoginSession.query.filter_by(is_active=True).count()

    total_events = SecurityEvent.query.count()
    failed_login_events = SecurityEvent.query.filter_by(event_type="FAILED_LOGIN").count()
    lockout_events = SecurityEvent.query.filter_by(event_type="ACCOUNT_LOCKED").count()
    session_revoked_events = SecurityEvent.query.filter_by(event_type="SESSION_REVOKED").count()

    # Recent security events (last 24h)
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    recent_events_count = SecurityEvent.query.filter(
        SecurityEvent.created_at >= twenty_four_hours_ago
    ).count()

    # Top IP addresses by authentication activity
    top_ips = _calculate_top_ip_activity(limit=10)

    # Locked accounts count
    locked_users_count = User.query.filter(
        User.locked_until > datetime.utcnow()
    ).count()

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "sessions": {
            "total_tracked_sessions": total_sessions,
            "active_sessions": active_sessions,
        },
        "security_events": {
            "total_events": total_events,
            "failed_logins": failed_login_events,
            "account_lockouts": lockout_events,
            "sessions_revoked": session_revoked_events,
            "events_last_24h": recent_events_count,
        },
        "account_security": {
            "currently_locked_accounts": locked_users_count,
        },
        "ip_telemetry": {
            "top_activity_ips": top_ips
        }
    }


def analyze_user_security_profile(user_id: int) -> Dict[str, Any]:
    """
    Analyzes the security profile for a specific user ID, including active sessions,
    recent login attempts, lockout history, and security events.
    """
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError(f"User #{user_id} not found")

    user_sessions = LoginSession.query.filter_by(user_id=user_id).order_by(LoginSession.login_time.desc()).all()
    active_sessions = [s for s in user_sessions if s.is_active]

    events = SecurityEvent.query.filter_by(user_id=user_id).order_by(SecurityEvent.created_at.desc()).all()
    audit_logs = AuditLog.query.filter_by(user_id=user_id).order_by(AuditLog.created_at.desc()).limit(20).all()

    is_currently_locked = bool(user.locked_until and user.locked_until > datetime.utcnow())

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "is_locked": is_currently_locked,
            "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            "failed_attempts": user.failed_login_attempts,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        },
        "sessions": {
            "total_sessions": len(user_sessions),
            "active_session_count": len(active_sessions),
            "active_sessions": [s.to_dict() for s in active_sessions]
        },
        "security_events": {
            "total": len(events),
            "recent_events": [e.to_dict() for e in events[:10]]
        },
        "audit_activity": {
            "recent_actions": [a.to_dict() for a in audit_logs]
        }
    }


def _calculate_top_ip_activity(limit: int = 10) -> List[Dict[str, Any]]:
    """Helper calculating IP address activity frequency across logins and audit logs."""
    ip_counts: Dict[str, int] = {}
    
    events = SecurityEvent.query.limit(500).all()
    for e in events:
        ip = e.ip_address or "127.0.0.1"
        ip_counts[ip] = ip_counts.get(ip, 0) + 1

    sorted_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"ip_address": ip, "event_count": count} for ip, count in sorted_ips]
