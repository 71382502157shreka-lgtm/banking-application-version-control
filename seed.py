"""
Populate a fresh database with demo data for the viva/presentation:
one admin, one employee, one customer with two accounts, a beneficiary,
a few transactions, and the version/audit trail that naturally results
from running everything through the real service layer (not raw INSERTs).

Run with:  python seed.py
"""
import os
from app import create_app, db
from app.models.user import User, Role
from app.services import auth_service, banking_service, beneficiary_service


def seed_database(app_instance=None):
    from flask import current_app
    app = app_instance or current_app
    admin_pass = app.config.get("SEED_ADMIN_PASSWORD", "Admin123!")
    emp_pass = app.config.get("SEED_EMPLOYEE_PASSWORD", "Employee123!")
    cust_pass = app.config.get("SEED_CUSTOMER_PASSWORD", "Customer123!")

    admin = auth_service.register_user(
        "admin", "admin@bank.local", admin_pass,
        full_name="System Administrator", role=Role.ADMIN,
    )
    admin1 = auth_service.register_user(
        "admin1", "admin1@bank.local", "Password123",
        full_name="Chief Admin", role=Role.ADMIN,
    )
    employee = auth_service.register_user(
        "employee", "employee@bank.local", emp_pass,
        full_name="Bank Employee", role=Role.EMPLOYEE,
    )
    staff1 = auth_service.register_user(
        "staff1", "staff1@bank.local", "Password123",
        full_name="Branch Officer Sarah", role=Role.EMPLOYEE,
    )
    customer = auth_service.register_user(
        "customer", "customer@bank.local", cust_pass,
        full_name="John Doe", phone="9876543210", role=Role.CUSTOMER,
    )
    sarika = auth_service.register_user(
        "sarika", "sarika@bank.local", "Password123",
        full_name="Sarika M", phone="9876543211", role=Role.CUSTOMER,
    )

    savings = banking_service.create_account(customer.id, "SAVINGS")
    current = banking_service.create_account(customer.id, "CURRENT")

    sarika_savings = banking_service.create_account(sarika.id, "SAVINGS")
    sarika_current = banking_service.create_account(sarika.id, "CURRENT")

    # Deposits
    banking_service.deposit(savings, "50000.00", "Initial deposit", customer.id)
    banking_service.deposit(current, "20000.00", "Initial deposit", customer.id)
    banking_service.withdraw(savings, "5000.00", "ATM withdrawal", customer.id)

    banking_service.deposit(sarika_savings, "75000.00", "Salary Credit", sarika.id)
    banking_service.deposit(sarika_current, "30000.00", "Business Earnings", sarika.id)
    banking_service.withdraw(sarika_savings, "4500.00", "Utility Bill & Groceries", sarika.id)
    banking_service.transfer(sarika_savings, sarika_current, "10000.00", "Inter-Account Transfer", sarika.id)

    beneficiary = beneficiary_service.add_beneficiary(customer.id, {
        "name": "Jane Smith",
        "account_number": "123456789012",
        "bank_name": "Sample National Bank",
        "ifsc": "SAMP0001234",
    })
    beneficiary_service.update_beneficiary(
        beneficiary, {"account_number": "123456789099"}, customer.id
    )

    sarika_bene = beneficiary_service.add_beneficiary(sarika.id, {
        "name": "Ramesh Kumar",
        "account_number": "987654321001",
        "bank_name": "HDFC Bank",
        "ifsc": "HDFC0001234",
    })

    return admin, employee, customer, sarika


def run():
    app = create_app(os.environ.get("FLASK_ENV", "development"))
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_database(app)
        print("Seed complete.")


if __name__ == "__main__":
    run()
