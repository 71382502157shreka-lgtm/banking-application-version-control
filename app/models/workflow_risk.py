from datetime import datetime, date
from decimal import Decimal
from app import db
from app.models.base import BaseModel


class RiskLevel:
    LOW = "LOW"            # 0-29
    MEDIUM = "MEDIUM"      # 30-59
    HIGH = "HIGH"          # 60-79
    CRITICAL = "CRITICAL"  # 80-100


class RiskDecision:
    APPROVED = "APPROVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class RollbackStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class RiskAssessment(BaseModel):
    __tablename__ = "risk_assessments"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True, index=True)

    risk_score = db.Column(db.Integer, nullable=False)  # 0 to 100
    risk_level = db.Column(db.String(20), nullable=False, default=RiskLevel.LOW)
    decision = db.Column(db.String(30), nullable=False, default=RiskDecision.APPROVED)

    risk_factors = db.Column(db.JSON, nullable=True)  # List of strings e.g. ["large_amount", "new_beneficiary"]
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "transaction_id": self.transaction_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "decision": self.decision,
            "risk_factors": self.risk_factors or [],
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_notes": self.review_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RollbackRequest(BaseModel):
    __tablename__ = "rollback_requests"

    id = db.Column(db.Integer, primary_key=True)
    requested_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    entity_type = db.Column(db.String(30), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    target_version = db.Column(db.Integer, nullable=False)

    reason = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=RollbackStatus.PENDING)

    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "requested_by": self.requested_by,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "target_version": self.target_version,
            "reason": self.reason,
            "status": self.status,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_notes": self.review_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TransferLimit(BaseModel):
    __tablename__ = "transfer_limits"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, unique=True, index=True)

    per_transaction_limit = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("100000.00"))
    daily_limit = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("500000.00"))
    used_today = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    last_reset_date = db.Column(db.Date, default=date.today, nullable=False)

    def reset_if_new_day(self):
        if self.last_reset_date != date.today():
            self.used_today = Decimal("0.00")
            self.last_reset_date = date.today()

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "per_transaction_limit": str(self.per_transaction_limit),
            "daily_limit": str(self.daily_limit),
            "used_today": str(self.used_today),
            "last_reset_date": self.last_reset_date.isoformat() if self.last_reset_date else None,
        }
