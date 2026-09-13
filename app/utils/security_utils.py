"""
Production Security Hardening & Rate Limiting Engine for BankVCS 2.0.

Provides:
- Safe IP extraction (get_client_ip) with proxy header protection.
- Thread-safe sliding-window rate limiter (SlidingWindowLimiter).
- Pluggable storage interface (RateLimitStorage / InMemoryRateLimitStorage).
- Route decorator (@rate_limit) returning HTTP 429 with standard headers.
- Global HTTP security response headers middleware (apply_security_headers).
"""

import time
import threading
from abc import ABC, abstractmethod
from collections import deque
from functools import wraps
from typing import Dict, Tuple, Optional, Any, Callable

from flask import request, jsonify, current_app
from flask_login import current_user


def get_client_ip() -> str:
    """
    Extract client IP address safely.
    If TRUSTED_PROXIES_COUNT > 0, inspect X-Forwarded-For up to trusted count;
    otherwise use request.remote_addr to prevent IP spoofing attacks.
    """
    if not request:
        return "127.0.0.1"

    trusted_count = current_app.config.get("TRUSTED_PROXIES_COUNT", 0) if current_app else 0
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded and trusted_count > 0:
        ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        if len(ips) >= trusted_count:
            return ips[-trusted_count]
        return ips[0]

    return request.remote_addr or "127.0.0.1"


def sanitize_for_log(value: str, max_len: int = 200) -> str:
    """Prevent log injection by stripping newlines/control chars before writing to logs."""
    if value is None:
        return ""
    cleaned = "".join(ch for ch in str(value) if ch.isprintable())
    return cleaned[:max_len]


class RateLimitStorage(ABC):
    """Abstract rate limit storage interface to support memory, SQLite, or Redis."""

    @abstractmethod
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int, int]:
        """Return tuple: (is_allowed, limit, remaining, reset_timestamp)"""
        pass

    @abstractmethod
    def cleanup_expired(self, window_seconds: int = 3600):
        """Remove old expired keys."""
        pass


class InMemoryRateLimitStorage(RateLimitStorage):
    """Thread-safe sliding-window in-memory storage using deques per client key."""

    def __init__(self):
        self._buckets: Dict[str, deque] = {}
        self._lock = threading.RLock()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int, int]:
        now = time.time()
        window_start = now - window_seconds
        reset_time = int(now + window_seconds)

        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = deque()

            timestamps = self._buckets[key]
            while timestamps and timestamps[0] <= window_start:
                timestamps.popleft()

            current_count = len(timestamps)
            if current_count >= max_requests:
                remaining = 0
                reset_time = int(timestamps[0] + window_seconds) if timestamps else reset_time
                return False, max_requests, remaining, reset_time

            timestamps.append(now)
            remaining = max_requests - len(timestamps)
            return True, max_requests, remaining, reset_time

    def cleanup_expired(self, window_seconds: int = 3600):
        now = time.time()
        with self._lock:
            expired = [k for k, deq in self._buckets.items() if not deq or deq[-1] < (now - window_seconds)]
            for k in expired:
                del self._buckets[k]

    def reset_all(self):
        """Reset storage state (primarily for testing)."""
        with self._lock:
            self._buckets.clear()


class SlidingWindowLimiter:
    """Sliding-window rate limiter implementation."""

    def __init__(self, storage: Optional[RateLimitStorage] = None):
        self.storage = storage or InMemoryRateLimitStorage()

    def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int, int]:
        return self.storage.is_allowed(key, max_requests, window_seconds)


# Global rate limiter instance
limiter = SlidingWindowLimiter()


def rate_limit(limit: Optional[int] = None, window_seconds: Optional[int] = None, key_prefix: str = ""):
    """
    Flask route decorator for enforcing rate limits.
    Returns HTTP 429 with standard headers on limit breach.
    """
    def decorator(f: Callable):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if current_app and not current_app.config.get("RATELIMIT_ENABLED", True):
                return f(*args, **kwargs)

            max_reqs = limit
            if max_reqs is None:
                max_reqs = current_app.config.get("RATELIMIT_DEFAULT_LIMIT", 100)

            win_sec = window_seconds or current_app.config.get("RATELIMIT_WINDOW_SECONDS", 60)

            ip = get_client_ip()
            user_id = current_user.id if hasattr(current_user, "is_authenticated") and current_user.is_authenticated else "anon"
            prefix = key_prefix or request.endpoint or request.path
            rate_key = f"{prefix}:{ip}:{user_id}"

            allowed, limit_val, remaining, reset_ts = limiter.check_rate_limit(rate_key, max_reqs, win_sec)
            retry_after = max(1, reset_ts - int(time.time()))

            if not allowed:
                try:
                    from app.services.security_service import record_security_event
                    record_security_event(
                        event_type="RATE_LIMIT_EXCEEDED",
                        description=f"Rate limit exceeded on {request.path} ({max_reqs} req/{win_sec}s)",
                        severity="HIGH",
                        user_id=current_user.id if hasattr(current_user, "is_authenticated") and current_user.is_authenticated else None,
                        ip_address=ip,
                        user_agent=request.user_agent.string if request.user_agent else None
                    )
                except Exception:
                    pass

                response_data = {
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    "retry_after": retry_after
                }
                resp = jsonify(response_data)
                resp.status_code = 429
                resp.headers["Retry-After"] = str(retry_after)
                resp.headers["X-RateLimit-Limit"] = str(limit_val)
                resp.headers["X-RateLimit-Remaining"] = "0"
                resp.headers["X-RateLimit-Reset"] = str(reset_ts)
                return resp

            res = f(*args, **kwargs)

            # Inject rate limit headers on Flask Response object or tuple
            if hasattr(res, "headers"):
                res.headers["X-RateLimit-Limit"] = str(limit_val)
                res.headers["X-RateLimit-Remaining"] = str(remaining)
                res.headers["X-RateLimit-Reset"] = str(reset_ts)
            elif isinstance(res, tuple) and len(res) >= 1 and hasattr(res[0], "headers"):
                res[0].headers["X-RateLimit-Limit"] = str(limit_val)
                res[0].headers["X-RateLimit-Remaining"] = str(remaining)
                res[0].headers["X-RateLimit-Reset"] = str(reset_ts)

            return res
        return wrapped
    return decorator


def apply_security_headers(response):
    """
    Global Flask after_request hook adding production security headers.
    """
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
    return response
