# Data Flow

Example: Customer deposits money.

1. Browser sends `POST /api/transactions/deposit` with account_id, amount,
   description.
2. Route confirms the account belongs to the logged-in customer.
3. `banking_service.deposit()`:
   a. Reads the account's current state → `old_data`.
   b. Updates `balance` and `available_balance`.
   c. Inserts a new `Transaction` row (status COMPLETED).
   d. Reads the account's new state → `new_data`.
   e. Calls `version_service.create_version()`, which inserts one
      `entity_versions` row and one `audit_logs` row.
   f. Commits everything in a single database transaction.
4. Response returns the transaction JSON to the browser.

If any step fails, the whole transaction rolls back — the balance update,
the transaction record, the version row, and the audit log all succeed or
fail together.
