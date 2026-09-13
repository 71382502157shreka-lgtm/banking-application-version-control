# BankVCS 2.0 — Deployment Readiness & Production Handoff Checklist

This document provides a comprehensive operational guide for deploying, configuring, and maintaining **BankVCS 2.0** in production environments.

---

## 1. Prerequisites & Prerequisites Checklist

* **Python Runtime**: Python 3.11+ (Python 3.13 recommended) with virtual environment support.
* **Database**: PostgreSQL 16+ (Production) or SQLite 3.35+ (Local development/testing).
* **Container Engine**: Docker Desktop or Docker Engine v24+ & Docker Compose v2.20+ (Required for containerized deployment).
* **Reverse Proxy**: Nginx, Caddy, or Cloud Application Load Balancer with TLS 1.3 certificate termination.

---

## 2. Environment Variables & Secret Configuration

Create a `.env` file in the root directory by copying `.env.example`:

```bash
cp .env.example .env
```

### Required Configuration Key Reference

| Key | Example / Default | Required in Production | Description |
| :--- | :--- | :---: | :--- |
| `FLASK_ENV` | `production` | Yes | Application environment mode (`production` or `development`). |
| `SECRET_KEY` | `<generate-64-char-random-hex>` | Yes | Cryptographic secret key for session signing and CSRF tokens. |
| `SECURITY_PASSWORD_SALT` | `<generate-64-char-random-hex>` | Yes | Salt for password hashing and security tokens. |
| `DATABASE_URL` | `postgresql://user:pass@localhost:5432/bankvcs_db` | Yes | Connection URI for production database. |
| `RATELIMIT_ENABLED` | `true` | Yes | Enforces rate limiting on sensitive API endpoints. |
| `TRUSTED_PROXIES_COUNT` | `1` | Yes | Number of reverse proxies in front of app for real client IP extraction. |
| `SESSION_COOKIE_SECURE` | `true` | Yes | Restricts session cookies to HTTPS connections. |

> [!CAUTION]
> **Secret Key Generation**: Generate cryptographically secure keys using Python before deployment:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```
> Never commit `.env` or share private keys in code repositories.

---

## 3. Local & Production Startup Commands

### Local Development Server
For rapid local testing and development:
```powershell
.venv\Scripts\python.exe app.py
```
* Access at: `http://127.0.0.1:5000`

### Windows Production Server (Waitress)
For single-node Windows server deployments:
```powershell
.venv\Scripts\python.exe -m waitress --host=127.0.0.1 --port=5000 wsgi:app
```

### Linux / Docker Production Server (Gunicorn)
For Linux nodes and containerized environments:
```bash
gunicorn --bind 0.0.0.0:5000 --workers 4 --threads 2 wsgi:app
```

---

## 4. Database Migrations & Data Safety Procedures

### Database Backup (Mandatory Before Migration)
Always create a complete database snapshot before executing schema upgrades:

```bash
# PostgreSQL Backup
pg_dump -U bankvcs_user -d bankvcs_db -F c -b -v -f bankvcs_backup_$(date +%Y%m%d_%H%M%S).dump

# SQLite Backup (Local Dev)
cp bankvcs.db bankvcs_backup_$(date +%Y%m%d_%H%M%S).db
```

### Running Schema Migrations
Apply Alembic migrations to update database schema cleanly:

```powershell
.venv\Scripts\python.exe -m flask db upgrade
```

### Verify Migration Status
Confirm database schema revision matches the migration head:

```powershell
.venv\Scripts\python.exe -m flask db current
.venv\Scripts\python.exe -m flask db heads
```

---

## 5. Docker Compose Deployment & Container Handoff

### Container Stack Architecture
The `docker-compose.yml` stack orchestrates two isolated services:
1. `bankvcs_app`: Multi-stage Python runner running Gunicorn as non-root user `bankvcs` (UID 1000).
2. `bankvcs_db`: PostgreSQL 16 Alpine database with persistent volume mount `postgres_data`.

### Docker Startup Sequence
On a Docker-enabled host machine:

```bash
# 1. Validate configuration
docker compose config

# 2. Build images cleanly
docker compose build --no-cache

# 3. Launch stack in background
docker compose up -d

# 4. Check service health & container status
docker compose ps

# 5. Run database migration inside app container
docker compose exec app flask db upgrade

# 6. Check logs for errors
docker compose logs --tail=100
```

### Health Check Endpoint Verification
Verify health probe returns HTTP 200 OK:

```bash
curl -i http://127.0.0.1:5000/api/v1/health
```

Expected JSON Response:
```json
{
  "application": "BankVCS",
  "database": "connected",
  "status": "healthy",
  "timestamp": "2026-09-13T07:55:00.000000Z",
  "version": "2.0.0"
}
```

### Container Restart & Data Recovery Test
Test service recovery without data loss:

```bash
# Restart application service
docker compose restart app

# Restart database service
docker compose restart db

# Confirm database persistence
docker compose exec app python -c "from app import create_app, db; from app.models.user import User; app=create_app('production'); app.app_context().push(); print('Users count:', User.query.count())"
```

---

## 6. Security Checklist Before Public Launch

- [ ] `.env` created and added to `.gitignore`.
- [ ] Production `SECRET_KEY` and `SECURITY_PASSWORD_SALT` generated randomly.
- [ ] `FLASK_ENV` set to `production` and `DEBUG=False`.
- [ ] Database credentials updated from default placeholders.
- [ ] Reverse proxy configured with valid TLS 1.3 certificates (HTTPS).
- [ ] Rate limiting enabled and tested (`RATELIMIT_ENABLED=true`).
- [ ] CSRF protection enabled on all HTML web forms (`WTF_CSRF_ENABLED=True`).
- [ ] Step-Up MFA enabled for high-value operations (>= ₹50,000).
- [ ] Server-side RBAC verified across Customer, Employee, Admin, and SOC roles.
- [ ] Firewall configured to block external direct access to port 5000 (access through reverse proxy on 443 only).

---

## 7. Operational Troubleshooting

| Symptom | Probable Cause | Resolution |
| :--- | :--- | :--- |
| `503 Service Unavailable` on `/api/v1/health` | Database connection error | Check `DATABASE_URL` credentials and verify PostgreSQL container health. |
| CSRF Token Missing / Invalid | Missing `{{ csrf_token() }}` or cookie flags | Ensure web form includes `csrf_token` input and `SESSION_COOKIE_DOMAIN` matches host. |
| Database Migration Conflict | Multiple revision heads | Run `flask db heads` to identify branches and resolve in `migrations/versions/`. |
| Port 5000 Already in Use | Port conflict with another process | Change `PORT` in `.env` or set custom host binding in WSGI startup command. |
