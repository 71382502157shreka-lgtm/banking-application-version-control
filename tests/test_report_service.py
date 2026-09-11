"""
Unit tests for Report Generation Service in BankVCS 2.0.
"""

import pytest
from app import db
from app.models.account import AccountType
from app.services import auth_service, banking_service, report_service


def test_executive_summary_report(app):
    """Test generation of system-wide executive summary report."""
    with app.app_context():
        u = auth_service.register_user("repuser", "rep@bank.com", "Pass1234!", "Report User")
        acc1 = banking_service.create_account(u.id, AccountType.SAVINGS)
        acc2 = banking_service.create_account(u.id, AccountType.CURRENT)
        banking_service.deposit(acc1, 1500, "Deposit 1", u.id)
        banking_service.deposit(acc2, 3500, "Deposit 2", u.id)

        summary = report_service.generate_executive_summary_report()
        assert summary["users_summary"]["customers"] >= 1
        assert summary["financial_summary"]["total_accounts"] >= 2
        assert summary["financial_summary"]["total_system_balance"] >= 5000.0
        assert summary["transaction_summary"]["total_transactions"] >= 2


def test_customer_portfolio_summary(app):
    """Test generating portfolio summary for a specific customer."""
    with app.app_context():
        u = auth_service.register_user("custport", "custport@bank.com", "Pass1234!", "Customer Portfolio")
        acc = banking_service.create_account(u.id, AccountType.SAVINGS)
        banking_service.deposit(acc, 2500, "Initial deposit", u.id)

        port = report_service.generate_customer_portfolio_summary(u.id)
        assert port is not None
        assert port["customer"]["username"] == "custport"
        assert port["financial_summary"]["account_count"] == 1
        assert port["financial_summary"]["total_balance"] == 2500.0
        assert len(port["financial_summary"]["accounts"]) == 1


def test_csv_audit_export(app):
    """Test export of audit logs to CSV string."""
    with app.app_context():
        csv_data = report_service.export_audit_log_csv(limit=50)
        assert isinstance(csv_data, str)
        assert "Log_ID" in csv_data
        assert "Action" in csv_data
        assert "Hash" in csv_data


def test_text_executive_report_export(app):
    """Test generating plain text formatted executive report."""
    with app.app_context():
        json_rep = report_service.export_executive_summary_json()
        assert "BANKVCS_2_0_EXECUTIVE_REPORT" in json_rep
        assert "users_summary" in json_rep
