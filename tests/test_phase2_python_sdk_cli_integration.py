"""
Phase 2 - Feature 10 Automated Test Suite:
Python Programmatic SDK, Standalone CLI Application, & End-to-End System Integration Suite.

Tests Python SDK (bankvcs.py), CLI formatting helpers (cli.py), and end-to-end integration workflows:
- User registration & duplicate validation via SDK
- Authentication success & failure error handling via SDK
- Deposit, withdrawal, insufficient funds, & invalid account handling via SDK
- Fund transfers & self-transfer prevention via SDK
- Beneficiary management & IFSC validation via SDK
- Entity version history & field-level diff calculation via SDK
- Maker-checker rollback request submission & dual-control approval via SDK
- Security & risk assessment review & transaction release via SDK
- Cryptographic SHA-256 audit chain verification via SDK
- CLI diff and header output formatting functions
- Complete end-to-end programmatic workflow execution
"""

import pytest
from decimal import Decimal

from bankvcs import BankingApp, BankVCSAPI
from cli import print_header, print_diff
from app import db
from app.models.user import User, Role
from app.models.account import Account, AccountType
from app.models.version import EntityType
from app.models.workflow_risk import RiskAssessment, RiskDecision, RiskLevel, RollbackStatus
from app.services import auth_service, banking_service, risk_engine, approval_service


def test_sdk_register_user_success_and_duplicate(app):
    """Test SDK register_user with valid details and duplicate username rejection."""
    with app.app_context():
        sdk = BankingApp()
        user, err = sdk.register_user(
            username="sdkuser1",
            email="sdkuser1@bank.com",
            password="Password123!",
            full_name="SDK User One",
            phone="9876543210",
            role=Role.CUSTOMER
        )
        assert err is None
        assert user is not None
        assert user.username == "sdkuser1"

        # Attempt duplicate registration
        dup_user, dup_err = sdk.register_user(
            username="sdkuser1",
            email="another@bank.com",
            password="Password123!",
            full_name="Duplicate User"
        )
        assert dup_user is None
        assert dup_err is not None
        assert "already taken" in dup_err.lower()


def test_sdk_authenticate_success_and_failure(app):
    """Test SDK authenticate method for valid credentials and invalid password handling."""
    with app.app_context():
        sdk = BankingApp()
        sdk.register_user("authuser1", "auth1@bank.com", "SecurePass123!", "Auth User 1")

        # Valid authentication
        u, err = sdk.authenticate("authuser1", "SecurePass123!")
        assert err is None
        assert u is not None
        assert u.username == "authuser1"

        # Invalid password
        bad_u, bad_err = sdk.authenticate("authuser1", "WrongPassword!")
        assert bad_u is None
        assert bad_err is not None
        assert "invalid username or password" in bad_err.lower()

        # Non-existent user
        no_u, no_err = sdk.authenticate("nonexistent_user", "AnyPassword!")
        assert no_u is None
        assert no_err is not None
        assert "invalid username or password" in no_err.lower()


def test_sdk_deposit_withdraw_and_invalid_account(app):
    """Test SDK deposit and withdraw operations, insufficient funds, and invalid account IDs."""
    with app.app_context():
        sdk = BankingApp()
        u, _ = sdk.register_user("txuser1", "tx1@bank.com", "Pass1234!", "TX User 1")
        acc = banking_service.create_account(u.id, AccountType.SAVINGS)
        db.session.commit()

        # Deposit
        txn, err = sdk.deposit(acc.id, Decimal("5000.00"), description="Initial SDK Deposit")
        assert err is None
        assert txn is not None
        db.session.refresh(acc)
        assert acc.balance == Decimal("5000.00")

        # Withdraw
        w_txn, w_err = sdk.withdraw(acc.id, Decimal("2000.00"), description="ATM Withdrawal")
        assert w_err is None
        assert w_txn is not None
        db.session.refresh(acc)
        assert acc.balance == Decimal("3000.00")

        # Insufficient funds withdrawal
        fail_w, fail_err = sdk.withdraw(acc.id, Decimal("99999.00"), description="Excess Withdrawal")
        assert fail_w is None
        assert fail_err is not None
        assert "insufficient" in fail_err.lower()

        # Non-existent account
        bad_dep, bad_err = sdk.deposit(999999, Decimal("100.00"))
        assert bad_dep is None
        assert bad_err == "Account not found"


