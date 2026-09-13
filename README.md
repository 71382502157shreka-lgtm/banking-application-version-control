# BankVCS 2.0 – Python-First Architecture & Database Version Control System

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-green.svg)](https://flask.palletsprojects.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/Tests-233%20Passed%20%7C%20100%25%20Pass%20Rate-brightgreen.svg)]()
[![Architecture](https://img.shields.io/badge/Architecture-Python--First%20%2F%20Backend--Heavy-purple.svg)]()
[![Audit Chain](https://img.shields.io/badge/Audit%20Chain-SHA--256%20Tamper--Evident-emerald.svg)]()
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)]()

**BankVCS 2.0** is an enterprise-grade digital banking application, database version control system, and Security Operations Center (SOC) built with a **Python-first, backend-heavy architecture**. All business logic, transaction calculations, financial validations, risk evaluations, 10-vector behavioral anomaly scores, Step-Up MFA challenges, idempotency replay protection, version control snapshotting, field-level diffing, audit hash chaining, and security operations are executed strictly in **Python**. HTML and Jinja2 templates are used for server-side rendering, with minimal client-side JavaScript for essential UI interactions (theme toggling, modal opening, Chart.js display).

---

## 1. Executive Summary & Python-First Architecture

Traditional web applications often leak business or calculation logic into frontend JavaScript. **BankVCS 2.0** enforces strict architectural boundaries:

- **100% Python Backend Logic**: Account balances, transaction processing, transfer approvals, behavioral risk scores, Step-Up MFA tokens, version creation, audit hashing, rollbacks, and role-based access permissions are verified and executed inside Python services.
- **Server-Side Rendering (SSR)**: Pages are rendered through Flask routes and Jinja2 templates.
- **Security Operations Center (SOC)**: Administrative SOC command center (`/admin/soc`) for real-time incident tickets (`INC-YYYYMM-XXXX`), account freezes, transaction holds (`BLOCKED_FOR_REVIEW`), and 360° user security timelines.
- **Pure Python SDK & Interactive CLI**: The application can run entirely in a terminal or python script without a web browser via `cli.py` and `bankvcs.py`.

---

## 2. System Roles & Access Control Model

BankVCS 2.0 enforces explicit **Role-Based Access Control (RBAC)** across four distinct system roles:

### 👤 Customer (`Role.CUSTOMER`)
- Self-service registration & secure login.
- View personal accounts, balances, and real-time transaction history.
- Perform deposit, withdrawal, intra-bank, and inter-bank transfers.
- Add, edit, and track version history (diffs) of personal beneficiaries.
- Access BankVCS AI Assistant chatbot for advisory guidance.
- View and download account statements (CSV export).
- Submit complaints / service tickets and access Document Vault.

### 💼 Provider / Employee (`Role.EMPLOYEE`)
- Banking Service Officer / Staff Provider responsible for customer support and service requests.
- Customer directory search, profile inspection, deposit/withdrawal assistance.
- Maker-Checker rollback request creation and complaint resolution.

### 🛡️ Admin (`Role.ADMIN`)

## 5. Security & AI Safety Precautions

### 🤖 BankVCS AI Banking Assistant (`app/services/ai_service.py`)
- **Zero API Key Exposure**: All external LLM requests are proxied via the Python backend. No API keys or secret tokens are ever exposed to the client browser, HTML, JavaScript, Git history, or API responses.
- **Optional Gemini Integration & Rule Fallback**:
  - Setting `GEMINI_API_KEY` in environment variables uses Google Gemini API.
  - If `GEMINI_API_KEY` is omitted or unconfigured, the system operates seamlessly using an offline **Deterministic Python Rule Engine**.
  - **Placeholder Setup**:
    ```bash
    # Set optional Gemini key in environment or .env:
    GEMINI_API_KEY=your_key_here
    ```
- **Strict Advisory Enforcement**:
  - The chatbot is **advisory only** and cannot execute banking transactions, alter balances, or modify accounts.
  - Direct execution prompts (e.g., *"transfer Rs 5000"*) return:
    > *"I can provide guidance, but I cannot directly perform banking transactions. Please use the official banking portal."*
- **Input Constraints & Safeguards**:
  - Max Message Length: **500 Characters**. Messages exceeding this limit return `400 Bad Request`.
  - Sensitive Prompt Filtering: Requests attempting to extract database credentials, system prompts, or passwords return:
    > *"I cannot disclose system configuration, security credentials, or sensitive administrative data."*

---

## 6. Key Innovations & Python Service Architecture

### ⭐ 1. Python-Based Git-Like Entity Version Control Engine (`app/services/version_service.py`)
- **Polymorphic Snapshots**: Entity state changes (`ACCOUNT`, `BENEFICIARY`, `USER_PROFILE`) are stored as JSON snapshots in an immutable `EntityVersion` ledger.
- **Maker-Checker Forward Rollback**: Restoring a past version creates a **NEW version snapshot** (`v1 → v2 → v3 → RESTORE(v1) → v4`). History is **NEVER deleted**.

### ⭐ 2. Tamper-Evident SHA-256 Audit Chain (`app/services/audit_service.py`)
- Cryptographically links audit records sequentially using SHA-256 hash chaining.
- Sequential verifier confirms `AUDIT CHAIN VALID [OK]`.

### ⭐ 3. Python Risk Intelligence Engine (`app/services/risk_engine.py` & `risk_service.py`)
- Evaluates transparent rule-based risk factors (amount thresholds, >80% balance depletion, beneficiary age <24h, transfer velocity).

### ⭐ 4. AI Banking Assistant Engine (`app/services/ai_service.py`)
- Secure Python-first chatbot engine providing advisory assistance with zero secret key leakage and intelligent fallback.

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
│   │   ├── api.py                 # REST endpoints with RBAC, IDOR & AI Assistant
│   │   └── errors.py              # HTTP 404, 401, 403, 500 error handlers
│   ├── services/                  # Core Python Business Logic
│   │   ├── ai_service.py          # AI Assistant & Rule Fallback Engine
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
│   ├── templates/                 # Jinja2 Server-Rendered Templates
│   │   └── components/            # Reusable macros (ai_chatbot.html, cards, tables)
│   └── static/                    # Styling & Images
├── bankvcs.py                     # Programmatic Python SDK / API
├── cli.py                         # Interactive Python Terminal App
├── run.py                         # Flask web server runner
├── seed.py                        # Database seed script
└── tests/                         # Pytest Suite & Automated Verifiers
    ├── test_ai_assistant.py       # 13 AI Assistant security & behavior tests
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
- **Total Tests Executed**: **55**
- **Passed**: **55**
- **Failed**: **0**
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
| **Customer** | `customer` | `ChangeMe_Customer123!` | Dashboard, transfers, CSV statements, version history, AI Assistant |
| **Customer (Sarika)** | `sarika` | `Password123` | Secondary customer with active accounts |
| **Provider / Employee** | `employee` | `ChangeMe_Employee123!` | Customer directory, version reviews, staff deposits, risk reviews, AI Assistant |
| **Admin** | `admin` | `ChangeMe_Admin123!` | Security Center, SHA-256 Audit Verifier, Rollback Board |

---

## 11. License
MIT License - BankVCS 2.0 - Secure Intelligent Banking & Database Version Control System
