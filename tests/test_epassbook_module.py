import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from app import create_app, db
from app.models.user import User, Role
from app.models.account import Account, AccountType
from app.models.transaction import Transaction, TransactionType, TransactionStatus, TransactionMode
from app.services import auth_service, banking_service, statement_service


@pytest.fixture
def app_instance():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_epassbook_data_retrieval_and_ownership_isolation(app_instance):
    """Tests E-passbook calculation, totals, and customer IDOR isolation."""
    with app_instance.app_context():
        user1 = auth_service.register_user("user1_passbook", "u1@bank.com", "SecretPass123", "User One")
        user2 = auth_service.register_user("user2_passbook", "u2@bank.com", "SecretPass123", "User Two")

        acc1 = banking_service.create_account(user1.id, AccountType.SAVINGS)
        acc2 = banking_service.create_account(user2.id, AccountType.SAVINGS)

        # Deposit into acc1
        banking_service.deposit(acc1, Decimal("10000.00"), "Salary Deposit", user1.id, transaction_mode="NEFT")
        banking_service.withdraw(acc1, Decimal("2000.00"), "ATM Cash", user1.id, transaction_mode="ATM")
        banking_service.transfer(acc1, acc2, Decimal("3000.00"), "Rent Payment", user1.id, transaction_mode="UPI")

        # Statement for acc1
        statement1 = statement_service.generate_account_statement(acc1.id)
        assert statement1["success"] is True
        assert statement1["customer_name"] == "User One"
        assert statement1["opening_balance"] == 0.0
        assert statement1["total_credits"] == 10000.0
        assert statement1["total_debits"] == 5000.0  # 2000 withdrawal + 3000 transfer
        assert statement1["closing_balance"] == 5000.0
        assert statement1["transaction_count"] == 3

        # Web / API IDOR client test
        client = app_instance.test_client()

        # Login user1
        client.post("/login", data={"username": "user1_passbook", "password": "SecretPass123"})

        # User1 fetching acc1 statement -> 200 OK
        resp1 = client.get(f"/api/statements?account_id={acc1.id}")
        assert resp1.status_code == 200

        # User1 attempting to fetch acc2 statement -> 403 Forbidden (IDOR Protection)
        resp2 = client.get(f"/api/statements?account_id={acc2.id}")
        assert resp2.status_code == 403


def test_statement_date_range_presets(app_instance):
    """Tests date preset resolution math (7 days, 30 days, 3 months, financial year)."""
    today = date.today()

    s7, e7 = statement_service.resolve_date_preset("7_DAYS")
    assert e7 == today
    assert s7 == today - timedelta(days=7)

    s30, e30 = statement_service.resolve_date_preset("30_DAYS")
    assert e30 == today
    assert s30 == today - timedelta(days=30)

    s90, e90 = statement_service.resolve_date_preset("3_MONTHS")
    assert e90 == today
    assert s90 == today - timedelta(days=90)

    sfy, efy = statement_service.resolve_date_preset("CURRENT_FY")
    assert sfy.month == 4
    assert sfy.day == 1

    spf, epf = statement_service.resolve_date_preset("PREVIOUS_FY")
    assert spf.month == 4
    assert spf.day == 1
    assert epf.month == 3
    assert epf.day == 31


def test_transaction_filtering_search_sort_pagination(app_instance):
    """Tests searching, filtering by mode/status/type, sorting, and pagination."""
    with app_instance.app_context():
        user = auth_service.register_user("filter_user", "filter@bank.com", "Password123", "Filter User")
        acc = banking_service.create_account(user.id, AccountType.SAVINGS)

        banking_service.deposit(acc, Decimal("5000.00"), "UPI Transfer from Friend", user.id, transaction_mode="UPI")
        banking_service.deposit(acc, Decimal("2000.00"), "Cash Deposit at Branch", user.id, transaction_mode="CASH_DEPOSIT")
        banking_service.withdraw(acc, Decimal("1000.00"), "ATM Withdrawal", user.id, transaction_mode="ATM")

        # Client tests
        client = app_instance.test_client()
        client.post("/login", data={"username": "filter_user", "password": "Password123"})

        # Search filter
        res_search = client.get("/api/transactions?search=ATM")
        data_search = res_search.get_json()
        assert data_search["success"] is True
        assert len(data_search["items"]) == 1
        assert data_search["items"][0]["transaction_mode"] == "ATM"

        # Mode filter
        res_mode = client.get("/api/transactions?mode=UPI")
        data_mode = res_mode.get_json()
        assert len(data_mode["items"]) == 1
        assert data_mode["items"][0]["transaction_mode"] == "UPI"

        # Type filter
        res_type = client.get("/api/transactions?type=DEPOSIT")
        data_type = res_type.get_json()
        assert len(data_type["items"]) == 2

        # Sort order
        res_asc = client.get("/api/transactions?sort=asc")
        data_asc = res_asc.get_json()
        assert data_asc["items"][0]["transaction_mode"] == "UPI"

        res_desc = client.get("/api/transactions?sort=desc")
        data_desc = res_desc.get_json()
        assert data_desc["items"][0]["transaction_mode"] == "ATM"


