"""
Phase 3 - Feature 2 Automated Test Suite:
Step-Up MFA Challenge & Multi-Device Session Control Protocol.

Tests step-up OTP challenges, single-use 5-minute step-up tokens, high-value transaction
gating (>= 50,000), single-use token consumption, token expiration, active session
listing, and remote device session revocation.
"""

import time
from datetime import datetime, timedelta
import pytest
from app import create_app, db
from app.models.user import User, Role
from app.models.account import Account
from app.models.security_session import LoginSession, OTPVerification
from app.services import auth_service, banking_service, mfa_service, session_service


@pytest.fixture
def mfa_app():
    """App instance configured for Step-Up MFA testing."""
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["RATELIMIT_ENABLED"] = False
    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture
def mfa_client(mfa_app):
    return mfa_app.test_client()


@pytest.fixture
def test_customer(mfa_app):
    with mfa_app.app_context():
        user = User.query.filter_by(username="mfa_user").first()
        if not user:
            user = auth_service.register_user(
                username="mfa_user",
                email="mfa_user@bankvcs.local",
                password="SecurePassword123!",
                full_name="MFA Test User",
                phone="9876543210",
                role=Role.CUSTOMER
            )
            acc1 = banking_service.create_account(user.id, "SAVINGS")
            banking_service.deposit(acc1, 200000.0, "Initial Deposit", user.id)

            user2 = auth_service.register_user(
                username="mfa_dest",
                email="mfa_dest@bankvcs.local",
                password="SecurePassword123!",
                full_name="MFA Dest User",
                phone="9876543211",
                role=Role.CUSTOMER
            )
            acc2 = banking_service.create_account(user2.id, "SAVINGS")
            banking_service.deposit(acc2, 10000.0, "Initial Deposit", user2.id)

        user_id = user.id
    return user_id


def login_client(mfa_client, username="mfa_user", password="SecurePassword123!"):
    return mfa_client.post("/login", data={"username": username, "password": password})


def test_step_up_challenge_generation(mfa_client, test_customer):
    """Test requesting a step-up MFA challenge generates an OTP and logs audit action."""
    login_client(mfa_client)
    res = mfa_client.post("/api/v1/mfa/step-up-challenge", json={"action_type": "HIGH_VALUE_TRANSFER"})
    assert res.status_code == 200
    data = res.get_json()
    assert "demo_otp" in data
    assert len(data["demo_otp"]) == 6
    assert data["action_type"] == "HIGH_VALUE_TRANSFER"


def test_step_up_otp_verification_issues_token(mfa_client, test_customer):
    """Test verifying a valid step-up OTP returns a 5-minute single-use step-up token."""
    login_client(mfa_client)
    res_challenge = mfa_client.post("/api/v1/mfa/step-up-challenge", json={"action_type": "HIGH_VALUE_TRANSFER"})
    otp = res_challenge.get_json()["demo_otp"]

    res_verify = mfa_client.post("/api/v1/mfa/verify-step-up", json={
        "action_type": "HIGH_VALUE_TRANSFER",
        "otp_code": otp
    })
    assert res_verify.status_code == 200
    data = res_verify.get_json()
    assert "step_up_token" in data
    assert len(data["step_up_token"]) == 64
    assert data["expires_in_seconds"] == 300


def test_step_up_invalid_otp_rejection(mfa_client, test_customer):
    """Test verifying an invalid step-up OTP returns HTTP 400 error."""
    login_client(mfa_client)
    mfa_client.post("/api/v1/mfa/step-up-challenge", json={"action_type": "HIGH_VALUE_TRANSFER"})

    res_verify = mfa_client.post("/api/v1/mfa/verify-step-up", json={
        "action_type": "HIGH_VALUE_TRANSFER",
        "otp_code": "000000"
    })
    assert res_verify.status_code == 400
    assert "Invalid OTP code" in res_verify.get_json()["error"]


