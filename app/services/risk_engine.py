from datetime import datetime, timedelta
from decimal import Decimal
from app import db
from app.models.account import Account
from app.models.transaction import Transaction, TransactionStatus
from app.models.beneficiary import Beneficiary
from app.models.workflow_risk import RiskAssessment, RiskLevel, RiskDecision


def evaluate_transaction_risk(source_account: Account, destination_account: Account,
                             amount: Decimal, actor_user_id: int) -> RiskAssessment:
    """
    Transparent rule-based risk evaluation engine (0 - 100 risk score).
    Factors evaluated:
      - High transaction amount (absolute & relative to balance)
      - New beneficiary (< 24 hrs old)
      - Rapid successive transfers in last 10 minutes
      - Depleting > 80% of total available account balance
    """
    score = 0
    factors = []

    amount_val = float(amount)
    balance_val = float(source_account.balance) if source_account.balance else 0.0

    # 1. Absolute High Amount Rule
    if amount_val >= 50000.0:
        score += 35
        factors.append(f"High transfer amount (₹{amount_val:,.2f} >= ₹50,000)")
    elif amount_val >= 25000.0:
        score += 20
        factors.append(f"Elevated transfer amount (₹{amount_val:,.2f})")

    # 2. Percentage of Balance Rule
    if balance_val > 0 and (amount_val / balance_val) >= 0.8:
        score += 25
        factors.append("Transfer consumes > 80% of account balance")

    # 3. New Beneficiary / Unverified Counterparty Check
    if destination_account:
        bene = Beneficiary.query.filter_by(
            user_id=actor_user_id,
            account_number=destination_account.account_number
        ).first()

        if bene:
            age = datetime.utcnow() - bene.created_at
            if age < timedelta(hours=24):
                score += 30
                factors.append("Newly added beneficiary (< 24 hours)")

    # 4. Rapid Transfer Frequency Check
    ten_mins_ago = datetime.utcnow() - timedelta(minutes=10)
    recent_txns_count = Transaction.query.filter(
        Transaction.account_id == source_account.id,
        Transaction.created_at >= ten_mins_ago
    ).count()

    if recent_txns_count >= 3:
        score += 25
        factors.append(f"High transaction frequency ({recent_txns_count} txns in last 10 mins)")

    # Cap score at 100
    score = min(score, 100)

    # Risk level classification
    if score >= 80:
        level = RiskLevel.CRITICAL
        decision = RiskDecision.REVIEW_REQUIRED
    elif score >= 60:
        level = RiskLevel.HIGH
        decision = RiskDecision.REVIEW_REQUIRED
    elif score >= 30:
        level = RiskLevel.MEDIUM
        decision = RiskDecision.APPROVED
    else:
        level = RiskLevel.LOW
        decision = RiskDecision.APPROVED

    assessment = RiskAssessment(
        risk_score=score,
        risk_level=level,
        decision=decision,
        risk_factors=factors,
    )
    return assessment
