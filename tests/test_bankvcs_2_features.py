import pytest
from app import db
from app.models import User, Role, Account, Beneficiary, AuditLog, EntityVersion, RiskAssessment, RollbackRequest, RollbackStatus
from app.services.audit_service import log_action, verify_audit_integrity
from app.services.fraud_service import evaluate_transaction_risk
from app.services.version_service import create_version, restore_version


def test_audit_hash_chain_integrity(app):
    with app.app_context():
        # Clear existing logs for isolated test
        AuditLog.query.delete()
        db.session.commit()

        log_action("LOGIN", user_id=1, role=Role.CUSTOMER, description="User logged in")
        log_action("DEPOSIT", user_id=1, role=Role.CUSTOMER, description="Deposited ₹5,000")
        db.session.commit()

        result = verify_audit_integrity()
        assert result["valid"] is True
        assert result["total_records"] == 2
        assert "AUDIT CHAIN VALID" in result["message"]


def test_audit_tampering_detection(app):
    with app.app_context():
        AuditLog.query.delete()
        db.session.commit()

        e1 = log_action("LOGIN", user_id=1, role=Role.CUSTOMER, description="Clean event 1")
        e2 = log_action("DEPOSIT", user_id=1, role=Role.CUSTOMER, description="Clean event 2")
        db.session.commit()

        # Tamper with event 1 description directly in DB
        e1.description = "TAMPERED_EVENT"
        db.session.commit()

        result = verify_audit_integrity()
        assert result["valid"] is False
        assert "AUDIT INTEGRITY VIOLATION" in result["message"]


def test_risk_intelligence_engine(app):
    with app.app_context():
        user = User(username="risktest", email="risk@test.com")
        user.set_password("Pass123!")
        db.session.add(user)
        db.session.flush()

        acc = Account(user_id=user.id, balance=100000.0, available_balance=100000.0)
        db.session.add(acc)
        db.session.commit()

        # Small amount transfer -> Low risk
        res_low = evaluate_transaction_risk(user.id, acc, amount=5000.0)
        assert res_low.risk_score < 30
        assert res_low.decision == "APPROVED"

        # Very high amount transfer (₹100,000 & 100% balance depletion) -> Medium/High risk score (55+)
        res_high = evaluate_transaction_risk(user.id, acc, amount=100000.0)
        assert res_high.risk_score >= 50
        assert res_high.risk_level in ("MEDIUM", "HIGH", "CRITICAL")


def test_rollback_creates_new_version(app):
    with app.app_context():
        user = User(username="rolltest", email="roll@test.com")
        user.set_password("Pass123!")
        db.session.add(user)
        db.session.flush()

        acc = Account(user_id=user.id, account_type="SAVINGS")
        db.session.add(acc)
        db.session.flush()

        v1 = create_version("ACCOUNT", acc.id, "CREATE", None, acc.to_dict(), user.id, "v1 created")
        db.session.commit()

        # Modify account
        acc.account_type = "CHECKING"
        v2 = create_version("ACCOUNT", acc.id, "UPDATE", v1.new_data, acc.to_dict(), user.id, "v2 updated")
        db.session.commit()

        # Restore to v1 snapshot
        def apply_fn(snap):
            acc.account_type = snap["account_type"]
            return acc.to_dict()

        restored_state = restore_version("ACCOUNT", acc.id, 1, user.id, apply_fn, reason="Testing rollback")
        db.session.commit()

        # Verify history has 3 distinct versions (v1, v2, v3 RESTORE)
        history = EntityVersion.query.filter_by(entity_type="ACCOUNT", entity_id=acc.id).order_by(EntityVersion.version_number.asc()).all()
        assert len(history) == 3
        assert history[2].version_number == 3
        assert history[2].change_type == "RESTORE"
        assert history[2].restored_from_version == 1
        assert history[2].new_data["account_type"] == "SAVINGS"


def test_api_v1_status(client):
    res = client.get("/api/v1/status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["api_version"] == "v1"
    assert data["status"] == "online"
