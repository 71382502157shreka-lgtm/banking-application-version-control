from datetime import datetime
from app import db


class LoginSession(db.Model):
    __tablename__ = "login_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    session_token = db.Column(db.String(128), unique=True, nullable=False, index=True)

    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    browser = db.Column(db.String(50))
    os = db.Column(db.String(50))
    device_type = db.Column(db.String(30), default="Desktop")

    login_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    last_activity_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    status = db.Column(db.String(20), default="ACTIVE")  # ACTIVE, EXPIRED, REVOKED

    user = db.relationship("User", backref=db.backref("login_sessions", lazy=True))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_token": self.session_token[:10] + "..." if self.session_token else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "browser": self.browser,
            "os": self.os,
            "device_type": self.device_type,
            "login_at": self.login_at.isoformat() if self.login_at else None,
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
            "status": self.status,
        }
