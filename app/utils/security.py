from flask import request


def get_client_ip() -> str:
    """Respect X-Forwarded-For when behind a proxy, else fall back to remote_addr."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def sanitize_for_log(value: str, max_len: int = 200) -> str:
    """Prevent log injection by stripping newlines/control chars before writing to logs."""
    if value is None:
        return ""
    cleaned = "".join(ch for ch in str(value) if ch.isprintable())
    return cleaned[:max_len]
