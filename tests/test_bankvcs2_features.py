import pytest
from decimal import Decimal
from app import db
from app.models.user import Role
from app.models.version import EntityType
from app.models.workflow_risk import RollbackStatus, RiskLevel, RiskDecision
from app.models.audit_log import AuditLog
from app.services import (
    auth_service, banking_service, beneficiary_service,
    audit_service, risk_engine, mfa_service, session_service, approval_service
)


def test_audit_hash_chain_verification(app):
    with app.app_context():
        u = auth_service.register_user("hashuser", "hash@example.com", "Str0ngPass!", role=Role.CUSTOMER)
        acc = banking_service.create_account(u.id, "SAVINGS")
        banking_service.deposit(acc, "1000.00", "Test Deposit", u.id)

        # 1. Verify chain is initially valid
        report = audit_service.verify_audit_integrity()
        assert report["valid"] is True
        assert "VALID" in report["status"]

        # 2. Simulate Tampering: mutate an old audit record's description directly
        log_to_tamper = AuditLog.query.filter_by(action="DEPOSIT").first()
        assert log_to_tamper is not None
        log_to_tamper.description = "TAMPERED_DESCRIPTION"
        db.session.commit()

        # 3. Verify integrity check flags the tampered record
        tampered_report = audit_service.verify_audit_integrity()
        assert tampered_report["valid"] is False
        assert "VIOLATION" in tampered_report["status"]
        assert tampered_report["broken_record_id"] == log_to_tamper.id


def test_risk_engine_scoring_and_blocking(app):
    with app.app_context():
        c1 = auth_service.register_user("riskcust1", "risk1@example.com", "Str0ngPass!", role=Role.CUSTOMER)
        c2 = auth_service.register_user("riskcust2", "risk2@example.com", "Str0ngPass!", role=Role.CUSTOMER)

        acc1 = banking_service.create_account(c1.id, "SAVINGS")
        acc2 = banking_service.create_account(c2.id, "SAVINGS")
        banking_service.deposit(acc1, "100000.00", "Initial deposit", c1.id)

        # High amount transfer (₹85,000) should trigger score >= 60 -> BLOCKED_FOR_REVIEW
        debit, credit = banking_service.transfer(acc1, acc2, "85000.00", "High Risk Transfer", c1.id)

        assert debit.status == "BLOCKED_FOR_REVIEW"
        assert credit is None  # Money not transferred until approved


def test_maker_checker_rollback_workflow(app):
    with app.app_context():
        admin = auth_service.register_user("admin_mc", "adminmc@example.com", "Str0ngPass!", role=Role.ADMIN)
        cust = auth_service.register_user("cust_mc", "custmc@example.com", "Str0ngPass!", role=Role.CUSTOMER)

        bene = beneficiary_service.add_beneficiary(cust.id, {
            "name": "Original Name",
            "account_number": "111122223333",
            "bank_name": "Bank A",
            "ifsc": "SBIN0001111",
        })
        assert bene.version_number == 1

        # Update beneficiary -> version 2
        beneficiary_service.update_beneficiary(bene, {"name": "Updated Name"}, cust.id)
        assert bene.version_number == 2
        assert bene.name == "Updated Name"

        # Request Rollback to Version 1
        req = approval_service.request_rollback(
            user_id=cust.id,
            entity_type=EntityType.BENEFICIARY,
            entity_id=bene.id,
            target_version=1,
            reason="Mistake in update"
        )
        assert req.status == RollbackStatus.PENDING

        # Admin approves rollback
        approval_service.approve_rollback_request(req.id, admin.id, "Approved rollback")
        
        # Verify beneficiary state restored AND new version (v3) created without deleting history
        restored_bene = db.session.get(type(bene), bene.id)
        assert restored_bene.name == "Original Name"
        assert restored_bene.version_number == 3


def test_mfa_otp_generation_and_verification(app):
    with app.app_context():
        user = auth_service.register_user("mfauser", "mfa@example.com", "Str0ngPass!", role=Role.CUSTOMER)

        code = mfa_service.generate_otp(user.id, "LOGIN")
        assert len(code) == 6

        # Wrong code fails
        with pytest.raises(mfa_service.OTPError):
            mfa_service.verify_otp(user.id, "LOGIN", "000000")

        # Correct code succeeds
        assert mfa_service.verify_otp(user.id, "LOGIN", code) is True


def test_session_creation_and_revocation(app):
    with app.app_context():
        user = auth_service.register_user("sessuser", "sess@example.com", "Str0ngPass!", role=Role.CUSTOMER)

        sess1 = session_service.create_user_session(user.id)
        sess2 = session_service.create_user_session(user.id)

        assert sess1.is_active is True
        assert sess2.is_active is True

        revoked_count = session_service.revoke_other_sessions(user.id, sess2.session_token)
        assert revoked_count == 1
        assert sess1.is_active is False
        assert sess2.is_active is True
