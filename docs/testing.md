# Testing

Automated tests live in `tests/` and run with `pytest`.

- `test_auth.py` — registration creates a profile version; duplicate
  usernames are rejected; successful/failed authentication; lockout after
  repeated failed attempts.
- `test_transactions.py` — deposit increases balance; withdrawal with
  insufficient funds raises `InsufficientBalanceError`; transfer moves
  funds between two accounts; reversal restores the balance and preserves
  (rather than deletes) the original transaction.

Run with:
```
pytest
```
