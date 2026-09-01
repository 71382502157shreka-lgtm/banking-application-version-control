import pytest

from app import create_app, db as _db
from app.models.user import Role
from app.services import auth_service


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def customer(app):
    return auth_service.register_user(
        "janedoe", "jane@example.com", "Str0ngPass!", full_name="Jane Doe", role=Role.CUSTOMER
    )


@pytest.fixture
def admin(app):
    return auth_service.register_user(
        "adminuser", "admin2@example.com", "Str0ngPass!", full_name="Admin User", role=Role.ADMIN
    )
