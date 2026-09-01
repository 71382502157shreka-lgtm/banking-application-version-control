from datetime import datetime

from app import db


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


class AuditLog(db.Model):
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

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

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
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
