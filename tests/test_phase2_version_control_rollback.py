import re
import pytest
from app import db
from app.models.user import Role
from app.models.account import AccountType
from app.models.beneficiary import Beneficiary, BeneficiaryStatus
from app.models.version import EntityVersion, ChangeType
from app.models.workflow_risk import RollbackRequest, RollbackStatus
from app.services import version_service, approval_service, audit_service, auth_service, banking_service


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
    return auth_service.register_user(
        "admin_vc", "admin_vc@example.com", "Str0ngPass!", full_name="Admin VC", role=Role.ADMIN
    )


@pytest.fixture
def employee_user(app):
    return auth_service.register_user(
        "emp_vc", "emp_vc@example.com", "Str0ngPass!", full_name="Employee VC", role=Role.EMPLOYEE
    )


@pytest.fixture
def customer_user(app):
    user = auth_service.register_user(
        "cust_vc", "cust_vc@example.com", "Str0ngPass!", full_name="Customer VC", role=Role.CUSTOMER
    )
    acc = banking_service.create_account(user.id, AccountType.SAVINGS)
    return user, acc


def test_version_creation_on_entity_mutation(app, customer_user):
    customer, _ = customer_user
    with app.app_context():
        b = Beneficiary(
            user_id=customer.id,
            name="Initial Beneficiary Name",
            account_number="998877665544",
            bank_name="Test Bank",
            ifsc="TEST0123456",
            status=BeneficiaryStatus.ACTIVE,
        )
        db.session.add(b)
        db.session.flush()

        v1 = version_service.create_version(
            entity_type="BENEFICIARY",
            entity_id=b.id,
            change_type=ChangeType.CREATE,
            old_data=None,
            new_data={"name": b.name, "account_number": b.account_number, "bank_name": b.bank_name, "ifsc": b.ifsc, "status": b.status},
            changed_by=customer.id,
            change_summary="Created beneficiary"
        )
        db.session.commit()

        assert v1.version_number == 1
        assert v1.entity_type == "BENEFICIARY"
        assert v1.new_data["name"] == "Initial Beneficiary Name"

        # Update beneficiary name
        old_data = dict(v1.new_data)
        b.name = "Updated Beneficiary Name"
        v2 = version_service.create_version(
            entity_type="BENEFICIARY",
            entity_id=b.id,
            change_type=ChangeType.UPDATE,
            old_data=old_data,
            new_data={"name": b.name, "account_number": b.account_number, "bank_name": b.bank_name, "ifsc": b.ifsc, "status": b.status},
            changed_by=customer.id,
            change_summary="Updated beneficiary name"
        )
        db.session.commit()

        assert v2.version_number == 2
        assert v2.old_data["name"] == "Initial Beneficiary Name"
        assert v2.new_data["name"] == "Updated Beneficiary Name"


def test_field_level_diffing(app, customer_user):
    customer, _ = customer_user
    with app.app_context():
        entity_id = customer.id + 99900
        v1 = version_service.create_version(
            entity_type="CUSTOM_ENTITY",
            entity_id=entity_id,
            change_type=ChangeType.CREATE,
            old_data=None,
            new_data={"full_name": "John Doe", "email": "john@example.com", "status": "ACTIVE"},
            changed_by=customer.id,
            change_summary="Entity v1"
        )
        db.session.commit()

        v2 = version_service.create_version(
            entity_type="CUSTOM_ENTITY",
            entity_id=entity_id,
            change_type=ChangeType.UPDATE,
            old_data=v1.new_data,
            new_data={"full_name": "John Smith", "phone": "9876543210", "status": "ACTIVE"},
            changed_by=customer.id,
            change_summary="Entity v2"
        )
        db.session.commit()

        diff_res = version_service.diff_versions("CUSTOM_ENTITY", entity_id, 1, 2)
        fields = diff_res["fields"]

        assert fields["full_name"]["status"] == "modified"
        assert fields["full_name"]["old"] == "John Doe"
        assert fields["full_name"]["new"] == "John Smith"

        assert fields["email"]["status"] == "removed"
        assert fields["phone"]["status"] == "added"
        assert fields["status"]["status"] == "unchanged"


def test_rollback_request_creation(app, employee_user, customer_user):
    employee = employee_user
    customer, _ = customer_user
    with app.app_context():
        b = Beneficiary(user_id=customer.id, name="Test Payee", account_number="1122334455", bank_name="Bank", ifsc="SBIN0001234", status=BeneficiaryStatus.ACTIVE)
        db.session.add(b)
        db.session.flush()

        version_service.create_version("BENEFICIARY", b.id, "CREATE", None, {"name": b.name, "account_number": b.account_number, "bank_name": b.bank_name, "ifsc": b.ifsc, "status": b.status}, customer.id)
        db.session.commit()

        req = approval_service.request_rollback(
            user_id=employee.id,
            entity_type="BENEFICIARY",
            entity_id=b.id,
            target_version=1,
            reason="Incorrect name modification by staff"
        )
        db.session.commit()

        assert req.id is not None
        assert req.status == RollbackStatus.PENDING
        assert req.requested_by == employee.id
        assert req.target_version == 1


