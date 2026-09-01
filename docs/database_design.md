# Database Design

## Core tables
- **users** — id, username, email, password_hash, role, status,
  failed_login_attempts, locked_until, timestamps
- **accounts** — id, user_id (FK), account_number, account_type, balance,
  available_balance, status, version_number, timestamps
- **transactions** — id, account_id (FK), transaction_type, amount,
  reference_number, description, status, counterparty_account_id (FK),
  related_transaction_id (self-FK, used for reversals), balance_after,
  created_at
- **beneficiaries** — id, user_id (FK), name, account_number, bank_name,
  ifsc, status, version_number, timestamps
- **notifications** — id, user_id (FK), title, message, notification_type,
  is_read, created_at

## Version & audit tables
- **entity_versions** — id, entity_type, entity_id, version_number,
  change_type, change_summary, old_data (JSON), new_data (JSON),
  changed_by (FK → users), created_at. Unique on
  (entity_type, entity_id, version_number).
- **audit_logs** — id, user_id (FK), action, entity_type, entity_id,
  old_data (JSON), new_data (JSON), ip_address, description, created_at.

## Design rationale
A single polymorphic `entity_versions` table (rather than
`account_versions` / `beneficiary_versions` / `user_versions` as separate
tables) keeps the version-control engine entity-agnostic: one function
creates, lists, and diffs versions for any entity type. This avoids
triplicated logic while still satisfying the requirement to track
before/after state, who changed it, and when.

Transactions are deliberately **not** versioned — they are immutable by
design, and `related_transaction_id` links a reversal back to its original.
