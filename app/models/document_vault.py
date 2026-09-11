from datetime import datetime
from app import db
from app.models.base import BaseModel


class DocumentStatus:
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class CustomerDocument(BaseModel):
    __tablename__ = "customer_documents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    document_type = db.Column(db.String(40), nullable=False)  # AADHAAR, PAN, PASSPORT, TAX_RETURN, ADDRESS_PROOF
    document_name = db.Column(db.String(120), nullable=False)
    file_path = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), nullable=False, default=DocumentStatus.PENDING_VERIFICATION)
    verification_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id], lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "document_type": self.document_type,
            "document_name": self.document_name,
            "status": self.status,
            "verification_notes": self.verification_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
