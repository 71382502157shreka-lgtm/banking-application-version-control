# BankVCS 2.0 – Project Presentation & Technical Architecture

## 1. Project Overview

- **Project Title**: BankVCS 2.0 – Python-First Digital Banking Platform & Entity Database Version Control System
- **Domain**: Digital Banking, FinTech Security, Database Auditability & Entity Version Control
- **Architecture**: 100% Python-First Backend Logic, Server-Side Jinja2 Rendering, Tamper-Evident SHA-256 Audit Chain, Maker-Checker Rollbacks, AI Banking Assistant

---

## 2. Problem Statement & Existing System Limitations

Traditional financial database management systems face critical audit and security vulnerabilities:
1. **Lack of Entity Versioning**: Standard database updates (`UPDATE accounts SET balance = ...`) overwrite past states, destroying past snapshot attributes.
2. **Audit Log Tampering**: Simple database audit tables can be modified directly via SQL access without leaving cryptographic footprints.
3. **Frontend Leakage of Business Logic**: Many modern web apps execute financial calculations in client-side JavaScript, introducing DOM manipulation and tampering risks.
4. **Uncontrolled Rollbacks**: Reverting data changes directly in SQL breaks transaction history and lacks dual-control authorization (Maker-Checker).

---

## 3. Proposed Solution & Objectives

**BankVCS 2.0** resolves these limitations through a Python-first architecture:
- **Git-Like Polymorphic Entity Versioning**: Stores state snapshots in an immutable `EntityVersion` ledger. Restoring a version creates a NEW forward snapshot ($v1 \rightarrow v2 \rightarrow v3 \rightarrow \text{RESTORE}(v1) \rightarrow v4$) without deleting past history.
- **Cryptographic SHA-256 Audit Chain**: Links every audit entry to its predecessor via SHA-256 hashing. Sequential verifiers detect any unauthorized database tampering immediately.
- **Maker-Checker Governance**: Staff officers create rollback requests; distinct administrators review and approve them.
- **Python AI Banking Assistant**: Embedded advisory chatbot with zero client API key exposure and a deterministic offline Python rule engine fallback.

---

## 4. System Modules & Role Capabilities

### 👤 1. Customer Module (`Role.CUSTOMER`)
- Account management, deposits, withdrawals, and intra/inter-bank transfers.
- Real-time payee beneficiary management with version history diffing.
- Statement generation and CSV export.
- AI Banking Assistant access for advisory guidance.
- Customer support complaint filing.

### 💼 2. Provider / Employee Module (`Role.EMPLOYEE`)
- Customer directory search and profile inspection.
- Assisted staff deposits and withdrawals.
- Maker-Checker rollback creation and review queue.
- Customer complaint ticket resolution.
- Operational AI Assistant support.

### 🛡️ 3. Admin Module (`Role.ADMIN`)
- Platform user and staff role administration.
- Cryptographic SHA-256 Audit Chain Integrity Verifier.
- Maker-Checker Rollback Approval Board.
- Security Telemetry Center (failed logins, session revocation, risk metrics).

---

## 5. Technology Stack & Architecture

- **Backend Logic**: Python 3.11 / 3.12 / 3.13 (100% pure Python business rules)
- **Web Framework**: Flask 3.0.3 with Blueprint modular architecture
- **ORM & Database**: SQLAlchemy 2.0 / Flask-SQLAlchemy with SQLite
- **Security & Auth**: Flask-Login, Werkzeug PBKDF2/SHA-256 hashing, Flask-WTF CSRF tokens
- **Templating & UI**: Server-side Jinja2 templates, Vanilla CSS design tokens, Bootstrap 5, Chart.js
- **Testing & Verification**: Pytest 8.2.2, pytest-cov (55 passed tests, 74% statement coverage)

---

## 6. Slide-by-Slide PPT Content (15 Slides)

### Slide 1: Title Slide
- **Title**: BankVCS 2.0 – Python-First Architecture & Database Version Control System
- **Subtitle**: Enterprise Digital Banking with Cryptographic Auditability and AI Advisory
- **Presenter**: Engineering Team

