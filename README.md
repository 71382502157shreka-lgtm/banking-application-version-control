# BankVCS 2.0 – Secure Intelligent Banking & Database Version Control System

[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-green.svg)](https://flask.palletsprojects.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/Tests-29%20Passed-brightgreen.svg)]()
[![Security](https://img.shields.io/badge/SHA--256%20Hash%20Chain-Verified-success.svg)]()
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

An enterprise-grade digital banking platform featuring **Git-like Entity Version Control**, **Field-Level Diffing**, **Tamper-Evident SHA-256 Audit Chaining**, **Transparent Rule-Based Risk Intelligence**, **Maker-Checker Approval Workflows**, **Active Session Management**, and **Complete Role-Based Portal Isolation**.

---

## 1. Project Title
**BankVCS 2.0 – Secure Intelligent Banking & Database Version Control System**

---

## 2. Problem Statement
Traditional banking systems face critical audit, governance, and security vulnerabilities:
- **Destructive Database Overwrites**: Standard SQL `UPDATE` or `DELETE` operations permanently destroy historical context, preventing retroactive compliance checks.
- **Audit Log Tampering Risks**: Plain-text log tables can be maliciously modified by internal bad actors without detection.
- **Unchecked Financial Risk**: High-value or rapid-fire transfers to unverified accounts often pass through without real-time threat evaluation.
- **Unauthorized Entity Restorations**: Single-user rollbacks create fraud risks without multi-party oversight.

---

## 3. Key Objectives
1. **Git-Like Database Version Control**: Maintain non-destructive, snapshot-based version histories (`v1 → v2 → v3 → RESTORE(v1) → v4`) across versioned entities.
2. **Tamper-Evident Audit Chain**: Protect audit logs using cryptographic SHA-256 hash chaining (`Audit N` incorporates `Audit N-1` hash) with live integrity verification.
3. **Transparent Risk Intelligence**: Deterministically score transaction risk (0–100) using transparent rules (transfer velocity, beneficiary cooling state, balance depletion).
4. **Maker-Checker Approvals**: Require administrative dual-control authorization for entity rollbacks and high-risk operations.
5. **Strict Role-Based Access Control**: Enforce complete portal separation between Customers, Employees, and Administrators with zero route leakage.

---

## 4. Key Innovations
- **Forward-Only Rollbacks**: Rollbacks never overwrite or delete historical versions. Restoring `v1` creates a brand-new version node `v4 (RESTORED from v1)` preserving complete chronological history.
- **SHA-256 Hash Chain Integrity**: Re-evaluates hash continuity across the entire audit database on demand, detecting any external tampering.
- **Rule-Based Risk Intelligence Engine**: Transparent scoring (0–100) classifying transfers into `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` risk tiers without black-box AI claims.
- **Dual-Theme Fintech Engine**: Seamless Light & Dark modes with persistent browser preferences and anti-flash rendering.

---

## 5. System Features
### Customer Portal
- Executive Dashboard with account balance summary cards and live spend graphs.
- Direct & Beneficiary Transfers with daily and per-transaction policy limit checks.
- Beneficiary Management with security cooling-off period validation.
- Interactive Version History & Side-by-Side Field Diff Comparator.
- Smart Account Statements with CSV export and printable receipt format.
- Active Sessions & MFA/OTP Verification controls.

### Employee Console
- Branch Operations Console monitoring customer balances and transaction throughput.
- Customer Directory & Account Inspection.
- Staff Entity Version Reviewer & Diff Inspector.
- Branch Audit Log Stream.

### Admin Security Center
- Cryptographic Audit Hash Chain Verification Widget (`AUDIT CHAIN VALID ✓` / `AUDIT INTEGRITY VIOLATION ⚠`).
- Maker-Checker Rollback Requests & Approval Queue.
- Advanced System Telemetry & Risk Analytics.
- User Management & RBAC Status Toggle.

---

## 6. Technology Stack
- **Backend Framework**: Python 3.14, Flask 3.0.3
- **Database & ORM**: Flask-SQLAlchemy 3.1.1, SQLite3 (Thread-Safe with Foreign Key enforcement)
- **Security & Hashing**: Flask-Login 0.6.3, Flask-WTF 1.2.1 (CSRFProtect), Werkzeug 3.0.3 (PBKDF2 SHA-256)
- **Frontend Architecture**: HTML5, Vanilla CSS3 (Design System with CSS Variables), Bootstrap 5.3.3, Chart.js 4.4.2
- **REST API**: Flask Blueprint `/api/v1/`
- **Testing & CI**: Pytest 8.2.2, GitHub Actions CI Pipeline

---

## 7. Database Schema & Architecture

```
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────────┐
│       User       │1     *│     Account      │1     *│     Transaction      │
├──────────────────┤───────├──────────────────┤───────├──────────────────────┤
│ id (PK)          │       │ id (PK)          │       │ id (PK)              │
│ username         │       │ user_id (FK)     │       │ account_id (FK)      │
│ password_hash    │       │ account_number   │       │ amount (Decimal)     │
│ role             │       │ balance          │       │ transaction_type     │
│ failed_logins    │       │ available_bal    │       │ status               │
│ locked_until     │       │ version_number   │       │ balance_after        │
└──────────────────┘       └──────────────────┘       └──────────────────────┘
         │                          │                            │
         ▼                          ▼                            ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────────┐
│   LoginSession   │       │  EntityVersion   │       │       AuditLog       │
├──────────────────┤       ├──────────────────┤       ├──────────────────────┤
│ id (PK)          │       │ id (PK)          │       │ id (PK)              │
│ session_token    │       │ entity_type      │       │ action, user_id      │
│ ip_address       │       │ entity_id        │       │ previous_hash (SHA)  │
│ browser / os     │       │ version_number   │       │ current_hash (SHA)   │
│ status (ACTIVE)  │       │ old_data (JSON)  │       │ ip_address           │
└──────────────────┘       │ new_data (JSON)  │       └──────────────────────┘
                           │ status, reason   │
                           └──────────────────┘
```

---

## 8. Version Control Workflow

```
[Entity Change Triggered]
         │
         ▼
1. Fetch current live state (old_data)
2. Execute state update (new_data)
3. Increment version_number (v_next = v_current + 1)
4. Save snapshot in EntityVersion table
5. Log matching event in AuditLog (with SHA-256 link)
6. Commit atomic DB transaction
```

For **Rollbacks**:
```
[Rollback Requested to v1]
         │
         ▼
1. Maker-Checker approval submitted (RollbackRequest PENDING)
2. Admin reviews reason & target snapshot
3. Admin approves → System extracts v1 new_data snapshot
4. Applies snapshot onto live entity
5. Creates NEW version node (v4 RESTORED from v1)
6. History remains 100% complete (v1 → v2 → v3 → v4 RESTORE)
```

---

## 9. SHA-256 Audit Hash Chain Workflow

Each `AuditLog` row calculates its cryptographic hash as:
$$\text{CurrentHash} = \text{SHA256}(\text{user\_id} \mid \text{role} \mid \text{action} \mid \text{entity\_type} \mid \text{entity\_id} \mid \text{old\_data} \mid \text{new\_data} \mid \text{ip} \mid \text{previous\_hash})$$

```
Audit #101 (GENESIS) ──► Hash: 4a8f...
                                 │
                                 ▼
Audit #102 ─────────────► PreviousHash: 4a8f... ──► CurrentHash: b91c...
                                                         │
                                                         ▼
Audit #103 ───────────────────────────────────────► PreviousHash: b91c... ──► CurrentHash: 7d2e...
```

Clicking **"Verify Audit Integrity"** in the Admin Security Center iterates through the entire audit chain, verifying that `previous_hash` matches the preceding record's `current_hash` and that recomputed hashes match stored hashes.

---

## 10. Risk Intelligence Engine Rules

The deterministic risk engine evaluates transfers against 4 core factors:
1. **High Amount**: Transfer $\ge ₹50,000$ (+25 pts) or $\ge ₹100,000$ (+35 pts).
2. **Balance Depletion**: Transfer depletes $\ge 80\%$ of account balance (+20 pts).
3. **Beneficiary Cooling**: Target beneficiary is in cooling period (+30 pts) or first transfer (+15 pts).
4. **Transfer Velocity**: $\ge 3$ transfers in last 15 minutes (+25 pts).

**Risk Level Tiers**:
- `0–29`: **LOW** (Auto-Approved)
- `30–59`: **MEDIUM** (OTP Verified)
- `60–79`: **HIGH** (Maker-Checker Review Required)
- `80–100`: **CRITICAL** (Blocked for Admin Review)

---

## 11. Role-Based Access Control (RBAC) Matrix

| Portal Route / Capability | Customer | Employee | Admin |
| :--- | :---: | :---: | :---: |
| Customer Portal (`/customer/dashboard`) | ✅ | ❌ | ❌ |
| Employee Portal (`/employee/dashboard`) | ❌ | ✅ | ✅ |
| Admin Portal (`/admin/dashboard`) | ❌ | ❌ | ✅ |
| Own Accounts, Deposits & Transfers | ✅ | ❌ | ❌ |
| Beneficiary Cooling & Versioning | ✅ | ❌ | ❌ |
| Staff Version Review & Customer Inspection | ❌ | ✅ | ✅ |
| Admin Security Center & Hash Verification | ❌ | ❌ | ✅ |
| Maker-Checker Rollback Approvals | ❌ | ❌ | ✅ |

---

## 12. Security Architecture
- **CSRF Defense**: `CSRFProtect` middleware validating CSRF tokens on forms and AJAX headers.
- **XSS & SQL Injection Mitigation**: Automatic HTML auto-escaping in Jinja2 templates and strict parameterized ORM queries.
- **Brute-Force Lockout Policy**: Automatically locks accounts for 15 minutes after 5 consecutive failed authentication attempts.
- **Environment Isolation**: All sensitive seeds, secret keys, and database paths are configured via environment variables.

---

## 13. REST API v1 Documentation

| Endpoint | Method | Role | Description |
| :--- | :---: | :---: | :--- |
| `/api/v1/status` | `GET` | Public | Returns system status & feature matrix |
| `/api/v1/auth/sessions` | `GET` | Authenticated | Lists user's active login sessions |
| `/api/v1/auth/sessions/<id>/revoke` | `POST` | Authenticated | Revokes a specific active session |
| `/api/v1/audit/verify` | `GET` | Staff/Admin | Executes SHA-256 audit chain integrity verification |
| `/api/v1/audit/logs` | `GET` | Staff/Admin | Fetches audit log records with filters |
| `/api/v1/versions/history` | `GET` | Authenticated | Returns entity version history nodes |
| `/api/v1/versions/diff` | `GET` | Authenticated | Returns side-by-side field diff comparison |
| `/api/v1/versions/rollback/request` | `POST` | Authenticated | Submits Maker-Checker rollback approval request |
| `/api/v1/risk/assessments` | `GET` | Staff/Admin | Lists transaction risk evaluations |

---

## 14. Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/71382502157shreka-lgtm/banking-application-version-control.git
   cd banking-application-version-control
   ```

2. **Set up virtual environment**:
   ```bash
   python -m venv .venv
   # Windows (PowerShell)
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## 15. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

---

## 16. Database Setup & Seeding
Initialize the SQLite database with realistic demo accounts:
```bash
python seed.py
```

---

## 17. Running the Application
Start the Flask development server:
```bash
python run.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your web browser.

---

## 18. Running Automated Tests
Execute the Pytest test suite:
```bash
.\.venv\Scripts\pytest -v
```
**Results**: `29 passed in 5.90s` (100% pass rate).

---

## 19. Demo Workflow

### Test Personas & Credentials

| Persona | Role | Username | Password |
| :--- | :--- | :--- | :--- |
| **Customer** | Customer | `customer` | `ChangeMe_Customer123!` |
| **Customer 2** | Customer | `sarika` | `Password123` |
| **Bank Officer** | Employee | `employee` | `ChangeMe_Employee123!` |
| **Administrator** | Admin | `admin` | `ChangeMe_Admin123!` |

*(Use the quick-fill persona buttons on the login page for instant authentication).*

---

## 20. Version Control & Audit Demo Instructions

### Demo 1: Version Control & Side-by-Side Diff
1. Log in as Customer (`customer`).
2. Navigate to **Beneficiaries** → Click **Edit** on a payee.
3. Modify the account number or bank name → Click **Save & Version**.
4. Go to **Version History** → Observe `v2` creation.
5. Click **Diff v1 ↔ v2** → Inspect the side-by-side field diff highlighting changed attributes in amber.

### Demo 2: Maker-Checker Rollback & Tamper-Evident Audit
1. As Customer, submit a Rollback Request for Beneficiary #1 to `v1`.
2. Log out and log in as Admin (`admin`).
3. Navigate to **Rollback Requests** → Click **Approve & Restore**.
4. Observe that the system creates `v3 (RESTORED from v1)` without deleting `v2`.
5. Go to **Security Center** → Click **Run Chain Audit** → Observe `AUDIT CHAIN VALID ✓`.

---

## 21. Future Enhancements
- Hardware Security Module (HSM) key signing for audit chain genesis blocks.
- Real-time WebSocket event streaming for instant security alerts.
- PostgreSQL production cluster deployment with automated database migration scripts.
