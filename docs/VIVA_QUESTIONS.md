# BankVCS 2.0 – Viva Voice Questions & Detailed Answers

This document contains **45 comprehensive Viva Voice questions and answers** prepared specifically for technical evaluations, external examiners, and project defenses.

---

## Part 1: Python & Flask Web Framework Architecture

### Q1: Why is BankVCS 2.0 described as having a "Python-First Architecture"?
**Answer**: In BankVCS 2.0, 100% of business logic—including financial calculations, balance updates, transfer limits, risk scoring, version creation, audit hash chaining, and security checks—is implemented strictly in Python backend services. HTML and Jinja2 templates are used only for server-side rendering (SSR), ensuring no business or financial calculations leak into client-side JavaScript.

### Q2: What is Flask and why was it chosen over Django for this project?
**Answer**: Flask is a lightweight WSGI micro web framework for Python. It was chosen because of its minimalist core, explicit control over HTTP requests, modular Blueprint architecture, and seamless integration with SQLAlchemy ORM, which allowed us to build custom version control and audit engines cleanly.

### Q3: What are Flask Blueprints and how are they used in BankVCS 2.0?
**Answer**: Blueprints are Flask's mechanism for organizing application routes into modular components. BankVCS 2.0 uses Blueprints to isolate feature areas into dedicated modules:
- `auth_bp`: Authentication and session routes (`/login`, `/register`, `/logout`).
- `customer_bp`: Customer portal routes (`/customer/*`).
- `employee_bp`: Employee staff routes (`/employee/*`).
- `admin_bp`: Administrator dashboard and audit board (`/admin/*`).
- `api_bp`: RESTful JSON API endpoints (`/api/*`).

### Q4: How is application configuration managed in Flask?
**Answer**: Configuration settings are stored in `app/config.py` using Python classes (`Config`, `DevelopmentConfig`, `TestingConfig`, `ProductionConfig`). Environment variables (such as `SECRET_KEY` and `GEMINI_API_KEY`) are read using Python's `os.getenv()`.

### Q5: How does Flask handle custom error pages?
**Answer**: Custom error handlers are defined in `app/routes/errors.py` using `@app.errorhandler(code)`. It catches HTTP 404 (Not Found), 401 (Unauthorized), 403 (Forbidden), and 500 (Internal Server Error) exceptions, rendering styled Jinja2 templates without exposing internal technical tracebacks.

---

## Part 2: Database, ORM & Data Access

### Q6: What database engine is used in BankVCS 2.0?
**Answer**: BankVCS 2.0 uses SQLite via SQLAlchemy ORM. SQLite provides an ACID-compliant embedded database engine ideal for single-file deployment, rapid testing, and deterministic audit chain verification.

### Q7: What is SQLAlchemy and what are its advantages?
**Answer**: SQLAlchemy is an Object-Relational Mapper (ORM) for Python. It maps Python classes to database tables and object instances to database rows, allowing developers to interact with the database using object-oriented Python code instead of raw SQL queries.

### Q8: What SQLAlchemy models exist in BankVCS 2.0?
**Answer**:
1. `User`: User accounts, passwords, and roles (`CUSTOMER`, `EMPLOYEE`, `ADMIN`).
2. `Account`: Bank account details, account types, balances, and account status.
3. `Transaction`: Deposit, withdrawal, and transfer records with reference numbers.
4. `Beneficiary`: Payee details for fund transfers.
5. `EntityVersion`: JSON snapshot records for entity version history.
6. `AuditLog`: Cryptographic SHA-256 tamper-evident audit ledger entries.
7. `LoginSession`: Active login sessions and security telemetry.
8. `WorkflowRisk` / `RiskAssessment`: Risk engine evaluation scores.
9. `RollbackRequest`: Maker-Checker rollback approval requests.
10. `Complaint`: Customer support tickets.

### Q9: How are database transactions handled to ensure ACID compliance?
**Answer**: Fund transfers require atomic operations. In `app/services/banking_service.py`, transfers are wrapped in SQLAlchemy database sessions. Both debit and credit balance updates occur within a single database transaction block (`db.session.commit()`). If an error occurs (such as insufficient balance or risk block), `db.session.rollback()` reverts all changes completely.

### Q10: How does SQLAlchemy handle relationship mapping?
**Answer**: Relationships are defined using `db.relationship()` and `db.ForeignKey()`. For example, `Account.user_id` is a foreign key referencing `User.id`, enabling `user.accounts` to return all accounts belonging to a specific customer.

---

## Part 3: Authentication, Security & Session Management

### Q11: How is user authentication implemented?
**Answer**: User authentication is managed using `Flask-Login` and `app/services/auth_service.py`. Passwords are encrypted using Werkzeug's `generate_password_hash()` (PBKDF2 with SHA-256 and salt). When logging in, `check_password_hash()` verifies credentials without storing or logging plaintext passwords.

