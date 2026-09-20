from datetime import datetime, timedelta
from app import db
from app.models.transaction import Transaction, TransactionStatus
from app.models.beneficiary import Beneficiary, BeneficiaryStatus
from app.models.risk_assessment import RiskAssessment, RiskLevel
from app.models.audit_log import AuditAction
from app.services.audit_service import log_action


def evaluate_transaction_risk(user_id: int, account, amount: float, beneficiary_id: int = None) -> RiskAssessment:
    """
    Transparent, rule-based transaction risk intelligence engine.
    Calculates a risk score from 0–100 based on deterministic risk factors:
    1. Transaction amount relative to account balance & threshold (>₹50,000)
    2. Beneficiary status (new beneficiary within cooling period or zero prior transfers)
    3. Transfer velocity (frequency of transactions in 15-minute window)
    4. Account balance depletion (>80% depletion in single transfer)
    """
    amount = float(amount)
    score = 0
    factors = []

    # 1. High Amount Factor
    if amount >= 100000.0:
        score += 35
        factors.append("Very high transfer amount (≥ ₹100,000)")
    elif amount >= 50000.0:
        score += 25
        factors.append("High transfer amount (≥ ₹50,000)")

    # 2. Account Balance Depletion Factor
    balance = float(account.balance) if account else 0.0
    if balance > 0 and (amount / balance) >= 0.8:
        score += 20
        factors.append(f"Depletes {int((amount/balance)*100)}% of total account balance")

    # 3. Beneficiary Cooling Period & History Factor
    if beneficiary_id:
        beneficiary = db.session.get(Beneficiary, beneficiary_id)
        if beneficiary:
            if beneficiary.status == BeneficiaryStatus.COOLING:
                score += 30
                factors.append("Beneficiary is currently in security cooling-off period")
            
            # Check prior successful transfers to this beneficiary
            prior_count = (
                Transaction.query
                .filter_by(account_id=account.id, status=TransactionStatus.COMPLETED)
                .filter(Transaction.description.ilike(f"%{beneficiary.account_number}%"))
                .count()
            )
            if prior_count == 0:
                score += 15
                factors.append("First transfer to this beneficiary")

    # 4. Transfer Velocity Factor (last 15 minutes)
    fifteen_mins_ago = datetime.now() - timedelta(minutes=15)
    recent_txns = (
        Transaction.query
        .filter(Transaction.account_id == account.id)
        .filter(Transaction.created_at >= fifteen_mins_ago)
        .count()
    )
    if recent_txns >= 3:
        score += 25
        factors.append(f"High transaction velocity ({recent_txns} transfers in last 15 minutes)")
    elif recent_txns >= 1:
        score += 10
        factors.append("Multiple transactions in short timeframe")

    # Cap score at 100
    score = min(100, score)

    # Classify Risk Level
    if score >= 80:
        level = RiskLevel.CRITICAL
        decision = "BLOCKED"
    elif score >= 60:
        level = RiskLevel.HIGH
        decision = "REVIEW_REQUIRED"
    elif score >= 30:
        level = RiskLevel.MEDIUM
        decision = "APPROVED"
    else:
        level = RiskLevel.LOW
        decision = "APPROVED"

    assessment = RiskAssessment(
        user_id=user_id,
        risk_score=score,
        risk_level=level,
        factors=factors,
        decision=decision,
    )
    db.session.add(assessment)

    log_action(
        action=AuditAction.RISK_EVALUATED,
        user_id=user_id,
        entity_type="RISK_ASSESSMENT",
        description=f"Risk score evaluated: {score}/100 [{level}] - Decision: {decision}",
        new_data={"score": score, "level": level, "factors": factors, "decision": decision},
    )

    return assessment
