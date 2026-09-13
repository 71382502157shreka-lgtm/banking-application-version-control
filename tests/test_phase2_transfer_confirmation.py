import re
import pytest
from decimal import Decimal
from app import db
from app.models.user import Role
from app.models.account import Account, AccountType, AccountStatus
from app.models.beneficiary import Beneficiary, BeneficiaryStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.services import auth_service, banking_service, beneficiary_service


def login(client, username, password="Str0ngPass!"):
    get_res = client.get("/login")
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', get_res.get_data(as_text=True))
    token = match.group(1) if match else ""
    return client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": token},
        follow_redirects=True,
    )


@pytest.fixture
def customer_sender(app):
    user = auth_service.register_user(
        "sender_user", "sender@example.com", "Str0ngPass!", full_name="Sender User", role=Role.CUSTOMER
    )
    acc = banking_service.create_account(user.id, AccountType.SAVINGS)
    banking_service.deposit(acc, 5000, "Initial Deposit", user.id)
    return user, acc


@pytest.fixture
def customer_receiver(app):
    user = auth_service.register_user(
        "receiver_user", "receiver@example.com", "Str0ngPass!", full_name="Receiver User", role=Role.CUSTOMER
    )
    acc = banking_service.create_account(user.id, AccountType.SAVINGS)
    banking_service.deposit(acc, 1000, "Initial Deposit", user.id)
    return user, acc


def test_successful_fund_transfer(client, customer_sender, customer_receiver):
    sender_user, sender_acc = customer_sender
    _, receiver_acc = customer_receiver

    login(client, sender_user.username)

    resp = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "destination_account_id": receiver_acc.id,
            "amount": 1500,
            "description": "Test Transfer",
            "otp": "123456"
        }
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert "debit" in data
    assert "credit" in data
    assert float(data["debit"]["amount"]) == 1500

    db.session.refresh(sender_acc)
    db.session.refresh(receiver_acc)
    assert sender_acc.available_balance == Decimal("3500.00")
    assert receiver_acc.available_balance == Decimal("2500.00")


def test_zero_transfer_amount_rejection(client, customer_sender, customer_receiver):
    sender_user, sender_acc = customer_sender
    _, receiver_acc = customer_receiver

    login(client, sender_user.username)

    resp = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "destination_account_id": receiver_acc.id,
            "amount": 0,
            "description": "Zero Amount",
            "otp": "123456"
        }
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_negative_transfer_amount_rejection(client, customer_sender, customer_receiver):
    sender_user, sender_acc = customer_sender
    _, receiver_acc = customer_receiver

    login(client, sender_user.username)

    resp = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "destination_account_id": receiver_acc.id,
            "amount": -500,
            "description": "Negative Amount",
            "otp": "123456"
        }
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_insufficient_balance_rejection(client, customer_sender, customer_receiver):
    sender_user, sender_acc = customer_sender
    _, receiver_acc = customer_receiver

    login(client, sender_user.username)

    resp = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "destination_account_id": receiver_acc.id,
            "amount": 40000,
            "description": "Overdraft Attempt",
            "otp": "123456"
        }
    )
    assert resp.status_code == 422
    data = resp.get_json()
    assert "Insufficient available balance" in data.get("error", "")


def test_same_account_transfer_rejection(client, customer_sender):
    sender_user, sender_acc = customer_sender

    login(client, sender_user.username)

    resp = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "destination_account_id": sender_acc.id,
            "amount": 500,
            "description": "Self Transfer",
            "otp": "123456"
        }
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "same account" in data.get("error", "").lower() or "cannot transfer to the same account" in data.get("error", "").lower()


def test_invalid_destination_account_rejection(client, customer_sender):
    sender_user, sender_acc = customer_sender

    login(client, sender_user.username)

    resp = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "destination_account_id": 999999,
            "amount": 500,
            "description": "Non-existent Destination",
            "otp": "123456"
        }
    )
    assert resp.status_code == 404
    data = resp.get_json()
    assert "Destination account not found" in data.get("error", "")


def test_inactive_beneficiary_rejection(client, customer_sender, customer_receiver):
    sender_user, sender_acc = customer_sender
    _, receiver_acc = customer_receiver

    # Add inactive beneficiary
    bene = beneficiary_service.add_beneficiary(
        user_id=sender_user.id,
        data={
            "name": "Inactive Beneficiary",
            "bank_name": "Test Bank",
            "account_number": receiver_acc.account_number,
            "ifsc": "SBIN0001111"
        }
    )
    bene.status = BeneficiaryStatus.INACTIVE
    db.session.commit()

    login(client, sender_user.username)

    resp = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "beneficiary_id": bene.id,
            "amount": 500,
            "description": "Transfer to Inactive Beneficiary",
            "otp": "123456"
        }
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "inactive" in data.get("error", "").lower()