### Q12: How are user sessions secured against session hijacking?
**Answer**:
- Sessions are encrypted using Flask's `SECRET_KEY`.
- Cookie flags are set to `HttpOnly` and `SameSite=Lax`.
- Each login generates a tracked `LoginSession` record in the database with IP address and User-Agent telemetry.
- Admins or users can remotely revoke sessions, immediately invalidating the session token.

### Q13: What is Account Lockout protection?
**Answer**: If a user enters an incorrect password 5 consecutive times (`MAX_FAILED_LOGIN_ATTEMPTS = 5`), `auth_service.py` sets `locked_until` to 15 minutes in the future, blocking further login attempts to prevent brute-force attacks.

### Q14: What is CSRF and how is BankVCS 2.0 protected against it?
**Answer**: Cross-Site Request Forgery (CSRF) is an attack where a malicious site tricks a logged-in user's browser into submitting unauthorized requests. BankVCS 2.0 uses `Flask-WTF` to generate unique CSRF tokens (`{{ csrf_token() }}`) for every HTML form and POST request. Requests lacking a valid CSRF token are rejected (`HTTP 400`).

### Q15: How does Time-Based OTP / MFA work in the project?
**Answer**: `app/services/mfa_service.py` generates a 6-digit numeric OTP with an expiration time of 5 minutes. To complete sensitive actions, the user inputs the OTP, which is verified against the stored hash and expiration timestamp.

---

## Part 4: Role-Based Access Control (RBAC) & Portal Isolation

### Q16: What three roles exist in BankVCS 2.0?
**Answer**:
1. `CUSTOMER`: End-user digital banking client.
2. `EMPLOYEE`: Banking Service Officer / Staff Provider handling support and reviews.
3. `ADMIN`: System Administrator managing security, audit verification, and rollbacks.

### Q17: How is Role-Based Access Control enforced in Flask?
**Answer**: Using custom Python decorators in `app/utils/decorators.py`:
- `@login_required`: Ensures user is authenticated.
- `@roles_required(Role.CUSTOMER)`: Restricts route execution to users possessing specified database roles.

### Q18: What happens when a Customer tries to access `/employee/dashboard` or `/admin/users`?
**Answer**: The `@roles_required` decorator intercepts the request, logs an `ACCESS_DENIED` event in the audit trail, and returns an explicit **HTTP 403 Forbidden** error.

### Q19: What status code is returned for unauthenticated users?
**Answer**: Web page routes redirect unauthenticated users to `/login` (`HTTP 302`), while REST API endpoints return an explicit **HTTP 401 Unauthorized** JSON payload.

### Q20: What is IDOR and how is it prevented?
**Answer**: Insecure Direct Object Reference (IDOR) occurs when a user accesses another user's private data by altering a URL parameter (e.g. `/api/accounts/5`). BankVCS 2.0 prevents IDOR via `_get_owned_account_or_403()` helper functions that verify `account.user_id == current_user.id` before returning records.

---

## Part 5: Database Version Control System (VCS) & Field Diffing

### Q21: What is the core concept of Entity Database Version Control in BankVCS 2.0?
**Answer**: Whenever a financial entity (`ACCOUNT`, `BENEFICIARY`, `USER_PROFILE`) is created or modified, `app/services/version_service.py` serializes its complete state into a JSON snapshot stored in the `EntityVersion` model along with a version number ($v1, v2, v3$).

### Q22: Why is the EntityVersion ledger immutable?
**Answer**: Past version snapshot records are **NEVER updated or deleted**. This maintains an immutable historical audit trail of how data evolved over time.

### Q23: How does the Maker-Checker Forward Rollback pattern work?
**Answer**: Instead of executing SQL `DELETE` or `UPDATE` statements that destroy history, restoring a previous version (e.g. restoring $v1$ when current version is $v3$) computes the diff and writes a **NEW forward snapshot version $v4$** containing $v1$'s attributes.

### Q24: Can financial transactions (deposits/transfers) be rolled back via version control?
**Answer**: **No**. Transactions are immutable financial ledger entries. Reversing a transaction creates an explicit counter-transaction (`REVERSAL`), preserving original ledger entries in accordance with banking compliance rules.

### Q25: How is field-level diffing calculated?
**Answer**: `app/utils/diff.py` compares two JSON snapshots key-by-key in Python and returns structured diff categories: `added`, `removed`, `modified`, and `unchanged`.

---

## Part 6: Cryptographic SHA-256 Audit Chain

### Q26: What is a SHA-256 Audit Hash Chain?
**Answer**: It is a cryptographic ledger technique where each audit log entry contains a `previous_hash` field holding the SHA-256 hash of the preceding entry, forming an unbroken cryptographic chain similar to a blockchain block headers chain.

### Q27: How is the SHA-256 hash calculated for an audit entry?
**Answer**:
$$\text{Hash}_i = \text{SHA256}(\text{previous\_hash} \mid \text{user\_id} \mid \text{action} \mid \text{entity\_type} \mid \text{entity\_id} \mid \text{timestamp} \mid \text{payload})$$

