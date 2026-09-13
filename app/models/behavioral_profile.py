from datetime import datetime
from decimal import Decimal
from app import db
from app.models.base import BaseModel


class UserBehavioralProfile(BaseModel):
    __tablename__ = "user_behavioral_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)

    known_ips = db.Column(db.JSON, default=list, nullable=False)
    known_user_agents = db.Column(db.JSON, default=list, nullable=False)

    avg_transfer_amount = db.Column(db.Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    max_transfer_amount = db.Column(db.Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_transfer_count = db.Column(db.Integer, default=0, nullable=False)

    usual_login_hours = db.Column(db.JSON, default=list, nullable=False)
    last_profile_updated_at = db.Column(db.DateTime, nullable=True)
    last_beneficiary_added_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @classmethod
    def get_or_create(cls, user_id: int) -> "UserBehavioralProfile":
        profile = cls.query.filter_by(user_id=user_id).first()
        if not profile:
            profile = cls(
                user_id=user_id,
                known_ips=[],
                known_user_agents=[],
                avg_transfer_amount=Decimal("0.00"),
                max_transfer_amount=Decimal("0.00"),
                total_transfer_count=0,
                usual_login_hours=[],
            )
            db.session.add(profile)
            db.session.commit()
        return profile

    def is_ip_known(self, ip_address: str) -> bool:
        if not self.known_ips or not ip_address:
            return False
        return ip_address in self.known_ips

    def is_user_agent_known(self, user_agent: str) -> bool:
        if not self.known_user_agents or not user_agent:
            return False
        return user_agent in self.known_user_agents

    def record_login(self, ip_address: str, user_agent: str):
        updated = False
        ips = list(self.known_ips or [])
        uas = list(self.known_user_agents or [])
        hours = list(self.usual_login_hours or [])

        if ip_address and ip_address not in ips:
            ips.append(ip_address)
            self.known_ips = ips
            updated = True

        if user_agent and user_agent not in uas:
            uas.append(user_agent)
            self.known_user_agents = uas
            updated = True

        current_hour = datetime.utcnow().hour
        if current_hour not in hours:
            hours.append(current_hour)
            self.usual_login_hours = hours
            updated = True

        if updated:
            self.updated_at = datetime.utcnow()
            db.session.commit()

    def record_transfer(self, amount: Decimal):
        amt = Decimal(str(amount))
        count = self.total_transfer_count or 0
        current_avg = Decimal(str(self.avg_transfer_amount or 0))

        # Update cumulative moving average
        new_avg = ((current_avg * count) + amt) / (count + 1)
        self.avg_transfer_amount = round(new_avg, 2)
        self.total_transfer_count = count + 1

        if amt > Decimal(str(self.max_transfer_amount or 0)):
            self.max_transfer_amount = amt

        self.updated_at = datetime.utcnow()
        db.session.commit()

    def record_profile_update(self):
        self.last_profile_updated_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        db.session.commit()

    def record_beneficiary_added(self):
        self.last_beneficiary_added_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        db.session.commit()

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "known_ips_count": len(self.known_ips or []),
            "known_user_agents_count": len(self.known_user_agents or []),
            "avg_transfer_amount": str(self.avg_transfer_amount),
            "max_transfer_amount": str(self.max_transfer_amount),
            "total_transfer_count": self.total_transfer_count,
            "usual_login_hours": self.usual_login_hours or [],
            "last_profile_updated_at": self.last_profile_updated_at.isoformat() if self.last_profile_updated_at else None,
            "last_beneficiary_added_at": self.last_beneficiary_added_at.isoformat() if self.last_beneficiary_added_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
