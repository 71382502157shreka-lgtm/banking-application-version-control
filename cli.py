"""
Interactive Python CLI for Banking Application with Version Control.
Allows full interactive management of Banking, Version Control, Risk Engine,
Maker-Checker Rollbacks, and Audit Log Verification entirely in Python.
"""

import sys
import os
from decimal import Decimal
from getpass import getpass

from app import create_app, db
from app.models.user import User, Role
from app.models.account import Account
from app.models.version import EntityType
from app.services import (
    auth_service,
    banking_service,
    beneficiary_service,
    version_service,
    approval_service,
    risk_engine,
    audit_service,
    session_service,
    mfa_service,
)

app = create_app(os.environ.get("FLASK_ENV", "development"))


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title.upper()}")
    print("=" * 60)


def print_diff(diff_data: dict):
    print("\n" + "-" * 50)
    print(f" VERSION COMPARISON: v{diff_data.get('v1')} -> v{diff_data.get('v2')}")
    print(f" Entity: {diff_data.get('entity_type')} #{diff_data.get('entity_id')}")
    print("-" * 50)
    fields = diff_data.get("fields", {})
    if not fields:
        print("  No changes detected.")
        return

    for field, info in fields.items():
        status = info.get("status")
        old_val = info.get("old")
        new_val = info.get("new")
        if status == "modified":
            print(f" [*] {field}: {old_val} -> {new_val}")
        elif status == "added":
            print(f" [+] {field}: {new_val}")
        elif status == "removed":
            print(f" [-] {field}: {old_val}")
        else:
            print(f" [ ] {field}: {old_val}")
    print("-" * 50)