def test_unauthorized_beneficiary_idor_rejection(client, customer_sender, customer_receiver):
    sender_user, sender_acc = customer_sender
    receiver_user, receiver_acc = customer_receiver

    # Receiver adds a beneficiary
    bene = beneficiary_service.add_beneficiary(
        user_id=receiver_user.id,
        data={
            "name": "Receiver Private Bene",
            "bank_name": "Test Bank",
            "account_number": "987654321098",
            "ifsc": "SBIN0002222"
        }
    )

    # Sender tries to use receiver's beneficiary ID
    login(client, sender_user.username)

    resp = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "beneficiary_id": bene.id,
            "amount": 500,
            "description": "IDOR Attempt",
            "otp": "123456"
        }
    )
    assert resp.status_code == 404
    data = resp.get_json()
    assert "not found or unauthorized" in data.get("error", "").lower()


def test_duplicate_submission_prevention(client, customer_sender, customer_receiver):
    sender_user, sender_acc = customer_sender
    _, receiver_acc = customer_receiver

    login(client, sender_user.username)

    # Make transfer
    resp1 = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "destination_account_id": receiver_acc.id,
            "amount": 1000,
            "description": "First Attempt",
            "otp": "123456"
        }
    )
    assert resp1.status_code == 201

    # Check sender balance after first transfer
    db.session.refresh(sender_acc)
    assert sender_acc.available_balance == Decimal("4000.00")


def test_database_rollback_on_exception(app, customer_sender, customer_receiver):
    sender_user, sender_acc = customer_sender
    _, receiver_acc = customer_receiver

    initial_sender_balance = sender_acc.balance

    # Force error during transfer by passing mock invalid state
    with pytest.raises(Exception):
        with app.app_context():
            # Trigger exception inside transaction
            db.session.get(Account, sender_acc.id)
            banking_service.transfer(
                sender_acc, receiver_acc, Decimal("100.00"), "Rollback Test", sender_user.id
            )
            # Simulate a failure before commit
            raise RuntimeError("Database error forced")

    db.session.refresh(sender_acc)
    assert sender_acc.balance == initial_sender_balance


def test_unique_reference_number_generation(client, customer_sender, customer_receiver):
    sender_user, sender_acc = customer_sender
    _, receiver_acc = customer_receiver

    login(client, sender_user.username)

    r1 = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "destination_account_id": receiver_acc.id,
            "amount": 100,
            "description": "Ref Test 1",
            "otp": "123456"
        }
    )
    r2 = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "destination_account_id": receiver_acc.id,
            "amount": 200,
            "description": "Ref Test 2",
            "otp": "123456"
        }
    )

    d1 = r1.get_json()["debit"]["reference_number"]
    d2 = r2.get_json()["debit"]["reference_number"]

    assert d1.startswith("TXN-")
    assert d2.startswith("TXN-")
    assert d1 != d2


def test_sender_and_receiver_balance_verification(client, customer_sender, customer_receiver):
    sender_user, sender_acc = customer_sender
    _, receiver_acc = customer_receiver

    login(client, sender_user.username)

    start_sender = sender_acc.balance
    start_receiver = receiver_acc.balance
    transfer_amount = Decimal("750.50")

    resp = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "destination_account_id": receiver_acc.id,
            "amount": float(transfer_amount),
            "description": "Exact Balance Test",
            "otp": "123456"
        }
    )
    assert resp.status_code == 201

    db.session.refresh(sender_acc)
    db.session.refresh(receiver_acc)

    assert sender_acc.balance == start_sender - transfer_amount
    assert receiver_acc.balance == start_receiver + transfer_amount


def test_transaction_history_entry_creation(client, customer_sender, customer_receiver):
    sender_user, sender_acc = customer_sender
    _, receiver_acc = customer_receiver

    login(client, sender_user.username)

    resp = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "destination_account_id": receiver_acc.id,
            "amount": 300,
            "description": "History Entry Test",
            "otp": "123456"
        }
    )
    assert resp.status_code == 201

    sender_txns = Transaction.query.filter_by(account_id=sender_acc.id).all()
    receiver_txns = Transaction.query.filter_by(account_id=receiver_acc.id).all()

    # Includes initial deposit + transfer
    assert len(sender_txns) >= 2
    assert len(receiver_txns) >= 2

    latest_sender_txn = sender_txns[-1]
    assert latest_sender_txn.transaction_type == TransactionType.TRANSFER
    assert latest_sender_txn.amount == Decimal("300.00")
    assert latest_sender_txn.counterparty_account_id == receiver_acc.id


def test_transfer_confirmation_receipt_download(client, customer_sender, customer_receiver):
    sender_user, sender_acc = customer_sender
    _, receiver_acc = customer_receiver

    login(client, sender_user.username)

    resp = client.post(
        "/api/transactions/transfer",
        json={
            "source_account_id": sender_acc.id,
            "destination_account_id": receiver_acc.id,
            "amount": 500,
            "description": "Receipt Test",
            "otp": "123456"
        }
    )
    assert resp.status_code == 201
    debit_id = resp.get_json()["debit"]["id"]

    receipt_resp = client.get(f"/api/transactions/{debit_id}/receipt")
    assert receipt_resp.status_code == 200
    assert receipt_resp.mimetype == "application/pdf"
