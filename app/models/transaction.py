import uuid
from datetime import datetime
from decimal import Decimal

from app import db
from app.models.base import BaseModel


class TransactionType:
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER = "TRANSFER"
    REVERSAL = "REVERSAL"


class TransactionMode:
    UPI = "UPI"
    IMPS = "IMPS"
    NEFT = "NEFT"
    RTGS = "RTGS"
    ATM = "ATM"
    CASH_DEPOSIT = "CASH_DEPOSIT"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL"
    TRANSFER = "TRANSFER"


class TransactionStatus:
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


def generate_reference_number() -> str:
    return f"TXN-{uuid.uuid4().hex[:12].upper()}"


class Transaction(BaseModel):
    """
    Financial transactions are append-only: once COMPLETED they are never
    edited or deleted. Corrections are made by inserting a new REVERSAL
    transaction that references the original via related_transaction_id.
    """
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)

    transaction_type = db.Column(db.String(20), nullable=False)
    transaction_mode = db.Column(db.String(30), nullable=True, default=TransactionMode.TRANSFER)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    reference_number = db.Column(db.String(40), unique=True, nullable=False, default=generate_reference_number)
    description = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default=TransactionStatus.PENDING)

    counterparty_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    related_transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)

    balance_after = db.Column(db.Numeric(14, 2), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def narration(self) -> str:
        return self.description or "N/A"

    @property
    def credit_amount(self) -> str:
        if self.transaction_type in [TransactionType.DEPOSIT, TransactionType.REVERSAL]:
            return str(self.amount)
        if self.transaction_type == TransactionType.TRANSFER and self.amount and self.amount > 0:
            return str(self.amount)
        return "0.00"

    @property
    def debit_amount(self) -> str:
        if self.transaction_type in [TransactionType.WITHDRAWAL]:
            return str(self.amount)
        if self.transaction_type == TransactionType.TRANSFER and self.amount and self.amount < 0:
            return str(abs(self.amount))
        return "0.00"

    @property
    def balance_after_transaction(self) -> str:
        return str(self.balance_after) if self.balance_after is not None else "0.00"

    def to_dict(self):
        mode_val = self.transaction_mode or TransactionMode.TRANSFER
        return {
            "id": self.id,
            "account_id": self.account_id,
            "transaction_type": self.transaction_type,
            "transaction_mode": mode_val,
            "amount": str(self.amount),
            "reference_number": self.reference_number,
            "description": self.description,
            "narration": self.narration,
            "credit_amount": self.credit_amount,
            "debit_amount": self.debit_amount,
            "status": self.status,
            "counterparty_account_id": self.counterparty_account_id,
            "related_transaction_id": self.related_transaction_id,
            "balance_after": str(self.balance_after) if self.balance_after is not None else None,
            "balance_after_transaction": self.balance_after_transaction,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Transaction {self.reference_number} {self.transaction_type} {self.amount}>"

