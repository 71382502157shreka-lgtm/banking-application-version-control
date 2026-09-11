"""
Executive Reporting & Financial Analytics Service for BankVCS 2.0.
Provides comprehensive pure Python analytical reporting, financial portfolio breakdowns,
risk telemetry metrics, SHA-256 audit chain health reports, and export generators.
"""

import csv
import io
import json
import logging
from datetime import datetime
from decimal import Decimal

from app import db
from app.models.user import User, Role
from app.models.account import Account, AccountStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.beneficiary import Beneficiary
from app.models.version import EntityVersion
from app.models.audit_log import AuditLog
from app.models.workflow_risk import RiskAssessment, RollbackRequest, RollbackStatus
from app.models.complaint import Complaint, ComplaintStatus
from app.services import audit_service, version_service

logger = logging.getLogger(__name__)


def generate_executive_summary_report() -> dict:
    """
    Generates an executive-level summary report of system-wide financial health,
    user distributions, risk metrics, version counts, and audit integrity status.
    """
    total_users = User.query.count()
    customer_count = User.query.filter_by(role=Role.CUSTOMER).count()
    employee_count = User.query.filter_by(role=Role.EMPLOYEE).count()
    admin_count = User.query.filter_by(role=Role.ADMIN).count()

    total_accounts = Account.query.count()
    active_accounts = Account.query.filter_by(status=AccountStatus.ACTIVE).count()
    
    accounts = Account.query.all()
    total_system_balance = sum((a.balance for a in accounts), Decimal("0.00"))

    total_transactions = Transaction.query.count()
    completed_txns = Transaction.query.filter_by(status=TransactionStatus.COMPLETED).count()

    # Risk metrics
    total_risk_evals = RiskAssessment.query.count()
    high_risk_evals = RiskAssessment.query.filter(RiskAssessment.risk_score >= 60).count()
    critical_risk_evals = RiskAssessment.query.filter(RiskAssessment.risk_score >= 80).count()

    # Rollback metrics
    total_rollbacks = RollbackRequest.query.count()
    pending_rollbacks = RollbackRequest.query.filter_by(status=RollbackStatus.PENDING).count()
    approved_rollbacks = RollbackRequest.query.filter_by(status=RollbackStatus.APPROVED).count()

    # Version metrics
    total_versions = EntityVersion.query.count()
    account_versions = EntityVersion.query.filter_by(entity_type="ACCOUNT").count()
    beneficiary_versions = EntityVersion.query.filter_by(entity_type="BENEFICIARY").count()
    profile_versions = EntityVersion.query.filter_by(entity_type="USER_PROFILE").count()

    # Audit chain verification
    audit_report = audit_service.verify_audit_integrity()

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "users_summary": {
            "total_users": total_users,
            "customers": customer_count,
            "employees": employee_count,
            "admins": admin_count,
        },
        "financial_summary": {
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "total_system_balance": float(total_system_balance),
            "formatted_balance": f"₹{total_system_balance:,.2f}",
        },
        "transaction_summary": {
            "total_transactions": total_transactions,
            "completed_transactions": completed_txns,
        },
        "risk_telemetry": {
            "total_evaluations": total_risk_evals,
            "high_risk_count": high_risk_evals,
            "critical_risk_count": critical_risk_evals,
        },
        "maker_checker_summary": {
            "total_requests": total_rollbacks,
            "pending_requests": pending_rollbacks,
            "approved_requests": approved_rollbacks,
        },
        "version_control_ledger": {
            "total_versions_created": total_versions,
            "account_snapshots": account_versions,
            "beneficiary_snapshots": beneficiary_versions,
            "profile_snapshots": profile_versions,
        },
        "audit_integrity": {
            "chain_valid": audit_report.get("valid", True),
            "status_message": audit_report.get("message", "OK"),
            "total_audit_records": AuditLog.query.count(),
        }
    }
    return report


def generate_risk_telemetry_report() -> dict:
    """
    Generates detailed risk engine telemetry, including risk factor trigger frequencies,
    decision metrics, and high-risk evaluation records.
    """
    evaluations = RiskAssessment.query.order_by(RiskAssessment.created_at.desc()).all()
    
    level_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    decision_counts = {"ALLOW": 0, "REVIEW_REQUIRED": 0, "REJECT": 0}
    factor_frequency = {}

    for ev in evaluations:
        lvl = ev.risk_level or "LOW"
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

        dec = ev.decision or "ALLOW"
        decision_counts[dec] = decision_counts.get(dec, 0) + 1

        factors = ev.risk_factors or []
        for factor in factors:
            factor_frequency[factor] = factor_frequency.get(factor, 0) + 1

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "total_evaluations": len(evaluations),
        "risk_level_breakdown": level_counts,
        "decision_breakdown": decision_counts,
        "frequent_risk_factors": factor_frequency,
        "recent_high_risk_evaluations": [ev.to_dict() for ev in evaluations if ev.risk_score >= 60][:15]
    }


