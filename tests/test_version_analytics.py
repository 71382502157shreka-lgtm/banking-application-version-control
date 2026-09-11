"""
Unit tests for Version Analytics Service in BankVCS 2.0.
"""

import pytest
from app import db
from app.models.account import AccountType
from app.models.version import EntityType
from app.services import auth_service, banking_service, version_analytics_service


def test_entity_version_trajectory(app):
    """Test generating version trajectory curve for an Account entity."""
    with app.app_context():
        u = auth_service.register_user("vuser", "vuser@bank.com", "Pass1234!", "Version User")
        acc = banking_service.create_account(u.id, AccountType.SAVINGS)

        trajectory = version_analytics_service.analyze_entity_version_trajectory(EntityType.ACCOUNT, acc.id)
        assert trajectory["entity_type"] == EntityType.ACCOUNT
        assert trajectory["entity_id"] == acc.id
        assert trajectory["latest_version"] >= 1
        assert isinstance(trajectory["trajectory"], list)
        assert len(trajectory["trajectory"]) >= 1


def test_system_version_metrics(app):
    """Test generating system-wide version control metrics."""
    with app.app_context():
        summary = version_analytics_service.generate_version_analytics_summary()
        assert "total_snapshots_recorded" in summary
        assert "snapshot_distribution_by_entity" in summary
        assert "rollback_requests" in summary
