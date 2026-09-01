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
