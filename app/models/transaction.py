import uuid
from datetime import datetime
from decimal import Decimal

from app import db


class TransactionType:
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER = "TRANSFER"
    REVERSAL = "REVERSAL"


class TransactionStatus:
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


def generate_reference_number() -> str:
    return f"TXN-{uuid.uuid4().hex[:12].upper()}"


class Transaction(db.Model):
    """
    Financial transactions are append-only: once COMPLETED they are never
    edited or deleted. Corrections are made by inserting a new REVERSAL
    transaction that references the original via related_transaction_id.
    """
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)

    transaction_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    reference_number = db.Column(db.String(40), unique=True, nullable=False, default=generate_reference_number)
    description = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default=TransactionStatus.PENDING)

    counterparty_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    related_transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)

    balance_after = db.Column(db.Numeric(14, 2), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "transaction_type": self.transaction_type,
            "amount": str(self.amount),
            "reference_number": self.reference_number,
            "description": self.description,
            "status": self.status,
            "counterparty_account_id": self.counterparty_account_id,
            "related_transaction_id": self.related_transaction_id,
            "balance_after": str(self.balance_after) if self.balance_after is not None else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Transaction {self.reference_number} {self.transaction_type} {self.amount}>"
