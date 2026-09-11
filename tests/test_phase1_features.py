import re
from decimal import Decimal
import pytest
from app.models.user import Role
from app.models.account import Account, AccountType, AccountStatus
from app.models.service_request import ServiceRequest, ServiceRequestStatus
from app.models.document_vault import CustomerDocument
from app.services import auth_service, banking_service


@pytest.fixture
def auditor_user(app):
    return auth_service.register_user(
        "auditor_john", "auditor@example.com", "Str0ngPass!", full_name="John Auditor", role=Role.AUDITOR
    )


@pytest.fixture
def employee_user(app):
    return auth_service.register_user(
        "emp_mark", "emp@example.com", "Str0ngPass!", full_name="Mark Staff", role=Role.EMPLOYEE
    )


@pytest.fixture
def customer_user(app):
    u = auth_service.register_user(
        "cust_sarah", "sarah@example.com", "Str0ngPass!", full_name="Sarah Customer", role=Role.CUSTOMER
    )
    acc = banking_service.create_account(u.id, AccountType.SAVINGS)
    banking_service.deposit(acc, Decimal("25000.00"), "Initial Deposit", u.id)
    return u, acc


def login(client, username, password="Str0ngPass!"):
    get_res = client.get("/login")
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', get_res.get_data(as_text=True))
    token = match.group(1) if match else ""
    return client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": token},
        follow_redirects=True,
    )


def get_csrf(client, url):
    res = client.get(url)
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', res.get_data(as_text=True))
    return match.group(1) if match else ""


def test_auditor_dashboard_access(client, auditor_user):
    login(client, "auditor_john")
    resp = client.get("/auditor/dashboard")
    assert resp.status_code == 200
    assert b"Auditor Portal" in resp.data


def test_auditor_ledger_access(client, auditor_user):
    login(client, "auditor_john")
    resp = client.get("/auditor/audit-ledger")
    assert resp.status_code == 200
    assert b"Cryptographic Audit Ledger" in resp.data


def test_customer_calculators(client, customer_user):
    u, acc = customer_user
    login(client, "cust_sarah")

    resp = client.get("/customer/calculators")
    assert resp.status_code == 200

    token = get_csrf(client, "/customer/calculators")
    resp_post = client.post("/customer/calculators", data={
        "csrf_token": token,
        "calc_type": "emi",
        "principal": "100000",
        "rate": "10",
        "tenure_months": "12"
    })
    assert resp_post.status_code == 200
    assert b"EMI Calculation Summary" in resp_post.data


def test_customer_deposits_loans(client, customer_user):
    u, acc = customer_user
    login(client, "cust_sarah")

    resp = client.get("/customer/deposits-loans")
    assert resp.status_code == 200

    # Open FD deposit
    token = get_csrf(client, "/customer/deposits-loans")
    resp_fd = client.post("/customer/deposits-loans", data={
        "csrf_token": token,
        "action": "open_deposit",
        "source_account_id": str(acc.id),
        "deposit_type": "FIXED_DEPOSIT",
        "amount": "5000",
        "tenure_months": "12"
    }, follow_redirects=True)
    assert resp_fd.status_code == 200
    assert b"opened successfully" in resp_fd.data or b"Deposit Account" in resp_fd.data

    # Apply loan
    token = get_csrf(client, "/customer/deposits-loans")
    resp_ln = client.post("/customer/deposits-loans", data={
        "csrf_token": token,
        "action": "apply_loan",
        "loan_type": "PERSONAL",
        "amount": "50000",
        "tenure_years": "2",
        "monthly_income": "30000"
    }, follow_redirects=True)
    assert resp_ln.status_code == 200
    assert b"Loan application submitted successfully" in resp_ln.data


def test_customer_quick_pay(client, customer_user):
    u, acc = customer_user
    login(client, "cust_sarah")

    resp = client.get("/customer/quick-pay")
    assert resp.status_code == 200

    token = get_csrf(client, "/customer/quick-pay")
    resp_pay = client.post("/customer/quick-pay", data={
        "csrf_token": token,
        "account_id": str(acc.id),
        "category": "MOBILE_RECHARGE",
        "biller_name": "Airtel",
        "consumer_number": "9876543210",
        "amount": "299.00"
    }, follow_redirects=True)
    assert resp_pay.status_code == 200
    assert b"completed successfully" in resp_pay.data


def test_customer_service_requests(client, customer_user, employee_user, app):
    u, acc = customer_user
    login(client, "cust_sarah")

    resp = client.get("/customer/service-requests")
    assert resp.status_code == 200

    token = get_csrf(client, "/customer/service-requests")
    resp_create = client.post("/customer/service-requests", data={
        "csrf_token": token,
        "request_type": "CHEQUE_BOOK",
        "account_id": str(acc.id),
        "details": "Need 25-leaf cheque book"
    }, follow_redirects=True)
    assert resp_create.status_code == 200
    assert b"Service Request submitted" in resp_create.data

    # Check employee processing
    client.get("/logout")
    login(client, "emp_mark")
    resp_emp = client.get("/employee/service-requests")
    assert resp_emp.status_code == 200

    with app.app_context():
        sr = ServiceRequest.query.filter_by(user_id=u.id).first()
        sr_id = sr.id
        assert sr is not None

    token = get_csrf(client, "/employee/service-requests")
    resp_proc = client.post("/employee/service-requests", data={
        "csrf_token": token,
        "ticket_id": str(sr_id),
        "status": "APPROVED",
        "notes": "Approved and dispatched via speed post"
    }, follow_redirects=True)
    assert resp_proc.status_code == 200
    assert b"updated to APPROVED" in resp_proc.data


def test_customer_document_vault(client, customer_user):
    u, acc = customer_user
    login(client, "cust_sarah")

    resp = client.get("/customer/document-vault")
    assert resp.status_code == 200

    token = get_csrf(client, "/customer/document-vault")
    resp_upload = client.post("/customer/document-vault", data={
        "csrf_token": token,
        "document_type": "AADHAAR",
        "document_name": "My Aadhaar Card"
    }, follow_redirects=True)
    assert resp_upload.status_code == 200
    assert b"uploaded to vault successfully" in resp_upload.data


