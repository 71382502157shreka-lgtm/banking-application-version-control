# Objectives

1. Implement standard customer/employee/admin banking operations.
2. Version every account, beneficiary, and profile change at the database
   level (not via source-control tooling).
3. Provide a version-comparison UI that shows field-level differences
   between any two versions of a record.
4. Log every security-relevant action (login, logout, deposit, withdrawal,
   transfer, beneficiary change, admin action) to an immutable audit trail.
5. Guarantee financial transactions are append-only: corrections happen via
   reversal transactions, never edits or deletes.
6. Enforce role-based access control across customer, employee, and admin
   roles.
7. Demonstrate the full workflow end-to-end for a project viva.
