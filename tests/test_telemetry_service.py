"""
Unit tests for Security Telemetry Service in BankVCS 2.0.
"""

import pytest
from app import db
from app.models.security_session import LoginSession, SecurityEvent
from app.services import auth_service, telemetry_service


def test_security_telemetry_summary(app):
    """Test security telemetry report generation."""
    with app.app_context():
        u = auth_service.register_user("telemuser", "telem@bank.com", "Pass1234!", "Telemetry User")
        sess = LoginSession.create_session(u.id, "192.168.1.100", "Mozilla/5.0 Chrome/120.0")
        evt = SecurityEvent(user_id=u.id, event_type="FAILED_LOGIN", severity="WARNING", description="Invalid password attempt", ip_address="192.168.1.100")
        db.session.add(evt)
        db.session.commit()

        summary = telemetry_service.generate_security_telemetry_summary()
        assert summary["sessions"]["total_tracked_sessions"] >= 1
        assert summary["sessions"]["active_sessions"] >= 1
        assert summary["security_events"]["total_events"] >= 1


def test_user_session_analytics(app):
    """Test detailed user security profile analytics generation."""
    with app.app_context():
        u = auth_service.register_user("sessuser", "sess@bank.com", "Pass1234!", "Session User")
        LoginSession.create_session(u.id, "10.0.0.1", "Mozilla/5.0 (Windows NT 10.0)")
        
        profile = telemetry_service.analyze_user_security_profile(u.id)
        assert profile["user"]["id"] == u.id
        assert profile["user"]["username"] == "sessuser"
        assert profile["sessions"]["total_sessions"] == 1
        assert profile["sessions"]["active_session_count"] == 1
