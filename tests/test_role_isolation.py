import pytest
from app import db
from app.models.user import User, Role
from app.models.account import Account


def test_customer_login_redirect_to_customer_dashboard(client, app):
    with app.app_context():
        customer = User(username="cust_test", email="cust_test@example.com", role=Role.CUSTOMER)
        customer.set_password("Password123!")
        db.session.add(customer)
        db.session.commit()

    res = client.post("/login", data={"username": "cust_test", "password": "Password123!"}, follow_redirects=False)
    assert res.status_code == 302
    assert "/customer/dashboard" in res.location


def test_employee_login_redirect_to_employee_dashboard(client, app):
    with app.app_context():
        emp = User(username="emp_test", email="emp_test@example.com", role=Role.EMPLOYEE)
        emp.set_password("Password123!")
        db.session.add(emp)
        db.session.commit()

    res = client.post("/auth/employee/login", data={"username": "emp_test", "password": "Password123!"}, follow_redirects=False)
    assert res.status_code == 302
    assert "/employee/dashboard" in res.location


def test_admin_login_redirect_to_admin_dashboard(client, app):
    with app.app_context():
        admin = User(username="adm_test", email="adm_test@example.com", role=Role.ADMIN)
        admin.set_password("Password123!")
        db.session.add(admin)
        db.session.commit()

    res = client.post("/auth/admin/login", data={"username": "adm_test", "password": "Password123!"}, follow_redirects=False)
    assert res.status_code == 302
    assert "/admin/dashboard" in res.location


def test_customer_cannot_access_employee_or_admin_dashboards(client, app):
    with app.app_context():
        customer = User(username="cust_isolation", email="cust_iso@example.com", role=Role.CUSTOMER)
        customer.set_password("Password123!")
        db.session.add(customer)
        db.session.commit()

    # Login customer
    client.post("/login", data={"username": "cust_isolation", "password": "Password123!"})

    # Try employee dashboard
    res_emp = client.get("/employee/dashboard")
    assert res_emp.status_code == 403

    # Try admin dashboard
    res_adm = client.get("/admin/dashboard")
    assert res_adm.status_code == 403

    # Try admin user management
    res_users = client.get("/admin/users")
    assert res_users.status_code == 403


def test_employee_cannot_access_admin_portal(client, app):
    with app.app_context():
        emp = User(username="emp_isolation", email="emp_iso@example.com", role=Role.EMPLOYEE)
        emp.set_password("Password123!")
        db.session.add(emp)
        db.session.commit()

    client.post("/auth/employee/login", data={"username": "emp_isolation", "password": "Password123!"})

    # Try admin dashboard & settings
    res_adm = client.get("/admin/dashboard")
    assert res_adm.status_code == 403

    res_sett = client.get("/admin/settings")
    assert res_sett.status_code == 403


def test_idor_customer_cannot_access_other_customer_account(client, app):
    with app.app_context():
        u1 = User(username="user1_idor", email="user1_idor@example.com", role=Role.CUSTOMER)
        u1.set_password("Password123!")
        u2 = User(username="user2_idor", email="user2_idor@example.com", role=Role.CUSTOMER)
        u2.set_password("Password123!")
        db.session.add_all([u1, u2])
        db.session.commit()

        acc2 = Account(user_id=u2.id, account_number="111122223333", account_type="SAVINGS", balance=500.0)
        db.session.add(acc2)
        db.session.commit()
        acc2_id = acc2.id

    # Login as u1
    client.post("/login", data={"username": "user1_idor", "password": "Password123!"})

    # Attempt to view u2's account details via API
    res = client.get(f"/api/accounts/{acc2_id}")
    assert res.status_code == 403
