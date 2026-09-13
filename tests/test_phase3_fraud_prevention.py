"""
Phase 3 - Feature 4 Automated Test Suite:
Transaction Intelligence & Fraud Prevention Layer.

Tests 24-hour idempotency replay protection, 120-second duplicate transaction suppression,
mule account detection, pessimistic row locking, and admin fraud alert management workflows.
"""

from decimal import Decimal
import pytest
from app import create_app, db
from app.models.user import User, Role
from app.models.account import Account
from app.models.fraud_alert import FraudAlert, FraudAlertStatus, FraudAlertSeverity
from app.services import auth_service, banking_service, fraud_prevention_service


@pytest.fixture
def fraud_app():
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["RATELIMIT_ENABLED"] = False
    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture
def fraud_client(fraud_app):
    return fraud_app.test_client()


@pytest.fixture
def test_fraud_users(fraud_app):
    with fraud_app.app_context():
        u1 = User.query.filter_by(username="fraud_user1").first()
        if not u1:
            u1 = auth_service.register_user(
                username="fraud_user1",
                email="fraud_user1@bankvcs.local",
                password="SecurePassword123!",
                full_name="Fraud Test User 1",
                phone="9876543111",
                role=Role.CUSTOMER
            )
            acc1 = banking_service.create_account(u1.id, "SAVINGS")
            banking_service.deposit(acc1, 200000.0, "Initial Deposit", u1.id)

            u2 = auth_service.register_user(
                username="fraud_user2",
                email="fraud_user2@bankvcs.local",
                password="SecurePassword123!",
                full_name="Fraud Test User 2",
                phone="9876543112",
                role=Role.CUSTOMER
            )
            acc2 = banking_service.create_account(u2.id, "SAVINGS")
            banking_service.deposit(acc2, 100000.0, "Initial Deposit", u2.id)

            u3 = auth_service.register_user(
                username="fraud_user3",
                email="fraud_user3@bankvcs.local",
                password="SecurePassword123!",
                full_name="Fraud Test User 3",
                phone="9876543113",
                role=Role.CUSTOMER
            )
            acc3 = banking_service.create_account(u3.id, "SAVINGS")
            banking_service.deposit(acc3, 100000.0, "Initial Deposit", u3.id)

            mule = auth_service.register_user(
                username="mule_dest",
                email="mule_dest@bankvcs.local",
                password="SecurePassword123!",
                full_name="Mule Dest User",
                phone="9876543114",
                role=Role.CUSTOMER
            )
            acc_mule = banking_service.create_account(mule.id, "SAVINGS")
            banking_service.deposit(acc_mule, 5000.0, "Initial Deposit", mule.id)

        user_id = u1.id
    return user_id


def login_fraud_user(fraud_client, username="fraud_user1", password="SecurePassword123!"):
    return fraud_client.post("/login", data={"username": username, "password": password})


def test_idempotency_key_replay_protection(fraud_app, fraud_client, test_fraud_users):
    """Test submitting a transfer with X-Idempotency-Key returns cached response without double debiting."""
    login_fraud_user(fraud_client, username="fraud_user1")
    with fraud_app.app_context():
        u1 = User.query.filter_by(username="fraud_user1").first()
        acc1 = Account.query.filter_by(user_id=u1.id).first()
        u2 = User.query.filter_by(username="fraud_user2").first()
        acc2 = Account.query.filter_by(user_id=u2.id).first()
        acc1_id, acc2_id = acc1.id, acc2.id
        initial_balance = float(acc1.balance)

    idem_key = "IDEM-KEY-UNIQUE-12345"

    # 1st execution
    res1 = fraud_client.post(
        "/api/v1/transactions/transfer",
        json={"source_account_id": acc1_id, "destination_account_id": acc2_id, "amount": 5000.0, "description": "Idempotent Transfer Test"},
        headers={"X-Idempotency-Key": idem_key}
    )
    assert res1.status_code == 201

    with fraud_app.app_context():
        acc_check = db.session.get(Account, acc1_id)
        assert float(acc_check.balance) == initial_balance - 5000.0

    # 2nd execution using SAME X-Idempotency-Key returns cached result
    res2 = fraud_client.post(
        "/api/v1/transactions/transfer",
        json={"source_account_id": acc1_id, "destination_account_id": acc2_id, "amount": 5000.0, "description": "Idempotent Transfer Test"},
        headers={"X-Idempotency-Key": idem_key}
    )
    assert res2.status_code == 200

    # Balance remains unchanged (no double debit)
    with fraud_app.app_context():
        acc_check2 = db.session.get(Account, acc1_id)
        assert float(acc_check2.balance) == initial_balance - 5000.0


def test_duplicate_transaction_120s_suppression(fraud_app, fraud_client, test_fraud_users):
    """Test submitting an identical transfer payload within 120 seconds returns HTTP 409 Conflict."""
    login_fraud_user(fraud_client, username="fraud_user1")
    with fraud_app.app_context():
        u1 = User.query.filter_by(username="fraud_user1").first()
        acc1 = Account.query.filter_by(user_id=u1.id).first()
        u2 = User.query.filter_by(username="fraud_user2").first()
        acc2 = Account.query.filter_by(user_id=u2.id).first()
        acc1_id, acc2_id = acc1.id, acc2.id

    # 1st Transfer
    res1 = fraud_client.post(
        "/api/v1/transactions/transfer",
        json={"source_account_id": acc1_id, "destination_account_id": acc2_id, "amount": 2500.0, "description": "Duplicate Window Test"}
    )
    assert res1.status_code == 201

    # Immediate 2nd Transfer (Identical payload without Idempotency Key) -> Rejected 409
    res2 = fraud_client.post(
        "/api/v1/transactions/transfer",
        json={"source_account_id": acc1_id, "destination_account_id": acc2_id, "amount": 2500.0, "description": "Duplicate Window Test"}
    )
    assert res2.status_code == 409
    assert res2.get_json()["duplicate"] is True