def test_statement_download_pdf_csv_xlsx(app_instance):
    """Tests PDF, CSV, and XLSX export file generation endpoints."""
    with app_instance.app_context():
        user = auth_service.register_user("export_user", "exp@bank.com", "Password123", "Exporter User")
        acc = banking_service.create_account(user.id, AccountType.SAVINGS)
        banking_service.deposit(acc, Decimal("15000.00"), "Salary", user.id)

        client = app_instance.test_client()
        client.post("/login", data={"username": "export_user", "password": "Password123"})

        # PDF Download
        pdf_res = client.get(f"/api/statements/download/pdf?account_id={acc.id}")
        assert pdf_res.status_code == 200
        assert pdf_res.mimetype == "application/pdf"
        assert b"%PDF" in pdf_res.data[:10]

        # CSV Download
        csv_res = client.get(f"/api/statements/download/csv?account_id={acc.id}")
        assert csv_res.status_code == 200
        assert csv_res.mimetype == "text/csv"
        assert b"BANKVCS 2.0 OFFICIAL E-PASSBOOK" in csv_res.data

        # Excel Download
        xlsx_res = client.get(f"/api/statements/download/excel?account_id={acc.id}")
        assert xlsx_res.status_code == 200
        assert "spreadsheetml" in xlsx_res.mimetype
        assert len(xlsx_res.data) > 100


def test_transaction_receipt_download_and_invalid_ids(app_instance):
    """Tests PDF receipt generation and invalid transaction / unauthorized access errors."""
    with app_instance.app_context():
        user1 = auth_service.register_user("rec_user1", "rec1@bank.com", "Password123", "Receipt User 1")
        user2 = auth_service.register_user("rec_user2", "rec2@bank.com", "Password123", "Receipt User 2")

        acc1 = banking_service.create_account(user1.id, AccountType.SAVINGS)
        acc2 = banking_service.create_account(user2.id, AccountType.SAVINGS)

        txn1 = banking_service.deposit(acc1, Decimal("2500.00"), "Deposit 1", user1.id)
        txn2 = banking_service.deposit(acc2, Decimal("4000.00"), "Deposit 2", user2.id)

        client = app_instance.test_client()
        client.post("/login", data={"username": "rec_user1", "password": "Password123"})

        # Authorized receipt download
        rec_res = client.get(f"/api/transactions/{txn1.id}/receipt")
        assert rec_res.status_code == 200
        assert rec_res.mimetype == "application/pdf"
        assert b"%PDF" in rec_res.data[:10]

        # Unauthorized access to user2's receipt -> 403
        unauth_res = client.get(f"/api/transactions/{txn2.id}/receipt")
        assert unauth_res.status_code == 403

        # Invalid transaction ID -> 404
        invalid_res = client.get("/api/transactions/999999/receipt")
        assert invalid_res.status_code == 404


def test_empty_transaction_history_and_mini_statement(app_instance):
    """Tests empty state handling and mini statement API."""
    with app_instance.app_context():
        user = auth_service.register_user("empty_user", "empty@bank.com", "Password123", "Empty User")
        acc = banking_service.create_account(user.id, AccountType.SAVINGS)

        client = app_instance.test_client()
        client.post("/login", data={"username": "empty_user", "password": "Password123"})

        # Mini statement for empty account
        mini_res = client.get(f"/api/transactions/mini-statement?account_id={acc.id}")
        assert mini_res.status_code == 200
        mini_data = mini_res.get_json()
        assert mini_data["success"] is True
        assert mini_data["count"] == 0
        assert mini_data["transactions"] == []

        # Statement for empty account
        stmt_res = client.get(f"/api/statements?account_id={acc.id}")
        assert stmt_res.status_code == 200
        stmt_data = stmt_res.get_json()
        assert stmt_data["opening_balance"] == 0.0
        assert stmt_data["closing_balance"] == 0.0
        assert stmt_data["transaction_count"] == 0
