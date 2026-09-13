import re
import pytest
from app import db
from app.models.user import Role
from app.models.account import AccountType
from app.models.beneficiary import Beneficiary, BeneficiaryStatus
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
def customer_a(app):
    user = auth_service.register_user(
        "cust_alpha", "alpha@example.com", "Str0ngPass!", full_name="Customer Alpha", role=Role.CUSTOMER
    )
    acc = banking_service.create_account(user.id, AccountType.SAVINGS)
    return user, acc


@pytest.fixture
def customer_b(app):
    user = auth_service.register_user(
        "cust_beta", "beta@example.com", "Str0ngPass!", full_name="Customer Beta", role=Role.CUSTOMER
    )
    acc = banking_service.create_account(user.id, AccountType.SAVINGS)
    return user, acc


def test_add_beneficiary_success(client, customer_a):
    user, _ = customer_a
    login(client, user.username)

    resp = client.post(
        "/api/beneficiaries",
        json={
            "name": "Ramesh Kumar",
            "bank_name": "State Bank of India",
            "account_number": "123456789012",
            "confirm_account_number": "123456789012",
            "ifsc": "SBIN0001234",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "Ramesh Kumar"
    assert data["account_number"] == "123456789012"
    assert data["ifsc"] == "SBIN0001234"
    assert data["version_number"] == 1


def test_missing_required_fields(client, customer_a):
    user, _ = customer_a
    login(client, user.username)

    resp = client.post(
        "/api/beneficiaries",
        json={
            "name": "",
            "bank_name": "State Bank of India",
            "account_number": "123456789012",
            "ifsc": "SBIN0001234",
        },
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_invalid_account_number(client, customer_a):
    user, _ = customer_a
    login(client, user.username)

    # Short / non-numeric account number
    resp = client.post(
        "/api/beneficiaries",
        json={
            "name": "Suresh Sharma",
            "bank_name": "HDFC Bank",
            "account_number": "123",
            "confirm_account_number": "123",
            "ifsc": "HDFC0001234",
        },
    )
    assert resp.status_code == 400
    assert "Account number" in resp.get_json()["error"]


def test_invalid_ifsc_code(client, customer_a):
    user, _ = customer_a
    login(client, user.username)

    resp = client.post(
        "/api/beneficiaries",
        json={
            "name": "Suresh Sharma",
            "bank_name": "HDFC Bank",
            "account_number": "123456789012",
            "confirm_account_number": "123456789012",
            "ifsc": "INVALID_IFSC",
        },
    )
    assert resp.status_code == 400
    assert "IFSC" in resp.get_json()["error"]


def test_account_number_mismatch(client, customer_a):
    user, _ = customer_a
    login(client, user.username)

    resp = client.post(
        "/api/beneficiaries",
        json={
            "name": "Suresh Sharma",
            "bank_name": "HDFC Bank",
            "account_number": "123456789012",
            "confirm_account_number": "999999999999",
            "ifsc": "HDFC0001234",
        },
    )
    assert resp.status_code == 400
    assert "match" in resp.get_json()["error"].lower()


def test_duplicate_beneficiary(client, customer_a):
    user, _ = customer_a
    login(client, user.username)

    payload = {
        "name": "Duplicate Test",
        "bank_name": "ICICI Bank",
        "account_number": "987654321012",
        "confirm_account_number": "987654321012",
        "ifsc": "ICIC0001234",
    }
    # First creation
    resp1 = client.post("/api/beneficiaries", json=payload)
    assert resp1.status_code == 201

    # Second creation (duplicate)
    resp2 = client.post("/api/beneficiaries", json=payload)
    assert resp2.status_code == 400
    assert "already exists" in resp2.get_json()["error"].lower()


def test_adding_own_account(client, customer_a):
    user, own_acc = customer_a
    login(client, user.username)

    resp = client.post(
        "/api/beneficiaries",
        json={
            "name": "Self Account",
            "bank_name": "BankVCS Bank",
            "account_number": own_acc.account_number,
            "confirm_account_number": own_acc.account_number,
            "ifsc": "BANK0001234",
        },
    )
    assert resp.status_code == 400
    assert "own account" in resp.get_json()["error"].lower()


def test_edit_beneficiary(client, customer_a):
    user, _ = customer_a
    login(client, user.username)

    b = beneficiary_service.add_beneficiary(
        user.id,
        {
            "name": "Original Name",
            "bank_name": "Axis Bank",
            "account_number": "112233445566",
            "ifsc": "UTIB0001234",
        },
    )

    resp = client.put(
        f"/api/beneficiaries/{b.id}",
        json={
            "name": "Updated Name",
            "bank_name": "Axis Bank",
            "account_number": "112233445566",
            "confirm_account_number": "112233445566",
            "ifsc": "UTIB0001234",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "Updated Name"
    assert data["version_number"] == 2


def test_delete_beneficiary(client, customer_a):
    user, _ = customer_a
    login(client, user.username)

    b = beneficiary_service.add_beneficiary(
        user.id,
        {
            "name": "To Be Deleted",
            "bank_name": "Kotak Bank",
            "account_number": "556677889900",
            "ifsc": "KKBK0001234",
        },
    )

    resp = client.delete(f"/api/beneficiaries/{b.id}")
    assert resp.status_code == 200
    assert "deleted" in resp.get_json()["message"].lower()

    # Verify status in database
    b_db = db.session.get(Beneficiary, b.id)
    assert b_db.status == BeneficiaryStatus.INACTIVE


def test_unauthorized_beneficiary_access(client):
    # Unauthenticated access
    resp = client.get("/api/beneficiaries")
    assert resp.status_code in (401, 302)

    resp_get = client.get("/api/beneficiaries/99999")
    assert resp_get.status_code in (401, 302)


def test_customer_isolation(client, customer_a, customer_b):
    user_a, _ = customer_a
    user_b, _ = customer_b

    # Customer A adds a beneficiary
    bene_a = beneficiary_service.add_beneficiary(
        user_a.id,
        {
            "name": "Customer A Payee",
            "bank_name": "SBI",
            "account_number": "991122334455",
            "ifsc": "SBIN0001234",
        },
    )

    # Login as Customer B
    login(client, user_b.username)

    # Customer B lists beneficiaries -> should not see Customer A's beneficiary
    list_resp = client.get("/api/beneficiaries")
    assert list_resp.status_code == 200
    b_ids = [item["id"] for item in list_resp.get_json()]
    assert bene_a.id not in b_ids

    # Customer B gets Customer A's beneficiary by ID -> 403 / 404 (IDOR blocked)
    get_resp = client.get(f"/api/beneficiaries/{bene_a.id}")
    assert get_resp.status_code in (403, 404)

    # Customer B tries to edit Customer A's beneficiary -> 403 / 404 (IDOR blocked)
    put_resp = client.put(f"/api/beneficiaries/{bene_a.id}", json={"name": "Hacked Name"})
    assert put_resp.status_code in (403, 404)

    # Customer B tries to delete Customer A's beneficiary -> 403 / 404 (IDOR blocked)
    del_resp = client.delete(f"/api/beneficiaries/{bene_a.id}")
    assert del_resp.status_code in (403, 404)

