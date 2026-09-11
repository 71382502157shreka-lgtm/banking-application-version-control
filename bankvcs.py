"""
Python SDK / API Module for Banking Application with Version Control.
Allows pure Python programmatic access to all banking operations, version control,
audit logging, risk engine, and maker-checker approvals without HTML templates.
"""

from decimal import Decimal
from typing import Tuple, List, Dict, Any, Optional

from app import create_app, db
from app.models.user import User, Role
from app.models.account import Account
from app.services import (
    auth_service,
    banking_service,
    beneficiary_service,
    version_service,
    approval_service,
    risk_engine,
    audit_service,
)


class BankingApp:
    """
    Pure Python API wrapper for the Banking Application with Version Control.
    """

    def __init__(self, config_name: str = "development"):
        self.flask_app = create_app(config_name)
        self._ctx = self.flask_app.app_context()
        self._ctx.push()

    def close(self):
        self._ctx.pop()

    def register_user(self, username: str, email: str, password: str,
                      full_name: str = "", phone: str = "", role: str = Role.CUSTOMER) -> Tuple[Optional[User], Optional[str]]:
        try:
            user = auth_service.register_user(username, email, password, full_name, phone, role)
            return user, None
        except Exception as e:
            return None, str(e)

    def authenticate(self, username: str, password: str) -> Tuple[Optional[User], Optional[str]]:
        try:
            user = auth_service.authenticate(username, password)
            return user, None
        except Exception as e:
            return None, str(e)

    def get_accounts(self, user_id: int) -> List[Account]:
        return Account.query.filter_by(user_id=user_id).all()

    def deposit(self, account_id: int | Account, amount: Decimal | str | float, description: str = "Deposit", actor_user_id: Optional[int] = None) -> Tuple[Any, Optional[str]]:
        try:
            acc = Account.query.get(account_id) if isinstance(account_id, int) else account_id
            if not acc:
                return None, "Account not found"
            actor_id = actor_user_id or acc.user_id
            txn = banking_service.deposit(acc, Decimal(str(amount)), description, actor_id)
            return txn, None
        except Exception as e:
            return None, str(e)

    def withdraw(self, account_id: int | Account, amount: Decimal | str | float, description: str = "Withdrawal", actor_user_id: Optional[int] = None) -> Tuple[Any, Optional[str]]:
        try:
            acc = Account.query.get(account_id) if isinstance(account_id, int) else account_id
            if not acc:
                return None, "Account not found"
            actor_id = actor_user_id or acc.user_id
            txn = banking_service.withdraw(acc, Decimal(str(amount)), description, actor_id)
            return txn, None
        except Exception as e:
            return None, str(e)

    def transfer(self, from_account_id: int | Account, to_account_id: int | Account,
                 amount: Decimal | str | float, description: str = "Transfer", actor_user_id: Optional[int] = None) -> Tuple[Any, Optional[str]]:
        try:
            from_acc = Account.query.get(from_account_id) if isinstance(from_account_id, int) else from_account_id
            to_acc = Account.query.get(to_account_id) if isinstance(to_account_id, int) else to_account_id
            if not from_acc or not to_acc:
                return None, "One or both accounts not found"
            actor_id = actor_user_id or from_acc.user_id
            res = banking_service.transfer(from_acc, to_acc, Decimal(str(amount)), description, actor_id)
            return res, None
        except Exception as e:
            return None, str(e)

    def create_beneficiary(self, user_id: int, name: str, account_number: str,
                           bank_name: str, ifsc: str) -> Tuple[Any, Optional[str]]:
        try:
            b = beneficiary_service.add_beneficiary(user_id, {
                "name": name,
                "account_number": account_number,
                "bank_name": bank_name,
                "ifsc": ifsc,
            })
            return b, None
        except Exception as e:
            return None, str(e)

    def get_version_history(self, entity_type: str, entity_id: int) -> List[Any]:
        return version_service.get_history(entity_type, entity_id)

    def compare_versions(self, entity_type: str, entity_id: int, v1: int, v2: int) -> Dict[str, Any]:
        return version_service.compare_versions(entity_type, entity_id, v1, v2)

    def request_rollback(self, requested_by: int, entity_type: str, entity_id: int,
                         target_version: int, reason: str) -> Tuple[Any, Optional[str]]:
        return approval_service.request_rollback(requested_by, entity_type, entity_id, target_version, reason)

    def approve_rollback(self, request_id: int, reviewer_id: int, review_notes: str = "") -> Tuple[bool, str]:
        return approval_service.approve_rollback(request_id, reviewer_id, review_notes)

    def review_risk(self, assessment_id: int, reviewer_id: int, approve: bool, review_notes: str = "") -> Tuple[Any, Optional[str]]:
        return risk_engine.review_risk_assessment(assessment_id, reviewer_id, approve, review_notes)

    def verify_audit_chain(self) -> Tuple[bool, str]:
        res = audit_service.verify_audit_integrity()
        return res.get("valid", False), res.get("message", "")