def test_sdk_transfer_funds_and_self_transfer_prevention(app):
    """Test SDK fund transfer between accounts and self-transfer error handling."""
    with app.app_context():
        sdk = BankingApp()
        u1, _ = sdk.register_user("truser1", "tr1@bank.com", "Pass1234!", "TR User 1")
        u2, _ = sdk.register_user("truser2", "tr2@bank.com", "Pass1234!", "TR User 2")

        acc1 = banking_service.create_account(u1.id, AccountType.SAVINGS)
        acc2 = banking_service.create_account(u2.id, AccountType.CURRENT)
        db.session.commit()

        sdk.deposit(acc1.id, Decimal("10000.00"))

        # Valid transfer
        res, err = sdk.transfer(acc1.id, acc2.id, Decimal("4000.00"), description="SDK Transfer")
        assert err is None
        assert res is not None
        db.session.refresh(acc1)
        db.session.refresh(acc2)
        assert acc1.balance == Decimal("6000.00")
        assert acc2.balance == Decimal("4000.00")

        # Self-transfer attempt
        self_res, self_err = sdk.transfer(acc1.id, acc1.id, Decimal("500.00"))
        assert self_res is None
        assert self_err is not None
        assert "cannot transfer to the same account" in self_err.lower()


def test_sdk_create_beneficiary_and_validation(app):
    """Test SDK create_beneficiary with valid data and IFSC validation error handling."""
    with app.app_context():
        sdk = BankingApp()
        u, _ = sdk.register_user("benuser1", "ben1@bank.com", "Pass1234!", "Ben User 1")

        # Valid beneficiary
        b, err = sdk.create_beneficiary(
            user_id=u.id,
            name="Alice Smith",
            account_number="123456789012",
            bank_name="National Reserve Bank",
            ifsc="NRBN0123456"
        )
        assert err is None
        assert b is not None
        assert b.name == "Alice Smith"

        # Invalid IFSC
        bad_b, bad_err = sdk.create_beneficiary(
            user_id=u.id,
            name="Bob Brown",
            account_number="987654321098",
            bank_name="Global Bank",
            ifsc="INVALID_IFSC"
        )
        assert bad_b is None
        assert bad_err is not None
        assert "ifsc" in bad_err.lower() or "invalid" in bad_err.lower()


def test_sdk_version_history_and_compare_versions(app):
    """Test SDK get_version_history and compare_versions for entity changes."""
    with app.app_context():
        sdk = BankingApp()
        u, _ = sdk.register_user("veruser1", "ver1@bank.com", "Pass1234!", "Ver User 1")
        acc = banking_service.create_account(u.id, AccountType.SAVINGS)
        db.session.commit()

        # Make two balance changes
        sdk.deposit(acc.id, Decimal("1000.00"))
        sdk.deposit(acc.id, Decimal("2500.00"))

        history = sdk.get_version_history(EntityType.ACCOUNT, acc.id)
        assert len(history) >= 2

        # Compare version 1 and 2
        diff = sdk.compare_versions(EntityType.ACCOUNT, acc.id, 1, 2)
        assert diff["entity_type"] == EntityType.ACCOUNT
        assert "version_a" in diff
        assert "version_b" in diff
        assert "fields" in diff


def test_sdk_maker_checker_rollback_workflow(app):
    """Test SDK maker-checker rollback request submission and admin approval."""
    with app.app_context():
        sdk = BankingApp()
        maker, _ = sdk.register_user("maker1", "maker1@bank.com", "Pass1234!", "Maker User", role=Role.CUSTOMER)
        admin, _ = sdk.register_user("admin1", "admin1@bank.com", "Pass1234!", "Admin Reviewer", role=Role.ADMIN)

        acc = banking_service.create_account(maker.id, AccountType.SAVINGS)
        db.session.commit()

        sdk.deposit(acc.id, Decimal("1000.00"))  # v1 balance 1000
        sdk.deposit(acc.id, Decimal("5000.00"))  # v2 balance 6000

        # Request rollback to v1
        req, req_err = sdk.request_rollback(
            requested_by=maker.id,
            entity_type=EntityType.ACCOUNT,
            entity_id=acc.id,
            target_version=1,
            reason="Accidental deposit input"
        )
        assert req_err is None
        assert req is not None
        assert req.status == RollbackStatus.PENDING

        # Admin approves rollback
        app_req, app_err = sdk.approve_rollback(req.id, admin.id, "Approved error reversal")
        assert app_err is None
        assert app_req is not None
        assert app_req.status in [RollbackStatus.APPROVED, RollbackStatus.EXECUTED]

        db.session.refresh(acc)
        assert acc.balance == Decimal("1000.00")


