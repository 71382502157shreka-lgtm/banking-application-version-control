from datetime import datetime, timedelta
import secrets
import hashlib
from app import db
from app.models.base import BaseModel


class LoginSession(BaseModel):
    __tablename__ = "login_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    session_token = db.Column(db.String(64), unique=True, nullable=False, index=True)

    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    device_info = db.Column(db.String(100))
    browser = db.Column(db.String(50))
    operating_system = db.Column(db.String(50))

    login_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    step_up_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    step_up_expires_at = db.Column(db.DateTime, nullable=True)

    def issue_step_up_token(self, ttl_minutes: int = 5) -> str:
        token = secrets.token_hex(32)
        self.step_up_token = token
        self.step_up_expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
        db.session.commit()
        return token

    def is_step_up_valid(self, token: str) -> bool:
        if not self.step_up_token or self.step_up_token != token:
            return False
        if not self.step_up_expires_at or datetime.utcnow() > self.step_up_expires_at:
            return False
        return True

    def consume_step_up_token(self):
        self.step_up_token = None
        self.step_up_expires_at = None
        db.session.commit()

    @classmethod
    def create_session(cls, user_id: int, ip_address: str, user_agent_str: str):
        token = secrets.token_hex(32)
        browser, os_name, device = cls._parse_user_agent(user_agent_str)
        session = cls(
            user_id=user_id,
            session_token=token,
            ip_address=ip_address,
            user_agent=user_agent_str[:255] if user_agent_str else "",
            browser=browser,
            operating_system=os_name,
            device_info=device,
            login_time=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            is_active=True,
        )
        db.session.add(session)
        return session

    @staticmethod
    def _parse_user_agent(ua_str: str):
        if not ua_str:
            return "Unknown Browser", "Unknown OS", "Desktop"
        ua_lower = ua_str.lower()

        # Browser detection
        if "chrome" in ua_lower and "edg" not in ua_lower:
            browser = "Google Chrome"
        elif "edg" in ua_lower:
            browser = "Microsoft Edge"
        elif "firefox" in ua_lower:
            browser = "Mozilla Firefox"
        elif "safari" in ua_lower and "chrome" not in ua_lower:
            browser = "Apple Safari"
        else:
            browser = "Web Browser"

        # OS detection
        if "windows" in ua_lower:
            os_name = "Windows OS"
        elif "mac os" in ua_lower or "macintosh" in ua_lower:
            os_name = "macOS"
        elif "linux" in ua_lower:
            os_name = "Linux OS"
        elif "android" in ua_lower:
            os_name = "Android"
        elif "iphone" in ua_lower or "ipad" in ua_lower:
            os_name = "iOS"
        else:
            os_name = "Unknown OS"

        device = "Mobile" if ("mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower) else "Desktop"
        return browser, os_name, device

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_token": self.session_token[:10] + "...",
            "ip_address": self.ip_address,
            "browser": self.browser,
            "operating_system": self.operating_system,
            "device_info": self.device_info,
            "login_time": self.login_time.isoformat() if self.login_time else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "is_active": self.is_active,
            "has_active_step_up": bool(self.step_up_token and self.step_up_expires_at and datetime.utcnow() < self.step_up_expires_at),
        }


class SecurityEvent(BaseModel):
    __tablename__ = "security_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    event_type = db.Column(db.String(50), nullable=False, index=True)
    severity = db.Column(db.String(20), nullable=False, default="INFO")  # INFO, WARNING, HIGH, CRITICAL
    description = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "description": self.description,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OTPVerification(BaseModel):
    __tablename__ = "otp_verifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    otp_hash = db.Column(db.String(64), nullable=False)
    action_type = db.Column(db.String(40), nullable=False)  # LOGIN, BENEFICIARY_ADD, HIGH_VALUE_TRANSFER
    entity_id = db.Column(db.Integer, nullable=True)

    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @staticmethod
    def hash_otp(code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action_type": self.action_type,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_verified": self.is_verified,
            "attempts": self.attempts,
        }
