from datetime import datetime
from app import db
from app.models.base import BaseModel


class FraudAlertSeverity:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FraudAlertStatus:
    NEW = "NEW"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    CONFIRMED_FRAUD = "CONFIRMED_FRAUD"
    DISMISSED = "DISMISSED"


class FraudAlert(BaseModel):
    __tablename__ = "fraud_alerts"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("security_incidents.id"), nullable=True, index=True)

    alert_type = db.Column(db.String(50), nullable=False, index=True)  # DUPLICATE_ATTEMPT, MULE_ACCOUNT_SUSPECT, HIGH_VELOCITY_BURST, CRITICAL_RISK_HOLD
    severity = db.Column(db.String(20), nullable=False, default=FraudAlertSeverity.MEDIUM)
    status = db.Column(db.String(30), nullable=False, default=FraudAlertStatus.NEW)

    details = db.Column(db.JSON, nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    resolution_notes = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "transaction_id": self.transaction_id,
            "user_id": self.user_id,
            "incident_id": self.incident_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "status": self.status,
            "details": self.details or {},
            "assigned_to": self.assigned_to,
            "resolution_notes": self.resolution_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
