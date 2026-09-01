import pytest
from decimal import Decimal

from app.services import banking_service


def test_deposit_increases_balance(app, db, customer):
    account = banking_service.create_account(customer.id)
    txn = banking_service.deposit(account, "100.00", "Test deposit", customer.id)
    assert account.balance == Decimal("100.00")
    assert txn.status == "COMPLETED"


def test_withdraw_insufficient_balance_raises(app, db, customer):
    account = banking_service.create_account(customer.id)
    with pytest.raises(banking_service.InsufficientBalanceError):
        banking_service.withdraw(account, "50.00", "Overdraw attempt", customer.id)


def test_transfer_moves_funds_between_accounts(app, db, customer):
    source = banking_service.create_account(customer.id)
    dest = banking_service.create_account(customer.id)
    banking_service.deposit(source, "200.00", "Fund source", customer.id)

    banking_service.transfer(source, dest, "50.00", "Test transfer", customer.id)

    assert source.balance == Decimal("150.00")
    assert dest.balance == Decimal("50.00")


def test_reversal_restores_balance_and_preserves_original(app, db, customer):
    account = banking_service.create_account(customer.id)
    original = banking_service.deposit(account, "100.00", "Deposit to reverse", customer.id)

    reversal = banking_service.reverse_transaction(original, customer.id, "Bank error")

    assert account.balance == Decimal("0.00")
    assert original.status == "REVERSED"
    assert reversal.transaction_type == "REVERSAL"
    assert reversal.related_transaction_id == original.id
