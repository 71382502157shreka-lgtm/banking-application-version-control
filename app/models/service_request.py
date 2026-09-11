from datetime import datetime
from app import db
from app.models.base import BaseModel


class ServiceRequestType:
    CHEQUE_BOOK = "CHEQUE_BOOK"
    STOP_CHEQUE = "STOP_CHEQUE"
    CARD_BLOCK = "CARD_BLOCK"
    PIN_RESET = "PIN_RESET"
    ADDRESS_CHANGE = "ADDRESS_CHANGE"


class ServiceRequestStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class ServiceRequest(BaseModel):
    __tablename__ = "service_requests"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(40), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)

    request_type = db.Column(db.String(40), nullable=False)
    details = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=ServiceRequestStatus.PENDING)
    admin_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id], lazy=True)
    account = db.relationship("Account", foreign_keys=[account_id], lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_number": self.ticket_number,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "request_type": self.request_type,
            "details": self.details,
            "status": self.status,
            "admin_notes": self.admin_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
