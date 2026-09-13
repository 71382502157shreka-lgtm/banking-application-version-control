"""
Phase 2 - Feature 9 Automated Test Suite:
Cryptographic Audit Chain Verification, Tamper Detection, & System Health Diagnostics Engine.

Tests SHA-256 hash chain verification, payload tampering detection, broken link detection,
database schema integrity, foreign key checks, orphan record detection, and environment diagnostics.
"""

import pytest
from app import db
from app.models.user import User, Role
from app.models.account import Account, AccountType
from app.models.audit_log import AuditLog, AuditAction
from app.services import auth_service, audit_service
from app.services.audit_chain_service import AuditChainService
from app.utils.diagnostics import (
    DatabaseIntegrityDiagnostic,
    CryptographicAuditDiagnostic,
    EnvironmentHealthDiagnostic,
    run_full_system_diagnostic,
)


def test_audit_chain_verification_intact_chain(app):
    """Test AuditChainService full verification on an intact audit chain."""
    with app.app_context():
        u = auth_service.register_user("diaguser1", "diag1@bank.com", "Pass1234!", "Diag User 1")
        audit_service.log_action(user_id=u.id, action=AuditAction.LOGIN, description="User login test 1")
        audit_service.log_action(user_id=u.id, action=AuditAction.ACCOUNT_CREATED, description="Account setup test 1")

        result = AuditChainService.verify_full_chain_integrity()
        assert result["is_intact"] is True
        assert result["status"] == "VALID"
        assert result["total_records"] >= 2
        assert len(result["broken_records"]) == 0
        assert len(result["tampered_logs"]) == 0


def test_audit_chain_tamper_detection_tampered_payload(app):
    """Test AuditChainService detects payload tampering when current_hash mismatch occurs."""
    with app.app_context():
        u = auth_service.register_user("tamperuser", "tamper@bank.com", "Pass1234!", "Tamper User")
        log_entry = audit_service.log_action(user_id=u.id, action="TRANSFER", description="Valid transfer")

        # Mutate payload directly in DB to simulate tampering
        log_entry.description = "Tampered transfer description"
        db.session.commit()

        result = AuditChainService.verify_full_chain_integrity()
        assert result["is_intact"] is False
        assert result["status"] == "CORRUPTED"
        assert len(result["tampered_logs"]) >= 1
        tampered_ids = [t["id"] for t in result["tampered_logs"]]
        assert log_entry.id in tampered_ids


def test_audit_chain_broken_link_detection(app):
    """Test AuditChainService detects broken previous_hash links."""
    with app.app_context():
        u = auth_service.register_user("brokenuser", "broken@bank.com", "Pass1234!", "Broken User")
        l1 = audit_service.log_action(user_id=u.id, action="ACTION_1", description="action 1")
        l2 = audit_service.log_action(user_id=u.id, action="ACTION_2", description="action 2")

        # Break hash link continuity
        l2.previous_hash = "CORRUPTED_HASH_LINK_0000000000000000000000000000000000000000"
        db.session.commit()

        result = AuditChainService.verify_full_chain_integrity()
        assert result["is_intact"] is False
        assert len(result["broken_records"]) >= 1


def test_audit_action_frequency_breakdown(app):
    """Test action breakdown frequency map calculations."""
    with app.app_context():
        u = auth_service.register_user("frequser", "freq@bank.com", "Pass1234!", "Freq User")
        audit_service.log_action(user_id=u.id, action="FREQ_ACT_A", description="act a")
        audit_service.log_action(user_id=u.id, action="FREQ_ACT_A", description="act a again")
        audit_service.log_action(user_id=u.id, action="FREQ_ACT_B", description="act b")

        breakdown = AuditChainService.get_action_breakdown()
        assert breakdown.get("FREQ_ACT_A", 0) >= 2
        assert breakdown.get("FREQ_ACT_B", 0) >= 1


def test_user_activity_summary_audit_logs(app):
    """Test per-user audit log activity breakdown and non-existent user handling."""
    with app.app_context():
        u = auth_service.register_user("summaryuser", "summaryuser@bank.com", "Pass1234!", "Summary User")
        audit_service.log_action(user_id=u.id, action="LOGIN", description="login event")

        summary = AuditChainService.get_user_activity_summary(u.id)
        assert summary["found"] is not False
        assert summary["user_id"] == u.id
        assert summary["total_audit_events"] >= 1

        non_user_summary = AuditChainService.get_user_activity_summary(999999)
        assert non_user_summary["found"] is False


def test_audit_chain_json_export_structure(app):
    """Test AuditChainService.export_audit_summary_json formatting."""
    with app.app_context():
        json_str = AuditChainService.export_audit_summary_json()
        assert "BANKVCS_2_0_AUDIT_LEDGER" in json_str
        assert "audit_chain_verification" in json_str
        assert "action_frequency_breakdown" in json_str


def test_database_integrity_diagnostic_schema_and_rows(app):
    """Test DatabaseIntegrityDiagnostic table existence and row count checks."""
    with app.app_context():
        diag = DatabaseIntegrityDiagnostic()
        tables = diag.check_tables_exist()
        assert tables["users"] is True
        assert tables["accounts"] is True
        assert tables["transactions"] is True
        assert tables["audit_logs"] is True

        counts = diag.get_table_row_counts()
        assert "users" in counts
        assert counts["users"] >= 0


def test_database_integrity_orphan_records_check(app):
    """Test orphan record detection in DatabaseIntegrityDiagnostic."""
    with app.app_context():
        diag = DatabaseIntegrityDiagnostic()
        orphans = diag.check_orphan_records()
        assert "orphans_found" in orphans
        assert isinstance(orphans["orphans_found"], list)


def test_cryptographic_audit_diagnostic_verification(app):
    """Test CryptographicAuditDiagnostic verify_hash_chain method."""
    with app.app_context():
        crypto_diag = CryptographicAuditDiagnostic()
        res = crypto_diag.verify_hash_chain()
        assert "verified" in res
        assert "total_records" in res
        assert "broken_links" in res


def test_environment_health_diagnostic_metadata():
    """Test EnvironmentHealthDiagnostic system metadata extraction."""
    meta = EnvironmentHealthDiagnostic.get_system_metadata()
    assert "python_version" in meta
    assert "platform" in meta
    assert "executable" in meta
    assert "system_time_utc" in meta


def test_run_full_system_diagnostic_aggregator(app):
    """Test consolidated system diagnostic runner."""
    with app.app_context():
        diag_res = run_full_system_diagnostic()
        assert "status" in diag_res
        assert "database" in diag_res
        assert "cryptographic_audit" in diag_res
        assert "environment" in diag_res


def test_audit_chain_empty_database_handling(app):
    """Test AuditChainService behavior when audit log is completely empty."""
    with app.app_context():
        db.session.query(AuditLog).delete()
        db.session.commit()

        res = AuditChainService.verify_full_chain_integrity()
        assert res["status"] == "EMPTY"
        assert res["is_intact"] is True
        assert res["total_records"] == 0
