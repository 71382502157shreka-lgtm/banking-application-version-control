# BankVCS 2.0 – Python-First Architecture & Database Version Control System

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-green.svg)](https://flask.palletsprojects.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/Tests-46%20Passed%20%7C%2074%25%20Coverage-brightgreen.svg)]()
[![Architecture](https://img.shields.io/badge/Architecture-Python--First%20%2F%20Backend--Heavy-purple.svg)]()
[![Audit Chain](https://img.shields.io/badge/Audit%20Chain-SHA--256%20Tamper--Evident-emerald.svg)]()

**BankVCS 2.0** is an enterprise-grade digital banking application and database version control system built with a **Python-first, backend-heavy architecture**. All business logic, transaction calculations, financial validations, risk evaluations, version control snapshotting, field-level diffing, audit hash chaining, and security checks are executed strictly in **Python**. HTML and Jinja2 templates are used for server-side rendering, with minimal client-side JavaScript for essential UI interactions (theme toggling, modal opening, Chart.js display).

---

## 1. Executive Summary & Python-First Architecture

Traditional web applications often leak business or calculation logic into frontend JavaScript. **BankVCS 2.0** enforces strict architectural boundaries:

- **100% Python Backend Logic**: Account balances, transaction processing, transfer approvals, risk scores, version creation, audit hashing, rollbacks, and role-based access permissions are verified and executed inside Python services.
- **Server-Side Rendering (SSR)**: Pages are rendered through Flask routes and Jinja2 templates.
- **Minimal JavaScript**: Frontend JS handles only theme switching, chart rendering, sidebar toggling, and minor UI updates. No financial or security logic exists in JavaScript.
- **Pure Python SDK & Interactive CLI**: The application can run entirely in a terminal or python script without a web browser via `cli.py` and `bankvcs.py`.

---

## 2. Repository Language Breakdown

The language composition of the codebase, generated automatically via `python scripts/analyze_project_languages.py` (excluding virtual environments, `.git`, and cache files), is:

```text
============================================================
BANKVCS 2.0 - REPOSITORY LANGUAGE STATISTICS
============================================================
Python      :   59 files ( 52.7%) |   5,991 lines ( 40.7%)
HTML (Jinja):   52 files ( 46.4%) |   7,778 lines ( 52.9%)
CSS         :    1 file  (  0.9%) |     936 lines (  6.4%)
JavaScript  :    0 files (  0.0%) |       0 lines (  0.0%)
------------------------------------------------------------
Total       :  112 files         |  14,705 lines
============================================================
```

> **Note**: JavaScript usage is restricted to inline helpers for theme toggling and Chart.js initialization inside Jinja2 base/page templates. There are 0 standalone JS files in the project.

---

## 3. System Roles & Access Control Model

BankVCS 2.0 enforces explicit **Role-Based Access Control (RBAC)** across three distinct system roles:

### 👤 Customer (`Role.CUSTOMER`)
- **Primary Function**: Digital banking client who manages personal accounts, beneficiaries, and transactions.
- **Capabilities**:
  - Self-service registration & secure login.
  - View personal accounts, balances, and real-time transaction history.
  - Perform deposit, withdrawal, intra-bank, and inter-bank transfers.
  - Add, edit, and track version history (diffs) of personal beneficiaries.
  - View and download account statements (CSV export).
  - Submit complaints / service tickets to bank support.
  - Manage personal user profile.

### 💼 Provider / Employee (`Role.EMPLOYEE`)
- **Primary Function**: Banking Service Officer / Staff Provider responsible for customer support, service request handling, and risk/approval workflows.
- **Capabilities**:
  - Secure employee login and access to the dedicated Employee Portal (`/employee/dashboard`).
  - Search customer directory and inspect customer profile details.
  - Assist customers with deposit and withdrawal requests.
  - View assigned customer requests, pending transactions, and service tickets.
  - Create and review Maker-Checker rollback requests (cannot approve self-created requests).
  - Resolve customer complaints and update ticket statuses.
  - View provider performance and transaction service metrics.

### 🛡️ Admin (`Role.ADMIN`)
- **Primary Function**: System Administrator with full platform oversight, security auditing, and governance controls.
- **Capabilities**:
  - Full access to the Admin Dashboard (`/admin/dashboard`).
  - System User & Provider/Employee administration.
  - Verify and manage service provider profiles.
  - Inspect Security Telemetry Center and manage active user sessions.
  - Execute cryptographic **SHA-256 Audit Chain Verification** to detect any data tampering.
  - Approve or reject Maker-Checker version rollback requests on the **Rollback Approval Board**.
  - Monitor platform risk metrics, audit logs, and compliance reports.

---

## 4. Role Permission Matrix

| Feature / Resource | Customer | Provider (Employee) | Admin | Unauthenticated |
| :--- | :---: | :---: | :---: | :---: |
| **Public Landing & Login (`/`, `/login`)** | ✅ | ✅ | ✅ | ✅ |
| **User Registration (`/register`)** | ✅ (Forces Customer Role) | ❌ | ❌ | ✅ |
| **Customer Portal (`/customer/*`)** | ✅ (Own Data Only) | ❌ (403 Forbidden) | ❌ (403 Forbidden) | 302 Redirect |
| **Deposit / Withdraw (`/customer/deposit`, `/withdraw`)** | ✅ (Own Account) | ❌ (Must use staff portal) | ❌ | 302 Redirect |
| **Transfers & Beneficiaries (`/customer/transfer`)** | ✅ (Own Account) | ❌ | ❌ | 302 Redirect |
| **View Version Diffs (`/customer/version/*`)** | ✅ (Own Data) | ❌ | ❌ | 302 Redirect |
| **CSV Statement Download (`/customer/statement`)** | ✅ (Own Statements) | ❌ | ❌ | 302 Redirect |
| **Employee Portal (`/employee/*`)** | ❌ (403 Forbidden) | ✅ | ❌ (403 Forbidden) | 302 Redirect |
| **Customer Directory & Search (`/employee/customers`)** | ❌ (403 Forbidden) | ✅ | ❌ (403 Forbidden) | 302 Redirect |
| **Staff Deposit/Withdraw Helper (`/employee/deposit`)** | ❌ (403 Forbidden) | ✅ | ❌ (403 Forbidden) | 302 Redirect |
| **Create Rollback Request (`/employee/rollback/request`)**| ❌ (403 Forbidden) | ✅ | ❌ (403 Forbidden) | 302 Redirect |
| **Complaint Resolution Board (`/employee/complaints`)** | ❌ (403 Forbidden) | ✅ | ❌ (403 Forbidden) | 302 Redirect |
| **Admin Portal (`/admin/*`)** | ❌ (403 Forbidden) | ❌ (403 Forbidden) | ✅ | 302 Redirect |
| **SHA-256 Audit Verifier (`/admin/audit`)** | ❌ (403 Forbidden) | ❌ (403 Forbidden) | ✅ | 302 Redirect |
| **Security Center & Session Revoke (`/admin/security`)** | ❌ (403 Forbidden) | ❌ (403 Forbidden) | ✅ | 302 Redirect |
| **Rollback Approval Board (`/admin/rollback/board`)** | ❌ (403 Forbidden) | ❌ (403 Forbidden) | ✅ | 302 Redirect |
| **Rest APIs (`/api/*`)** | ✅ (Role Restricted) | ✅ (Role Restricted) | ✅ (Full Scope) | 401 Unauthorized |

---

## 5. Security & Authorization Guarantees

- **Strict Portal Redirection & Isolation**:
  - Upon authentication, users are redirected exclusively to their designated role portal (`/customer`, `/employee`, or `/admin`).
  - Attempting to cross boundaries (e.g., a Customer accessing `/employee/dashboard` or `/admin/users`) returns an explicit **HTTP 403 Forbidden**.
  - Admins and Employees are strictly isolated to their respective portals (`/admin/*` and `/employee/*`).
- **HTTP Status Code Protocol**:
  - **HTTP 401 Unauthorized**: Returned for unauthenticated API requests or unauthenticated page access (web routes redirect to `/login`).
  - **HTTP 403 Forbidden**: Returned whenever an authenticated user attempts to access a route or API beyond their role's permission matrix.
- **Sensitive Data Scrubbing**:
  - Passwords, secret keys, OTP tokens, session hashes, and internal tracebacks are never exposed in error responses, JSON error payloads, or logs.
- **IDOR Protection & Ownership Validation**:
  - Database queries check `account.user_id == current_user.id` or `beneficiary.user_id == current_user.id` to prevent Horizontal Privilege Escalation.

---

## 6. Key Innovations & Python Service Architecture

### ⭐ 1. Python-Based Git-Like Entity Version Control Engine (`app/services/version_service.py`)
- **Polymorphic Snapshots**: Entity state changes (`ACCOUNT`, `BENEFICIARY`, `USER_PROFILE`) are stored as JSON snapshots in an immutable `EntityVersion` ledger.
- **Maker-Checker Forward Rollback**: Restoring a past version creates a **NEW version snapshot** (`v1 → v2 → v3 → RESTORE(v1) → v4`). History is **NEVER deleted**.
- **Field-Level Diffing (`app/utils/diff.py`)**: Computes field-level differences (`added`, `removed`, `modified`, `unchanged`) in pure Python.

### ⭐ 2. Tamper-Evident SHA-256 Audit Chain (`app/services/audit_service.py`)
- Each audit log entry links to the previous entry via a cryptographic SHA-256 hash chain:
  `SHA256(previous_hash | user_id | action | entity_type | entity_id | description | timestamp | old_data | new_data)`
- **`verify_audit_integrity()`**: Traverses the database chain sequentially in Python to confirm `AUDIT CHAIN VALID [OK]`. Any database tampering immediately triggers `INTEGRITY_VIOLATION`.

### ⭐ 3. Python Risk Intelligence Engine (`app/services/risk_engine.py` & `risk_service.py`)
- Evaluates transparent rule-based risk factors (amount thresholds, >80% balance depletion, beneficiary age <24h, transfer frequency >3 in 10 mins).
- Returns a structured Python response:
  ```json
  {
    "risk_score": 85,
    "risk_level": "CRITICAL",
    "risk_factors": ["High transfer amount (Rs. 85,000.00)", "Newly added beneficiary (< 24 hours)"],
    "decision": "REVIEW_REQUIRED"
  }
  ```

### ⭐ 4. Python Security & MFA Service (`app/services/security_service.py` & `mfa_service.py`)
- Password hashing with Werkzeug PBKDF2/SHA256.
- Account lockout protection after 5 consecutive failed attempts.
- Active session tracking (`LoginSession`) with remote session invalidation.
- Time-based OTP / MFA generation and verification.

---

## 7. Project Structure

```text
banking-application-version-control-main/
├── app/
│   ├── __init__.py                # Flask application factory
│   ├── config.py                  # Environment configurations
│   ├── models/                    # SQLAlchemy ORM Models
│   │   ├── base.py                # Base model class
│   │   ├── user.py                # User & Role models (CUSTOMER, EMPLOYEE, ADMIN)
│   │   ├── account.py             # Bank Account model
│   │   ├── transaction.py         # Transaction model
│   │   ├── beneficiary.py         # Payee beneficiary model
│   │   ├── version.py             # Entity Version snapshot model
│   │   ├── audit_log.py           # Hash-chained Audit Log model
│   │   ├── notification.py        # System notifications model
│   │   ├── security_session.py    # Login sessions & security events
│   │   ├── workflow_risk.py       # Risk assessments & rollback requests
│   │   └── complaint.py           # Customer complaint tickets
│   ├── routes/                    # Server-rendered Flask Blueprints
│   │   ├── auth.py                # Authentication & session routes
│   │   ├── customer.py            # Customer portal & banking routes
│   │   ├── employee.py            # Staff portal & review routes
│   │   ├── admin.py               # Admin dashboard, audit & rollback board
│   │   ├── api.py                 # REST endpoints with RBAC & IDOR guards
│   │   └── errors.py              # HTTP 404, 401, 403, 500 error handlers
│   ├── services/                  # Core Python Business Logic
│   │   ├── auth_service.py        # Authentication & password management
│   │   ├── banking_service.py     # Deposit, withdrawal, transfer, limits
│   │   ├── beneficiary_service.py # Beneficiary CRUD & verification
│   │   ├── version_service.py     # Version snapshots & diffing
│   │   ├── audit_service.py       # SHA-256 audit hash chain verifier
│   │   ├── risk_service.py        # Transaction risk engine wrapper
│   │   ├── risk_engine.py         # Rule-based scoring engine
│   │   ├── approval_service.py    # Maker-checker approval board
│   │   ├── statement_service.py   # Statement generation & CSV export
│   │   ├── notification_service.py# Notification management
│   │   ├── security_service.py    # Telemetry & session security
│   │   └── mfa_service.py         # OTP & 2FA verification
│   ├── utils/                     # Python Utilities
│   │   ├── decorators.py          # RBAC decorators (@login_required, @roles_required)
│   │   ├── diff.py                # Field diffing utility
│   │   ├── formatting.py          # Currency & date formatters
│   │   ├── security.py            # Token generation & sanitization
│   │   └── validators.py          # Form input validation
│   ├── templates/                 # Jinja2 Server-Rendered Templates
│   │   ├── base.html              # Base layout with theme toggle
│   │   ├── components/            # Reusable UI macros (cards, tables, modals)
│   │   ├── auth/                  # Login, register, MFA pages
│   │   ├── customer/              # Customer dashboard, transfer, statement pages
│   │   ├── employee/              # Staff directory, deposits & complaint review pages
│   │   ├── admin/                 # Admin dashboard, security center, rollback board
│   │   └── errors/                # 404, 401, 403, 500 error pages
│   └── static/                    # Styling & Images
│       ├── css/style.css          # Vanilla CSS design tokens & themes
│       └── images/                # Brand logos & icons
├── bankvcs.py                     # Programmatic Python SDK / API
├── cli.py                         # Interactive Python Terminal App
├── run.py                         # Flask web server runner
├── seed.py                        # Database seed script
├── scripts/
│   ├── analyze_project_languages.py # Language stats analyzer
│   └── generate_architecture_diagram.py
└── tests/                         # Pytest Suite & Automated Verifiers
    ├── test_auth.py               # Authentication & lockout tests
    ├── test_banking_features.py   # Banking transactions & limits tests
    ├── test_bankvcs2_features.py  # Audit, risk & MFA tests
    ├── test_csrf.py               # CSRF protection tests
    ├── test_employee_portal.py    # Employee portal & maker-checker tests
    ├── test_python_architecture.py# Unit tests for core services
    ├── test_security_audit.py     # Role isolation & RBAC security tests
    ├── test_transactions.py       # Transaction engine & reversal tests
    ├── test_version_control.py    # Versioning & diffing tests
    └── verify_all_workflows.py    # Live end-to-end integration test runner
```

---

## 8. Installation & Execution

### 1. Set Up Environment & Install Dependencies
```bash
python -m venv .venv

# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Seed Database
```bash
python seed.py
```

### 3. Option A: Run Interactive Terminal Application (Pure Python CLI)
```bash
python cli.py
```

### 4. Option B: Run Flask Web Server
```bash
python run.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

---

## 9. Running Tests & Automated Verification

Run the full Pytest suite with coverage:
```bash
.\.venv\Scripts\python.exe -m pytest -v --cov=app --cov-report=term-missing
```
- **Total Tests Executed**: 42
- **Passed**: 42
- **Failed**: 0
- **Pass Rate**: 100%
- **Code Coverage**: **74% Statement Coverage** across all Python modules and services.

Run live end-to-end workflow verification:
```bash
.\.venv\Scripts\python.exe tests/verify_all_workflows.py
```

---

## 10. Demo Credentials

| Role | Username | Password | Key Features |
| :--- | :--- | :--- | :--- |
| **Customer** | `customer` | `ChangeMe_Customer123!` | Dashboard, transfers, CSV statements, version history |
| **Customer (Sarika)** | `sarika` | `Password123` | Secondary customer with active accounts |
| **Provider / Employee** | `employee` | `ChangeMe_Employee123!` | Customer directory, version reviews, staff deposits, risk reviews |
| **Admin** | `admin` | `ChangeMe_Admin123!` | Security Center, SHA-256 Audit Verifier, Rollback Board |

---

## 11. License
MIT License - BankVCS 2.0 - Secure Intelligent Banking & Database Version Control System
