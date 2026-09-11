from flask import current_app

from app import db
from app.models.user import User, Role
from app.models.audit_log import AuditAction
from app.models.version import EntityType, ChangeType
from app.services.audit_service import log_action
from app.services.version_service import create_version
from app.services.session_service import create_user_session
from app.utils.validators import (
    ValidationError, validate_email, validate_username, validate_password_strength,
)


class AuthError(Exception):
    pass


def register_user(username, email, password, full_name=None, phone=None, role=Role.CUSTOMER):
    validate_username(username)
    validate_email(email)
    validate_password_strength(password)

    if User.query.filter_by(username=username).first():
        raise ValidationError("Username already taken", field="username")
    if User.query.filter_by(email=email).first():
        raise ValidationError("Email already registered", field="email")

    user = User(username=username, email=email, full_name=full_name, phone=phone, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    create_version(
        entity_type=EntityType.USER_PROFILE,
        entity_id=user.id,
        change_type=ChangeType.CREATE,
        old_data=None,
        new_data=user.to_dict(),
        changed_by=user.id,
        change_summary="Account registered",
        audit_action=AuditAction.REGISTER,
    )
    db.session.commit()
    return user


def authenticate(username, password):
    max_attempts = current_app.config["MAX_FAILED_LOGIN_ATTEMPTS"]
    lockout_minutes = current_app.config["LOCKOUT_DURATION_MINUTES"]

    user = User.query.filter_by(username=username).first()

    if not user:
        log_action(AuditAction.FAILED_LOGIN, description=f"Unknown username: {username}")
        db.session.commit()
        raise AuthError("Invalid username or password")

    if user.is_locked():
        log_action(AuditAction.FAILED_LOGIN, user_id=user.id, description="Account locked")
        db.session.commit()
        raise AuthError("Account is temporarily locked due to repeated failed attempts")

    if user.status != "active":
        log_action(AuditAction.FAILED_LOGIN, user_id=user.id, description="Account not active")
        db.session.commit()
        raise AuthError("Account is not active. Contact support.")

    if not user.check_password(password):
        user.register_failed_login(max_attempts, lockout_minutes)
        log_action(AuditAction.FAILED_LOGIN, user_id=user.id, description="Incorrect password")
        db.session.commit()
        raise AuthError("Invalid username or password")

    user.register_successful_login()
    log_action(AuditAction.LOGIN, user_id=user.id, description="Successful login")
    
    # Track LoginSession
    create_user_session(user.id)
    db.session.commit()
    return user


def logout_event(user_id):
    log_action(AuditAction.LOGOUT, user_id=user_id, description="User logged out")
    db.session.commit()


def change_password(user: User, old_password: str, new_password: str):
    if not user.check_password(old_password):
        raise AuthError("Current password is incorrect")
    validate_password_strength(new_password)
    user.set_password(new_password)
    log_action(AuditAction.PASSWORD_CHANGED, user_id=user.id, description="Password changed")
    db.session.commit()


def update_profile(user: User, **changes):
    old_data = user.to_dict()
    for field in ("full_name", "phone", "email"):
        if field in changes and changes[field] is not None:
            setattr(user, field, changes[field])
    new_data = user.to_dict()

    create_version(
        entity_type=EntityType.USER_PROFILE,
        entity_id=user.id,
        change_type=ChangeType.UPDATE,
        old_data=old_data,
        new_data=new_data,
        changed_by=user.id,
        change_summary="Profile updated",
        audit_action=AuditAction.PROFILE_UPDATED,
    )
    db.session.commit()
    return user
