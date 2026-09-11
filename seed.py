r"""
Populate a fresh database with demo data for viva / project demonstration:
- Roles: Admin, Employee, Customer
- Accounts & Transactions
- Entity Versions (Account, Beneficiary, UserProfile)
- SHA-256 Tamper-Evident Audit Hash Chain
- Active Login Sessions
- Pending Rollback Request for Maker-Checker demo
- Flagged High-Risk Transaction (BLOCKED_FOR_REVIEW) for Risk Engine demo

Run with:  .venv\Scripts\python.exe seed.py
"""
import os
from app import create_app, db
from app.models.user import User, Role
from app.models.version import EntityType
from app.services import auth_service, banking_service, beneficiary_service, approval_service, audit_service


def run():
    app = create_app(os.environ.get("FLASK_ENV", "development"))
    with app.app_context():
        db.drop_all()
        db.create_all()

        admin = auth_service.register_user(
            "admin", "admin@bank.local", app.config["SEED_ADMIN_PASSWORD"],
            full_name="System Administrator", role=Role.ADMIN,
        )
        admin1 = auth_service.register_user(
            "admin1", "admin1@bank.local", "Password123",
            full_name="Chief Admin", role=Role.ADMIN,
        )
        employee = auth_service.register_user(
            "employee", "employee@bank.local", app.config["SEED_EMPLOYEE_PASSWORD"],
            full_name="Bank Employee", role=Role.EMPLOYEE,
        )
        staff1 = auth_service.register_user(
            "staff1", "staff1@bank.local", "Password123",
            full_name="Senior Operations Officer", role=Role.EMPLOYEE,
        )
        customer = auth_service.register_user(
            "customer", "customer@bank.local", app.config["SEED_CUSTOMER_PASSWORD"],
            full_name="John Doe", phone="9876543210", role=Role.CUSTOMER,
        )
        sarika = auth_service.register_user(
            "sarika", "sarika@bank.local", "Password123",
            full_name="Sarika M", phone="9876543211", role=Role.CUSTOMER,
        )

        # Accounts
        savings = banking_service.create_account(customer.id, "SAVINGS")
        current = banking_service.create_account(customer.id, "CURRENT")

        sarika_savings = banking_service.create_account(sarika.id, "SAVINGS")
        sarika_current = banking_service.create_account(sarika.id, "CURRENT")

        # Deposits & Transfers
        banking_service.deposit(savings, "150000.00", "Initial deposit", customer.id)
        banking_service.deposit(current, "40000.00", "Business Working Capital", customer.id)
        banking_service.withdraw(savings, "5000.00", "ATM Cash Withdrawal", customer.id)

        banking_service.deposit(sarika_savings, "85000.00", "Salary Credit", sarika.id)
        banking_service.deposit(sarika_current, "30000.00", "Consulting Fee", sarika.id)
        banking_service.transfer(sarika_savings, sarika_current, "10000.00", "Inter-Account Transfer", sarika.id)

        # Beneficiaries & Version Updates
        beneficiary = beneficiary_service.add_beneficiary(customer.id, {
            "name": "Jane Smith",
            "account_number": "123456789012",
            "bank_name": "State Bank of India",
            "ifsc": "SBIN0001234",
        })
        beneficiary_service.update_beneficiary(
            beneficiary, {"account_number": "123456789099", "bank_name": "HDFC Bank", "ifsc": "HDFC0001234"}, customer.id
        )

        sarika_bene = beneficiary_service.add_beneficiary(sarika.id, {
            "name": "Ramesh Kumar",
            "account_number": "987654321001",
            "bank_name": "ICICI Bank",
            "ifsc": "ICIC0001234",
        })

        # Demo High-Risk Transaction (Triggers Risk Score >= 60 -> BLOCKED_FOR_REVIEW)
        banking_service.transfer(savings, sarika_savings, "85000.00", "High Value Overseas Transfer", customer.id)

        # Demo Rollback Request for Maker-Checker
        approval_service.request_rollback(
            user_id=customer.id,
            entity_type=EntityType.BENEFICIARY,
            entity_id=beneficiary.id,
            target_version=1,
            reason="Incorrect bank details entered during update"
        )

        # Seed Demo Complaints
        from app.models.complaint import Complaint, ComplaintStatus, ComplaintPriority
        c1 = Complaint(
            ticket_number="TICK-1001",
            customer_id=sarika.id,
            assigned_employee_id=staff1.id,
            subject="Transaction Processing Time",
            description="Inter-account transfer took 5 minutes to show updated available balance.",
            category="TRANSACTION",
            priority=ComplaintPriority.MEDIUM,
            status=ComplaintStatus.OPEN,
        )
        c2 = Complaint(
            ticket_number="TICK-1002",
            customer_id=customer.id,
            assigned_employee_id=staff1.id,
            subject="Beneficiary Modification Verification",
            description="Updated beneficiary details for Jane Smith. Requesting manual staff verification.",
            category="BENEFICIARY",
            priority=ComplaintPriority.HIGH,
            status=ComplaintStatus.RESOLVED,
            resolution="Beneficiary details verified and version history confirmed intact."
        )
        db.session.add_all([c1, c2])
        db.session.commit()

        # Verify Audit Chain Integrity
        report = audit_service.verify_audit_integrity()

        print("==================================================")
        print(" BankVCS 2.0 Seed Initialization Complete [OK]")
        print("==================================================")
        print(f" Admin Credentials    : admin    / {app.config['SEED_ADMIN_PASSWORD']}")
        print(f" Employee Credentials : employee / {app.config['SEED_EMPLOYEE_PASSWORD']}")
        print(f" Employee (staff1)    : staff1   / Password123")
        print(f" Customer Credentials : customer / {app.config['SEED_CUSTOMER_PASSWORD']}")
        print(f" Customer (Sarika)    : sarika   / Password123")
        print("--------------------------------------------------")
        print(f" Primary Account Number: {savings.account_number}")
        print(f" Audit Chain Status   : {report['status']}")
        print(f" Total Audit Records  : {report['total_records']}")
        print("==================================================")


if __name__ == "__main__":
    run()