def test_high_value_transfer_blocked_without_step_up(mfa_app, mfa_client, test_customer):
    """Test transfers >= 50,000 without a step-up token are blocked with HTTP 403."""
    login_client(mfa_client)
    with mfa_app.app_context():
        user = db.session.get(User, test_customer)
        acc1 = Account.query.filter_by(user_id=user.id).first()
        dest_user = User.query.filter_by(username="mfa_dest").first()
        acc2 = Account.query.filter_by(user_id=dest_user.id).first()
        acc1_id, acc2_id = acc1.id, acc2.id

    res = mfa_client.post("/api/v1/transactions/transfer", json={
        "source_account_id": acc1_id,
        "destination_account_id": acc2_id,
        "amount": 75000.0,
        "description": "High value test transfer"
    })
    assert res.status_code == 403
    data = res.get_json()
    assert data["error"] == "Step-Up Authentication Required"
    assert data["step_up_required"] is True


def test_high_value_transfer_succeeds_with_valid_step_up(mfa_app, mfa_client, test_customer):
    """Test transfers >= 50,000 succeed when accompanied by a valid step-up token."""
    login_client(mfa_client)
    with mfa_app.app_context():
        user = db.session.get(User, test_customer)
        acc1 = Account.query.filter_by(user_id=user.id).first()
        dest_user = User.query.filter_by(username="mfa_dest").first()
        acc2 = Account.query.filter_by(user_id=dest_user.id).first()
        acc1_id, acc2_id = acc1.id, acc2.id

    # Step 1: Request OTP
    res_challenge = mfa_client.post("/api/v1/mfa/step-up-challenge", json={"action_type": "HIGH_VALUE_TRANSFER"})
    otp = res_challenge.get_json()["demo_otp"]

    # Step 2: Verify OTP -> Receive step_up_token
    res_verify = mfa_client.post("/api/v1/mfa/verify-step-up", json={
        "action_type": "HIGH_VALUE_TRANSFER",
        "otp_code": otp
    })
    step_up_token = res_verify.get_json()["step_up_token"]

    # Step 3: Execute transfer with X-Step-Up-Token header
    res_transfer = mfa_client.post(
        "/api/v1/transactions/transfer",
        json={
            "source_account_id": acc1_id,
            "destination_account_id": acc2_id,
            "amount": 60000.0,
            "description": "High value transfer with step-up"
        },
        headers={"X-Step-Up-Token": step_up_token}
    )
    assert res_transfer.status_code in (201, 202)


def test_step_up_token_is_single_use(mfa_app, mfa_client, test_customer):
    """Test step-up tokens are consumed upon first use and cannot be reused for a second transaction."""
    login_client(mfa_client)
    with mfa_app.app_context():
        user = db.session.get(User, test_customer)
        acc1 = Account.query.filter_by(user_id=user.id).first()
        dest_user = User.query.filter_by(username="mfa_dest").first()
        acc2 = Account.query.filter_by(user_id=dest_user.id).first()
        acc1_id, acc2_id = acc1.id, acc2.id

    res_challenge = mfa_client.post("/api/v1/mfa/step-up-challenge", json={"action_type": "HIGH_VALUE_TRANSFER"})
    otp = res_challenge.get_json()["demo_otp"]

    res_verify = mfa_client.post("/api/v1/mfa/verify-step-up", json={
        "action_type": "HIGH_VALUE_TRANSFER",
        "otp_code": otp
    })
    token = res_verify.get_json()["step_up_token"]

    # 1st transfer consumes token
    res1 = mfa_client.post(
        "/api/v1/transactions/transfer",
        json={"source_account_id": acc1_id, "destination_account_id": acc2_id, "amount": 55000.0},
        headers={"X-Step-Up-Token": token}
    )
    assert res1.status_code in (201, 202)

    # 2nd transfer reusing same token is rejected
    res2 = mfa_client.post(
        "/api/v1/transactions/transfer",
        json={"source_account_id": acc1_id, "destination_account_id": acc2_id, "amount": 55000.0},
        headers={"X-Step-Up-Token": token}
    )
    assert res2.status_code == 403
    assert res2.get_json()["error"] == "Step-Up Authentication Required"


