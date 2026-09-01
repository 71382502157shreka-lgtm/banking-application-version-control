# Banking Application Version Control System

[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-green.svg)](https://flask.palletsprojects.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/Tests-18%20Passed-brightgreen.svg)]()
[![Security](https://img.shields.io/badge/CSRF%20%26%20RBAC-Enforced-success.svg)]()
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

An enterprise-grade digital banking information system developed with **Python, Flask, SQLAlchemy, and SQLite3**, featuring **Database-Level Entity Version Control**, **Zero-Trust Financial Immutability**, and an **Append-Only Signed Audit Trail**.

---

## 1. Project Overview
In modern digital banking and enterprise Information Systems, maintaining a complete, verifiable history of data modifications is essential for compliance, dispute resolution, and security forensics. Traditional banking databases only store the latest state or overwrite rows during updates, losing intermediate historical context. 

The **Banking Application Version Control System (BankVCS)** solves this fundamental challenge by embedding **Git-like version control directly into the relational database engine**. Every critical state change—whether an account balance update, beneficiary modification, or customer profile edit—automatically snapshots previous and current state into an immutable `EntityVersion` ledger.

---

## 2. Problem Statement
Conventional financial applications suffer from three critical architectural vulnerabilities:
- **Destructive Updates (`UPDATE/DELETE`)**: Direct row overwrites erase historical audit evidence, making it impossible to reconstruct what an account or beneficiary looked like at a specific point in time.
- **Ambiguous Audit Logs**: Simple log files often state *that* a change occurred (e.g. "Profile Updated"), but fail to store structured side-by-side snapshots answering *what specific field values changed*.
- **Unauthorized Financial Modifications**: Erroneous financial changes cannot be safely audited or verified without immutable double-entry bookkeeping and explicit reversal transactions.

---

## 3. Project Objectives
1. **Database-Level Versioning**: Implement a generic polymorphic versioning engine (`EntityVersion`) capable of tracking version sequences (`v1 → v2 → v3`) across multiple entities.
2. **Deep Field-Level Diffing**: Provide automated side-by-side visual diff comparisons highlighting modified, added, removed, and unchanged attributes.
3. **Financial Immutability**: Guarantee that completed financial transactions are append-only and strictly immutable, enforcing reversal-based corrections.
4. **Safe Non-Financial Rollback**: Allow authorized administrators to roll back non-financial entities (`BENEFICIARY`, `USER_PROFILE`) to prior snapshots while preserving a forward-audit record.
5. **Robust Security & RBAC**: Enforce Role-Based Access Control, CSRF token validation on all mutations, PBKDF2 password hashing, and brute-force account lockout.

---

## 4. Key Features
- **Dynamic Fintech UI**: Modern dashboard with executive metallic debit cards, responsive sidebar navigation, and time-based greetings.
- **Real-Time Spending Analytics**: Integrated Chart.js visualizations for income vs. expense cash flow and transaction type distribution.
- **Complete Transaction Ledger**: Search, filter by transaction type/status, date range filtering, and printable official receipts.
- **Double-Entry Transfers**: Atomic fund transfers with dual-account balance updates and simultaneous version creation.
- **Live Notifications Center**: Instant alerts on deposits, withdrawals, transfers, and security events.
- **Official Account Statements**: Filterable account statements with closing balance calculations, print layout, and CSV export.

---

## 5. Technology Stack
- **Backend**: Python 3.14, Flask 3.0.3
- **ORM & Database**: Flask-SQLAlchemy 3.1.1, SQLite3 (Thread-Safe with Foreign Key constraints)
- **Authentication & Security**: Flask-Login 0.6.3, Flask-WTF 1.2.1 (CSRFProtect), Werkzeug 3.0.3 (PBKDF2 SHA-256)
- **Frontend**: HTML5, Vanilla CSS3 (Custom Design System), JavaScript (ES6+), Bootstrap 5.3.3, Bootstrap Icons 1.11.3
- **Data Visualization**: Chart.js 4.4.2
- **Testing**: pytest 8.2.2

---

## 6. System Architecture

```
                                  ┌─────────────────────────────────┐
                                  │      Client Browser (UI)        │
                                  │ (HTML5 / Modern CSS / Chart.js) │
                                  └───────────────┬─────────────────┘
                                                  │ HTTP (CSRF Protected)
                                                  ▼
                                  ┌─────────────────────────────────┐
                                  │     Flask Application Layer     │
                                  │  (Blueprints & RBAC Decorators) │
                                  └───────────────┬─────────────────┘
                                                  │
                 ┌────────────────────────────────┼────────────────────────────────┐
                 ▼                                ▼                                ▼
    ┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
    │     Banking Service     │      │ Version Control Service │      │      Audit Service      │
    │  (Accounts & Transfers) │      │   (Snapshots & Diff)    │      │  (Immutable Activity)   │
    └────────────┬────────────┘      └────────────┬────────────┘      └────────────┬────────────┘
                 │                                │                                │
                 └────────────────────────────────┼────────────────────────────────┘
                                                  │ SQLAlchemy ORM
                                                  ▼
                                  ┌─────────────────────────────────┐
                                  │   SQLite3 Relational Database   │
                                  │ (users, accounts, txns, etc.)   │
                                  └─────────────────────────────────┘
```

---

## 7. User Roles & RBAC Matrix

| Permission / Capability | Customer | Employee | Admin |
| :--- | :---: | :---: | :---: |
| Open Bank Accounts & View Own Balances | ✅ | ❌ | ❌ |
| Deposit, Withdraw & Transfer Money | ✅ | ❌ | ❌ |
| Manage Personal Beneficiaries | ✅ | ❌ | ❌ |
| Inspect Personal Version History | ✅ | ❌ | ❌ |
| Inspect Customer Directory & Account Balances | ❌ | ✅ | ✅ |
| Staff Review of System Versions & Diffs | ❌ | ✅ | ✅ |
| System-Wide Audit Log Monitoring | ❌ | ✅ | ✅ |
| User Directory Management & Status Toggle | ❌ | ❌ | ✅ |
| Safe Non-Financial Version Rollback | ❌ | ❌ | ✅ |
| System Configuration & Parameter Tuning | ❌ | ❌ | ✅ |

---

## 8. Customer Features
- **Account Overview**: Real-time total balance, available funds, account status, and interactive metallic card.
- **Deposit & Withdrawal**: Dedicated pages with live balance calculation previews and overdraft validation.
- **Instant Money Transfer**: Transfer to own accounts or registered beneficiaries with confirmation modal.
- **Beneficiary Directory**: Add, edit, and deactivate payees with IFSC validation and version tracking.
- **Account Statements**: Date-filtered transaction statement generator with CSV export and printable PDF layout.
- **Security & Profile**: Self-service profile management, password update, and session activity logs.

---

## 9. Employee Features
- **Branch Operations Dashboard**: Overview of total active customers, open accounts, and transaction throughput.
- **Customer Directory**: Search and inspect customer account balances, status, and registration dates.
- **Version Reviewer**: Staff-level inspection of entity state changes with side-by-side diff viewers.
- **Compliance Audit Viewer**: Read-only access to branch-level operational logs.

---

## 10. Admin Features
- **Executive Administration Console**: System metrics, total financial volume, failed login attempts, and active version counts.
- **User Management**: Role assignment, account activation, and deactivation controls.
- **Global Version Control & Rollback**: Safe restoration of non-financial entities with forward-version tracking.
- **Full Security Audit Trail**: Real-time stream of all authentication, administrative, and data mutation events.
- **System Settings**: Configurable daily transfer limits, session timeouts, and lockout thresholds.

---

## 11. Banking Operations & Financial Logic
- **Precision Financials**: All balances and monetary amounts use Python `Decimal` to eliminate floating-point rounding errors.
- **Atomic Double-Entry Bookkeeping**: A transfer creates simultaneous debit and credit `Transaction` records inside a single atomic database transaction.
- **Overdraft Protection**: Strict validation prevents withdrawals or transfers exceeding available balance.
- **Immutable Ledger**: Transactions cannot be modified. Corrections require an equal-and-opposite `REVERSAL` transaction linked to the original transaction ID.

---

## 12. Version Control System ⭐ (Core Academic Feature)
The unique innovation of this application is **Database-Level Entity Versioning**:
1. Every state modification captures a complete JSON snapshot of the record before (`old_data`) and after (`new_data`) the change.
2. The entity's `version_number` increments monotonically (`1 → 2 → 3`).
3. Each version record stores:
   - `entity_type`: `ACCOUNT`, `BENEFICIARY`, `USER_PROFILE`
   - `entity_id`: Primary key of the modified record
   - `version_number`: Sequential version counter
   - `change_type`: `CREATE`, `UPDATE`, `DELETE`, `RESTORE`
   - `changed_by`: User ID of the actor
   - `change_summary`: Human-readable explanation of why the change occurred
   - `audit_action`: Linked compliance audit event

---

## 13. Audit Trail ⭐
The system maintains an append-only `AuditLog` table answering:
- **WHO** performed the action? (`user_id` / `username`)
- **WHAT** action occurred? (`AuditAction` enum, e.g. `TRANSFER`, `LOGIN`, `PROFILE_UPDATED`)
- **WHICH** entity was affected? (`entity_type` & `entity_id`)
- **WHEN** did it happen? (`created_at` timestamp in UTC)
- **WHERE** did it originate? (`ip_address` of the client)
- **WHY** was it changed? (`description` / memo)

---

## 14. Security Features
- **CSRF Protection**: Global `CSRFProtect` verifying tokens on HTML forms and JSON `fetch()` API calls via `X-CSRFToken`.
- **Password Security**: Strong password enforcement (min 8 chars, uppercase, lowercase, digit) hashed with Werkzeug PBKDF2 SHA-256.
- **Brute-Force Lockout**: Accounts are automatically locked for 15 minutes after 5 consecutive failed login attempts.
- **SQL Injection Defense**: Strict SQLAlchemy ORM parameterized queries.
- **XSS Sanitization**: Automatic Jinja2 template auto-escaping.

---

## 15. Database Design & Models

```
┌─────────────────┐       ┌─────────────────┐       ┌──────────────────┐
│      User       │1     *│     Account     │1     *│   Transaction    │
├─────────────────┤───────├─────────────────┤───────├──────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)          │
│ username        │       │ user_id (FK)    │       │ account_id (FK)  │
│ password_hash   │       │ account_number  │       │ amount (Decimal) │
│ role            │       │ balance         │       │ txn_type         │
│ status          │       │ available_bal   │       │ status           │
│ failed_logins   │       │ version_number  │       │ balance_after    │
└─────────────────┘       └─────────────────┘       └──────────────────┘
         │1                        │                         │
         │*                        ▼                         ▼
┌─────────────────┐       ┌────────────────────────────────────────────┐
│   Beneficiary   │       │               EntityVersion                │
├─────────────────┤       ├────────────────────────────────────────────┤
│ id (PK)         │       │ id (PK), entity_type, entity_id            │
│ user_id (FK)    │       │ version_number, old_data (JSON)            │
│ account_number  │       │ new_data (JSON), change_type, changed_by   │
│ version_number  │       └────────────────────────────────────────────┘
```

---

## 16. Project Structure

```
banking-version-control/
├── .env.example              # Safe template for environment variables
├── .gitignore                # Git exclusions (caches, DBs, secrets)
├── LICENSE                   # MIT License
├── README.md                 # Project documentation
├── config.py                 # Configuration classes (Dev, Test, Prod)
├── requirements.txt          # Python dependencies
├── run.py                    # Application startup entrypoint
├── seed.py                   # Demo database seeder script
├── app/
│   ├── __init__.py           # Flask app factory & extensions init
│   ├── models/               # SQLAlchemy Models
│   │   ├── user.py           # User authentication & RBAC model
│   │   ├── account.py        # Bank account model
│   │   ├── transaction.py    # Immutable financial transaction model
│   │   ├── beneficiary.py    # Saved payee model
│   │   ├── version.py        # Polymorphic EntityVersion model
│   │   ├── audit_log.py      # System audit log model
│   │   └── notification.py   # User notification inbox model
│   ├── routes/               # Flask Blueprints
│   │   ├── auth.py           # Login, register, logout routes
│   │   ├── customer.py       # Customer portal routes
│   │   ├── employee.py       # Employee branch console routes
│   │   ├── admin.py          # Admin console routes
│   │   └── api.py            # REST API endpoints & CSRF handlers
│   ├── services/             # Core Business Logic Layer
│   │   ├── auth_service.py   # User auth & profile management
│   │   ├── banking_service.py# Account & transaction processing
│   │   ├── beneficiary_service.py # Beneficiary CRUD & versioning
│   │   ├── version_service.py# Version snapshotting & diff engine
│   │   └── audit_service.py  # Audit logging service
│   ├── static/
│   │   └── css/style.css     # Modern fintech CSS design system
│   ├── templates/            # Jinja2 HTML Templates
│   │   ├── base.html         # Base layout with responsive sidebar
│   │   ├── index.html        # Product landing page
│   │   ├── auth/             # Login & Register views
│   │   ├── customer/         # Dashboard, accounts, transfer, etc.
│   │   ├── employee/         # Staff dashboard, customer directory, etc.
│   │   └── admin/            # Admin console, user management, settings
│   └── utils/
│       ├── decorators.py     # Role-based access decorators
│       ├── security.py       # Sanitization & security helpers
│       └── validators.py     # Amount & input validation rules
└── tests/                    # Automated Test Suite (18 tests)
    ├── conftest.py           # Pytest fixtures & test app setup
    ├── test_auth.py          # Auth & account lockout tests
    ├── test_csrf.py          # CSRF protection & token tests
    ├── test_transactions.py  # Financial operations & reversals tests
    ├── test_version_control.py # Versioning & diff comparator tests
    ├── test_banking_features.py# Account & workflow tests
    └── verify_all_workflows.py # Live HTTP server end-to-end validator
```

---

## 17. Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/71382502157shreka-lgtm/banking-application-version-control.git
   cd banking-application-version-control
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## 18. Environment Setup
Copy the example environment configuration:
```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```
*(Optionally adjust `SECRET_KEY` in `.env` for production deployments).*

---

## 19. Database Setup
Initialize the database and populate demo records:
```bash
python seed.py
```
This automatically registers models, opens sample savings/current accounts, performs initial deposits/transfers, and creates the foundational version history.

---

## 20. Running the Application
Start the local development server:
```bash
python run.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your web browser.

---

## 21. Running Tests
Execute the full automated test suite:
```bash
python -m pytest -v
```
**Test Result**: `18 passed, 0 failures` (100% test coverage for core financial and versioning operations).

---

## 22. Demo Workflow

### Test Credentials

| Role | Username | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Customer** | `sarika` | `Password123` | Personal banking dashboard, transfers, version history |
| **Employee** | `staff1` | `Password123` | Operational review, customer accounts directory |
| **Admin** | `admin1` | `Password123` | System oversight, user RBAC, non-financial rollback |

*(Tip: On the login page, you can click the quick-fill demo buttons to sign in instantly).*

---

## 23. Version Control Demonstration ⭐
To demonstrate the academic version-control feature during a presentation or viva:

1. **Log in as Customer (`sarika`)**:
   - Go to **Beneficiaries** → Click **Edit** on `Ramesh Kumar`.
   - Change the Account Number from `987654321001` to `987654321099` → Click **Save & Version**.
2. **Inspect Version History**:
   - Navigate to **Version History**.
   - Notice that `BENEFICIARY #1` now displays `v2`.
   - Click **Diff v1 ↔ v2**.
3. **Inspect the Side-by-Side Diff Modal**:
   - The UI highlights the `account_number` field in <span style="color:#f59e0b; font-weight:bold;">MODIFIED (AMBER)</span>, displaying the old strikethrough value vs. the new value.
4. **Demonstrate Safe Rollback (Admin)**:
   - Log in as `admin1` → Go to **Version Control**.
   - Click **Restore** on `v1` of the Beneficiary → Enter a restoration reason.
   - The system restores the original account number and writes a forward `v3 (RESTORE)` version snapshot and audit log.

---

## 24. Future Enhancements
- **Multi-Factor Authentication (MFA/TOTP)**: Integration with authenticator apps (Google Authenticator / Authy).
- **Scheduled & Recurring Payments**: Automated cron execution of recurring standing instructions with version snapshots.
- **Biometric WebAuthn**: Passwordless FIDO2 biometric authentication for mobile devices.
- **Distributed Event Streaming**: Integration with Apache Kafka for asynchronous event-driven audit streaming.

---

## 25. Authors / Project Team
- **Author / Lead Developer**: [71382502157shreka-lgtm](https://github.com/71382502157shreka-lgtm)
- **Academic Project**: Information Systems Banking Application Version Control System
- **Repository**: [banking-application-version-control](https://github.com/71382502157shreka-lgtm/banking-application-version-control.git)
