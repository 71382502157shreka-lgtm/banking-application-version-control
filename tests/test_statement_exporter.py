"""
Unit tests for Bank Statement Exporter Service in BankVCS 2.0.
"""

import pytest
from app import db
from app.models.account import AccountType
from app.services import auth_service, banking_service
from app.services.statement_exporter import AccountStatementExporter


def test_statement_exporter_csv_and_text(app):
    """Test generating CSV and text formatted account statements."""
    with app.app_context():
        u = auth_service.register_user("stmtuser", "stmt@bank.com", "Pass1234!", "Statement User")
        acc = banking_service.create_account(u.id, AccountType.SAVINGS)
        banking_service.deposit(acc, 500, "Salary deposit", u.id)
        banking_service.withdraw(acc, 100, "ATM withdrawal", u.id)

        exporter = AccountStatementExporter(acc.id)
        data = exporter.get_statement_data()
        assert data["account_number"] == acc.account_number
        assert data["summary"]["total_deposits"] == 500.0
        assert data["summary"]["total_withdrawals"] == 100.0
        assert len(data["ledger"]) == 2

        csv_content = exporter.export_csv()
        assert "BANKVCS 2.0 ACCOUNT STATEMENT" in csv_content
        assert acc.account_number in csv_content

        text_content = exporter.export_text_statement()
        assert "BANKVCS 2.0 OFFICIAL STATEMENT" in text_content
        assert acc.account_number in text_content


def test_statement_exporter_invalid_account(app):
    """Test error handling for non-existent account ID."""
    with app.app_context():
        with pytest.raises(ValueError):
            AccountStatementExporter(999999)
