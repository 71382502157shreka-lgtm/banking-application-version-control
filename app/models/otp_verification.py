from datetime import datetime, timedelta
from app import db
from werkzeug.security import generate_password_hash, check_password_hash


class OTPVerification(db.Model):
    __tablename__ = "otp_verifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    otp_hash = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(40), nullable=False, default="LOGIN")  # LOGIN, BENEFICIARY_ADD, TRANSFER
    expires_at = db.Column(db.DateTime, nullable=False)
    failed_attempts = db.Column(db.Integer, default=0, nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    user = db.relationship("User", backref=db.backref("otp_verifications", lazy=True))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def set_otp(self, raw_code: str) -> None:
        self.otp_hash = generate_password_hash(str(raw_code))

    def check_otp(self, raw_code: str) -> bool:
        return check_password_hash(self.otp_hash, str(raw_code))

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "purpose": self.purpose,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_used": self.is_used,
            "is_expired": self.is_expired(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
