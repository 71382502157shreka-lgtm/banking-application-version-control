from datetime import datetime

from app import db


class BeneficiaryStatus:
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Beneficiary(db.Model):
    __tablename__ = "beneficiaries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    name = db.Column(db.String(120), nullable=False)
    account_number = db.Column(db.String(30), nullable=False)
    bank_name = db.Column(db.String(120), nullable=False)
    ifsc = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=BeneficiaryStatus.ACTIVE)

    version_number = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "account_number": self.account_number,
            "bank_name": self.bank_name,
            "ifsc": self.ifsc,
            "status": self.status,
            "version_number": self.version_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
