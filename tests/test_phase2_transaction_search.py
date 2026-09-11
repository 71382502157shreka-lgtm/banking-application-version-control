import re
from decimal import Decimal
from app import db
from app.models.user import User, Role
from app.models.account import Account
from app.models.transaction import Transaction, TransactionType, TransactionStatus


def login_client(client, username, password="Password123"):
    res = client.get("/login")
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', res.get_data(as_text=True))
    token = match.group(1) if match else ""
    return client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": token},
        follow_redirects=True,
    )


def test_transaction_search_and_pagination(client, app):
    with app.app_context():
        # Setup customer & account
        user = User(username="search_user", email="search@bank.local", role=Role.CUSTOMER)
        user.set_password("Password123")
        db.session.add(user)
        db.session.commit()

        acc = Account(account_number="ACC_SEARCH_001", user_id=user.id, balance=Decimal("5000.00"), available_balance=Decimal("5000.00"))
        db.session.add(acc)
        db.session.commit()

        # Create multiple transactions
        tx1 = Transaction(account_id=acc.id, transaction_type=TransactionType.DEPOSIT, amount=Decimal("1000.00"), description="Salary Credit Ref123", reference_number="TXN10001", status=TransactionStatus.COMPLETED)
        tx2 = Transaction(account_id=acc.id, transaction_type=TransactionType.WITHDRAWAL, amount=Decimal("200.00"), description="ATM Cash", reference_number="TXN10002", status=TransactionStatus.COMPLETED)
        tx3 = Transaction(account_id=acc.id, transaction_type=TransactionType.TRANSFER, amount=Decimal("500.00"), description="Rent Transfer", reference_number="TXN10003", status=TransactionStatus.COMPLETED)
        db.session.add_all([tx1, tx2, tx3])
        db.session.commit()

        login_client(client, "search_user", "Password123")

        # Test 1: Query all transactions with limit
        resp = client.get("/api/transactions?limit=2")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["items"]) == 2
        assert data["total"] == 3
        assert data["pages"] == 2

        # Test 2: Search keyword
        resp_search = client.get("/api/transactions?search=Salary")
        assert resp_search.status_code == 200
        data_search = resp_search.get_json()
        assert len(data_search["items"]) == 1
        assert data_search["items"][0]["reference_number"] == "TXN10001"

        # Test 3: Filter by type
        resp_type = client.get("/api/transactions?type=WITHDRAWAL")
        assert resp_type.status_code == 200
        data_type = resp_type.get_json()
        assert len(data_type["items"]) == 1
        assert data_type["items"][0]["reference_number"] == "TXN10002"
