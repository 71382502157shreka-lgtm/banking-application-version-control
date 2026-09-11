"""
System Diagnostic Utilities for BankVCS 2.0.

Provides comprehensive diagnostic checks for database integrity, foreign key relations,
cryptographic SHA-256 audit log hash chains, version table consistency, and system environment health.
"""

import logging
import os
import sys
import platform
import datetime
from typing import Dict, List, Any, Tuple
from sqlalchemy import inspect, text

from app import db
from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.models.version import EntityVersion
from app.models.workflow_risk import RollbackRequest

logger = logging.getLogger(__name__)


class DatabaseIntegrityDiagnostic:
    """
    Performs comprehensive diagnostic checks on SQLite database tables,
    schema configurations, indexes, and foreign key integrity.
    """

    EXPECTED_TABLES = [
        "users",
        "accounts",
        "transactions",
        "audit_logs",
        "entity_versions",
        "rollback_requests",
    ]

    def __init__(self, db_instance=db):
        self.db = db_instance

    def run_all_checks(self) -> Dict[str, Any]:
        """Runs complete database diagnostic suite and returns detailed results."""
        results = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "tables_status": self.check_tables_exist(),
            "fk_integrity": self.check_foreign_keys(),
            "table_row_counts": self.get_table_row_counts(),
            "orphan_records": self.check_orphan_records(),
            "passed_all": True,
        }

        # Check if any sub-checks failed
        tables_ok = all(results["tables_status"].values())
        fk_ok = results["fk_integrity"].get("integrity_ok", False)
        orphans_ok = len(results["orphan_records"].get("orphans_found", [])) == 0

        results["passed_all"] = tables_ok and fk_ok and orphans_ok
        return results

    def check_tables_exist(self) -> Dict[str, bool]:
        """Verifies that all required application tables exist in the database."""
        inspector = inspect(self.db.engine)
        existing_tables = set(inspector.get_table_names())
        return {table: (table in existing_tables) for table in self.EXPECTED_TABLES}

    def check_foreign_keys(self) -> Dict[str, Any]:
        """Executes SQLite foreign_key_check pragma to verify FK constraint compliance."""
        try:
            result = self.db.session.execute(text("PRAGMA foreign_key_check")).fetchall()
            if not result:
                return {"integrity_ok": True, "violations": []}
            
            violations = [
                {
                    "table": row[0],
                    "rowid": row[1],
                    "target_table": row[2],
                    "fkid": row[3],
                }
                for row in result
            ]
            return {"integrity_ok": False, "violations": violations}
        except Exception as e:
            logger.error(f"Error executing PRAGMA foreign_key_check: {e}")
            return {"integrity_ok": False, "error": str(e), "violations": []}

    def get_table_row_counts(self) -> Dict[str, int]:
        """Retrieves exact row counts for all application models."""
        counts = {}
        models_map = {
            "users": User,
            "accounts": Account,
            "transactions": Transaction,
            "audit_logs": AuditLog,
            "entity_versions": EntityVersion,
            "rollback_requests": RollbackRequest,
        }
        for table_name, model in models_map.items():
            try:
                counts[table_name] = self.db.session.query(model).count()
            except Exception as e:
                logger.error(f"Error counting table {table_name}: {e}")
                counts[table_name] = -1
        return counts

    def check_orphan_records(self) -> Dict[str, Any]:
        """Detects orphan accounts or transactions lacking existing parent references."""
        orphans = []
        try:
            # Accounts with non-existent user_id
            invalid_acc_users = (
                self.db.session.query(Account)
                .outerjoin(User, Account.user_id == User.id)
                .filter(User.id.is_(None))
                .all()
            )
            for acc in invalid_acc_users:
                orphans.append(f"Account ID {acc.id} references non-existent User ID {acc.user_id}")

            # Transactions with non-existent account_id
            invalid_tx_accs = (
                self.db.session.query(Transaction)
                .outerjoin(Account, Transaction.account_id == Account.id)
                .filter(Account.id.is_(None))
                .all()
            )
            for tx in invalid_tx_accs:
                orphans.append(f"Transaction ID {tx.id} references non-existent Account ID {tx.account_id}")

        except Exception as e:
            logger.error(f"Error checking orphan records: {e}")
            orphans.append(f"Error during orphan check: {str(e)}")

        return {"orphans_found": orphans, "count": len(orphans)}


class CryptographicAuditDiagnostic:
    """
    Diagnoses SHA-256 hash chain verification across audit log entries.
    """

    def __init__(self, db_instance=db):
        self.db = db_instance

    def verify_hash_chain(self) -> Dict[str, Any]:
        """Iterates through all AuditLog entries and verifies cryptographic continuity."""
        logs = self.db.session.query(AuditLog).order_by(AuditLog.id.asc()).all()
        if not logs:
            return {
                "verified": True,
                "total_records": 0,
                "broken_links": [],
                "message": "Audit log is empty.",
            }

        broken_links = []
        expected_prev_hash = "0" * 64

        for log in logs:
            # Verify prev_hash matches expected
            if log.prev_hash != expected_prev_hash:
                broken_links.append(
                    {
                        "log_id": log.id,
                        "expected_prev_hash": expected_prev_hash,
                        "actual_prev_hash": log.prev_hash,
                        "timestamp": log.created_at.isoformat() if log.created_at else None,
                    }
                )

            # Re-calculate expected hash for current log
            calc_hash = log.calculate_hash()
            if log.current_hash != calc_hash:
                broken_links.append(
                    {
                        "log_id": log.id,
                        "stored_hash": log.current_hash,
                        "calculated_hash": calc_hash,
                        "reason": "Hash mismatch (tampering or payload drift)",
                    }
                )

            expected_prev_hash = log.current_hash

        return {
            "verified": len(broken_links) == 0,
            "total_records": len(logs),
            "broken_links": broken_links,
            "first_log_id": logs[0].id if logs else None,
            "last_log_id": logs[-1].id if logs else None,
        }


class EnvironmentHealthDiagnostic:
    """
    Gathers environment and runtime diagnostic metadata for troubleshooting.
    """

    @staticmethod
    def get_system_metadata() -> Dict[str, Any]:
        """Returns Python runtime environment, OS details, and platform information."""
        return {
            "python_version": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "executable": sys.executable,
            "environment": os.environ.get("FLASK_ENV", "development"),
            "system_time_utc": datetime.datetime.utcnow().isoformat() + "Z",
        }


def run_full_system_diagnostic() -> Dict[str, Any]:
    """Helper function to execute all diagnostic modules and return consolidated output."""
    db_diag = DatabaseIntegrityDiagnostic()
    crypto_diag = CryptographicAuditDiagnostic()
    env_diag = EnvironmentHealthDiagnostic()

    db_res = db_diag.run_all_checks()
    crypto_res = crypto_diag.verify_hash_chain()
    env_res = env_diag.get_system_metadata()

    system_ok = db_res["passed_all"] and crypto_res["verified"]

    return {
        "status": "HEALTHY" if system_ok else "WARNING",
        "system_ok": system_ok,
        "database": db_res,
        "cryptographic_audit": crypto_res,
        "environment": env_res,
    }
