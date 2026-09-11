import random
from datetime import datetime
from decimal import Decimal

from app import db
from app.models.base import BaseModel


class AccountType:
    SAVINGS = "SAVINGS"
    CURRENT = "CURRENT"
    FIXED_DEPOSIT = "FIXED_DEPOSIT"
    RECURRING_DEPOSIT = "RECURRING_DEPOSIT"


class AccountStatus:
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


def generate_account_number() -> str:
    return f"{random.randint(10**11, 10**12 - 1)}"  # 12-digit account number


class Account(BaseModel):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    account_number = db.Column(db.String(20), unique=True, nullable=False, default=generate_account_number)
    account_type = db.Column(db.String(20), nullable=False, default=AccountType.SAVINGS)
    balance = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    available_balance = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    status = db.Column(db.String(20), nullable=False, default=AccountStatus.ACTIVE)

    version_number = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = db.relationship("Transaction", foreign_keys="Transaction.account_id", backref="account", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "account_number": self.account_number,
            "account_type": self.account_type,
            "balance": str(self.balance),
            "available_balance": str(self.available_balance),
            "status": self.status,
            "version_number": self.version_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Account {self.account_number} balance={self.balance}>"
