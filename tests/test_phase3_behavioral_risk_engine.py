"""
Phase 3 - Feature 3 Automated Test Suite:
Automated Anomaly Detection & Adaptive Behavioral Risk Engine.

Tests 10 behavioral anomaly detection vectors, per-user baseline tracking,
adaptive Step-Up MFA enforcement (< 50,000 threshold bypass), ATO sequence detection,
and user/admin risk profile endpoints.
"""

from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from app import create_app, db
from app.models.user import User, Role
from app.models.account import Account
from app.models.security_session import LoginSession, SecurityEvent
from app.models.beneficiary import Beneficiary
from app.models.behavioral_profile import UserBehavioralProfile
from app.services import auth_service, banking_service, behavioral_risk_engine, mfa_service, session_service


@pytest.fixture
def risk_app():
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["RATELIMIT_ENABLED"] = False
    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture
def risk_client(risk_app):
    return risk_app.test_client()


@pytest.fixture
def test_user(risk_app):
    with risk_app.app_context():
        user = User.query.filter_by(username="risk_user").first()
        if not user:
            user = auth_service.register_user(
                username="risk_user",
                email="risk_user@bankvcs.local",
                password="SecurePassword123!",
                full_name="Risk Test User",
                phone="9876543299",
                role=Role.CUSTOMER
            )
            acc1 = banking_service.create_account(user.id, "SAVINGS")
            banking_service.deposit(acc1, 500000.0, "Initial Deposit", user.id)

            dest_user = auth_service.register_user(
                username="risk_dest",
                email="risk_dest@bankvcs.local",
                password="SecurePassword123!",
                full_name="Risk Dest User",
                phone="9876543298",
                role=Role.CUSTOMER
            )
            acc2 = banking_service.create_account(dest_user.id, "SAVINGS")
            banking_service.deposit(acc2, 10000.0, "Initial Deposit", dest_user.id)

        user_id = user.id
    return user_id


def login_risk_user(risk_client, username="risk_user", password="SecurePassword123!"):
    return risk_client.post("/login", data={"username": username, "password": password})


def test_unusual_ip_location_detection(risk_app, test_user):
    """Test detection of an unrecognized IP address (+20 risk score)."""
    with risk_app.app_context():
        profile = UserBehavioralProfile.get_or_create(test_user)
        profile.known_ips = ["192.168.1.10"]
        db.session.commit()

        assessment = behavioral_risk_engine.evaluate_behavioral_risk(
            test_user, context_ip="10.0.0.99", context_user_agent="Mozilla/5.0"
        )
        assert assessment.risk_score >= 20
        assert any("unusual login ip" in factor.lower() for factor in assessment.risk_factors)


def test_new_device_user_agent_detection(risk_app, test_user):
    """Test detection of an unrecognized User-Agent / device (+15 risk score)."""
    with risk_app.app_context():
        profile = UserBehavioralProfile.get_or_create(test_user)
        profile.known_user_agents = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"]
        db.session.commit()

        assessment = behavioral_risk_engine.evaluate_behavioral_risk(
            test_user, context_ip="127.0.0.1", context_user_agent="CustomAndroidApp/1.0"
        )
        assert assessment.risk_score >= 15
        assert any("unrecognized device" in factor.lower() for factor in assessment.risk_factors)


def test_abnormal_transfer_amount_baseline_drift(risk_app, test_user):
    """Test detection of a transfer exceeding 3x historical average (+25 risk score)."""
    with risk_app.app_context():
        profile = UserBehavioralProfile.get_or_create(test_user)
        profile.avg_transfer_amount = Decimal("2000.00")
        profile.total_transfer_count = 5
        db.session.commit()

        acc = Account.query.filter_by(user_id=test_user).first()
        assessment = behavioral_risk_engine.evaluate_behavioral_risk(
            test_user, source_account=acc, amount=Decimal("15000.00")
        )
        assert assessment.risk_score >= 25
        assert any("abnormal transfer amount" in factor.lower() for factor in assessment.risk_factors)


def test_rapid_burst_transfer_frequency(risk_app, test_user):
    """Test detection of rapid burst transfers in last 10 minutes (+25 risk score)."""
    with risk_app.app_context():
        user = db.session.get(User, test_user)
        acc1 = Account.query.filter_by(user_id=user.id).first()
        dest_user = User.query.filter_by(username="risk_dest").first()
        acc2 = Account.query.filter_by(user_id=dest_user.id).first()

        for _ in range(3):
            banking_service.transfer(acc1, acc2, Decimal("100.00"), "Rapid burst", test_user)

        assessment = behavioral_risk_engine.evaluate_behavioral_risk(
            test_user, source_account=acc1, amount=Decimal("500.00")
        )
        assert assessment.risk_score >= 25
        assert any("high transaction frequency" in factor.lower() for factor in assessment.risk_factors)