### Q28: How does the Audit Integrity Verifier detect tampering?
**Answer**: `app/services/audit_service.py` fetches all audit records sequentially from ID 1 to $N$. In Python, it recomputes the expected SHA-256 hash for each entry and compares it against `stored_hash` and `previous_hash`. If any row was edited directly in SQL, the hashes mismatch, returning `INTEGRITY_VIOLATION`.

### Q29: Who can trigger the Audit Chain Verifier?
**Answer**: Only users with `Role.ADMIN` access can trigger verification from the Admin Audit Dashboard (`/admin/audit`).

---

## Part 7: Maker-Checker Approval Workflow

### Q30: What is the Maker-Checker principle?
**Answer**: Maker-Checker is a dual-control governance policy requiring two distinct authorized persons to complete a critical operation: one person creates/requests the change (Maker), and a second person reviews and approves it (Checker).

### Q31: How is Maker-Checker implemented in BankVCS 2.0?
**Answer**: An Employee (`Role.EMPLOYEE`) creates a `RollbackRequest` in `app/services/approval_service.py`. The request enters a `PENDING` state. An Admin (`Role.ADMIN`) or a non-creator staff member reviews and approves/rejects the request. Self-approval is blocked in Python backend code.

---

## Part 8: AI Banking Assistant & Safety Engineering

### Q32: What is the AI Banking Assistant in BankVCS 2.0?
**Answer**: It is an embedded virtual banking assistant (**"BankVCS AI Assistant"**) accessible via a floating chatbot widget on Customer and Employee dashboards.

### Q33: How is API key security enforced for the AI Assistant?
**Answer**: `GEMINI_API_KEY` is accessed **strictly on the Python backend** via `os.getenv()`. No API keys, secret tokens, or provider credentials are ever included in client-side HTML, JavaScript, Git code, or REST API responses.

### Q34: What happens if `GEMINI_API_KEY` is missing or the external API is offline?
**Answer**: The system gracefully falls back to an offline **Deterministic Python Rule Engine** (`_rule_based_fallback()`), which performs keyword matching against a local FAQ knowledge base without throwing errors.

### Q35: How is the chatbot prevented from executing accidental financial transactions?
**Answer**: The chatbot is strictly **advisory**. Prompts requesting direct actions (e.g. *"transfer Rs 5000"*) are intercepted by action guards in `ai_service.py`, returning the explicit advisory statement:
> *"I can provide guidance, but I cannot directly perform banking transactions. Please use the official banking portal."*

### Q36: What is the message length limit for the chatbot?
**Answer**: Input messages are restricted to a maximum of **500 characters**. Exceeding this limit returns a `400 Bad Request` payload with a clear user alert.

### Q37: How are sensitive prompt extraction attempts handled?
**Answer**: Prompts attempting to extract system prompts, database connection strings, or passwords trigger sensitive prompt filters, returning: *"I cannot disclose system configuration, security credentials, or sensitive administrative data."*

---

## Part 9: Testing, Quality Assurance & Git Version Control

### Q38: What testing framework is used in this project?
**Answer**: `Pytest 8.2.2` with `pytest-cov` plugin for statement code coverage analysis.

### Q39: What are the current test execution metrics?
**Answer**:
- **Total Tests Executed**: **55**
- **Passed**: **55**
- **Failed**: **0**
- **Statement Coverage**: **74% Total Application Coverage**

### Q40: What workflow verification tool exists in the project?
**Answer**: `tests/verify_all_workflows.py`, an automated Python integration runner that tests database seeding, customer workflows, employee operations, admin security dashboards, and audit verifications end-to-end.

### Q41: How do unit tests mock external API calls?
**Answer**: Using `unittest.mock.patch`, tests mock `urllib.request.urlopen` and `os.getenv` to test Gemini API failures, HTTP 500 errors, and offline rule fallback behavior without making real network or paid API requests.

### Q42: What Git version control commands are used to inspect project state?
**Answer**:
- `git status -sb`: Shows current branch and file status in short format.
- `git log -n 5 --oneline`: Displays recent commit history.
- `git fetch origin`: Synchronizes remote branch tracking without merging.

### Q43: What files are excluded via `.gitignore`?
**Answer**: Virtual environments (`.venv/`), SQLite database files (`instance/*.db`), Python bytecode (`__pycache__/`), environment secrets (`.env`), test coverage caches (`.pytest_cache/`, `.coverage`), and IDE settings (`.vscode/`).

### Q44: What is commit `c05a628`?
**Answer**: Commit `c05a628` (`feat: harden and improve AI Banking Assistant`) represents the final verified commit pushed to the GitHub repository, containing all AI safety guards, unit tests, and documentation updates.

### Q45: What makes BankVCS 2.0 production-ready for demonstration?
**Answer**: Python-first backend logic, 55 passing unit/integration tests, 74% statement coverage, zero exposed credentials, full RBAC portal isolation, cryptographic audit verifications, and complete documentation.
