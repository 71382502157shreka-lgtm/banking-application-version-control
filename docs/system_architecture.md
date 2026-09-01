# System Architecture

Layered architecture:

1. **Presentation** — Jinja2 templates (Bootstrap 5) + a JSON REST API
   consumed by page-level JavaScript.
2. **Application (routes)** — Flask blueprints (`auth`, `customer`,
   `employee`, `admin`, `api`). Routes are intentionally thin: parse the
   request, call a service, return a response.
3. **Service layer** — `auth_service`, `banking_service`,
   `beneficiary_service`, `version_service`, `audit_service`. All writes to
   the database go through this layer, which is where versioning and audit
   logging are enforced consistently.
4. **Data layer** — SQLAlchemy models mapped to a SQLite database.

This separation means the version-control and audit-logging guarantees hold
no matter which route or future client (mobile app, admin CLI, etc.) calls
into the service layer.