def test_maker_checker_self_approval_prevention(app, client, employee_user, customer_user):
    employee = employee_user
    customer, _ = customer_user
    with app.app_context():
        b = Beneficiary(user_id=customer.id, name="Test Payee", account_number="1122334455", bank_name="Bank", ifsc="SBIN0001234", status=BeneficiaryStatus.ACTIVE)
        db.session.add(b)
        db.session.flush()

        version_service.create_version("BENEFICIARY", b.id, "CREATE", None, {"name": b.name, "account_number": b.account_number, "bank_name": b.bank_name, "ifsc": b.ifsc, "status": b.status}, customer.id)
        db.session.commit()

        req = approval_service.request_rollback(
            user_id=employee.id,
            entity_type="BENEFICIARY",
            entity_id=b.id,
            target_version=1,
            reason="Testing self-approval prevention"
        )
        db.session.commit()
        req_id = req.id

    # Login as employee who created the request
    login(client, "emp_vc")

    # Employee tries to approve own request
    get_res = client.get("/employee/approvals")
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', get_res.get_data(as_text=True))
    token = match.group(1) if match else ""

    resp = client.post(
        "/employee/approvals",
        data={"request_id": req_id, "action": "approve", "notes": "Self approve attempt", "csrf_token": token},
        follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Maker-Checker Policy" in resp.data

    with app.app_context():
        updated_req = db.session.get(RollbackRequest, req_id)
        assert updated_req.status == RollbackStatus.PENDING


def test_admin_rollback_approval_and_forward_restore(app, admin_user, customer_user):
    admin = admin_user
    customer, _ = customer_user
    with app.app_context():
        b = Beneficiary(user_id=customer.id, name="Original Name", account_number="1234567890", bank_name="State Bank", ifsc="SBIN0001234", status=BeneficiaryStatus.ACTIVE)
        db.session.add(b)
        db.session.flush()

        v1 = version_service.create_version("BENEFICIARY", b.id, "CREATE", None, {"name": b.name, "account_number": b.account_number, "bank_name": b.bank_name, "ifsc": b.ifsc, "status": b.status}, customer.id)
        db.session.commit()

        b.name = "Accidental Bad Name"
        v2 = version_service.create_version("BENEFICIARY", b.id, "UPDATE", v1.new_data, {"name": b.name, "account_number": b.account_number, "bank_name": b.bank_name, "ifsc": b.ifsc, "status": b.status}, customer.id)
        db.session.commit()

        # Submit request
        req = approval_service.request_rollback(customer.id, "BENEFICIARY", b.id, target_version=1, reason="Restore original name")
        db.session.commit()

        # Admin approves
        res = approval_service.approve_rollback_request(req.id, admin.id, "Approved by Admin")
        db.session.commit()

        assert res.status in [RollbackStatus.APPROVED, RollbackStatus.EXECUTED] or res.status == "EXECUTED"
        assert b.name == "Original Name"

        # Confirm new version v3 is created with RESTORE action
        v3 = version_service.get_version("BENEFICIARY", b.id, 3)
        assert v3 is not None
        assert v3.change_type == "RESTORE"
        assert v3.new_data["name"] == "Original Name"


def test_financial_transaction_rollback_prohibition(app, customer_user):
    customer, _ = customer_user
    with app.app_context():
        with pytest.raises(ValueError) as excinfo:
            version_service.restore_version("TRANSACTION", 999, 1, customer.id, lambda x: x)

        assert "Transactions cannot be restored" in str(excinfo.value)


def test_sha256_audit_chain_verification(app):
    with app.app_context():
        report = audit_service.verify_audit_integrity()
        assert report.get("is_valid") is True or "AUDIT CHAIN VALID" in report.get("status", "")


def test_customer_version_ownership_idor_protection(app, client, admin_user, customer_user):
    admin = admin_user
    customer, _ = customer_user
    with app.app_context():
        b_admin = Beneficiary(user_id=admin.id, name="Admin Payee", account_number="5555555555", bank_name="Admin Bank", ifsc="ADMN0001234", status=BeneficiaryStatus.ACTIVE)
        db.session.add(b_admin)
        db.session.flush()

        v1 = version_service.create_version("BENEFICIARY", b_admin.id, "CREATE", None, {"name": b_admin.name}, admin.id)
        v2 = version_service.create_version("BENEFICIARY", b_admin.id, "UPDATE", v1.new_data, {"name": "Updated Admin Payee"}, admin.id)
        db.session.commit()
        target_b_id = b_admin.id

    # Login as regular customer
    login(client, "cust_vc")

    # Customer tries to diff admin's beneficiary
    resp = client.get(f"/api/versions/compare?entity_type=BENEFICIARY&entity_id={target_b_id}&v1=1&v2=2")
    assert resp.status_code == 403
