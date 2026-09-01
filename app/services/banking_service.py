from decimal import Decimal

from app import db
from app.models.account import Account, AccountType
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.audit_log import AuditAction
from app.models.version import EntityType, ChangeType
from app.models.notification import Notification
from app.services.version_service import create_version
from app.utils.validators import validate_amount, ValidationError


class InsufficientBalanceError(Exception):
    pass


def create_account(user_id: int, account_type: str = AccountType.SAVINGS) -> Account:
    account = Account(user_id=user_id, account_type=account_type)
    db.session.add(account)
    db.session.flush()

    create_version(
        entity_type=EntityType.ACCOUNT,
        entity_id=account.id,
        change_type=ChangeType.CREATE,
        old_data=None,
        new_data=account.to_dict(),
        changed_by=user_id,
        change_summary="Account opened",
        audit_action=AuditAction.ACCOUNT_CREATED,
    )
    db.session.add(Notification(
        user_id=user_id,
        title="Account Opened",
        message=f"New {account_type} account {account.account_number} created successfully.",
        notification_type="INFO"
    ))
    db.session.commit()
    return account


def _bump_account_version(account: Account):
    account.version_number += 1


def deposit(account: Account, amount, description: str, actor_user_id: int) -> Transaction:
    amount = validate_amount(amount)
    old_data = account.to_dict()

    account.balance = Decimal(account.balance) + amount
    account.available_balance = Decimal(account.available_balance) + amount
    _bump_account_version(account)

    txn = Transaction(
        account_id=account.id,
        transaction_type=TransactionType.DEPOSIT,
        amount=amount,
        description=description,
        status=TransactionStatus.COMPLETED,
        balance_after=account.balance,
    )
    db.session.add(txn)
    db.session.flush()

    create_version(
        entity_type=EntityType.ACCOUNT,
        entity_id=account.id,
        change_type=ChangeType.UPDATE,
        old_data=old_data,
        new_data=account.to_dict(),
        changed_by=actor_user_id,
        change_summary=f"Deposit of {amount}",
        audit_action=AuditAction.DEPOSIT,
    )
    db.session.add(Notification(
        user_id=account.user_id,
        title="Deposit Successful",
        message=f"₹{amount} deposited into account {account.account_number}.",
        notification_type="TRANSACTION"
    ))
    db.session.commit()
    return txn


def withdraw(account: Account, amount, description: str, actor_user_id: int) -> Transaction:
    amount = validate_amount(amount)
    if Decimal(account.available_balance) < amount:
        raise InsufficientBalanceError("Insufficient available balance for this withdrawal")

    old_data = account.to_dict()
    account.balance = Decimal(account.balance) - amount
    account.available_balance = Decimal(account.available_balance) - amount
    _bump_account_version(account)

    txn = Transaction(
        account_id=account.id,
        transaction_type=TransactionType.WITHDRAWAL,
        amount=amount,
        description=description,
        status=TransactionStatus.COMPLETED,
        balance_after=account.balance,
    )
    db.session.add(txn)
    db.session.flush()

    create_version(
        entity_type=EntityType.ACCOUNT,
        entity_id=account.id,
        change_type=ChangeType.UPDATE,
        old_data=old_data,
        new_data=account.to_dict(),
        changed_by=actor_user_id,
        change_summary=f"Withdrawal of {amount}",
        audit_action=AuditAction.WITHDRAWAL,
    )
    db.session.add(Notification(
        user_id=account.user_id,
        title="Withdrawal Successful",
        message=f"₹{amount} withdrawn from account {account.account_number}.",
        notification_type="TRANSACTION"
    ))
    db.session.commit()
    return txn


def transfer(source: Account, destination: Account, amount, description: str, actor_user_id: int):
    amount = validate_amount(amount)
    if source.id == destination.id:
        raise ValidationError("Cannot transfer to the same account")
    if Decimal(source.available_balance) < amount:
        raise InsufficientBalanceError("Insufficient available balance for this transfer")

    src_old, dst_old = source.to_dict(), destination.to_dict()

    source.balance = Decimal(source.balance) - amount
    source.available_balance = Decimal(source.available_balance) - amount
    _bump_account_version(source)

    destination.balance = Decimal(destination.balance) + amount
    destination.available_balance = Decimal(destination.available_balance) + amount
    _bump_account_version(destination)

    debit_txn = Transaction(
        account_id=source.id,
        transaction_type=TransactionType.TRANSFER,
        amount=amount,
        description=description,
        status=TransactionStatus.COMPLETED,
        counterparty_account_id=destination.id,
        balance_after=source.balance,
    )
    credit_txn = Transaction(
        account_id=destination.id,
        transaction_type=TransactionType.TRANSFER,
        amount=amount,
        description=description,
        status=TransactionStatus.COMPLETED,
        counterparty_account_id=source.id,
        balance_after=destination.balance,
    )
    db.session.add_all([debit_txn, credit_txn])
    db.session.flush()

    create_version(EntityType.ACCOUNT, source.id, ChangeType.UPDATE, src_old, source.to_dict(),
                    actor_user_id, f"Transfer out {amount} to account {destination.account_number}",
                    AuditAction.TRANSFER)
    create_version(EntityType.ACCOUNT, destination.id, ChangeType.UPDATE, dst_old, destination.to_dict(),
                    actor_user_id, f"Transfer in {amount} from account {source.account_number}",
                    AuditAction.TRANSFER)

    db.session.add(Notification(
        user_id=source.user_id,
        title="Transfer Sent",
        message=f"₹{amount} sent to account {destination.account_number}.",
        notification_type="TRANSACTION"
    ))
    if destination.user_id != source.user_id:
        db.session.add(Notification(
            user_id=destination.user_id,
            title="Transfer Received",
            message=f"₹{amount} received from account {source.account_number}.",
            notification_type="TRANSACTION"
        ))
    db.session.commit()
    return debit_txn, credit_txn


def reverse_transaction(original: Transaction, actor_user_id: int, reason: str) -> Transaction:
    """
    Financial corrections NEVER edit or delete the original transaction.
    Instead we post an equal-and-opposite REVERSAL transaction and mark
    the original's status as REVERSED, preserving full history.
    """
    if original.status == TransactionStatus.REVERSED:
        raise ValidationError("Transaction has already been reversed")

    account = db.session.get(Account, original.account_id)
    old_data = account.to_dict()

    is_credit_reversal = original.transaction_type in (TransactionType.WITHDRAWAL,)
    amount = Decimal(original.amount)

    if is_credit_reversal:
        account.balance += amount
        account.available_balance += amount
    else:
        account.balance -= amount
        account.available_balance -= amount
    _bump_account_version(account)

    reversal = Transaction(
        account_id=account.id,
        transaction_type=TransactionType.REVERSAL,
        amount=amount,
        description=f"Reversal of {original.reference_number}: {reason}",
        status=TransactionStatus.COMPLETED,
        related_transaction_id=original.id,
        balance_after=account.balance,
    )
    original.status = TransactionStatus.REVERSED
    db.session.add(reversal)
    db.session.flush()

    create_version(
        entity_type=EntityType.ACCOUNT,
        entity_id=account.id,
        change_type=ChangeType.UPDATE,
        old_data=old_data,
        new_data=account.to_dict(),
        changed_by=actor_user_id,
        change_summary=f"Reversal of transaction {original.reference_number}",
        audit_action=AuditAction.REVERSAL,
    )
    db.session.commit()
    return reversal