def test_beneficiary_addition_then_instant_transfer(risk_app, test_user):
    """Test transfer > 20,000 following recent beneficiary addition (< 1 hour) (+30 risk score)."""
    with risk_app.app_context():
        user = db.session.get(User, test_user)
        acc1 = Account.query.filter_by(user_id=user.id).first()
        dest_user = User.query.filter_by(username="risk_dest").first()
        acc2 = Account.query.filter_by(user_id=dest_user.id).first()

        profile = UserBehavioralProfile.get_or_create(test_user)
        profile.last_beneficiary_added_at = datetime.utcnow()
        db.session.commit()

        assessment = behavioral_risk_engine.evaluate_behavioral_risk(
            test_user, source_account=acc1, destination_account=acc2, amount=Decimal("30000.00")
        )
        assert assessment.risk_score >= 30
        assert any("newly added beneficiary" in factor.lower() for factor in assessment.risk_factors)


def test_failed_login_otp_spike_detection(risk_app, test_user):
    """Test detection of failed login / OTP spikes (+25 risk score)."""
    with risk_app.app_context():
        for _ in range(3):
            db.session.add(SecurityEvent(
                user_id=test_user,
                event_type="LOGIN_FAILED",
                severity="WARNING",
                description="Incorrect password"
            ))
        db.session.commit()

        assessment = behavioral_risk_engine.evaluate_behavioral_risk(test_user)
        assert assessment.risk_score >= 25
        assert any("failed authentication/otp" in factor.lower() for factor in assessment.risk_factors)


def test_concurrent_multi_ip_sessions_detection(risk_app, test_user):
    """Test detection of concurrent active sessions from multiple IPs (+30 risk score)."""
    with risk_app.app_context():
        LoginSession.create_session(test_user, "192.168.1.1", "Mozilla/5.0")
        LoginSession.create_session(test_user, "10.0.0.5", "Mozilla/5.0")
        db.session.commit()

        assessment = behavioral_risk_engine.evaluate_behavioral_risk(test_user)
        assert assessment.risk_score >= 30
        assert any("concurrent active sessions" in factor.lower() for factor in assessment.risk_factors)


def test_account_takeover_ato_sequence_detection(risk_app, test_user):
    """Test detection of ATO sequence: profile update followed by transfer (+40 risk score)."""
    with risk_app.app_context():
        profile = UserBehavioralProfile.get_or_create(test_user)
        profile.last_profile_updated_at = datetime.utcnow()
        db.session.commit()

        acc = Account.query.filter_by(user_id=test_user).first()
        assessment = behavioral_risk_engine.evaluate_behavioral_risk(
            test_user, source_account=acc, amount=Decimal("25000.00")
        )
        assert assessment.risk_score >= 40
        assert any("account takeover" in factor.lower() for factor in assessment.risk_factors)
        assert assessment.anomaly_details.get("ato_sequence_detected") is True


def test_adaptive_mfa_enforcement_below_50k(risk_app, risk_client, test_user):
    """Test elevated behavioral risk triggers Step-Up MFA even for small transfers (< 50,000)."""
    login_risk_user(risk_client)
    with risk_app.app_context():
        profile = UserBehavioralProfile.get_or_create(test_user)
        profile.known_ips = ["192.168.1.1"]
        profile.known_user_agents = ["Mozilla/5.0"]
        profile.last_profile_updated_at = datetime.utcnow()  # ATO indicator
        db.session.commit()

        user = db.session.get(User, test_user)
        acc1 = Account.query.filter_by(user_id=user.id).first()
        dest_user = User.query.filter_by(username="risk_dest").first()
        acc2 = Account.query.filter_by(user_id=dest_user.id).first()
        acc1_id, acc2_id = acc1.id, acc2.id

    # Transfer of 15,000 (< 50,000) with ATO sequence -> Risk score >= 60 -> Enforces Step-Up MFA
    res = risk_client.post(
        "/api/v1/transactions/transfer",
        json={"source_account_id": acc1_id, "destination_account_id": acc2_id, "amount": 15000.0},
        headers={"X-Forwarded-For": "10.99.99.99"}  # Unknown IP -> Score boosts
    )
    assert res.status_code == 403
    assert res.get_json()["step_up_required"] is True


def test_user_risk_profile_endpoint(risk_client, test_user):
    """Test GET /api/v1/security/risk-profile returns user behavioral profile."""
    login_risk_user(risk_client)
    res = risk_client.get("/api/v1/security/risk-profile")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "profile" in data
    assert "avg_transfer_amount" in data["profile"]


def test_admin_behavioral_anomalies_endpoint(risk_app, risk_client, test_user):
    """Test GET /api/v1/admin/behavioral-anomalies access and admin RBAC protection."""
    # Customer access -> Rejected 403
    login_risk_user(risk_client)
    res_cust = risk_client.get("/api/v1/admin/behavioral-anomalies")
    assert res_cust.status_code == 403

    # Admin access -> Returns list of anomalies
    with risk_app.app_context():
        admin = User.query.filter_by(username="risk_admin").first()
        if not admin:
            admin = auth_service.register_user(
                username="risk_admin",
                email="risk_admin@bankvcs.local",
                password="SecurePassword123!",
                role=Role.ADMIN
            )

    risk_client.get("/logout")
    login_risk_user(risk_client, username="risk_admin")
    res_admin = risk_client.get("/api/v1/admin/behavioral-anomalies")
    assert res_admin.status_code == 200
    assert res_admin.get_json()["success"] is True