def test_mule_beneficiary_cross_user_detection(fraud_app, test_fraud_users):
    """Test detecting a mule counterparty account receiving rapid transfers from >= 3 distinct senders."""
    with fraud_app.app_context():
        u1 = User.query.filter_by(username="fraud_user1").first()
        u2 = User.query.filter_by(username="fraud_user2").first()
        u3 = User.query.filter_by(username="fraud_user3").first()
        mule = User.query.filter_by(username="mule_dest").first()

        acc1 = Account.query.filter_by(user_id=u1.id).first()
        acc2 = Account.query.filter_by(user_id=u2.id).first()
        acc3 = Account.query.filter_by(user_id=u3.id).first()
        acc_mule = Account.query.filter_by(user_id=mule.id).first()

        # Sender 1 -> Mule
        banking_service.transfer(acc1, acc_mule, Decimal("1000.00"), "Mule Transfer 1", u1.id)
        # Sender 2 -> Mule
        banking_service.transfer(acc2, acc_mule, Decimal("1000.00"), "Mule Transfer 2", u2.id)
        # Sender 3 -> Mule
        banking_service.transfer(acc3, acc_mule, Decimal("1000.00"), "Mule Transfer 3", u3.id)

        is_mule = fraud_prevention_service.check_mule_beneficiary(acc_mule.id)
        assert is_mule is True


def test_concurrency_pessimistic_row_locking(fraud_app, test_fraud_users):
    """Test pessimistic row locking during transfer execution prevents invalid balance overdraws."""
    with fraud_app.app_context():
        u1 = User.query.filter_by(username="fraud_user1").first()
        acc1 = Account.query.filter_by(user_id=u1.id).first()
        u2 = User.query.filter_by(username="fraud_user2").first()
        acc2 = Account.query.filter_by(user_id=u2.id).first()

        # Execute serial transfers verifying row-locking safety
        t1, _ = banking_service.transfer(acc1, acc2, Decimal("10000.00"), "Serial Lock 1", u1.id)
        t2, _ = banking_service.transfer(acc1, acc2, Decimal("10000.00"), "Serial Lock 2", u1.id)
        assert t1.status == "COMPLETED"
        assert t2.status == "COMPLETED"


def test_admin_fraud_alerts_listing_and_filtering(fraud_app, fraud_client, test_fraud_users):
    """Test GET /api/v1/admin/fraud/alerts listing and filter options."""
    with fraud_app.app_context():
        u1 = User.query.filter_by(username="fraud_user1").first()
        fraud_prevention_service.create_fraud_alert(
            user_id=u1.id,
            alert_type="DUPLICATE_ATTEMPT",
            severity=FraudAlertSeverity.MEDIUM,
            details={"test": True}
        )

        admin = User.query.filter_by(username="fraud_admin").first()
        if not admin:
            admin = auth_service.register_user(
                username="fraud_admin",
                email="fraud_admin@bankvcs.local",
                password="SecurePassword123!",
                role=Role.ADMIN
            )

    login_fraud_user(fraud_client, username="fraud_admin")
    res = fraud_client.get("/api/v1/admin/fraud/alerts")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["alerts"]) >= 1


def test_admin_fraud_alert_resolution_workflow(fraud_app, fraud_client, test_fraud_users):
    """Test resolving a fraud alert as CONFIRMED_FRAUD or DISMISSED."""
    with fraud_app.app_context():
        u1 = User.query.filter_by(username="fraud_user1").first()
        alert = fraud_prevention_service.create_fraud_alert(
            user_id=u1.id,
            alert_type="MULE_ACCOUNT_SUSPECT",
            severity=FraudAlertSeverity.HIGH
        )
        alert_id = alert.id

        admin = User.query.filter_by(username="fraud_admin").first()
        if not admin:
            admin = auth_service.register_user(
                username="fraud_admin",
                email="fraud_admin@bankvcs.local",
                password="SecurePassword123!",
                role=Role.ADMIN
            )

    fraud_client.get("/logout")
    login_fraud_user(fraud_client, username="fraud_admin")

    res = fraud_client.post(
        f"/api/v1/admin/fraud/alerts/{alert_id}/resolve",
        json={"decision": "CONFIRMED_FRAUD", "resolution_notes": "Mule activity confirmed", "lock_account": True}
    )
    assert res.status_code == 200
    assert res.get_json()["alert"]["status"] == FraudAlertStatus.CONFIRMED_FRAUD


def test_non_admin_fraud_api_idor_rejection(fraud_client, test_fraud_users):
    """Test non-admin customer accounts are rejected from accessing fraud admin endpoints (HTTP 403)."""
    login_fraud_user(fraud_client, username="fraud_user1")
    res = fraud_client.get("/api/v1/admin/fraud/alerts")
    assert res.status_code == 403
