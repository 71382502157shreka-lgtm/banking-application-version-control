# Banking Application Version Control System (BankVCS)

[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-green.svg)](https://flask.palletsprojects.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x-red.svg)](https://www.sqlalchemy.org/)
[![Tests](https://img.shields.io/badge/Tests-18%20Passed-brightgreen.svg)]()
[![Security](https://img.shields.io/badge/CSRF%20%26%20RBAC-Enforced-success.svg)]()

An enterprise-grade, modern digital banking platform built with **Python, Flask, SQLAlchemy, and SQLite3**, featuring **Database-Level Entity Version Control**, **Immutable Audit Trails**, and **Role-Based Access Control (RBAC)**.

---

## 🌟 Core Concepts & Academic Highlights

1. **Entity Version Control Engine**:
   - Every modification to customer profiles, bank accounts, and beneficiaries creates an immutable snapshot (`v1 → v2 → v3`) in the `EntityVersion` table.
   - Built-in **Side-by-Side Version Diff Comparator** highlighting **Modified**, **Added**, and **Removed** attributes.
2. **Zero-Trust Financial Immutability**:
   - Financial ledger entries (`Transaction`) are strictly append-only and cannot be modified or deleted.
   - Corrections use equal-and-opposite **Reversal Transactions** to maintain full financial history.
3. **Safe Non-Financial Rollback**:
   - Rollback capability for non-financial entities (`BENEFICIARY`, `USER_PROFILE`) creating forward-version audit entries (`vN+1`).
4. **Comprehensive Security & RBAC**:
   - CSRF protection via Flask-WTF (`csrf_token` input and `X-CSRFToken` fetch interceptor).
   - PBKDF2 password hashing, failed login lockout (5 attempts), and full security event monitoring.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+ (tested with Python 3.14)
- `pip` package manager

### 2. Installation
Clone the repository and install requirements:
```bash
git clone https://github.com/71382502157shreka-lgtm/banking-application-version-control.git
cd banking-application-version-control
pip install -r requirements.txt
```

### 3. Database Initialization & Seeding
Populate the database with demo users, accounts, transactions, and version records:
```bash
python seed.py
```

### 4. Run the Application
```bash
python run.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your web browser.

---

## 🔑 Demo Login Credentials

| Role | Username | Password | Features / Access |
| :--- | :--- | :--- | :--- |
| **Customer** | `sarika` | `Password123` | Personal dashboard, metallic card, deposit, withdraw, transfer, statement, beneficiaries, personal version history |
| **Employee** | `staff1` | `Password123` | Branch console, customer directory, account inspection, staff version review |
| **Admin** | `admin1` | `Password123` | System metrics, user directory & RBAC, all versions with rollback, system audit logs, system settings |

---

## 🧪 Running the Test Suite

Run the full automated pytest suite:
```bash
python -m pytest -v
```
All **18 unit and integration tests** pass cleanly with 100% success.

---

## 🏛 Project Architecture

```
banking-version-control/
├── app/
│   ├── __init__.py           # Flask App Factory & DB init
│   ├── models/               # SQLAlchemy Models (User, Account, Transaction, Version, AuditLog, Notification)
│   ├── routes/               # Modular Blueprints (auth, customer, employee, admin, api)
│   ├── services/             # Core Services (banking_service, auth_service, version_service, beneficiary_service)
│   ├── static/               # Fintech CSS Design System & Assets
│   ├── templates/            # Jinja2 Templates (base, auth, customer, employee, admin)
│   └── utils/                # Decorators, Validators & Helpers
├── config.py                 # Configuration profiles (Development, Testing, Production)
├── run.py                    # Application Entrypoint
├── seed.py                   # Demo Database Seeder
├── requirements.txt          # Dependencies
└── tests/                    # Comprehensive Test Suite (18 tests)
```

---

## 📜 License
Developed as an academic Information Systems project demonstrating Version Control and Auditability in Banking Systems.
