from datetime import datetime
from app import db


class RiskLevel:
    LOW = "LOW"            # 0–29
    MEDIUM = "MEDIUM"      # 30–59
    HIGH = "HIGH"          # 60–79
    CRITICAL = "CRITICAL"  # 80–100


class RiskAssessment(db.Model):
    __tablename__ = "risk_assessments"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    risk_score = db.Column(db.Integer, nullable=False, default=0)  # 0 to 100
    risk_level = db.Column(db.String(20), nullable=False, default=RiskLevel.LOW)
    factors = db.Column(db.JSON, nullable=True)
    decision = db.Column(db.String(30), nullable=False, default="APPROVED")  # APPROVED, REVIEW_REQUIRED, BLOCKED

    assessed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("risk_assessments", lazy=True))
    transaction = db.relationship("Transaction", backref=db.backref("risk_assessment", uselist=False))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "transaction_id": self.transaction_id,
            "user_id": self.user_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "factors": self.factors or [],
            "decision": self.decision,
            "assessed_at": self.assessed_at.isoformat() if self.assessed_at else None,
        }
