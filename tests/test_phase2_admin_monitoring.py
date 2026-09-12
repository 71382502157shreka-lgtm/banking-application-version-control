import re
import pytest
from datetime import datetime
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
def admin_user(app):
    user = auth_service.register_user(
        "admin_mon", "admin_mon@example.com", "Str0ngPass!", full_name="Admin Mon", role=Role.ADMIN
    )
    return user


@pytest.fixture
def customer_user(app):
    user = auth_service.register_user(
        "cust_mon", "cust_mon@example.com", "Str0ngPass!", full_name="Customer Mon", role=Role.CUSTOMER
    )
    acc = banking_service.create_account(user.id, AccountType.SAVINGS)
    banking_service.deposit(acc, 2000, "Initial Seed", user.id)
    return user, acc


@pytest.fixture
def receiver_user(app):
    user = auth_service.register_user(
        "rec_mon", "rec_mon@example.com", "Str0ngPass!", full_name="Receiver Mon", role=Role.CUSTOMER
    )
    acc = banking_service.create_account(user.id, AccountType.SAVINGS)
    return user, acc


def test_admin_dashboard_access(client, admin_user):
    login(client, admin_user.username)
    resp = client.get("/admin/dashboard")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "System Administration Console" in html
    assert "Total Customers" in html


def test_non_admin_dashboard_rejection(client, customer_user):
    user, _ = customer_user
    login(client, user.username)
    resp = client.get("/admin/dashboard")
    assert resp.status_code in [403, 302]


def test_dashboard_statistics_accuracy(client, admin_user, customer_user, receiver_user):
    c_user, c_acc = customer_user
    _, r_acc = receiver_user

    # Add an active beneficiary
    bene = beneficiary_service.add_beneficiary(
        user_id=c_user.id,
        data={
            "name": "Receiver Mon",
            "bank_name": "Test Bank",
            "account_number": r_acc.account_number,
            "ifsc": "SBIN0001111"
        }
    )

    # Perform a transfer
    banking_service.transfer(c_acc, r_acc, Decimal("500.00"), "Stat Transfer Test", c_user.id)

    login(client, admin_user.username)
    resp = client.get("/admin/dashboard")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    
    assert "System Administration Console" in html


def test_transaction_list_rendering(client, admin_user, customer_user, receiver_user):
    c_user, c_acc = customer_user
    _, r_acc = receiver_user

    banking_service.transfer(c_acc, r_acc, Decimal("300.00"), "List Render Test", c_user.id)

    login(client, admin_user.username)
    resp = client.get("/admin/transactions")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "System Transaction Monitoring" in html
    assert "Reference No." in html


def test_transaction_search_by_reference(client, admin_user, customer_user, receiver_user):
    c_user, c_acc = customer_user
    _, r_acc = receiver_user

    debit_txn, _ = banking_service.transfer(c_acc, r_acc, Decimal("400.00"), "Search Test", c_user.id)
    ref_no = debit_txn.reference_number

    login(client, admin_user.username)
    resp = client.get(f"/admin/transactions?search={ref_no}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert ref_no in html


def test_transaction_filters_status_and_type(client, admin_user, customer_user, receiver_user):
    c_user, c_acc = customer_user
    _, r_acc = receiver_user

    banking_service.transfer(c_acc, r_acc, Decimal("250.00"), "Filter Test", c_user.id)

    login(client, admin_user.username)

    # Filter COMPLETED
    r1 = client.get("/admin/transactions?status=COMPLETED&type=TRANSFER")
    assert r1.status_code == 200
    assert "TRANSFER" in r1.get_data(as_text=True)

    # Filter FAILED
    r2 = client.get("/admin/transactions?status=FAILED")
    assert r2.status_code == 200


def test_transaction_pagination(client, admin_user, customer_user, receiver_user):
    c_user, c_acc = customer_user
    _, r_acc = receiver_user

    # Generate multiple transactions
    for i in range(20):
        banking_service.deposit(c_acc, Decimal("10.00"), f"Deposit #{i}", c_user.id)

    login(client, admin_user.username)

    p1 = client.get("/admin/transactions?page=1")
    assert p1.status_code == 200

    p2 = client.get("/admin/transactions?page=2")
    assert p2.status_code == 200


def test_masked_account_numbers(client, admin_user, customer_user, receiver_user):
    c_user, c_acc = customer_user
    _, r_acc = receiver_user

    banking_service.transfer(c_acc, r_acc, Decimal("150.00"), "Mask Test", c_user.id)

    login(client, admin_user.username)
    resp = client.get("/admin/transactions")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Ensure masked account format is present
    masked_acc = f"XXXX XXXX {c_acc.account_number[-4:]}"
    assert masked_acc in html


def test_audit_and_version_history_access(client, admin_user):
    login(client, admin_user.username)

    r_audit = client.get("/admin/audit-logs")
    assert r_audit.status_code == 200
    assert "Security Audit" in r_audit.get_data(as_text=True) or "Audit" in r_audit.get_data(as_text=True)

    r_ver = client.get("/admin/version-history")
    assert r_ver.status_code == 200
    assert "Version" in r_ver.get_data(as_text=True)


def test_idor_admin_endpoint_protection(client, customer_user):
    user, _ = customer_user
    login(client, user.username)

    assert client.get("/admin/audit-logs").status_code in [403, 302]
    assert client.get("/admin/version-history").status_code in [403, 302]
    assert client.get("/admin/transactions").status_code in [403, 302]
    assert client.get("/admin/users").status_code in [403, 302]


def test_empty_transaction_search_results(client, admin_user):
    login(client, admin_user.username)

    resp = client.get("/admin/transactions?search=NONEXISTENT_TXN_REF_99999")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "No transactions found matching the selected search criteria" in html


def test_transaction_date_filters(client, admin_user, customer_user, receiver_user):
    c_user, c_acc = customer_user
    _, r_acc = receiver_user

    debit_txn, _ = banking_service.transfer(c_acc, r_acc, Decimal("100.00"), "Date Filter Test", c_user.id)
    ref_no = debit_txn.reference_number

    login(client, admin_user.username)

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Match today's range
    r_pass = client.get(f"/admin/transactions?date_from={today_str}&date_to={today_str}")
    assert r_pass.status_code == 200
    assert ref_no in r_pass.get_data(as_text=True)

    # Future date range (should return no results)
    r_empty = client.get("/admin/transactions?date_from=2099-01-01&date_to=2099-01-02")
    assert r_empty.status_code == 200
    assert "No transactions found matching the selected search criteria" in r_empty.get_data(as_text=True)


def test_admin_user_management_search(client, admin_user, customer_user):
    c_user, _ = customer_user
    login(client, admin_user.username)

    resp = client.get(f"/admin/users?search={c_user.username}")
    assert resp.status_code == 200
    assert c_user.username in resp.get_data(as_text=True)

    c_resp = client.get(f"/admin/customer-management?search={c_user.username}")
    assert c_resp.status_code == 200
    assert c_user.username in c_resp.get_data(as_text=True)