def generate_customer_portfolio_summary(customer_id: int) -> dict:
    """
    Generates a comprehensive financial portfolio summary for a specific customer.
    Includes accounts, transaction volume, beneficiaries, and version snapshots.
    """
    customer = db.session.get(User, customer_id)
    if not customer or customer.role != Role.CUSTOMER:
        raise ValueError(f"Customer #{customer_id} not found")

    accounts = Account.query.filter_by(user_id=customer_id).all()
    account_ids = [a.id for a in accounts]
    total_balance = sum((a.balance for a in accounts), Decimal("0.00"))

    transactions = Transaction.query.filter(
        (Transaction.account_id.in_(account_ids)) | (Transaction.counterparty_account_id.in_(account_ids))
    ).order_by(Transaction.created_at.desc()).all()

    beneficiaries = Beneficiary.query.filter_by(user_id=customer_id).all()

    profile_versions = version_service.get_history("USER_PROFILE", customer_id)

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "customer": {
            "id": customer.id,
            "username": customer.username,
            "email": customer.email,
            "full_name": customer.full_name,
            "phone": customer.phone,
            "is_active": customer.is_active,
        },
        "financial_summary": {
            "account_count": len(accounts),
            "total_balance": float(total_balance),
            "formatted_balance": f"₹{total_balance:,.2f}",
            "accounts": [a.to_dict() for a in accounts]
        },
        "activity": {
            "total_transactions": len(transactions),
            "recent_transactions": [t.to_dict() for t in transactions[:10]]
        },
        "beneficiaries": {
            "count": len(beneficiaries),
            "items": [b.to_dict() for b in beneficiaries]
        },
        "version_history": {
            "profile_version_count": len(profile_versions)
        }
    }


def export_audit_log_csv(limit: int = None) -> str:
    """
    Exports SHA-256 audit log records into a CSV string format.
    """
    query = AuditLog.query.order_by(AuditLog.id.asc())
    if limit:
        query = query.limit(limit)
    audit_logs = query.all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Log_ID", "Timestamp", "User_ID", "Action", "Entity_Type",
        "Entity_ID", "Description", "IP_Address", "Hash", "Previous_Hash"
    ])

    for log in audit_logs:
        writer.writerow([
            log.id,
            log.created_at.isoformat() if log.created_at else "",
            log.user_id or "",
            log.action.value if hasattr(log.action, "value") else str(log.action),
            log.entity_type or "",
            log.entity_id or "",
            log.description or "",
            log.ip_address or "",
            log.current_hash or "",
            log.prev_hash or ""
        ])

    return output.getvalue()


def export_executive_summary_json() -> str:
    """
    Exports executive summary report as a JSON string.
    """
    summary = generate_executive_summary_report()
    summary["report_header"] = "BANKVCS_2_0_EXECUTIVE_REPORT"
    return json.dumps(summary, indent=2)


def export_executive_summary_text() -> str:
    """
    Formats the executive summary report as a clean plain-text corporate report.
    """
    summary = generate_executive_summary_report()
    lines = [
        "============================================================",
        "          BANKVCS 2.0 - EXECUTIVE FINANCIAL REPORT          ",
        "============================================================",
        f"Generated At          : {summary['generated_at']}",
        f"Audit Chain Status    : {summary['audit_integrity']['status_message']}",
        "------------------------------------------------------------",
        "USER DISTRIBUTION",
        f"  Total Registered Users : {summary['users_summary']['total_users']}",
        f"  Customers              : {summary['users_summary']['customers']}",
        f"  Staff Employees        : {summary['users_summary']['employees']}",
        f"  System Administrators  : {summary['users_summary']['admins']}",
        "------------------------------------------------------------",
        "FINANCIAL LEDGER",
        f"  Total Accounts         : {summary['financial_summary']['total_accounts']}",
        f"  Active Accounts        : {summary['financial_summary']['active_accounts']}",
        f"  Total System Balance   : {summary['financial_summary']['formatted_balance']}",
        f"  Total Transactions     : {summary['transaction_summary']['total_transactions']}",
        "------------------------------------------------------------",
        "RISK & MAKER-CHECKER GOVERNANCE",
        f"  Total Risk Evaluated   : {summary['risk_telemetry']['total_evaluations']}",
        f"  High/Critical Risk Txns: {summary['risk_telemetry']['high_risk_count']}",
        f"  Pending Rollbacks      : {summary['maker_checker_summary']['pending_requests']}",
        f"  Approved Rollbacks     : {summary['maker_checker_summary']['approved_requests']}",
        "------------------------------------------------------------",
        "DATABASE VERSION CONTROL (VCS) LEDGER",
        f"  Total Snapshots        : {summary['version_control_ledger']['total_versions_created']}",
        f"  Account Snapshots      : {summary['version_control_ledger']['account_snapshots']}",
        f"  Beneficiary Snapshots  : {summary['version_control_ledger']['beneficiary_snapshots']}",
        f"  Profile Snapshots      : {summary['version_control_ledger']['profile_snapshots']}",
        "============================================================"
    ]
    return "\n".join(lines)
