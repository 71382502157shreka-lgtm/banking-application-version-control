"""
Unit tests for System Diagnostic Utilities in BankVCS 2.0.
"""

import pytest
from app import db
from app.utils.diagnostics import (
    DatabaseIntegrityDiagnostic,
    CryptographicAuditDiagnostic,
    EnvironmentHealthDiagnostic,
    run_full_system_diagnostic,
)


def test_database_integrity_diagnostic(app):
    """Test database schema tables and foreign key integrity diagnostic."""
    with app.app_context():
        diag = DatabaseIntegrityDiagnostic()
        tables = diag.check_tables_exist()
        assert tables["users"] is True
        assert tables["accounts"] is True
        assert tables["transactions"] is True
        assert tables["audit_logs"] is True

        fk_check = diag.check_foreign_keys()
        assert fk_check["integrity_ok"] is True
        assert len(fk_check["violations"]) == 0

        counts = diag.get_table_row_counts()
        assert "users" in counts
        assert "accounts" in counts

        orphans = diag.check_orphan_records()
        assert orphans["count"] == 0


def test_cryptographic_audit_diagnostic(app):
    """Test cryptographic SHA-256 hash chain audit diagnostic."""
    with app.app_context():
        crypto_diag = CryptographicAuditDiagnostic()
        result = crypto_diag.verify_hash_chain()
        assert "verified" in result
        assert isinstance(result["broken_links"], list)


def test_environment_health_diagnostic():
    """Test environment metadata collection."""
    meta = EnvironmentHealthDiagnostic.get_system_metadata()
    assert "python_version" in meta
    assert "platform" in meta
    assert "executable" in meta


def test_run_full_system_diagnostic(app):
    """Test complete system diagnostic execution wrapper."""
    with app.app_context():
        full_res = run_full_system_diagnostic()
        assert full_res["status"] in ["HEALTHY", "WARNING"]
        assert "database" in full_res
        assert "cryptographic_audit" in full_res
        assert "environment" in full_res
