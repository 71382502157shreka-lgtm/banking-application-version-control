import re
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from app import db
from app.models.user import User, Role
from app.models.account import Account, AccountType
from app.models.security_session import LoginSession, SecurityEvent
from app.models.workflow_risk import RiskAssessment, RiskDecision, RiskLevel
from app.models.transaction import Transaction, TransactionStatus
from app.services import auth_service, banking_service, session_service, approval_service


def login(client, username, password="Str0ngPass!"):
    get_res = client.get("/login")
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', get_res.get_data(as_text=True))
    token = match.group(1) if match else ""
    return client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": token},
        follow_redirects=True,
    )


@pytest.fixture
def sec_admin(app):
    user = auth_service.register_user(
        "sec_admin", "sec_admin@example.com", "Str0ngPass!", full_name="Security Admin", role=Role.ADMIN
    )
    return user


@pytest.fixture
def sec_staff(app):
    user = auth_service.register_user(
        "sec_staff", "sec_staff@example.com", "Str0ngPass!", full_name="Security Staff", role=Role.EMPLOYEE
    )
    return user


@pytest.fixture
def sec_customer(app):
    user = auth_service.register_user(
        "sec_cust", "sec_cust@example.com", "Str0ngPass!", full_name="Security Customer", role=Role.CUSTOMER
    )
    acc = banking_service.create_account(user.id, AccountType.SAVINGS)
    banking_service.deposit(acc, Decimal("5000.00"), "Initial Deposit", user.id)
    return user, acc


@pytest.fixture
def sec_payee(app):
    user = auth_service.register_user(
        "sec_payee", "sec_payee@example.com", "Str0ngPass!", full_name="Security Payee", role=Role.CUSTOMER
    )
    acc = banking_service.create_account(user.id, AccountType.SAVINGS)
    return user, acc


def test_security_center_admin_access(client, sec_admin, sec_customer):
    cust_user, _ = sec_customer

    # Customer restricted
    login(client, cust_user.username)
    res_cust = client.get("/admin/security-center")
    assert res_cust.status_code in [403, 302]

    # Admin access
    client.get("/logout")
    login(client, sec_admin.username)
    res_admin = client.get("/admin/security-center")
    assert res_admin.status_code == 200
    html = res_admin.get_data(as_text=True)
    assert "Security Center & Threat Telemetry" in html or "Security Center" in html


def test_active_session_listing_and_revocation(client, sec_admin, sec_customer):
    cust_user, _ = sec_customer
    sess = LoginSession.create_session(cust_user.id, "127.0.0.1", "Mozilla/5.0")

    login(client, sec_admin.username)

    # Call API to revoke session
    resp = client.post(f"/api/v1/sessions/{sess.id}/revoke")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["session_id"] == sess.id

    revoked_sess = db.session.get(LoginSession, sess.id)
    assert revoked_sess.is_active is False


def test_user_account_lockout_toggle(client, sec_admin, sec_customer):
    cust_user, _ = sec_customer
    login(client, sec_admin.username)

    # Toggle lock account
    r_lock = client.post(f"/api/v1/users/{cust_user.id}/toggle-lockout")
    assert r_lock.status_code == 200
    assert r_lock.get_json()["status"] == "LOCKED"

    db.session.refresh(cust_user)
    assert cust_user.locked_until is not None

    # Toggle unlock account
    r_unlock = client.post(f"/api/v1/users/{cust_user.id}/toggle-lockout")
    assert r_unlock.status_code == 200
    assert r_unlock.get_json()["status"] == "UNLOCKED"

    db.session.refresh(cust_user)
    assert cust_user.locked_until is None


def test_risk_center_listing_and_filtering(client, sec_admin):
    # Add dummy risk assessments
    ra1 = RiskAssessment(risk_score=90, risk_level=RiskLevel.CRITICAL, decision=RiskDecision.REVIEW_REQUIRED, risk_factors=["High Amount", "New Device"])
    ra2 = RiskAssessment(risk_score=20, risk_level=RiskLevel.LOW, decision=RiskDecision.APPROVED, risk_factors=[])
    db.session.add_all([ra1, ra2])
    db.session.commit()

    login(client, sec_admin.username)

    # All risk center
    r_all = client.get("/admin/risk-center")
    assert r_all.status_code == 200

    # Filter CRITICAL
    r_crit = client.get("/admin/risk-center?risk_level=CRITICAL")
    assert r_crit.status_code == 200
    html = r_crit.get_data(as_text=True)
    assert "CRITICAL" in html


