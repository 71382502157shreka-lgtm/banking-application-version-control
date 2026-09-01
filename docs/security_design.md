# Security Design

- Passwords: hashed with Werkzeug's `generate_password_hash`
  (PBKDF2-SHA256), never stored or logged in plaintext.
- Sessions: Flask-Login with `SESSION_COOKIE_HTTPONLY`, strong session
  protection, and a configurable session lifetime.
- CSRF: enforced globally via Flask-WTF's `CSRFProtect`.
- Account lockout: after `MAX_FAILED_LOGIN_ATTEMPTS` consecutive failed
  logins, the account is locked for `LOCKOUT_DURATION_MINUTES`.
- Authorization: `@roles_required(...)` decorator checks `current_user.role`
  against an allow-list before any protected view executes.
- Input validation: centralized in `app/utils/validators.py` (email,
  username, password strength, monetary amount, IFSC format).
- Error handling: generic 404/403/500 JSON responses; stack traces are
  logged server-side only, never returned to the client.
- Audit trail: every login attempt (success or failure), password change,
  and administrative action is recorded with actor, IP address, and
  timestamp.
