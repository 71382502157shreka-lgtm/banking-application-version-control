from datetime import datetime
from app import db


class SystemSetting(db.Model):
    """
    Key-value store for application settings (e.g., dynamic authorization keys).
    Fault-tolerant: handles missing table gracefully if deployed on existing DB.
    """
    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get(cls, key: str, default: str = None) -> str:
        try:
            setting = cls.query.filter_by(key=key).first()
            return setting.value if setting and setting.value else default
        except Exception:
            db.session.rollback()
            try:
                db.create_all()
                setting = cls.query.filter_by(key=key).first()
                return setting.value if setting and setting.value else default
            except Exception:
                db.session.rollback()
                return default

    @classmethod
    def set(cls, key: str, value: str):
        try:
            db.create_all()
            setting = cls.query.filter_by(key=key).first()
            if setting:
                setting.value = value
            else:
                setting = cls(key=key, value=value)
                db.session.add(setting)
            db.session.commit()
            return setting
        except Exception:
            db.session.rollback()
            return None