def customer_menu(user: User):
    while True:
        print_header(f"Customer Menu - Welcome, {user.full_name or user.username}")
        print("1. View Accounts & Balance")
        print("2. Deposit Funds")
        print("3. Withdraw Funds")
        print("4. Transfer Funds (Versioned)")
        print("5. View Beneficiaries")
        print("6. Add Beneficiary (Versioned)")
        print("7. View Entity Version History")
        print("8. Compare Entity Versions (Diff)")
        print("9. Request Version Rollback (Maker-Checker)")
        print("10. Logout")

        choice = input("\nSelect an option (1-10): ").strip()
        if choice == "1":
            accounts = Account.query.filter_by(user_id=user.id).all()
            print("\nYOUR ACCOUNTS:")
            for acc in accounts:
                print(f"  - Account #{acc.account_number} [{acc.account_type}] Balance: Rs. {acc.balance:,.2f} (Status: {acc.status})")
        elif choice == "2":
            accounts = Account.query.filter_by(user_id=user.id).all()
            if not accounts:
                print("No accounts found.")
                continue
            acc = accounts[0]
            amt_str = input(f"Enter deposit amount for Account #{acc.account_number}: Rs. ").strip()
            try:
                amt = Decimal(amt_str)
                txn, err = banking_service.deposit(acc.id, amt, "CLI Deposit")
                if err:
                    print(f"Error: {err}")
                else:
                    print(f"Deposit Successful! Ref: {txn.reference_number}, New Balance: Rs. {acc.balance:,.2f}")
            except Exception as e:
                print(f"Invalid amount or operation failed: {e}")
        elif choice == "3":
            accounts = Account.query.filter_by(user_id=user.id).all()
            if not accounts:
                print("No accounts found.")
                continue
            acc = accounts[0]
            amt_str = input(f"Enter withdrawal amount for Account #{acc.account_number}: Rs. ").strip()
            try:
                amt = Decimal(amt_str)
                txn, err = banking_service.withdraw(acc.id, amt, "CLI Withdrawal")
                if err:
                    print(f"Error: {err}")
                else:
                    print(f"Withdrawal Successful! Ref: {txn.reference_number}, New Balance: Rs. {acc.balance:,.2f}")
            except Exception as e:
                print(f"Invalid amount or operation failed: {e}")
        elif choice == "4":
            accounts = Account.query.filter_by(user_id=user.id).all()
            if not accounts:
                print("No accounts found.")
                continue
            from_acc = accounts[0]
            to_acc_num = input("Enter destination account number: ").strip()
            to_acc = Account.query.filter_by(account_number=to_acc_num).first()
            if not to_acc:
                print("Destination account not found.")
                continue
            amt_str = input("Enter transfer amount: Rs. ").strip()
            try:
                amt = Decimal(amt_str)
                res, err = banking_service.transfer(from_acc.id, to_acc.id, amt, "CLI Transfer")
                if err:
                    print(f"Transfer Error: {err}")
                elif isinstance(res, dict) and res.get("status") == "REVIEW_REQUIRED":
                    print(f"Transfer Held by Risk Engine! Assessment ID #{res.get('assessment_id')}. Awaiting Admin Review.")
                else:
                    print(f"Transfer Successful! Debit Ref: {res[0].reference_number}, Credit Ref: {res[1].reference_number}")
            except Exception as e:
                print(f"Transfer failed: {e}")
        elif choice == "5":
            benes, _ = beneficiary_service.list_beneficiaries(user.id)
            print("\nYOUR BENEFICIARIES:")
            for b in benes:
                print(f"  - ID #{b.id} | Name: {b.name} | Acc: {b.account_number} | Bank: {b.bank_name} (v{b.version_number})")
        elif choice == "6":
            name = input("Beneficiary Name: ").strip()
            acc_num = input("Account Number: ").strip()
            bank = input("Bank Name: ").strip()
            ifsc = input("IFSC Code: ").strip()
            b, err = beneficiary_service.create_beneficiary(user.id, name, acc_num, bank, ifsc)
            if err:
                print(f"Error: {err}")
            else:
                print(f"Beneficiary created successfully! ID #{b.id} (Version 1)")
        elif choice == "7":
            entity_type = input("Entity Type (BENEFICIARY / ACCOUNT / USER_PROFILE): ").strip().upper()
            entity_id = input("Entity ID: ").strip()
            try:
                versions = version_service.get_history(entity_type, int(entity_id))
                print(f"\nVERSION HISTORY FOR {entity_type} #{entity_id}:")
                for v in versions:
                    print(f"  - v{v.version_number} [{v.change_type}] | Summary: {v.change_summary} | Changed By: User #{v.changed_by or 'System'}")
            except Exception as e:
                print(f"Failed to fetch history: {e}")
        elif choice == "8":
            entity_type = input("Entity Type (BENEFICIARY / ACCOUNT / USER_PROFILE): ").strip().upper()
            entity_id = input("Entity ID: ").strip()
            v1 = input("Version 1 (older): ").strip()
            v2 = input("Version 2 (newer): ").strip()
            try:
                diff = version_service.compare_versions(entity_type, int(entity_id), int(v1), int(v2))
                print_diff(diff)
            except Exception as e:
                print(f"Diff error: {e}")
        elif choice == "9":
            entity_type = input("Entity Type to Rollback (BENEFICIARY / USER_PROFILE): ").strip().upper()
            entity_id = input("Entity ID: ").strip()
            target_v = input("Target Version Number to Restore: ").strip()
            reason = input("Reason for Rollback Request: ").strip()
            try:
                req, err = approval_service.request_rollback(user.id, entity_type, int(entity_id), int(target_v), reason)
                if err:
                    print(f"Rollback Request Error: {err}")
                else:
                    print(f"Rollback Request #{req.id} submitted for Maker-Checker review!")
            except Exception as e:
                print(f"Error submitting request: {e}")
        elif choice == "10":
            print("Logged out.")
            break


