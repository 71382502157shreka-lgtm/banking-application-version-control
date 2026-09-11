import pytest
from app import db
from app.models.user import User, Role
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.beneficiary import Beneficiary
from app.models.version import EntityVersion, EntityType
from app.models.audit_log import AuditLog
from app.models.workflow_risk import RollbackRequest, RollbackStatus
from app.services import auth_service, banking_service, beneficiary_service, version_service, approval_service


def test_public_registration_forces_customer_role(client, app):
    """Verify that public registration form ignores hidden role parameters and enforces Role.CUSTOMER."""
    # Attempt to register with role=admin
    res = client.post('/register', data={
        'username': 'attacker_admin',
        'email': 'attacker@example.com',
        'password': 'Password123!',
        'full_name': 'Attacker Admin',
        'role': 'admin'
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        user = User.query.filter_by(username='attacker_admin').first()
        assert user is not None
        assert user.role == Role.CUSTOMER  # Must be CUSTOMER, not ADMIN!

    client.get('/logout')

    # Attempt to register via /register/employee with role=employee
    res = client.post('/register/employee', data={
        'username': 'attacker_employee',
        'email': 'attacker_emp@example.com',
        'password': 'Password123!',
        'full_name': 'Attacker Staff',
        'role': 'employee'
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        user = User.query.filter_by(username='attacker_employee').first()
        assert user is not None
        assert user.role == Role.CUSTOMER  # Must be CUSTOMER!


def test_unauthenticated_route_protections(client):
    """Verify all protected page routes redirect to login and API endpoints return 401."""
    protected_page_routes = [
        '/customer/dashboard',
        '/customer/accounts',
        '/customer/transfer',
        '/employee/dashboard',
        '/employee/customers',
        '/employee/transactions/export',
        '/admin/dashboard',
        '/admin/users',
        '/admin/settings',
        '/admin/risk-center',
    ]

    for route in protected_page_routes:
        res = client.get(route)
        assert res.status_code == 302
        assert '/login' in res.location

    protected_api_routes = [
        '/api/accounts',
        '/api/transactions',
        '/api/beneficiaries',
        '/api/audit-logs',
        '/api/rollback-requests',
    ]

    for route in protected_api_routes:
        res = client.get(route)
        assert res.status_code in (302, 401)


def test_customer_portal_isolation_and_idor_protection(client, app):
    """Verify customer cannot access employee/admin portals, or another user's accounts, receipts, or versions."""
    with app.app_context():
        cust1 = auth_service.register_user("audit_cust1", "acust1@example.com", "Password123!", role=Role.CUSTOMER)
        cust2 = auth_service.register_user("audit_cust2", "acust2@example.com", "Password123!", role=Role.CUSTOMER)
        acc1 = banking_service.create_account(cust1.id, "SAVINGS")
        acc2 = banking_service.create_account(cust2.id, "CHECKING")
        txn2 = banking_service.deposit(acc2, 500, "Deposit Cust 2", cust2.id)

        cust2_id = cust2.id
        acc2_id = acc2.id
        txn2_id = txn2.id

    # Login as Customer 1
    client.post('/login', data={'username': 'audit_cust1', 'password': 'Password123!'}, follow_redirects=True)

    # 1. Access employee and admin routes -> 403 Forbidden
    res = client.get('/employee/dashboard')
    assert res.status_code == 403
    res = client.get('/admin/dashboard')
    assert res.status_code == 403
    res = client.get('/admin/users')
    assert res.status_code == 403
    res = client.get('/admin/risk-center')
    assert res.status_code == 403

    # 2. Access Customer 2 account details via API -> 403 Forbidden
    res = client.get(f'/api/accounts/{acc2_id}')
    assert res.status_code == 403

    # 3. Access Customer 2 transaction receipt via API -> 403 Forbidden
    res = client.get(f'/api/transactions/{txn2_id}/receipt')
    assert res.status_code == 403

    # 4. Access Customer 2 version history via API -> 403 Forbidden
    res = client.get(f'/api/versions/Customer/{cust2_id}')
    assert res.status_code == 403

    # 5. Compare Customer 2 account versions via API -> 403 Forbidden
    res = client.get(f'/api/versions/compare?entity_type=Account&entity_id={acc2_id}&v1=1&v2=2')
    assert res.status_code == 403

    # 6. Create rollback request for Customer 2 account -> 403 Forbidden
    res = client.post('/api/rollback-requests', json={
        'entity_type': 'Account',
        'entity_id': acc2_id,
        'target_version': 1,
        'reason': 'Malicious rollback attempt'
    })
    assert res.status_code == 403

    # Verify ACCESS_DENIED audit log generation
    with app.app_context():
        denied_logs = AuditLog.query.filter_by(action="ACCESS_DENIED").all()
        assert len(denied_logs) >= 5


def test_employee_portal_isolation(client, app):
    """Verify employee cannot access admin portals or customer portals."""
    with app.app_context():
        emp = auth_service.register_user("audit_emp1", "aemp1@example.com", "Password123!", role=Role.EMPLOYEE)

    client.post('/login', data={'username': 'audit_emp1', 'password': 'Password123!'}, follow_redirects=True)

    # Employee attempting customer routes -> 403
    res = client.get('/customer/dashboard')
    assert res.status_code == 403

    # Employee attempting strict admin routes -> 403
    res = client.get('/admin/dashboard')
    assert res.status_code == 403
    res = client.get('/admin/users')
    assert res.status_code == 403
    res = client.get('/admin/settings')
    assert res.status_code == 403
    res = client.get('/admin/risk-center')
    assert res.status_code == 403
    res = client.get('/admin/security-center')
    assert res.status_code == 403

    # Employee accessing permitted employee features -> 200 OK
    res = client.get('/employee/dashboard')
    assert res.status_code == 200
    res = client.get('/employee/customers')
    assert res.status_code == 200
    res = client.get('/employee/transactions/export')
    assert res.status_code == 200
    assert 'text/csv' in res.headers['Content-Type']


def test_admin_portal_isolation(client, app):
    """Verify admin can access admin portal & admin management pages, but gets 403 on customer & employee routes."""
    with app.app_context():
        admin_usr = auth_service.register_user("audit_admin1", "aadmin1@example.com", "Password123!", role=Role.ADMIN)

    client.post('/login', data={'username': 'audit_admin1', 'password': 'Password123!'}, follow_redirects=True)

    # Admin accessing admin pages -> 200 OK
    res = client.get('/admin/dashboard')
    assert res.status_code == 200
    res = client.get('/admin/users')
    assert res.status_code == 200
    res = client.get('/admin/risk-center')
    assert res.status_code == 200
    res = client.get('/admin/transactions')
    assert res.status_code == 200
    res = client.get('/admin/customer-management')
    assert res.status_code == 200
    res = client.get('/admin/approvals')
    assert res.status_code == 200

    # Admin accessing customer-only page -> 403 Forbidden
    res = client.get('/customer/dashboard')
    assert res.status_code == 403

    # Admin accessing employee-only portal -> 403 Forbidden
    res = client.get('/employee/dashboard')
    assert res.status_code == 403


def test_maker_checker_self_approval_prevention_api(client, app):
    """Verify Maker-Checker policy prevents self-approval of rollback requests via API."""
    with app.app_context():
        admin1 = auth_service.register_user("audit_admin2", "aadmin2@example.com", "Password123!", role=Role.ADMIN)
        acc = banking_service.create_account(admin1.id, "SAVINGS")

        req = approval_service.request_rollback(
            user_id=admin1.id,
            entity_type="Account",
            entity_id=acc.id,
            target_version=1,
            reason="Admin created rollback"
        )
        req_id = req.id

    client.post('/login', data={'username': 'audit_admin2', 'password': 'Password123!'}, follow_redirects=True)

    # Admin attempting to approve own rollback request via API -> Error 400
    res = client.post(f'/api/rollback-requests/{req_id}/approve', json={'review_notes': 'Self approval'})
    assert res.status_code == 400
    assert b"cannot approve" in res.data.lower() or b"maker-checker" in res.data.lower()
