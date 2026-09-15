from datetime import datetime, date
from app import db


class TransferLimit(db.Model):
    __tablename__ = "transfer_limits"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True)

    daily_transfer_limit = db.Column(db.Numeric(12, 2), default=100000.00, nullable=False)
    per_transaction_limit = db.Column(db.Numeric(12, 2), default=50000.00, nullable=False)

    current_daily_spent = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    last_reset_date = db.Column(db.Date, default=date.today, nullable=False)

    user = db.relationship("User", backref=db.backref("transfer_limit", uselist=False))

    def reset_if_new_day(self):
        if self.last_reset_date != date.today():
            self.current_daily_spent = 0.00
            self.last_reset_date = date.today()

    def can_transfer(self, amount: float) -> tuple[bool, str]:
        self.reset_if_new_day()
        if float(amount) > float(self.per_transaction_limit):
            return False, f"Transaction amount ₹{amount:,.2f} exceeds per-transaction limit of ₹{self.per_transaction_limit:,.2f}"
        if float(self.current_daily_spent) + float(amount) > float(self.daily_transfer_limit):
            remaining = float(self.daily_transfer_limit) - float(self.current_daily_spent)
            return False, f"Transaction exceeds remaining daily limit of ₹{max(0, remaining):,.2f}"
        return True, "OK"

    def record_transfer(self, amount: float):
        self.reset_if_new_day()
        self.current_daily_spent = float(self.current_daily_spent) + float(amount)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "daily_transfer_limit": float(self.daily_transfer_limit),
            "per_transaction_limit": float(self.per_transaction_limit),
            "current_daily_spent": float(self.current_daily_spent),
            "remaining_daily_limit": max(0.0, float(self.daily_transfer_limit) - float(self.current_daily_spent)),
            "last_reset_date": self.last_reset_date.isoformat() if self.last_reset_date else None,
        }
