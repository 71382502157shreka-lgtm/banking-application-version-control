"""
Unit tests for Audit Chain Service in BankVCS 2.0.
"""

import pytest
from app import db
from app.services import auth_service, audit_service
from app.services.audit_chain_service import AuditChainService


def test_audit_chain_service_verification(app):
    """Test full audit chain verification service."""
    with app.app_context():
        u = auth_service.register_user("chainuser", "chain@bank.com", "Pass1234!", "Chain User")

        # Log some audit actions
        audit_service.log_action(user_id=u.id, action="TEST_ACTION_1", description="step 1")
        audit_service.log_action(user_id=u.id, action="TEST_ACTION_2", description="step 2")

        res = AuditChainService.verify_full_chain_integrity()
        assert res["is_intact"] is True
        assert res["status"] == "VALID"
        assert res["total_records"] >= 2
        assert len(res["broken_records"]) == 0
        assert len(res["tampered_logs"]) == 0

        breakdown = AuditChainService.get_action_breakdown()
        assert "TEST_ACTION_1" in breakdown
        assert "TEST_ACTION_2" in breakdown

        summary = AuditChainService.get_user_activity_summary(u.id)
        assert summary["user_id"] == u.id
        assert summary["total_audit_events"] >= 2

        json_out = AuditChainService.export_audit_summary_json()
        assert "BANKVCS_2_0_AUDIT_LEDGER" in json_out
        assert "audit_chain_verification" in json_out
