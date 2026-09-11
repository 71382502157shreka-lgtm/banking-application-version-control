import pytest
from decimal import Decimal
from app import db
from app.models import (
    User, Role, Account, Complaint, ComplaintStatus, ComplaintPriority,
    RollbackRequest, RollbackStatus, AuditLog
)
from app.services import auth_service, banking_service


def test_employee_access_control(client, app):
    """Test that customer users cannot access /employee/dashboard, but staff users can."""
    with app.app_context():
        customer_user = auth_service.register_user(
            "testcust1", "cust1@example.com", "Password123!", full_name="Test Cust", role=Role.CUSTOMER
        )
        staff_user = auth_service.register_user(
            "teststaff1", "staff1@example.com", "Password123!", full_name="Test Staff", role=Role.EMPLOYEE
        )

    # Test unauthenticated access -> redirect to login
    response = client.get('/employee/dashboard')
    assert response.status_code == 302

    # Login as customer
    client.post('/login', data={'username': 'testcust1', 'password': 'Password123!'}, follow_redirects=True)
    response = client.get('/employee/dashboard')
    assert response.status_code == 403  # Customer gets 403 Forbidden

    # Logout customer
    client.get('/logout', follow_redirects=True)

    # Login as employee
    client.post('/login', data={'username': 'teststaff1', 'password': 'Password123!'}, follow_redirects=True)
    response = client.get('/employee/dashboard')
    assert response.status_code == 200
    assert b"Employee Dashboard" in response.data or b"Staff" in response.data or b"Summary" in response.data


def test_employee_deposit_and_withdraw(client, app):
    """Test employee deposit and withdrawal operations."""
    with app.app_context():
        customer_user = auth_service.register_user(
            "testcust2", "cust2@example.com", "Password123!", full_name="Test Cust 2", role=Role.CUSTOMER
        )
        staff_user = auth_service.register_user(
            "teststaff2", "staff2@example.com", "Password123!", full_name="Test Staff 2", role=Role.EMPLOYEE
        )
        account = banking_service.create_account(customer_user.id)
        acc_num = account.account_number
        initial_balance = account.balance

    # Login as employee
    client.post('/login', data={'username': 'teststaff2', 'password': 'Password123!'}, follow_redirects=True)

    # Deposit $500.00
    res = client.post('/employee/banking/deposit', data={'account_number': acc_num, 'amount': '500.00', 'description': 'Employee test deposit'}, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        updated_account = Account.query.filter_by(account_number=acc_num).first()
        assert updated_account.balance == initial_balance + Decimal('500.00')

    # Withdraw $200.00
    res = client.post('/employee/banking/withdraw', data={'account_number': acc_num, 'amount': '200.00', 'description': 'Employee test withdraw'}, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        updated_account = Account.query.filter_by(account_number=acc_num).first()
        assert updated_account.balance == initial_balance + Decimal('300.00')


def test_maker_checker_self_approval_prevention(client, app):
    """Test that a staff user cannot approve their own rollback request (Maker-Checker)."""
    with app.app_context():
        staff_user = auth_service.register_user(
            "teststaff3", "staff3@example.com", "Password123!", full_name="Test Staff 3", role=Role.EMPLOYEE
        )
        
        # Create a mock pending rollback request by staff_user
        req = RollbackRequest(
            entity_type="Customer",
            entity_id=1,
            target_version=1,
            requested_by=staff_user.id,
            reason="Test rollback by staff",
            status=RollbackStatus.PENDING
        )
        db.session.add(req)
        db.session.commit()
        req_id = req.id

    # Login as the same staff user
    client.post('/login', data={'username': 'teststaff3', 'password': 'Password123!'}, follow_redirects=True)

    # Attempt to self-approve
    res = client.post('/employee/approvals', data={'request_id': req_id, 'action': 'approve'}, follow_redirects=True)
    assert res.status_code == 200
    assert b"cannot approve" in res.data.lower() or b"maker-checker" in res.data.lower() or b"prohibited" in res.data.lower()

    with app.app_context():
        saved_req = db.session.get(RollbackRequest, req_id)
        assert saved_req.status == RollbackStatus.PENDING


def test_complaint_workflow(client, app):
    """Test complaint filing by customer and updating status by employee."""
    with app.app_context():
        customer_user = auth_service.register_user(
            "testcust4", "cust4@example.com", "Password123!", full_name="Test Cust 4", role=Role.CUSTOMER
        )
        staff_user = auth_service.register_user(
            "teststaff4", "staff4@example.com", "Password123!", full_name="Test Staff 4", role=Role.EMPLOYEE
        )

    # Customer logs in and files a complaint
    client.post('/login', data={'username': 'testcust4', 'password': 'Password123!'}, follow_redirects=True)
    res = client.post('/customer/complaints', data={
        'subject': 'Delayed Transfer Investigation',
        'priority': 'MEDIUM',
        'description': 'My transfer took 2 hours to clear.'
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        complaint = Complaint.query.filter_by(subject='Delayed Transfer Investigation').first()
        assert complaint is not None
        assert complaint.status == ComplaintStatus.OPEN
        complaint_id = complaint.id

    # Logout customer and login as employee
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'username': 'teststaff4', 'password': 'Password123!'}, follow_redirects=True)

    # Employee views complaints page
    res = client.get('/employee/complaints')
    assert res.status_code == 200
    assert b"Delayed Transfer Investigation" in res.data

    # Employee updates complaint status to RESOLVED
    res = client.post('/employee/complaints', data={
        'complaint_id': complaint_id,
        'status': 'RESOLVED',
        'resolution': 'Cleared after review.'
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        updated_complaint = db.session.get(Complaint, complaint_id)
        assert updated_complaint.status == ComplaintStatus.RESOLVED


def test_strict_portal_redirection_and_isolation(client, app):
    """Test post-login role redirection, portal isolation, and audit log generation on 403."""
    with app.app_context():
        c_user = auth_service.register_user("cust_iso", "iso1@example.com", "Password123!", role=Role.CUSTOMER)
        e_user = auth_service.register_user("emp_iso", "iso2@example.com", "Password123!", role=Role.EMPLOYEE)
        a_user = auth_service.register_user("admin_iso", "iso3@example.com", "Password123!", role=Role.ADMIN)

    # 1. Customer login -> redirects to /customer/dashboard
    res = client.post('/login', data={'username': 'cust_iso', 'password': 'Password123!'})
    assert res.status_code == 302
    assert res.location.endswith('/customer/dashboard')

    # Customer attempts to access employee & admin pages -> 403 Forbidden
    res = client.get('/employee/dashboard')
    assert res.status_code == 403
    res = client.get('/admin/dashboard')
    assert res.status_code == 403

    client.get('/logout')

    # 2. Employee login -> redirects to /employee/dashboard
    res = client.post('/login', data={'username': 'emp_iso', 'password': 'Password123!'})
    assert res.status_code == 302
    assert res.location.endswith('/employee/dashboard')

    # Employee attempts to access admin users page -> 403 Forbidden
    res = client.get('/admin/users')
    assert res.status_code == 403

    client.get('/logout')

    # 3. Admin login -> redirects to /admin/dashboard
    res = client.post('/login', data={'username': 'admin_iso', 'password': 'Password123!'})
    assert res.status_code == 302
    assert res.location.endswith('/admin/dashboard')

    # Verify audit security log recorded ACCESS_DENIED events
    with app.app_context():
        denied_logs = AuditLog.query.filter_by(action="ACCESS_DENIED").all()
        assert len(denied_logs) >= 3
