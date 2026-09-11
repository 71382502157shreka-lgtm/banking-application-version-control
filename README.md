# BankVCS 2.0 – Secure Intelligent Banking & Database Version Control System

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-green.svg)](https://flask.palletsprojects.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/Tests-23%20Passed-brightgreen.svg)]()
[![Audit Chain](https://img.shields.io/badge/Audit%20Chain-SHA--256%20Tamper--Evident-emerald.svg)]()
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

**BankVCS 2.0** is an enterprise-grade digital banking and database version control system built with **Python, Flask, SQLAlchemy, SQLite/PostgreSQL, and Chart.js**. It features **Git-Like Database Entity Version Control**, **SHA-256 Tamper-Evident Audit Hash Chaining**, **Rule-Based Risk Intelligence Engine**, **Maker-Checker Admin Approval Workflows**, **MFA / OTP 2FA Security**, and **Active Session Telemetry**.

---

## 1. Executive Summary & Problem Statement
Traditional financial database architectures suffer from critical vulnerabilities:
- **Destructive Overwrites**: Direct row updates erase past state, destroying audit context.
- **Vulnerable Audit Trails**: Plain text or basic DB logs can be retroactively edited without detection.
- **Unverified Rollbacks**: Direct DB rollbacks erase history or leave no record of who authorized the revert.

**BankVCS 2.0** solves these challenges by treating the relational database as a version-controlled entity store. Non-financial entity state changes (`ACCOUNT`, `BENEFICIARY`, `USER_PROFILE`) are snapshot into an immutable polymorphic `EntityVersion` ledger. Financial transactions remain append-only and strictly immutable (corrections require `REVERSAL` transactions).

---

## 2. Key Innovations in BankVCS 2.0

### ⭐ 1. Git-Like Entity Version Control Engine
- **Timeline & History**: Sequence tracking (`v1 → v2 → v3 → RESTORE(v1) → v4`).
- **Maker-Checker Rollback**: Restoring a past version creates a **NEW version snapshot** containing the restored state. History is **NEVER deleted**.
- **Field-Level Diffing**: Side-by-side comparison showing `added`, `removed`, `modified`, and `unchanged` fields.

### ⭐ 2. Tamper-Evident SHA-256 Audit Chain
- Every audit entry includes `previous_hash` and `current_hash`, computed via SHA-256 over:
  `SHA256(previous_hash | user_id | action | entity_type | entity_id | description | timestamp | old_data | new_data)`
- **Audit Integrity Verifier**: Admin single-click verification traverses the chain sequentially to confirm `AUDIT CHAIN VALID [OK]`. Any manual DB tampering immediately results in `AUDIT INTEGRITY VIOLATION [ALERT]`.

### ⭐ 3. Intelligent Transaction Risk Engine
- Calculates a transparent risk score (0–100) prior to transfer execution.
- Evaluates amount thresholds, account balance depletion percentage (>80%), beneficiary age (<24h), and rapid transfer frequency (>3 in 10 mins).
- Transfers with risk score ≥ 60 are placed in `BLOCKED_FOR_REVIEW` for Maker-Checker review.

### ⭐ 4. MFA / OTP Security & Session Telemetry
- 2FA / OTP verification for sensitive operations (login, payee addition, high-value transfers).
- Active session tracking (`LoginSession`) showing IP, browser, OS, device type, and login timestamps.
- One-click **"Logout other sessions"** capability.

### ⭐ 5. Smart Statements & Analytics
- Account statements with date range, transaction type, credit/debit filters, opening/closing balance calculation, and **CSV Export**.
- Interactive Chart.js monthly cash flow & spending breakdown graphs.

---

## 3. System Architecture & Component Design

```
                               ┌─────────────────────────────────┐
                               │   Client Browser & Dashboard    │
                               │ (Vanilla CSS / Tailwind / JS)   │
                               └───────────────┬─────────────────┘
                                               │ REST API v1 (CSRF / Cookie Auth)
                                               ▼
                               ┌─────────────────────────────────┐
                               │     Flask Application Layer     │
                               │  (Blueprints & RBAC Decorators) │
                               └───────────────┬─────────────────┘
                                               │
             ┌─────────────────────────────────┼─────────────────────────────────┐
             ▼                                 ▼                                 ▼
┌─────────────────────────┐       ┌─────────────────────────┐       ┌─────────────────────────┐
│     Banking Service     │       │ Version Control Engine  │       │ Audit & Security Engine │
│(Transfers/Limits/Risk)  │       │(Snapshots/Diff/Rollback)│       │ (SHA-256 Chain/Sessions)│
└────────────┬────────────┘       └────────────┬────────────┘       └────────────┬────────────┘
             │                                 │                                 │
             └─────────────────────────────────┼─────────────────────────────────┘
                                               │ SQLAlchemy ORM & Migrations
                                               ▼
                               ┌─────────────────────────────────┐
                               │  Relational DB (SQLite / Postgres)│
                               │ (users, accounts, versions, etc)│
                               └─────────────────────────────────┘
```

---

## 4. Role-Based Access Control (RBAC) Matrix

| Capability / Feature | Customer | Employee | Admin |
| :--- | :---: | :---: | :---: |
| Open Bank Accounts & View Own Balances | ✅ | ❌ | ❌ |
| Deposit, Withdraw & Initiate Transfers | ✅ | ❌ | ❌ |
| Add Beneficiary (OTP & Cooling Check) | ✅ | ❌ | ❌ |
| Export CSV Statements & Transaction Receipts | ✅ | ❌ | ❌ |
| Manage Active Login Sessions | ✅ | ❌ | ❌ |
| Review Customer Account Balances | ❌ | ✅ | ✅ |
| Review Flagged Risk Transfers (`BLOCKED_FOR_REVIEW`) | ❌ | ✅ | ✅ |
| Submit Rollback Request (Maker) | ✅ | ✅ | ✅ |
| Approve/Reject Rollback Requests (Checker) | ❌ | ❌ | ✅ |
| Run SHA-256 Audit Integrity Verification | ❌ | ❌ | ✅ |
| Admin Security Center & User Management | ❌ | ❌ | ✅ |

---

## 5. Technology Stack
- **Backend Framework**: Python 3.11 / 3.12 / 3.13, Flask 3.0.3, Werkzeug 3.0.3
- **Database & ORM**: Flask-SQLAlchemy 3.1.1, Flask-Migrate 4.0.7 (Alembic), SQLite3 / PostgreSQL
- **Security & Auth**: Flask-Login 0.6.3, Flask-WTF 1.2.1 (CSRFProtect), hashlib SHA-256
- **Frontend & UI**: HTML5, Vanilla CSS3 + Tailwind CDN, Bootstrap 5.3.3, Chart.js 4.4.2
- **Testing & DevOps**: Pytest 8.2.2, GitHub Actions CI (`.github/workflows/tests.yml`)

---

## 6. Installation & Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/71382502157shreka-lgtm/banking-application-version-control.git
   cd banking-application-version-control
   ```

2. **Set up Virtual Environment**:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .\.venv\Scripts\Activate.ps1
   # Linux / macOS:
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize Database & Demo Data**:
   ```bash
   python seed.py
   ```

5. **Run Development Server**:
   ```bash
   python run.py
   ```
   Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your web browser.

---

## 7. Running Tests & CI

Execute the complete automated test suite:
```bash
python -m pytest -v
```
**Test Results**: `23 passed, 0 failures` (100% test pass rate across authentication, RBAC, banking, versioning, audit hash chaining, risk engine, Maker-Checker rollbacks, MFA OTP, and sessions).

---

## 8. Demo Workflows for Viva & Presentation

### Demo Credentials

| Role | Username | Password | Key Demonstration Features |
| :--- | :--- | :--- | :--- |
| **Customer** | `customer` | `ChangeMe_Customer123!` | Personal dashboard, transfers, CSV statements, version history |
| **Customer 2** | `sarika` | `Password123` | Secondary customer with active transactions & payees |
| **Employee** | `employee` | `ChangeMe_Employee123!` | Staff overview, customer account directory, risk reviews |
| **Admin** | `admin` | `ChangeMe_Admin123!` | Security Center, SHA-256 Audit Verifier, Maker-Checker Rollback Board |

---

### Demo Workflow 1: Version Control & Maker-Checker Rollback
1. **Log in as `customer`**:
   - Go to **Beneficiaries** → Edit payee `Jane Smith`.
   - Update Account Number to `123456789099` → Click **Save**.
2. **Submit Rollback Request**:
   - Navigate to **Version History** → View `v1` vs `v2` side-by-side diff.
   - Click **Request Rollback to v1** → Provide reason *"Incorrect account number entered"*.
3. **Approve Rollback as `admin`**:
   - Log in as `admin` → Go to **Rollback Board** (`/admin/rollback-requests`).
   - Click **Approve** on the pending request.
   - Observe that the beneficiary account number is restored to `v1` state **and a NEW version (`v3`) is created**. Historical versions `v1` and `v2` remain completely intact!

---

### Demo Workflow 2: Risk Engine & Tamper-Evident Audit Verification
1. **Trigger High-Risk Transaction**:
   - Log in as `customer` → Initiate a high-value transfer of ₹85,000 to `sarika`.
   - The Risk Engine calculates a **Risk Score of 85/100 (CRITICAL)**.
   - The transaction state becomes `BLOCKED_FOR_REVIEW` and funds are held.
2. **Review & Approve as `admin`**:
   - Log in as `admin` → Go to **Risk Center** (`/admin/risk-center`).
   - Click **Approve & Release** to complete the transfer.
3. **Verify Audit Chain Integrity**:
   - Go to **Security Center** (`/admin/security-center`).
   - Click **Verify Audit Chain Integrity**.
   - Receives **`AUDIT CHAIN VALID [OK]`** confirming all SHA-256 hashes match.

---

## 9. License & Credits
- **License**: MIT License
- **Project**: BankVCS 2.0 – Secure Intelligent Banking & Database Version Control System
