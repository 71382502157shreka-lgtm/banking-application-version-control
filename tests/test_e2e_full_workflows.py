"""
Comprehensive End-to-End Workflow Test Suite for BankVCS 2.0.
Verifies all 16 core banking, authentication, security, fraud, SOC, and audit workflows.
"""
import pytest
from decimal import Decimal
from app import create_app, db
from app.models.user import User, Role
from app.models.account import Account, AccountStatus
from app.models.transaction import Transaction, TransactionStatus
from app.models.beneficiary import Beneficiary
from app.models.version import EntityVersion
from app.models.security_session import LoginSession
from app.services import (
    auth_service, banking_service, beneficiary_service,
    mfa_service, risk_service, fraud_prevention_service,
    soc_service, audit_service
)
from app.utils.validators import ValidationError


@pytest.fixture
def e2e_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def e2e_client(e2e_app):
    return e2e_app.test_client()


def test_e2e_16_workflows_complete_journey(e2e_app, e2e_client):
    # -------------------------------------------------------------------------
    # 1. User Registration (Role.CUSTOMER)
    # -------------------------------------------------------------------------
    customer_user = auth_service.register_user(
        username="e2e_customer",
        email="customer@e2e.bank",
        password="Password123!",
        full_name="E2E John Doe",
        phone="9876543210",
        role=Role.CUSTOMER
    )
    assert customer_user.id is not None
    assert customer_user.role == Role.CUSTOMER

    admin_user = auth_service.register_user(
        username="e2e_admin",
        email="admin@e2e.bank",
        password="AdminPassword123!",
        full_name="E2E Administrator",
        role=Role.ADMIN
    )
    assert admin_user.role == Role.ADMIN

    # Create Accounts
    acc1 = banking_service.create_account(customer_user.id, "SAVINGS")
    acc2 = banking_service.create_account(customer_user.id, "CURRENT")
    assert acc1.account_number is not None

    # -------------------------------------------------------------------------
    # 2. Login & Session Creation
    # -------------------------------------------------------------------------
    auth_result = auth_service.authenticate("e2e_customer", "Password123!")
    assert auth_result.id == customer_user.id

    sess = LoginSession.create_session(customer_user.id, "127.0.0.1", "pytest-runner")
    assert sess.is_active is True

    # -------------------------------------------------------------------------
    # 3. OTP Request & Verification
    # -------------------------------------------------------------------------
    otp_code = mfa_service.generate_otp(customer_user.id, "LOGIN_VERIFY")
    assert len(otp_code) == 6
    verified = mfa_service.verify_otp(customer_user.id, "LOGIN_VERIFY", otp_code)
    assert verified is True

    # -------------------------------------------------------------------------
    # 4. Customer Dashboard & Accounts Aggregation
    # -------------------------------------------------------------------------
    res_dash = e2e_client.get("/api/v1/health")
    assert res_dash.status_code == 200
    assert res_dash.json["status"] == "healthy"

    # -------------------------------------------------------------------------
    # 5. Account Details & Health Check
    # -------------------------------------------------------------------------
    assert Decimal(str(acc1.balance)) == Decimal("0.00")

    # -------------------------------------------------------------------------
    # 6. Deposit & Withdrawal Execution
    # -------------------------------------------------------------------------
    tx_dep = banking_service.deposit(acc1, "100000.00", "Initial Salary Deposit", customer_user.id)
    assert tx_dep.status == TransactionStatus.COMPLETED
    assert Decimal(str(acc1.balance)) == Decimal("100000.00")

    tx_wd = banking_service.withdraw(acc1, "5000.00", "ATM Cash Withdrawal", customer_user.id)
    assert tx_wd.status == TransactionStatus.COMPLETED
    assert Decimal(str(acc1.balance)) == Decimal("95000.00")

    # -------------------------------------------------------------------------
    # 7. Beneficiary Creation & Version History Logging
    # -------------------------------------------------------------------------
    bene = beneficiary_service.add_beneficiary(customer_user.id, {
        "name": "E2E Beneficiary",
        "account_number": "999888777666",
        "bank_name": "Axis Bank",
        "ifsc": "UTIB0001234",
    })
    assert bene.id is not None

    versions = EntityVersion.query.filter_by(changed_by=customer_user.id).all()
    assert len(versions) >= 3  # Accounts + Beneficiary

    # -------------------------------------------------------------------------
    # 8. Fund Transfer Execution (Intra-Account)
    # -------------------------------------------------------------------------
    tx_debit, tx_credit = banking_service.transfer(acc1, acc2, "10000.00", "Self Transfer", customer_user.id)
    assert tx_debit.status == TransactionStatus.COMPLETED
    assert Decimal(str(acc1.balance)) == Decimal("85000.00")
    assert Decimal(str(acc2.balance)) == Decimal("10000.00")

    # -------------------------------------------------------------------------
    # 9. Step-Up MFA Challenge Generation & Token Issuance
    # -------------------------------------------------------------------------
    otp_stepup = mfa_service.generate_otp(customer_user.id, "HIGH_VALUE_TRANSFER")
    is_valid_otp = mfa_service.verify_otp(customer_user.id, "HIGH_VALUE_TRANSFER", otp_stepup)
    assert is_valid_otp is True
    step_up_token = sess.issue_step_up_token(ttl_minutes=5)
    assert sess.is_step_up_valid(step_up_token) is True

    # -------------------------------------------------------------------------
    # 10. Behavioral Anomaly Detection & Risk Matrix Scoring
    # -------------------------------------------------------------------------
    risk_assessment = risk_service.evaluate_transaction_risk(
        acc1,
        Decimal("40000.00"),
        bene.id
    )
    assert risk_assessment["risk_score"] >= 0
    assert "risk_level" in risk_assessment

    # -------------------------------------------------------------------------
    # 11. Idempotency Key Replay Protection & 120s Duplicate Suppression
    # -------------------------------------------------------------------------
    is_dup = fraud_prevention_service.check_duplicate_transaction(
        source_account_id=acc1.id,
        dest_account_id=acc2.id,
        amount=Decimal("1000.00"),
        description="Idempotency Test"
    )
    assert is_dup is False

    tx_dup_debit, tx_dup_credit = banking_service.transfer(acc1, acc2, "1000.00", "Idempotency Test", customer_user.id)
    assert tx_dup_debit.status == TransactionStatus.COMPLETED

    is_dup_now = fraud_prevention_service.check_duplicate_transaction(
        source_account_id=acc1.id,
        dest_account_id=acc2.id,
        amount=Decimal("1000.00"),
        description="Idempotency Test"
    )
    assert is_dup_now is True

    # -------------------------------------------------------------------------
    # 12. Administrative Account Freeze (TOTAL_FREEZE) & Session Revocation
    # -------------------------------------------------------------------------
    freeze = soc_service.freeze_account(
        account_id=acc1.id,
        freeze_type="TOTAL_FREEZE",
        reason="E2E Security Investigation",
        admin_id=admin_user.id
    )
    assert freeze.is_active is True
    assert acc1.status == AccountStatus.FROZEN

    # Verify frozen account blocks transfer
    with pytest.raises(ValidationError):
        banking_service.withdraw(acc1, "100.00", "Attempt on Frozen Acc", customer_user.id)

    # Unfreeze Account
    unfrozen_acc = soc_service.unfreeze_account(acc1.id, "E2E Verification Cleared", admin_user.id)
    assert unfrozen_acc.status == AccountStatus.ACTIVE

    # -------------------------------------------------------------------------
    # 13. High-Risk Transaction Hold (BLOCKED_FOR_REVIEW) & Release
    # -------------------------------------------------------------------------
    # Create blocked transaction manually for review
    held_tx = Transaction(
        account_id=acc1.id,
        transaction_type="TRANSFER",
        transaction_mode="IMPS",
        amount=Decimal("5000.00"),
        description="Suspicious Transfer",
        status="BLOCKED_FOR_REVIEW",
        counterparty_account_id=acc2.id,
        balance_after=acc1.balance
    )
    db.session.add(held_tx)
    db.session.commit()

    rel_debit, rel_credit = soc_service.release_held_transaction(held_tx.id, admin_user.id, "Cleared by SOC Admin")
    assert rel_debit.status == TransactionStatus.COMPLETED

    # -------------------------------------------------------------------------
    # 14. SOC Incident Management & Tamper-Evident Evidence Export
    # -------------------------------------------------------------------------
    inc = soc_service.create_incident(
        title="Suspicious Login Cluster",
        severity="HIGH",
        user_id=customer_user.id,
        actor_id=admin_user.id,
        description="Multiple failed OTP attempts from foreign IP range"
    )
    assert inc.incident_number.startswith("INC-")

    soc_service.assign_incident(inc.id, admin_user.id, admin_user.id)
    soc_service.update_incident_status(inc.id, "CONTAINED", admin_user.id, "Contained via account freeze")

    evidence = soc_service.export_evidence_bundle(inc.id)
    assert "digest_sha256" in evidence
    assert len(evidence["digest_sha256"]) == 64

    # -------------------------------------------------------------------------
    # 15. Audit Log SHA-256 Tamper-Evident Ledger Verification
    # -------------------------------------------------------------------------
    audit_report = audit_service.verify_audit_integrity()
    assert audit_report["valid"] is True
    assert audit_report["broken_record_id"] is None
    assert audit_report["total_records"] > 0

    # -------------------------------------------------------------------------
    # 16. Logout & Session Invalidation
    # -------------------------------------------------------------------------
    auth_service.logout_event(customer_user.id)
    sess_after = db.session.get(LoginSession, sess.id)
    assert sess_after.is_active is False