### Slide 2: Problem Statement
- Financial data overwrites cause permanent loss of historical state.
- Audit logs without cryptographic verification are vulnerable to direct database tampering.
- Client-side JavaScript financial logic introduces security vulnerabilities.

### Slide 3: Objectives of BankVCS 2.0
- Build a 100% Python backend financial engine.
- Implement Git-like polymorphic entity version control with forward-only rollbacks.
- Enforce cryptographic SHA-256 audit log hash chaining.
- Integrate a safe, key-protected AI Banking Assistant.

### Slide 4: System Architecture
- **Layer 1**: Flask Blueprints & Server-Side Jinja2 Rendering.
- **Layer 2**: Pure Python Business Services (Banking, Versioning, Risk, Audit, Security, AI).
- **Layer 3**: SQLAlchemy ORM Models & SQLite Database Store.

### Slide 5: Customer Portal Features
- Account management, deposits, withdrawals, and transfers.
- Real-time risk scoring evaluation during transfers.
- Beneficiary payee version history & field-level diffing (`added`, `modified`, `removed`).
- e-Statements with CSV exports.

### Slide 6: Provider / Employee Portal
- Customer Directory search & customer account assistance.
- Staff deposit/withdrawal helpers.
- Maker-Checker rollback request generation.
- Complaint ticket resolution board.

### Slide 7: Admin Security & Audit Center
- User and Staff role management.
- Cryptographic SHA-256 Audit Log Chain Verifier (`AUDIT CHAIN VALID [OK]`).
- Maker-Checker Rollback Approval Board.
- Active Login Session tracking & remote session revocation.

### Slide 8: Database Version Control Concept (VCS)
- Entity state changes (`ACCOUNT`, `BENEFICIARY`, `USER_PROFILE`) stored as JSON snapshots.
- Immutable ledger: past versions are never updated or deleted.
- Forward rollback pattern: Restoring $v1$ produces $v4$, preserving complete audit trails.

### Slide 9: Cryptographic SHA-256 Audit Chain
- Formula: $\text{Hash}_i = \text{SHA256}(\text{Hash}_{i-1} \mid \text{user\_id} \mid \text{action} \mid \text{entity} \mid \text{timestamp} \mid \text{data})$
- Sequential verifier iterates through database records to validate cryptographic chain integrity.
- Any manual SQL edit breaks the chain immediately (`INTEGRITY_VIOLATION`).

### Slide 10: Python Risk Intelligence Engine
- Transparent rule-based scoring engine.
- Evaluates amount thresholds, account depletion percentage (>80%), beneficiary age (<24h), and transfer velocity (>3 in 10 mins).
- Returns structured risk score, risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), and decision.

### Slide 11: AI Banking Assistant (BankVCS AI)
- Embedded floating chatbot widget for Customers and Employees.
- Zero client-side API key exposure (API key handled strictly via `os.getenv()` in Python).
- Fail-safe hybrid model: uses Google Gemini API when configured; falls back to an offline deterministic Python NLP engine when offline.

### Slide 12: AI Safety & Advisory Guards
- Chatbot is strictly **advisory** and cannot execute banking transactions.
- Action prompts return: *"I can provide guidance, but I cannot directly perform banking transactions. Please use the official banking portal."*
- Input length limit enforced at **500 characters**.
- Sensitive prompt sanitization blocks database password or secret extraction attempts.

### Slide 13: Testing & Code Quality Metrics
- Automated Pytest Suite: **55 Passed, 0 Failed** (100% pass rate).
- Statement Coverage: **74% Total Application Statement Coverage** (`pytest-cov`).
- Live Workflow Integration: `verify_all_workflows.py` passes 100%.

### Slide 14: Advantages & Innovations
- Complete backend execution eliminates client-side tampering.
- Immutable entity version control with dual-control (Maker-Checker) safety.
- Tamper-evident cryptographic auditability.
- Fail-safe AI Banking Assistant with key protection.

### Slide 15: Conclusion & Future Enhancements
- **Conclusion**: BankVCS 2.0 successfully combines digital banking, database version control, and AI advisory in a secure Python architecture.
- **Future Enhancements**: Multi-currency support, mobile app SDK integration, biometrics 2FA, and automated ML anomaly detection.