def admin_menu(user: User):
    while True:
        print_header(f"Admin / Control Center - User: {user.username}")
        print("1. View Maker-Checker Rollback Requests")
        print("2. Approve Rollback Request")
        print("3. Reject Rollback Request")
        print("4. View Risk Assessment Queue")
        print("5. Review & Release/Block Risk Transaction")
        print("6. Verify Audit Log Hash Chain Integrity")
        print("7. View Recent Audit Logs")
        print("8. Logout")

        choice = input("\nSelect an option (1-8): ").strip()
        if choice == "1":
            reqs = approval_service.get_pending_requests()
            print("\nPENDING MAKER-CHECKER ROLLBACK REQUESTS:")
            for r in reqs:
                print(f"  - Request #{r.id} | Entity: {r.entity_type} #{r.entity_id} -> Target v{r.target_v} | Requested By: User #{r.requested_by} | Reason: {r.reason}")
        elif choice == "2":
            req_id = input("Enter Rollback Request ID to APPROVE: ").strip()
            try:
                success, msg = approval_service.approve_rollback(int(req_id), user.id, "Approved via CLI")
                print(f"Result: {msg}")
            except Exception as e:
                print(f"Approval error: {e}")
        elif choice == "3":
            req_id = input("Enter Rollback Request ID to REJECT: ").strip()
            reason = input("Enter Rejection Reason: ").strip()
            try:
                success, msg = approval_service.reject_rollback(int(req_id), user.id, reason)
                print(f"Result: {msg}")
            except Exception as e:
                print(f"Rejection error: {e}")
        elif choice == "4":
            pending = risk_engine.get_pending_risk_reviews()
            print("\nPENDING RISK REVIEWS:")
            for t in pending:
                print(f"  - Assessment #{t.get('id')} | Ref: {t.get('reference_number')} | Amount: Rs. {t.get('amount'):,.2f} | Factors: {t.get('risk_factors')}")
        elif choice == "5":
            asm_id = input("Enter Risk Assessment ID: ").strip()
            decision = input("Approve & Release? (y/n): ").strip().lower() == "y"
            try:
                res, err = risk_engine.review_risk_assessment(int(asm_id), user.id, decision, "Reviewed via CLI")
                if err:
                    print(f"Error: {err}")
                else:
                    print(f"Transaction {'Approved' if decision else 'Rejected'} successfully!")
            except Exception as e:
                print(f"Risk review failed: {e}")
        elif choice == "6":
            res = audit_service.verify_audit_integrity()
            print(f"\nAUDIT LOG HASH CHAIN INTEGRITY: {'VALID' if res.get('valid') else 'TAMPERED'}")
            print(f"Details: {res.get('message')}")
        elif choice == "7":
            logs = audit_service.get_audit_logs(limit=10)
            print("\nRECENT AUDIT LOGS:")
            for l in logs:
                print(f"  - [{l.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {l.action} | User #{l.user_id or 'System'} | Hash: {l.current_hash[:12]}...")
        elif choice == "8":
            print("Logged out.")
            break


def main():
    with app.app_context():
        print_header("Banking Application with Database Version Control (Python CLI)")
        while True:
            print("\n1. Login")
            print("2. Register New User")
            print("3. Exit")

            choice = input("\nSelect option (1-3): ").strip()
            if choice == "1":
                username = input("Username: ").strip()
                password = getpass("Password: ").strip()
                user, err = auth_service.authenticate(username, password)
                if err:
                    print(f"Login failed: {err}")
                else:
                    print(f"Login successful! Role: {user.role.upper()}")
                    if user.role == Role.ADMIN or user.role == Role.EMPLOYEE:
                        admin_menu(user)
                    else:
                        customer_menu(user)
            elif choice == "2":
                username = input("New Username: ").strip()
                email = input("Email Address: ").strip()
                full_name = input("Full Name: ").strip()
                phone = input("Phone Number: ").strip()
                password = getpass("Password: ").strip()
                user, err = auth_service.register_user(username, email, password, full_name, phone)
                if err:
                    print(f"Registration failed: {err}")
                else:
                    print(f"Registration successful! Welcome {user.username}.")
            elif choice == "3":
                print("Exiting Python Application. Goodbye!")
                sys.exit(0)


if __name__ == "__main__":
    main()
