"""
Application configuration.
Values are pulled from environment variables so no secrets live in source control.
"""
import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    _db_path = os.path.join(BASE_DIR, "instance", "banking.db").replace("\\", "/")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{_db_path}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session / auth
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = True

    # Account lockout policy
    MAX_FAILED_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15

    # Rate limiting & Security Hardening
    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "True").lower() in ("true", "1", "yes")
    RATELIMIT_DEFAULT_LIMIT = int(os.environ.get("RATELIMIT_DEFAULT_LIMIT", 100))
    RATELIMIT_AUTH_LIMIT = int(os.environ.get("RATELIMIT_AUTH_LIMIT", 5))
    RATELIMIT_FINANCIAL_LIMIT = int(os.environ.get("RATELIMIT_FINANCIAL_LIMIT", 10))
    RATELIMIT_ADMIN_LIMIT = int(os.environ.get("RATELIMIT_ADMIN_LIMIT", 30))
    RATELIMIT_WINDOW_SECONDS = int(os.environ.get("RATELIMIT_WINDOW_SECONDS", 60))
    TRUSTED_PROXIES_COUNT = int(os.environ.get("TRUSTED_PROXIES_COUNT", 0))

    # Demo/seed credentials — override via environment, never hardcode in real deployments
    SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe_Admin123!")
    SEED_EMPLOYEE_PASSWORD = os.environ.get("SEED_EMPLOYEE_PASSWORD", "ChangeMe_Employee123!")
    SEED_CUSTOMER_PASSWORD = os.environ.get("SEED_CUSTOMER_PASSWORD", "ChangeMe_Customer123!")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