def test_step_up_token_expiration(mfa_app, test_customer):
    """Test expired step-up tokens (> 5 minutes) fail validation."""
    with mfa_app.app_context():
        token = mfa_service.issue_step_up_token_for_user(test_customer, ttl_minutes=-1)  # Already expired
        is_valid = mfa_service.validate_and_consume_step_up_token(test_customer, token)
        assert is_valid is False


def test_active_sessions_listing(mfa_client, test_customer):
    """Test GET /api/v1/sessions/active returns list of active device sessions."""
    login_client(mfa_client)
    res = mfa_client.get("/api/v1/sessions/active")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["sessions"]) >= 1
    sess = data["sessions"][0]
    assert "browser" in sess
    assert "operating_system" in sess
    assert "is_active" in sess


def test_remote_session_revocation(mfa_app, mfa_client, test_customer):
    """Test revoking a session by token marks it inactive and revokes access."""
    login_client(mfa_client)
    with mfa_app.app_context():
        s = LoginSession.create_session(test_customer, "10.0.0.99", "Mozilla/5.0 (Windows)")
        db.session.commit()
        token_to_revoke = s.session_token
        s_id = s.id

    res = mfa_client.post("/api/v1/sessions/revoke", json={"session_token": token_to_revoke})
    assert res.status_code == 200
    assert res.get_json()["message"] == "Session successfully revoked"

    with mfa_app.app_context():
        updated = db.session.get(LoginSession, s_id)
        assert updated.is_active is False


def test_exact_threshold_50k_requires_step_up(mfa_app, mfa_client, test_customer):
    """Test transfer of exactly 50,000.00 requires Step-Up MFA."""
    login_client(mfa_client)
    with mfa_app.app_context():
        user = db.session.get(User, test_customer)
        acc1 = Account.query.filter_by(user_id=user.id).first()
        dest_user = User.query.filter_by(username="mfa_dest").first()
        acc2 = Account.query.filter_by(user_id=dest_user.id).first()
        acc1_id, acc2_id = acc1.id, acc2.id

    res = mfa_client.post("/api/v1/transactions/transfer", json={
        "source_account_id": acc1_id,
        "destination_account_id": acc2_id,
        "amount": 50000.0,
        "description": "Exact threshold transfer"
    })
    assert res.status_code == 403
    assert res.get_json()["step_up_required"] is True


def test_wrong_user_step_up_token_rejection(mfa_app, mfa_client, test_customer):
    """Test using another user's step-up token is rejected with HTTP 403."""
    with mfa_app.app_context():
        dest_user = User.query.filter_by(username="mfa_dest").first()
        dest_user_id = dest_user.id
        dest_token = mfa_service.issue_step_up_token_for_user(dest_user_id)
        acc1 = Account.query.filter_by(user_id=test_customer).first()
        acc2 = Account.query.filter_by(user_id=dest_user_id).first()
        acc1_id, acc2_id = acc1.id, acc2.id

    login_client(mfa_client, username="mfa_user")  # Logged in as mfa_user
    res = mfa_client.post(
        "/api/v1/transactions/transfer",
        json={"source_account_id": acc1_id, "destination_account_id": acc2_id, "amount": 60000.0},
        headers={"X-Step-Up-Token": dest_token}  # Using mfa_dest's token
    )
    assert res.status_code == 403
    assert res.get_json()["error"] == "Step-Up Authentication Required"


def test_cross_user_session_revocation_blocked(mfa_app, mfa_client, test_customer):
    """Test User A cannot revoke User B's session token."""
    with mfa_app.app_context():
        dest_user = User.query.filter_by(username="mfa_dest").first()
        dest_sess = LoginSession.create_session(dest_user.id, "192.168.1.50", "Mozilla/5.0")
        db.session.commit()
        dest_token = dest_sess.session_token
        dest_sess_id = dest_sess.id

    login_client(mfa_client, username="mfa_user")  # Logged in as mfa_user
    res = mfa_client.post("/api/v1/sessions/revoke", json={"session_token": dest_token})
    assert res.status_code == 404

    with mfa_app.app_context():
        check_sess = db.session.get(LoginSession, dest_sess_id)
        assert check_sess.is_active is True  # Remained active
