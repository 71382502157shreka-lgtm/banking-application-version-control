import pytest

from app.services import auth_service
from app.utils.validators import ValidationError


def test_register_creates_profile_version(app, db, customer):
    from app.models.version import EntityVersion, EntityType

    versions = EntityVersion.query.filter_by(
        entity_type=EntityType.USER_PROFILE, entity_id=customer.id
    ).all()
    assert len(versions) == 1
    assert versions[0].change_type == "CREATE"


def test_duplicate_username_rejected(app, db, customer):
    with pytest.raises(ValidationError):
        auth_service.register_user("janedoe", "other@example.com", "Str0ngPass!")


def test_authenticate_success(app, db, customer):
    user = auth_service.authenticate("janedoe", "Str0ngPass!")
    assert user.id == customer.id


def test_authenticate_wrong_password_fails(app, db, customer):
    with pytest.raises(auth_service.AuthError):
        auth_service.authenticate("janedoe", "WrongPassword1")


def test_account_locks_after_max_failed_attempts(app, db, customer):
    max_attempts = app.config["MAX_FAILED_LOGIN_ATTEMPTS"]
    for _ in range(max_attempts):
        with pytest.raises(auth_service.AuthError):
            auth_service.authenticate("janedoe", "WrongPassword1")

    with pytest.raises(auth_service.AuthError) as exc_info:
        auth_service.authenticate("janedoe", "Str0ngPass!")  # even correct password now blocked
    assert "locked" in str(exc_info.value).lower()


def test_customer_web_registration_and_login_flow(client, app, db):
    # Register new customer via HTTP POST
    resp = client.post("/register", data={
        "username": "newcust1",
        "email": "newcust1@example.com",
        "password": "SecurePass123!",
        "full_name": "New Customer One",
        "phone": "9876543210"
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Welcome! Your Customer account has been created successfully." in resp.data or b"Dashboard" in resp.data

    # Logout
    client.get("/logout", follow_redirects=True)

    # Login as newly registered customer
    login_resp = client.post("/login", data={
        "username": "newcust1",
        "password": "SecurePass123!"
    }, follow_redirects=True)
    assert login_resp.status_code == 200
    assert b"Customer Dashboard" in login_resp.data or b"Accounts" in login_resp.data


def test_employee_web_registration_and_login_flow(client, app, db):
    default_key = app.config.get("EMPLOYEE_AUTH_KEY", "ChangeMe_Employee123!")

    resp = client.post("/auth/employee/register", data={
        "username": "newstaff1",
        "email": "newstaff1@example.com",
        "password": "SecurePass123!",
        "full_name": "New Staff One",
        "phone": "9876543211",
        "auth_key": default_key
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Employee account successfully registered" in resp.data or b"Staff Operational Dashboard" in resp.data

    client.get("/logout", follow_redirects=True)

    login_resp = client.post("/auth/employee/login", data={
        "username": "newstaff1",
        "password": "SecurePass123!"
    }, follow_redirects=True)
    assert login_resp.status_code == 200
    assert b"Staff Operational Dashboard" in login_resp.data or b"Employee" in login_resp.data


def test_admin_web_registration_and_login_flow(client, app, db):
    default_key = app.config.get("ADMIN_AUTH_KEY", "ChangeMe_Admin123!")

    resp = client.post("/auth/admin/register", data={
        "username": "newadmin1",
        "email": "newadmin1@example.com",
        "password": "SecurePass123!",
        "full_name": "New Admin One",
        "phone": "9876543212",
        "auth_key": default_key
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Administrator account successfully registered" in resp.data or b"Administrator Command Center" in resp.data

    client.get("/logout", follow_redirects=True)

    login_resp = client.post("/auth/admin/login", data={
        "username": "newadmin1",
        "password": "SecurePass123!"
    }, follow_redirects=True)
    assert login_resp.status_code == 200
    assert b"Administrator Command Center" in login_resp.data or b"Admin" in login_resp.data

