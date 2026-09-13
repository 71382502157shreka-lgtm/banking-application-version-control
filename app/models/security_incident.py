from datetime import datetime
from app import db
from app.models.base import BaseModel


class IncidentSeverity:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus:
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    CONTAINED = "CONTAINED"
    RESOLVED = "RESOLVED"
    CLOSED_FALSE_POSITIVE = "CLOSED_FALSE_POSITIVE"


class FreezeType:
    DEBIT_FREEZE = "DEBIT_FREEZE"
    CREDIT_FREEZE = "CREDIT_FREEZE"
    TOTAL_FREEZE = "TOTAL_FREEZE"


class SecurityIncident(BaseModel):
    __tablename__ = "security_incidents"

    id = db.Column(db.Integer, primary_key=True)
    incident_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False, default=IncidentSeverity.MEDIUM)
    status = db.Column(db.String(30), nullable=False, default=IncidentStatus.OPEN)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    assigned_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    evidence_snapshot = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

    events = db.relationship("IncidentEvent", backref="incident", lazy="dynamic", cascade="all, delete-orphan")
    alerts = db.relationship("FraudAlert", backref="incident", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "incident_number": self.incident_number,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "user_id": self.user_id,
            "assigned_admin_id": self.assigned_admin_id,
            "evidence_snapshot": self.evidence_snapshot or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class IncidentEvent(BaseModel):
    __tablename__ = "incident_events"

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("security_incidents.id"), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False)  # CREATED, STATUS_CHANGED, NOTE_ADDED, ACCOUNT_FROZEN, etc.
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    details = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "details": self.details or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AccountFreeze(BaseModel):
    __tablename__ = "account_freezes"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    freeze_type = db.Column(db.String(30), nullable=False, default=FreezeType.TOTAL_FREEZE)
    reason = db.Column(db.String(255), nullable=False)

    frozen_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    unfrozen_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    unfreeze_reason = db.Column(db.String(255), nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    unfrozen_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "freeze_type": self.freeze_type,
            "reason": self.reason,
            "frozen_by_admin_id": self.frozen_by_admin_id,
            "unfrozen_by_admin_id": self.unfrozen_by_admin_id,
            "unfreeze_reason": self.unfreeze_reason,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "unfrozen_at": self.unfrozen_at.isoformat() if self.unfrozen_at else None,
        }
