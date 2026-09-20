from datetime import datetime
from app import db


class RollbackStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class RollbackRequest(db.Model):
    __tablename__ = "rollback_requests"

    id = db.Column(db.Integer, primary_key=True)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    entity_type = db.Column(db.String(30), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    target_version_number = db.Column(db.Integer, nullable=False)

    reason = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default=RollbackStatus.PENDING, nullable=False)

    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    requested_by = db.relationship("User", foreign_keys=[requested_by_id], backref=db.backref("rollback_requests_made", lazy=True))
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id], backref=db.backref("rollback_requests_reviewed", lazy=True))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "requested_by_id": self.requested_by_id,
            "requested_by_name": self.requested_by.full_name if self.requested_by else None,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "target_version_number": self.target_version_number,
            "reason": self.reason,
            "status": self.status,
            "reviewed_by_id": self.reviewed_by_id,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_notes": self.review_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
