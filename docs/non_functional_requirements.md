# Non-Functional Requirements

- **Security:** passwords hashed (never stored in plaintext), CSRF
  protection, account lockout after repeated failed logins, role-based
  authorization on every protected route.
- **Auditability:** every state-changing operation must produce a
  corresponding version and/or audit-log row in the same database
  transaction as the operation itself.
- **Consistency:** financial operations and their audit trail must commit or
  roll back together — no operation may succeed while its audit record is
  lost.
- **Usability:** responsive Bootstrap-based UI, usable on desktop, tablet,
  and mobile.
- **Maintainability:** a single, entity-agnostic version-control service
  rather than duplicated per-entity implementations.
- **Portability:** SQLite by default; `DATABASE_URL` can point to any
  SQLAlchemy-supported database for production use.
