import random
from datetime import datetime, timedelta
from flask import session, has_request_context
from app import db
from app.models.security_session import OTPVerification, SecurityEvent
from app.models.audit_log import AuditAction
from app.services.audit_service import log_action


class OTPError(Exception):
    pass


def generate_otp(user_id: int, action_type: str, entity_id: int = None, expiry_minutes: int = 5) -> str:
    """
    Generate a 6-digit OTP code, invalidate any existing pending OTPs for
    this user/action, store the hashed OTP, and log the security event.
    Returns the plain 6-digit OTP string (to display in demo/dev mode).
    """
    # Invalidate previous unverified OTPs
    OTPVerification.query.filter_by(
        user_id=user_id, action_type=action_type, is_verified=False
    ).update({"is_verified": False})

    raw_code = f"{random.randint(100000, 999999)}"
    otp_record = OTPVerification(
        user_id=user_id,
        otp_hash=OTPVerification.hash_otp(raw_code),
        action_type=action_type,
        entity_id=entity_id,
        expires_at=datetime.utcnow() + timedelta(minutes=expiry_minutes),
        attempts=0,
        is_verified=False,
    )
    db.session.add(otp_record)

    log_action(
        action=AuditAction.OTP_GENERATED,
        user_id=user_id,
        entity_type="OTP",
        description=f"Generated OTP for {action_type}",
    )
    db.session.commit()

    # Store in Flask session for dev/demo UI helper if in request context
    if has_request_context():
        session["latest_otp_demo"] = raw_code
    return raw_code


def verify_otp(user_id: int, action_type: str, code: str) -> bool:
    """
    Verify a submitted 6-digit OTP code against the active database OTP record.
    Limits attempts to 3 before locking the OTP record.
    """
    code = (code or "").strip()
    if not code:
        raise OTPError("OTP code is required")

    otp_record = (
        OTPVerification.query
        .filter_by(user_id=user_id, action_type=action_type, is_verified=False)
        .order_by(OTPVerification.created_at.desc())
        .first()
    )

    if not otp_record:
        raise OTPError("No active OTP request found. Please request a new OTP.")

    if otp_record.is_expired():
        log_action(AuditAction.OTP_FAILED, user_id=user_id, description=f"Expired OTP attempt for {action_type}")
        db.session.commit()
        raise OTPError("OTP code has expired. Please request a new OTP.")

    if otp_record.attempts >= 3:
        log_action(AuditAction.OTP_FAILED, user_id=user_id, description=f"Max OTP attempts exceeded for {action_type}")
        db.session.commit()
        raise OTPError("Maximum OTP verification attempts exceeded. Request a new OTP.")

    otp_record.attempts += 1

    if OTPVerification.hash_otp(code) != otp_record.otp_hash:
        log_action(AuditAction.OTP_FAILED, user_id=user_id, description=f"Incorrect OTP code entered ({otp_record.attempts}/3)")
        db.session.commit()
        raise OTPError(f"Invalid OTP code. ({3 - otp_record.attempts} attempts remaining)")

    otp_record.is_verified = True
    if has_request_context():
        session.pop("latest_otp_demo", None)

    log_action(AuditAction.OTP_VERIFIED, user_id=user_id, description=f"OTP successfully verified for {action_type}")
    db.session.commit()
    return True