def test_sdk_risk_engine_review_and_release(app):
    """Test SDK review_risk for high-risk transactions."""
    with app.app_context():
        sdk = BankingApp()
        u, _ = sdk.register_user("riskuser1", "risk1@bank.com", "Pass1234!", "Risk User 1")
        admin, _ = sdk.register_user("riskadmin1", "riskadmin1@bank.com", "Pass1234!", "Risk Admin", role=Role.ADMIN)

        acc = banking_service.create_account(u.id, AccountType.SAVINGS)
        db.session.commit()

        # Trigger high risk evaluation
        txn, _ = sdk.deposit(acc.id, Decimal("500000.00"))
        assessment = risk_engine.evaluate_transaction_risk(source_account=acc, destination_account=None, amount=Decimal("500000.00"), actor_user_id=u.id)
        db.session.add(assessment)
        db.session.commit()

        # Review and approve risk assessment via SDK
        reviewed_assessment, err = sdk.review_risk(assessment.id, admin.id, approve=True, review_notes="Verified client identity")
        assert err is None
        assert reviewed_assessment is not None
        assert reviewed_assessment.decision == RiskDecision.APPROVED


def test_sdk_verify_audit_chain(app):
    """Test SDK verify_audit_chain returns valid status for pristine log ledger."""
    with app.app_context():
        sdk = BankingApp()
        sdk.register_user("auduser1", "aud1@bank.com", "Pass1234!", "Aud User 1")

        is_valid, msg = sdk.verify_audit_chain()
        assert is_valid is True
        assert "intact" in msg.lower() or "valid" in msg.lower() or "verified" in msg.lower()


def test_cli_print_diff_formatting(capsys):
    """Test CLI print_header and print_diff formatting utilities."""
    print_header("Test Section")
    out_header = capsys.readouterr().out
    assert "TEST SECTION" in out_header
    assert "=" * 60 in out_header

    sample_diff = {
        "v1": 1,
        "v2": 2,
        "entity_type": "account",
        "entity_id": 42,
        "fields": {
            "balance": {"status": "modified", "old": "1000.00", "new": "5000.00"},
            "status": {"status": "added", "old": None, "new": "active"},
        }
    }
    print_diff(sample_diff)
    out_diff = capsys.readouterr().out
    assert "VERSION COMPARISON: v1 -> v2" in out_diff
    assert "Entity: account #42" in out_diff
    assert "[*] balance: 1000.00 -> 5000.00" in out_diff
    assert "[+] status: active" in out_diff


def test_demo_python_workflow_script_execution(app):
    """Test end-to-end multi-step programmatic Python SDK session using BankVCSAPI alias."""
    with app.app_context():
        api = BankVCSAPI()

        # Step 1: Customer Onboarding
        cust, err = api.register_user("e2e_cust", "e2e@bank.com", "StrongPass99!", "E2E Customer")
        assert err is None

        adm, err = api.register_user("e2e_admin", "e2eadmin@bank.com", "StrongPass99!", "E2E Admin", role=Role.ADMIN)
        assert err is None

        # Step 2: Account & Banking Operations
        acc1 = banking_service.create_account(cust.id, AccountType.SAVINGS)
        acc2 = banking_service.create_account(cust.id, AccountType.CURRENT)
        db.session.commit()

        api.deposit(acc1.id, Decimal("25000.00"), description="Salary Credit")
        api.transfer(acc1.id, acc2.id, Decimal("5000.00"), description="Checking Allocation")

        # Step 3: Beneficiary Management
        ben, err = api.create_beneficiary(cust.id, "E2E Vendor", "998877665544", "HDFC Bank", "HDFC0001234")
        assert err is None

        # Step 4: Version Control & Rollback Governance
        history = api.get_version_history(EntityType.ACCOUNT, acc1.id)
        assert len(history) >= 2

        # Step 5: Audit Chain Integrity
        valid_chain, chain_msg = api.verify_audit_chain()
        assert valid_chain is True
