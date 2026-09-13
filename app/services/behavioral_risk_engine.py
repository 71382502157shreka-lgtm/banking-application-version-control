from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional
from flask import request, has_request_context

from app import db
from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.beneficiary import Beneficiary
from app.models.security_session import LoginSession, SecurityEvent, OTPVerification
from app.models.workflow_risk import RiskAssessment, RiskLevel, RiskDecision
from app.models.behavioral_profile import UserBehavioralProfile
from app.utils.security import get_client_ip


def evaluate_behavioral_risk(
    user_id: int,
    source_account: Optional[Account] = None,
    destination_account: Optional[Account] = None,
    amount: Decimal = Decimal("0.00"),
    context_ip: Optional[str] = None,
    context_user_agent: Optional[str] = None
) -> RiskAssessment:
    """
    Evaluate user activity against 10 behavioral anomaly vectors.
    Returns RiskAssessment populated with risk score, level, decision, factors, and action taken.
    """
    profile = UserBehavioralProfile.get_or_create(user_id)

    ip_addr = context_ip or _get_safe_ip()
    user_agent = context_user_agent or _get_safe_user_agent()

    score = 0
    factors: List[str] = []
    anomaly_details: Dict[str, Any] = {}

    amount_val = float(amount)
    now = datetime.utcnow()

    # Vector 1: Unusual Login IP / Subnet Drift (+20)
    if profile.known_ips and not profile.is_ip_known(ip_addr):
        score += 20
        factors.append(f"Unusual login IP / subnet drift ({ip_addr})")
        anomaly_details["unusual_ip"] = ip_addr

    # Vector 2: New / Unrecognized Device (+15)
    if profile.known_user_agents and not profile.is_user_agent_known(user_agent):
        score += 15
        factors.append("Access from unrecognized device or User-Agent")
        anomaly_details["unrecognized_user_agent"] = user_agent[:50]

    # Vector 3: Abnormal Transfer Amount (+25)
    if amount_val > 0 and profile.total_transfer_count >= 2:
        avg_amt = float(profile.avg_transfer_amount or 0)
        max_amt = float(profile.max_transfer_amount or 0)

        if avg_amt > 0 and amount_val >= (3.0 * avg_amt):
            score += 25
            factors.append(f"Abnormal transfer amount (₹{amount_val:,.2f} is >= 3x 30-day average ₹{avg_amt:,.2f})")
            anomaly_details["abnormal_amount_vs_avg"] = {"amount": amount_val, "avg": avg_amt}
        elif max_amt > 0 and amount_val > max_amt:
            score += 20
            factors.append(f"Transfer amount (₹{amount_val:,.2f}) exceeds historical maximum (₹{max_amt:,.2f})")
            anomaly_details["exceeds_historical_max"] = {"amount": amount_val, "max": max_amt}

    # Vector 4: Unusual Transaction Frequency (+25)
    if source_account:
        ten_mins_ago = now - timedelta(minutes=10)
        recent_txns = Transaction.query.filter(
            Transaction.account_id == source_account.id,
            Transaction.created_at >= ten_mins_ago
        ).count()
        if recent_txns >= 3:
            score += 25
            factors.append(f"High transaction frequency ({recent_txns} transactions in last 10 minutes)")
            anomaly_details["burst_frequency_count"] = recent_txns

    # Vector 5: Rapid Multiple Transfers to Distinct Counterparties (+20)
    if source_account:
        thirty_mins_ago = now - timedelta(minutes=30)
        distinct_destinations = db.session.query(Transaction.counterparty_account_id).filter(
            Transaction.account_id == source_account.id,
            Transaction.created_at >= thirty_mins_ago,
            Transaction.counterparty_account_id.isnot(None)
        ).distinct().count()

        if distinct_destinations >= 3:
            score += 20
            factors.append(f"Rapid transfers to {distinct_destinations} distinct counterparty accounts within 30 minutes")
            anomaly_details["distinct_counterparties"] = distinct_destinations

    # Vector 6: Beneficiary Change + Instant Transfer (+30)
    if destination_account and amount_val > 20000.0:
        one_hour_ago = now - timedelta(hours=1)
        recent_bene = Beneficiary.query.filter(
            Beneficiary.user_id == user_id,
            Beneficiary.account_number == destination_account.account_number,
            Beneficiary.created_at >= one_hour_ago
        ).first()

        if recent_bene or (profile.last_beneficiary_added_at and profile.last_beneficiary_added_at >= one_hour_ago):
            score += 30
            factors.append("Transfer > ₹20,000 to newly added beneficiary (< 1 hour)")
            anomaly_details["recent_beneficiary_addition"] = True

    # Vector 7: Unusual Login Time (+10)
    current_hour = now.hour
    if len(profile.usual_login_hours or []) >= 3 and current_hour not in profile.usual_login_hours:
        score += 10
        factors.append(f"Activity at unusual hour ({current_hour}:00 UTC)")
        anomaly_details["unusual_hour"] = current_hour

    # Vector 8: Failed Login / OTP Spikes (+25)
    thirty_mins_ago = now - timedelta(minutes=30)
    failed_sec_events = SecurityEvent.query.filter(
        SecurityEvent.user_id == user_id,
        SecurityEvent.event_type.in_(["LOGIN_FAILED", "OTP_FAILED", "MFA_FAILED"]),
        SecurityEvent.created_at >= thirty_mins_ago
    ).count()

    failed_otps = OTPVerification.query.filter(
        OTPVerification.user_id == user_id,
        OTPVerification.created_at >= thirty_mins_ago,
        OTPVerification.attempts >= 3
    ).count()

    if failed_sec_events >= 3 or failed_otps >= 1:
        score += 25
        factors.append(f"Elevated failed authentication/OTP attempts in last 30 minutes")
        anomaly_details["failed_auth_spikes"] = failed_sec_events + (failed_otps * 3)

    # Vector 9: Suspicious Multi-IP Sessions (+30)
    five_mins_ago = now - timedelta(minutes=5)
    active_ips = db.session.query(LoginSession.ip_address).filter(
        LoginSession.user_id == user_id,
        LoginSession.is_active == True,
        LoginSession.last_activity >= five_mins_ago
    ).distinct().all()

    active_ip_count = len(active_ips)
    if active_ip_count >= 2:
        score += 30
        factors.append(f"Concurrent active sessions detected from {active_ip_count} distinct IP addresses")
        anomaly_details["concurrent_ips"] = [ip[0] for ip in active_ips]

    # Vector 10: Account Takeover (ATO) Pattern (+40)
    thirty_mins_ago = now - timedelta(minutes=30)
    recent_profile_update = False
    if profile.last_profile_updated_at and profile.last_profile_updated_at >= thirty_mins_ago:
        recent_profile_update = True
    else:
        ato_event = SecurityEvent.query.filter(
            SecurityEvent.user_id == user_id,
            SecurityEvent.event_type.in_(["PASSWORD_CHANGED", "PROFILE_UPDATED"]),
            SecurityEvent.created_at >= thirty_mins_ago
        ).first()
        if ato_event:
            recent_profile_update = True

    if recent_profile_update and amount_val > 10000.0:
        score += 40
        factors.append("Account Takeover (ATO) sequence: Profile/password update followed by money transfer")
        anomaly_details["ato_sequence_detected"] = True

    # Score capping
    score = min(score, 100)

    # Risk level & action determination
    if score >= 80:
        level = RiskLevel.CRITICAL
        decision = RiskDecision.REVIEW_REQUIRED
        action = "HOLD_AND_REVOKE"
    elif score >= 60:
        level = RiskLevel.HIGH
        decision = RiskDecision.REVIEW_REQUIRED
        action = "STEP_UP_ENFORCED"
    elif score >= 30:
        level = RiskLevel.MEDIUM
        decision = RiskDecision.APPROVED
        action = "ALERTED"
    else:
        level = RiskLevel.LOW
        decision = RiskDecision.APPROVED
        action = "ALLOWED"

    assessment = RiskAssessment(
        risk_score=score,
        risk_level=level,
        decision=decision,
        action_taken=action,
        anomaly_details=anomaly_details,
        risk_factors=factors,
    )
    return assessment


def _get_safe_ip() -> str:
    if has_request_context():
        try:
            return get_client_ip()
        except RuntimeError:
            return request.remote_addr or "127.0.0.1"
    return "127.0.0.1"


def _get_safe_user_agent() -> str:
    if has_request_context():
        return request.headers.get("User-Agent", "Unknown")
    return "Unknown"
