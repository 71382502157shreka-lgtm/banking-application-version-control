"""
Server-side Python risk service module wrapping risk engine policy evaluation.
"""

from decimal import Decimal
from typing import Dict, Any, Optional, Union

from app import db
from app.models.account import Account
from app.services import risk_engine, behavioral_risk_engine


def evaluate_transaction_risk(
    account_or_user: Union[Account, int],
    amount_or_acc: Union[Decimal, str, float, int],
    counterparty: Optional[Union[int, str]] = None,
    amount: Optional[Union[Decimal, str, float]] = None
) -> Dict[str, Any]:
    """
    Evaluate transaction risk using adaptive behavioral anomaly engine.
    Supports flexible arguments:
      - evaluate_transaction_risk(account, amount, counterparty_id)
      - evaluate_transaction_risk(user_id, account_id, counterparty_account_num, amount)
    Returns: {risk_score, risk_level, decision, action_taken, anomaly_details, risk_factors}
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
            "action_taken": "ALLOWED",
            "anomaly_details": {},
            "risk_factors": ["Account not found"],
        }

    # Combine static rule-based engine and behavioral anomaly engine
    assessment_static = risk_engine.evaluate_transaction_risk(source_acc, dest_acc, amt, actor_id)
    assessment_behavioral = behavioral_risk_engine.evaluate_behavioral_risk(actor_id, source_acc, dest_acc, amt)

    # Composite risk score is max of static rule score and behavioral score
    composite_score = min(max(assessment_static.risk_score, assessment_behavioral.risk_score), 100)
    combined_factors = list(dict.fromkeys((assessment_static.risk_factors or []) + (assessment_behavioral.risk_factors or [])))

    if composite_score >= 80:
        level = "CRITICAL"
        decision = "REVIEW_REQUIRED"
        action = "HOLD_AND_REVOKE"
    elif composite_score >= 60:
        level = "HIGH"
        decision = "REVIEW_REQUIRED"
        action = "STEP_UP_ENFORCED"
    elif composite_score >= 30:
        level = "MEDIUM"
        decision = "APPROVED"
        action = "ALERTED"
    else:
        level = "LOW"
        decision = "APPROVED"
        action = "ALLOWED"

    return {
        "risk_score": composite_score,
        "risk_level": level,
        "decision": decision,
        "action_taken": action,
        "anomaly_details": assessment_behavioral.anomaly_details or {},
        "risk_factors": combined_factors,
    }