def test_high_risk_transaction_approval_and_release(client, sec_admin, sec_customer, sec_payee):
    c_user, c_acc = sec_customer
    _, p_acc = sec_payee

    # Create BLOCKED_FOR_REVIEW transaction
    blocked_txn = Transaction(
        account_id=c_acc.id,
        transaction_type="TRANSFER",
        transaction_mode="TRANSFER",
        amount=Decimal("1500.00"),
        description="High Risk Test Transfer",
        status="BLOCKED_FOR_REVIEW",
        counterparty_account_id=p_acc.id,
        balance_after=c_acc.balance
    )
    db.session.add(blocked_txn)
    db.session.flush()

    risk_rec = RiskAssessment(
        transaction_id=blocked_txn.id,
        risk_score=85,
        risk_level=RiskLevel.CRITICAL,
        decision=RiskDecision.REVIEW_REQUIRED,
        risk_factors=["Rapid velocity", "Large balance depletion"]
    )
    db.session.add(risk_rec)
    db.session.commit()

    initial_c_bal = c_acc.balance
    initial_p_bal = p_acc.balance

    login(client, sec_admin.username)

    # Approve via API
    r_app = client.post(f"/api/v1/risk/assessments/{risk_rec.id}/review", json={"approve": True, "notes": "Approved by Sec Admin"})
    assert r_app.status_code == 200

    db.session.refresh(blocked_txn)
    db.session.refresh(c_acc)
    db.session.refresh(p_acc)

    assert blocked_txn.status == "COMPLETED"
    assert c_acc.balance == initial_c_bal - Decimal("1500.00")
    assert p_acc.balance == initial_p_bal + Decimal("1500.00")


def test_high_risk_transaction_rejection(client, sec_admin, sec_customer, sec_payee):
    c_user, c_acc = sec_customer
    _, p_acc = sec_payee

    blocked_txn = Transaction(
        account_id=c_acc.id,
        transaction_type="TRANSFER",
        transaction_mode="TRANSFER",
        amount=Decimal("2000.00"),
        description="Suspicious Transfer",
        status="BLOCKED_FOR_REVIEW",
        counterparty_account_id=p_acc.id,
        balance_after=c_acc.balance
    )
    db.session.add(blocked_txn)
    db.session.flush()

    risk_rec = RiskAssessment(
        transaction_id=blocked_txn.id,
        risk_score=95,
        risk_level=RiskLevel.CRITICAL,
        decision=RiskDecision.REVIEW_REQUIRED,
        risk_factors=["Blacklisted IP"]
    )
    db.session.add(risk_rec)
    db.session.commit()

    initial_c_bal = c_acc.balance

    login(client, sec_admin.username)
    r_rej = client.post(f"/api/v1/risk/assessments/{risk_rec.id}/review", json={"approve": False, "notes": "Blocked due to security risk"})
    assert r_rej.status_code == 200

    db.session.refresh(blocked_txn)
    db.session.refresh(c_acc)

    assert blocked_txn.status == "FAILED"
    assert c_acc.balance == initial_c_bal  # Unchanged balance


def test_staff_risk_review_portal(client, sec_staff):
    login(client, sec_staff.username)
    resp = client.get("/employee/risk-reviews")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Staff Risk Review Portal" in html or "Risk Review" in html


def test_session_revocation_idor_protection(client, sec_customer, sec_payee):
    c_user, _ = sec_customer
    p_user, _ = sec_payee

    c_sess = LoginSession.create_session(c_user.id, "127.0.0.1", "Mozilla/5.0")
    p_sess = LoginSession.create_session(p_user.id, "127.0.0.1", "Chrome/100.0")

    # Customer tries to revoke payee's session -> Forbidden 403
    login(client, c_user.username)
    r_idor = client.post(f"/api/v1/sessions/{p_sess.id}/revoke")
    assert r_idor.status_code == 403

    # Customer revokes own session -> Success 200
    r_own = client.post(f"/api/v1/sessions/{c_sess.id}/revoke")
    assert r_own.status_code == 200
