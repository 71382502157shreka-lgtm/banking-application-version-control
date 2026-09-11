import re
import pytest
from app import db
from app.models.user import Role
from app.models.account import Account, AccountType
from app.models.complaint import Complaint, ComplaintStatus, ComplaintPriority
from app.models.service_request import ServiceRequest, ServiceRequestStatus
from app.models.document_vault import CustomerDocument, DocumentStatus
from app.services import auth_service, banking_service


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
def help_staff(app):
    user = auth_service.register_user(
        "help_staff", "help_staff@example.com", "Str0ngPass!", full_name="Help Desk Staff", role=Role.EMPLOYEE
    )
    return user


@pytest.fixture
def help_cust1(app):
    user = auth_service.register_user(
        "help_cust1", "help_cust1@example.com", "Str0ngPass!", full_name="Customer One", role=Role.CUSTOMER
    )
    acc = banking_service.create_account(user.id, AccountType.SAVINGS)
    return user, acc


@pytest.fixture
def help_cust2(app):
    user = auth_service.register_user(
        "help_cust2", "help_cust2@example.com", "Str0ngPass!", full_name="Customer Two", role=Role.CUSTOMER
    )
    acc = banking_service.create_account(user.id, AccountType.SAVINGS)
    return user, acc


def test_customer_complaint_submission_and_isolation(client, help_cust1, help_cust2):
    user1, _ = help_cust1
    user2, _ = help_cust2

    # User 1 submits a complaint via WEB form
    login(client, user1.username)
    res_sub = client.post(
        "/customer/complaints",
        data={
            "subject": "ATM Fee Dispute",
            "description": "Extra fee of Rs 50 charged on ATM withdrawal",
            "category": "CARD_ISSUES",
            "priority": "MEDIUM"
        },
        follow_redirects=True
    )
    assert res_sub.status_code == 200

    comp = Complaint.query.filter_by(customer_id=user1.id).first()
    assert comp is not None
    assert comp.subject == "ATM Fee Dispute"
    assert comp.status == ComplaintStatus.OPEN

    # User 2 lists complaints via API -> sees only own complaints
    client.get("/logout")
    login(client, user2.username)
    res_api = client.get("/api/v1/complaints")
    assert res_api.status_code == 200
    user2_items = res_api.get_json()
    assert all(c["customer_id"] == user2.id for c in user2_items)


def test_employee_complaint_resolution_workflow(client, help_staff, help_cust1):
    user1, _ = help_cust1
    comp = Complaint(
        ticket_number="TICK-TEST01",
        customer_id=user1.id,
        subject="Delay in Interest Credit",
        description="Quarterly interest not credited yet",
        category="SAVINGS_ACCOUNT",
        priority=ComplaintPriority.HIGH,
        status=ComplaintStatus.OPEN
    )
    db.session.add(comp)
    db.session.commit()

    # Employee logs in and updates complaint
    login(client, help_staff.username)
    res_emp = client.post(
        "/employee/complaints",
        data={
            "complaint_id": comp.id,
            "status": "RESOLVED",
            "resolution_notes": "Interest credited automatically; issue resolved."
        },
        follow_redirects=True
    )
    assert res_emp.status_code == 200

    db.session.refresh(comp)
    assert comp.status == "RESOLVED"
    assert comp.resolution == "Interest credited automatically; issue resolved."
    assert comp.assigned_employee_id == help_staff.id


def test_service_request_lifecycle(client, help_staff, help_cust1):
    user1, acc1 = help_cust1

    # Customer submits service request for Cheque Book
    login(client, user1.username)
    res_sr = client.post(
        "/customer/service-requests",
        data={
            "request_type": "CHEQUE_BOOK",
            "account_id": acc1.id,
            "details": "Dispatch 25-leaf cheque book to registered address"
        },
        follow_redirects=True
    )
    assert res_sr.status_code == 200

    sr = ServiceRequest.query.filter_by(user_id=user1.id).first()
    assert sr is not None
    assert sr.request_type == "CHEQUE_BOOK"
    assert sr.status == ServiceRequestStatus.PENDING

    # Employee approves service request via API
    client.get("/logout")
    login(client, help_staff.username)
    res_proc = client.post(
        f"/api/v1/service-requests/{sr.id}/process",
        json={"status": "APPROVED", "notes": "Approved for dispatch"}
    )
    assert res_proc.status_code == 200
    assert res_proc.get_json()["status"] == "APPROVED"

    db.session.refresh(sr)
    assert sr.status == "APPROVED"


def test_customer_document_upload(client, help_cust1):
    user1, _ = help_cust1

    login(client, user1.username)
    res_doc = client.post(
        "/customer/document-vault",
        data={
            "document_type": "PAN",
            "document_name": "PAN Card Scan"
        },
        follow_redirects=True
    )
    assert res_doc.status_code == 200

    doc = CustomerDocument.query.filter_by(user_id=user1.id).first()
    assert doc is not None
    assert doc.document_type == "PAN"
    assert doc.status == DocumentStatus.PENDING_VERIFICATION


def test_employee_document_verification_workflow(client, help_staff, help_cust1):
    user1, _ = help_cust1
    doc = CustomerDocument(
        user_id=user1.id,
        document_type="AADHAAR",
        document_name="Aadhaar Front Scan",
        status=DocumentStatus.PENDING_VERIFICATION
    )
    db.session.add(doc)
    db.session.commit()

    # Employee verifies document via WEB queue
    login(client, help_staff.username)
    res_ver = client.post(
        "/employee/documents",
        data={
            "doc_id": doc.id,
            "status": "VERIFIED",
            "notes": "Verified against UIDAI central database"
        },
        follow_redirects=True
    )
    assert res_ver.status_code == 200

    db.session.refresh(doc)
    assert doc.status == "VERIFIED"
    assert doc.verification_notes == "Verified against UIDAI central database"


def test_document_verification_rbac_and_idor_protection(client, help_cust1, help_cust2):
    user1, _ = help_cust1
    user2, _ = help_cust2

    doc = CustomerDocument(
        user_id=user1.id,
        document_type="PASSPORT",
        document_name="Passport Main Page",
        status=DocumentStatus.PENDING_VERIFICATION
    )
    db.session.add(doc)
    db.session.commit()

    # Non-staff customer attempting to call verification API -> Forbidden 403
    login(client, user2.username)
    res_unauth = client.post(
        f"/api/v1/documents/{doc.id}/verify",
        json={"status": "VERIFIED", "notes": "Self verification attempt"}
    )
    assert res_unauth.status_code == 403

    # Customer viewing document list via API -> sees only own documents
    res_docs = client.get("/api/v1/documents")
    assert res_docs.status_code == 200
    user2_docs = res_docs.get_json()
    assert all(d["user_id"] == user2.id for d in user2_docs)


def test_api_complaints_and_service_requests(client, help_staff, help_cust1):
    user1, acc1 = help_cust1

    # Create complaint via API
    login(client, user1.username)
    res_c = client.post(
        "/api/v1/complaints",
        json={"subject": "API Support Ticket", "description": "Submitted via mobile app API", "category": "MOBILE_APP"}
    )
    assert res_c.status_code == 201
    assert res_c.get_json()["subject"] == "API Support Ticket"

    # Staff list complaints via API
    client.get("/logout")
    login(client, help_staff.username)
    res_all_c = client.get("/api/v1/complaints")
    assert res_all_c.status_code == 200
    assert len(res_all_c.get_json()) >= 1
