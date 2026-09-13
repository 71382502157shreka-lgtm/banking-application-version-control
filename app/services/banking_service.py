from decimal import Decimal
from datetime import date
from app import db
from app.models.account import Account, AccountType, AccountStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.audit_log import AuditAction
from app.models.version import EntityType, ChangeType
from app.models.notification import Notification
from app.models.workflow_risk import TransferLimit, RiskDecision
from app.services.version_service import create_version
from app.services.risk_engine import evaluate_transaction_risk
from app.utils.validators import validate_amount, ValidationError


class InsufficientBalanceError(Exception):
    pass


def create_account(user_id: int, account_type: str = AccountType.SAVINGS) -> Account:
    account = Account(user_id=user_id, account_type=account_type)
    db.session.add(account)
    db.session.flush()

    # Create default Transfer Limit for the account
    t_limit = TransferLimit(
        account_id=account.id,
        per_transaction_limit=Decimal("100000.00"),
        daily_limit=Decimal("500000.00"),
        used_today=Decimal("0.00"),
        last_reset_date=date.today()
    )
    db.session.add(t_limit)

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


def deposit(account: Account, amount, description: str, actor_user_id: int, transaction_mode: str = None) -> Transaction:
    amount = validate_amount(amount)
    old_data = account.to_dict()

    account.balance = Decimal(account.balance) + amount
    account.available_balance = Decimal(account.available_balance) + amount
    _bump_account_version(account)

    txn = Transaction(
        account_id=account.id,
        transaction_type=TransactionType.DEPOSIT,
        transaction_mode=transaction_mode or "CASH_DEPOSIT",
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


def withdraw(account: Account, amount, description: str, actor_user_id: int, transaction_mode: str = None) -> Transaction:
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
        transaction_mode=transaction_mode or "CASH_WITHDRAWAL",
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


def transfer(source: Account, destination: Account, amount, description: str, actor_user_id: int, transaction_mode: str = None, idempotency_key: str = None):
    amount = validate_amount(amount)

    if not source or source.status != AccountStatus.ACTIVE:
        raise ValidationError("Source account is inactive or invalid")
    if not destination or destination.status != AccountStatus.ACTIVE:
        raise ValidationError("Destination account is inactive or invalid")

    if source.id == destination.id or source.account_number == destination.account_number:
        raise ValidationError("Cannot transfer to the same account")

    # Pessimistic row locking for concurrency safety
    try:
        locked_src = Account.query.filter_by(id=source.id).with_for_update().first()
        if locked_src:
            source = locked_src
    except Exception:
        pass

    if Decimal(source.available_balance) < amount:
        raise InsufficientBalanceError("Insufficient available balance for this transfer")

    mode = transaction_mode or "TRANSFER"

    try:
        # 1. Enforce Transfer Limits
        limit_rec = TransferLimit.query.filter_by(account_id=source.id).first()
        if limit_rec:
            limit_rec.reset_if_new_day()
            if amount > limit_rec.per_transaction_limit:
                raise ValidationError(f"Transfer amount exceeds per-transaction limit of ₹{limit_rec.per_transaction_limit:,.2f}")
            if (limit_rec.used_today + amount) > limit_rec.daily_limit:
                raise ValidationError(f"Transfer exceeds remaining daily limit of ₹{(limit_rec.daily_limit - limit_rec.used_today):,.2f}")

        # 2. Risk Engine Evaluation
        risk_assessment = evaluate_transaction_risk(source, destination, amount, actor_user_id)

        if risk_assessment.decision == RiskDecision.REVIEW_REQUIRED:
            # Flag transaction as BLOCKED_FOR_REVIEW for Maker-Checker review
            debit_txn = Transaction(
                account_id=source.id,
                transaction_type=TransactionType.TRANSFER,
                transaction_mode=mode,
                amount=amount,
                description=f"[REVIEW REQUIRED] {description}",
                status="BLOCKED_FOR_REVIEW",
                counterparty_account_id=destination.id,
                idempotency_key=idempotency_key,
                balance_after=source.balance,
            )
            db.session.add(debit_txn)
            db.session.flush()

            risk_assessment.transaction_id = debit_txn.id
            db.session.add(risk_assessment)

            db.session.add(Notification(
                user_id=source.user_id,
                title="Transfer Flagged for Review",
                message=f"Your transfer of ₹{amount} was flagged by the security risk engine and is pending admin approval.",
                notification_type="SECURITY"
            ))
            db.session.commit()
            return debit_txn, None

        # Normal Approved Transfer
        src_old, dst_old = source.to_dict(), destination.to_dict()

        source.balance = Decimal(source.balance) - amount
        source.available_balance = Decimal(source.available_balance) - amount
        _bump_account_version(source)

        destination.balance = Decimal(destination.balance) + amount
        destination.available_balance = Decimal(destination.available_balance) + amount
        _bump_account_version(destination)

        if limit_rec:
            limit_rec.used_today += amount

        debit_txn = Transaction(
            account_id=source.id,
            transaction_type=TransactionType.TRANSFER,
            transaction_mode=mode,
            amount=amount,
            description=description,
            status=TransactionStatus.COMPLETED,
            counterparty_account_id=destination.id,
            idempotency_key=idempotency_key,
            balance_after=source.balance,
        )
        credit_txn = Transaction(
            account_id=destination.id,
            transaction_type=TransactionType.TRANSFER,
            transaction_mode=mode,
            amount=amount,
            description=description,
            status=TransactionStatus.COMPLETED,
            counterparty_account_id=source.id,
            balance_after=destination.balance,
        )
        db.session.add_all([debit_txn, credit_txn])
        db.session.flush()

        risk_assessment.transaction_id = debit_txn.id
        db.session.add(risk_assessment)

        try:
            from app.models.behavioral_profile import UserBehavioralProfile
            profile = UserBehavioralProfile.get_or_create(actor_user_id)
            profile.record_transfer(amount)
        except Exception:
            pass

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
    except Exception:
        db.session.rollback()
        raise




def reverse_transaction(original: Transaction, actor_user_id: int, reason: str) -> Transaction:
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
