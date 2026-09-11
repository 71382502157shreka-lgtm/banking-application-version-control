import hashlib
import json
from datetime import datetime

from app import db
from app.models.base import BaseModel


class AuditAction:
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    REGISTER = "REGISTER"
    FAILED_LOGIN = "FAILED_LOGIN"
    ACCOUNT_CREATED = "ACCOUNT_CREATED"
    ACCOUNT_UPDATED = "ACCOUNT_UPDATED"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER = "TRANSFER"
    REVERSAL = "REVERSAL"
    BENEFICIARY_CREATED = "BENEFICIARY_CREATED"
    BENEFICIARY_UPDATED = "BENEFICIARY_UPDATED"
    BENEFICIARY_DELETED = "BENEFICIARY_DELETED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PROFILE_UPDATED = "PROFILE_UPDATED"
    ADMIN_ACTION = "ADMIN_ACTION"
    VERSION_CREATED = "VERSION_CREATED"
    VERSION_RESTORED = "VERSION_RESTORED"
    ROLLBACK_REQUESTED = "ROLLBACK_REQUESTED"
    ROLLBACK_APPROVED = "ROLLBACK_APPROVED"
    ROLLBACK_REJECTED = "ROLLBACK_REJECTED"
    RISK_REVIEW_APPROVED = "RISK_REVIEW_APPROVED"
    RISK_REVIEW_REJECTED = "RISK_REVIEW_REJECTED"
    OTP_GENERATED = "OTP_GENERATED"
    OTP_VERIFIED = "OTP_VERIFIED"
    OTP_FAILED = "OTP_FAILED"
    SESSION_REVOKED = "SESSION_REVOKED"
    ACCESS_DENIED = "ACCESS_DENIED"
    REPORT_EXPORTED = "REPORT_EXPORTED"
    CUSTOMER_LOOKUP = "CUSTOMER_LOOKUP"
    SERVICE_REQUEST = "SERVICE_REQUEST"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"



class AuditLog(BaseModel):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    action = db.Column(db.String(40), nullable=False, index=True)
    entity_type = db.Column(db.String(30), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)

    old_data = db.Column(db.JSON, nullable=True)
    new_data = db.Column(db.JSON, nullable=True)

    ip_address = db.Column(db.String(45))
    description = db.Column(db.String(255))

    previous_hash = db.Column(db.String(64), nullable=True)
    current_hash = db.Column(db.String(64), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def calculate_hash(self, prev_hash: str = None) -> str:
        ph = prev_hash if prev_hash is not None else (self.previous_hash or "GENESIS")
        ts_str = self.created_at.isoformat() if self.created_at else ""
        old_str = json.dumps(self.old_data, sort_keys=True) if self.old_data else ""
        new_str = json.dumps(self.new_data, sort_keys=True) if self.new_data else ""
        raw = f"{ph}|{self.user_id or ''}|{self.action}|{self.entity_type or ''}|{self.entity_id or ''}|{self.description or ''}|{ts_str}|{old_str}|{new_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "old_data": self.old_data,
            "new_data": self.new_data,
            "ip_address": self.ip_address,
            "description": self.description,
            "previous_hash": self.previous_hash,
            "current_hash": self.current_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
