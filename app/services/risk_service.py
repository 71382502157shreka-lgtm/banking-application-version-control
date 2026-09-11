"""
Server-side Python risk service module wrapping risk engine policy evaluation.
"""

from decimal import Decimal
from typing import Dict, Any, Optional, Union

from app import db
from app.models.account import Account
from app.services import risk_engine


def evaluate_transaction_risk(
    account_or_user: Union[Account, int],
    amount_or_acc: Union[Decimal, str, float, int],
    counterparty: Optional[Union[int, str]] = None,
    amount: Optional[Union[Decimal, str, float]] = None
) -> Dict[str, Any]:
    """
    Evaluate transaction risk using Python rule-based scoring engine.
    Supports flexible arguments:
      - evaluate_transaction_risk(account, amount, counterparty_id)
      - evaluate_transaction_risk(user_id, account_id, counterparty_account_num, amount)
    Returns: {risk_score, risk_level, decision, risk_factors}
    """
    if isinstance(account_or_user, Account):
        source_acc = account_or_user
        amt = Decimal(str(amount_or_acc))
        dest_acc = db.session.get(Account, counterparty) if isinstance(counterparty, int) else None
        actor_id = source_acc.user_id
    else:
        actor_id = int(account_or_user)
        account_id = int(amount_or_acc)
        source_acc = db.session.get(Account, account_id)
        amt = Decimal(str(amount)) if amount is not None else Decimal("0")
        dest_acc = Account.query.filter_by(account_number=str(counterparty)).first() if counterparty else None

    if not source_acc:
        return {
            "risk_score": 0,
            "risk_level": "LOW",
            "decision": "APPROVED",
            "risk_factors": ["Account not found"],
        }

    assessment = risk_engine.evaluate_transaction_risk(source_acc, dest_acc, amt, actor_id)
    return {
        "risk_score": assessment.risk_score,
        "risk_level": assessment.risk_level,
        "decision": assessment.decision,
        "risk_factors": assessment.risk_factors,
    }
