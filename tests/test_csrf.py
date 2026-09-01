import re
import pytest
from app import create_app, db as _db
from app.models.user import Role
from app.services import auth_service


@pytest.fixture
def csrf_app():
    application = create_app("testing")
    application.config["WTF_CSRF_ENABLED"] = True
    application.config["SECRET_KEY"] = "test-csrf-secret-key"
    with application.app_context():
        _db.create_all()
        auth_service.register_user(
            "testuser", "test@bank.local", "Str0ngPass1!", full_name="Test User", role=Role.CUSTOMER
        )
        yield application
        _db.drop_all()


@pytest.fixture
def csrf_client(csrf_app):
    return csrf_app.test_client()


def test_login_page_renders_csrf_token(csrf_client):
    response = csrf_client.get("/login")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="csrf_token"' in html
    assert '<meta name="csrf-token"' in html


def test_register_page_renders_csrf_token(csrf_client):
    response = csrf_client.get("/register")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="csrf_token"' in html


def test_post_login_without_csrf_is_rejected(csrf_client):
    response = csrf_client.post(
        "/login",
        data={"username": "testuser", "password": "Str0ngPass1!"},
    )
    assert response.status_code == 400
    assert "CSRF" in response.get_data(as_text=True)


def test_post_login_with_csrf_succeeds(csrf_client):
    get_res = csrf_client.get("/login")
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', get_res.get_data(as_text=True))
    assert match is not None
    token = match.group(1)

    response = csrf_client.post(
        "/login",
        data={"username": "testuser", "password": "Str0ngPass1!", "csrf_token": token},
        follow_redirects=False,
    )
    # Redirects to dashboard (302) on successful login
    assert response.status_code == 302
    assert "/customer/dashboard" in response.headers["Location"]
