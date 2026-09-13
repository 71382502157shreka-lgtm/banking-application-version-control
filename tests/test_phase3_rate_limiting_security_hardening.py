"""
Phase 3 - Feature 1 Automated Test Suite:
Production Security Hardening & API Rate Limiting Engine.

Tests sliding-window rate limiting, HTTP security headers, 429 Too Many Requests responses,
IP isolation, spoofing protection, and security audit event logging.
"""

import time
import pytest
from flask import json
from app import create_app, db
from app.models.user import User, Role
from app.models.security_session import SecurityEvent
from app.services import auth_service
from app.utils.security_utils import (
    limiter,
    get_client_ip,
    InMemoryRateLimitStorage,
    SlidingWindowLimiter,
)


@pytest.fixture
def rate_limit_app():
    """App instance with RATELIMIT_ENABLED = True for explicit testing."""
    app = create_app("testing")
    app.config["RATELIMIT_ENABLED"] = True
    app.config["RATELIMIT_DEFAULT_LIMIT"] = 5
    app.config["RATELIMIT_WINDOW_SECONDS"] = 60
    app.config["WTF_CSRF_ENABLED"] = False
    limiter.storage.reset_all()
    yield app
    limiter.storage.reset_all()


@pytest.fixture
def rate_limit_client(rate_limit_app):
    return rate_limit_app.test_client()


def test_security_headers_middleware(rate_limit_client):
    """Test global response middleware adds standard production security headers."""
    res = rate_limit_client.get("/")
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Strict-Transport-Security" in res.headers
    assert "Content-Security-Policy" in res.headers
    assert "Referrer-Policy" in res.headers


def test_rate_limit_within_limit(rate_limit_client):
    """Test normal requests under rate limit return standard success status and rate limit headers."""
    for i in range(3):
        res = rate_limit_client.get("/")
        assert res.status_code in (200, 302)
        assert "X-RateLimit-Limit" in res.headers
        assert "X-RateLimit-Remaining" in res.headers


def test_rate_limit_exceeded_returns_429(rate_limit_client):
    """Test requests exceeding the rate limit return HTTP 429 Too Many Requests."""
    # Default limit is 5 in fixture
    for _ in range(5):
        res = rate_limit_client.get("/")
        assert res.status_code in (200, 302)

    # 6th request breaches limit
    exceeded_res = rate_limit_client.get("/")
    assert exceeded_res.status_code == 429
    assert "Retry-After" in exceeded_res.headers
    assert exceeded_res.headers.get("X-RateLimit-Remaining") == "0"

    data = exceeded_res.get_json()
    assert data["error"] == "Too Many Requests"
    assert "Rate limit exceeded" in data["message"]


def test_rate_limit_window_reset():
    """Test sliding window rate limiter resets after window duration expires."""
    storage = InMemoryRateLimitStorage()
    lim = SlidingWindowLimiter(storage)
    key = "test_reset_key"

    # Allow 2 requests in 1 second window
    allowed1, _, rem1, _ = lim.check_rate_limit(key, max_requests=2, window_seconds=1)
    allowed2, _, rem2, _ = lim.check_rate_limit(key, max_requests=2, window_seconds=1)
    allowed3, _, _, _ = lim.check_rate_limit(key, max_requests=2, window_seconds=1)

    assert allowed1 is True
    assert allowed2 is True
    assert allowed3 is False

    # Wait for window to expire
    time.sleep(1.1)

    allowed4, _, rem4, _ = lim.check_rate_limit(key, max_requests=2, window_seconds=1)
    assert allowed4 is True
    assert rem4 == 1


def test_rate_limit_ip_isolation(rate_limit_client):
    """Test requests from different IP addresses are tracked in isolated buckets."""
    # Exhaust rate limit for IP 10.0.0.1
    for _ in range(5):
        rate_limit_client.get("/", environ_base={"REMOTE_ADDR": "10.0.0.1"})

    ip1_res = rate_limit_client.get("/", environ_base={"REMOTE_ADDR": "10.0.0.1"})
    assert ip1_res.status_code == 429

    # IP 10.0.0.2 should still be allowed
    ip2_res = rate_limit_client.get("/", environ_base={"REMOTE_ADDR": "10.0.0.2"})
    assert ip2_res.status_code in (200, 302)


def test_spoofed_x_forwarded_for_handling(rate_limit_app):
    """Test IP extraction ignores spoofed X-Forwarded-For when TRUSTED_PROXIES_COUNT is 0."""
    with rate_limit_app.test_request_context("/", headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}, environ_base={"REMOTE_ADDR": "192.168.1.100"}):
        ip = get_client_ip()
        assert ip == "192.168.1.100"


def test_trusted_proxy_ip_extraction(rate_limit_app):
    """Test IP extraction correctly extracts client IP from X-Forwarded-For when TRUSTED_PROXIES_COUNT > 0."""
    rate_limit_app.config["TRUSTED_PROXIES_COUNT"] = 1
    with rate_limit_app.test_request_context("/", headers={"X-Forwarded-For": "203.0.113.195, 70.41.3.18"}, environ_base={"REMOTE_ADDR": "127.0.0.1"}):
        ip = get_client_ip()
        assert ip == "70.41.3.18"


def test_auth_route_strict_rate_limiting(rate_limit_client):
    """Test strict rate limits on login route return 429 after threshold."""
    for _ in range(5):
        rate_limit_client.post("/login", data={"username": "invalid", "password": "wrong"})

    blocked = rate_limit_client.post("/login", data={"username": "invalid", "password": "wrong"})
    assert blocked.status_code == 429
    assert blocked.get_json()["error"] == "Too Many Requests"


def test_security_event_recorded_on_rate_limit_exceeded(rate_limit_app, rate_limit_client):
    """Test a HIGH severity security event is recorded when rate limit is exceeded."""
    with rate_limit_app.app_context():
        for _ in range(5):
            rate_limit_client.post("/login", data={"username": "baduser", "password": "badpassword"})

        rate_limit_client.post("/login", data={"username": "baduser", "password": "badpassword"})

        events = SecurityEvent.query.filter_by(event_type="RATE_LIMIT_EXCEEDED").all()
        assert len(events) >= 1
        assert events[0].severity == "HIGH"


def test_in_memory_storage_cleanup():
    """Test InMemoryRateLimitStorage cleanup_expired removes old keys."""
    storage = InMemoryRateLimitStorage()
    storage.is_allowed("old_key", max_requests=10, window_seconds=1)
    assert "old_key" in storage._buckets

    time.sleep(1.1)
    storage.cleanup_expired(window_seconds=1)
    assert "old_key" not in storage._buckets
