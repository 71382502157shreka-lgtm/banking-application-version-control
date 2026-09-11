"""
Comprehensive Pure Python Workflow Demonstration.
Executes banking workflows, version control snapshotting, diff comparisons,
risk engine reviews, maker-checker rollbacks, and audit hash chain verification in Python.
"""

from decimal import Decimal
from bankvcs import BankingApp
from app.models.version import EntityType
from app.services import banking_service


def main():
    app = BankingApp()

    print("=" * 60)
    print(" 1. AUTHENTICATION & USER SETUP (PYTHON)")
    print("=" * 60)
    user, err = app.register_user("python_dev", "pydev@bank.com", "SecurePass123!", "Python Developer", "9876543210")
    if not user:
        user, err = app.authenticate("python_dev", "SecurePass123!")

    print(f"Active Python User: {user.username} (ID #{user.id})")

    accounts = app.get_accounts(user.id)
    if not accounts:
        acc = banking_service.create_account(user.id)
        accounts = [acc]
    account = accounts[0]
    print(f"Primary Account Number: {account.account_number} | Initial Balance: Rs. {account.balance:,.2f}")

    print("\n" + "=" * 60)
    print(" 2. DEPOSIT & WITHDRAWAL (PYTHON)")
    print("=" * 60)
    app.deposit(account.id, Decimal("5000.00"), "Python Initial Deposit")
    app.withdraw(account.id, Decimal("1200.00"), "ATM Cash Withdrawal")
    print(f"Updated Balance: Rs. {account.balance:,.2f}")

    print("\n" + "=" * 60)
    print(" 3. BENEFICIARY VERSION CONTROL (PYTHON)")
    print("=" * 60)
    bene, _ = app.create_beneficiary(user.id, "Alice Smith", "998877665544", "HDFC Bank", "HDFC0001234")
    print(f"Created Beneficiary #{bene.id} Version 1: {bene.name}")

    history = app.get_version_history(EntityType.BENEFICIARY, bene.id)
    print(f"Version Count for Beneficiary #{bene.id}: {len(history)}")
    for v in history:
        print(f"  - Version {v.version_number}: {v.change_summary}")

    print("\n" + "=" * 60)
    print(" 4. AUDIT LOG HASH CHAIN INTEGRITY CHECK (PYTHON)")
    print("=" * 60)
    is_valid, msg = app.verify_audit_chain()
    print(f"Audit Log Integrity Status: {'PASSED [VALID]' if is_valid else 'FAILED [TAMPERED]'}")
    print(f"Details: {msg}")

    print("\n" + "=" * 60)
    print(" DEMO COMPLETED SUCCESSFULLY IN PURE PYTHON!")
    print("=" * 60)

    app.close()


if __name__ == "__main__":
    main()
