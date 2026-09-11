from datetime import datetime
from app import db
from app.models.workflow_risk import RollbackRequest, RollbackStatus, RiskAssessment, RiskDecision, RiskLevel
from app.models.account import Account
from app.models.beneficiary import Beneficiary
from app.models.user import User
from app.models.transaction import Transaction, TransactionStatus
from app.models.audit_log import AuditAction
from app.models.version import EntityType, ChangeType
from app.services.version_service import restore_version, get_version
from app.services.audit_service import log_action
from app.utils.validators import ValidationError


def request_rollback(user_id: int, entity_type: str, entity_id: int,
                     target_version: int, reason: str) -> RollbackRequest:
    """
    Employee or Customer submits a rollback request for Maker-Checker review.
    """
    entity_type = entity_type.upper()
    version = get_version(entity_type, entity_id, target_version)
    if not version:
        raise ValidationError(f"Target version {target_version} does not exist for {entity_type} #{entity_id}")

    if entity_type == EntityType.TRANSACTION:
        raise ValidationError("Financial transactions cannot be rolled back via version restore. Use reversal instead.")

    req = RollbackRequest(
        requested_by=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        target_version=target_version,
        reason=reason,
        status=RollbackStatus.PENDING,
    )
    db.session.add(req)
    db.session.flush()

    log_action(
        action=AuditAction.ROLLBACK_REQUESTED,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        description=f"Rollback to v{target_version} requested for {entity_type} #{entity_id}: {reason}",
    )
    db.session.commit()
    return req


def approve_rollback_request(request_id: int, admin_user_id: int, review_notes: str = None) -> RollbackRequest:
    """
    Maker-Checker Approval: Admin approves rollback request.
    Restores target snapshot onto the live record and creates a NEW version row
    (e.g., v1 -> v2 -> v3 -> RESTORE(v1) -> v4). History is NEVER deleted.
    """
    req = db.session.get(RollbackRequest, request_id)
    if not req:
        raise ValidationError("Rollback request not found")
    if req.status != RollbackStatus.PENDING:
        raise ValidationError(f"Rollback request is already {req.status}")

    # Applier functions for non-financial entities
    def apply_account(snapshot):
        acc = Account.query.get_or_404(req.entity_id)
        acc.account_type = snapshot["account_type"]
        acc.status = snapshot["status"]
        acc.version_number += 1
        db.session.flush()
        return acc.to_dict()

    def apply_beneficiary(snapshot):
        bene = Beneficiary.query.get_or_404(req.entity_id)
        bene.name = snapshot["name"]
        bene.account_number = snapshot["account_number"]
        bene.bank_name = snapshot["bank_name"]
        bene.ifsc = snapshot["ifsc"]
        bene.status = snapshot["status"]
        bene.version_number += 1
        db.session.flush()
        return bene.to_dict()

    def apply_profile(snapshot):
        usr = User.query.get_or_404(req.entity_id)
        if "full_name" in snapshot:
            usr.full_name = snapshot["full_name"]
        if "phone" in snapshot:
            usr.phone = snapshot["phone"]
        if "email" in snapshot:
            usr.email = snapshot["email"]
        db.session.flush()
        return usr.to_dict()

    appliers = {
        EntityType.ACCOUNT: apply_account,
        EntityType.BENEFICIARY: apply_beneficiary,
        EntityType.USER_PROFILE: apply_profile,
    }

    apply_fn = appliers.get(req.entity_type)
    if not apply_fn:
        raise ValidationError(f"Restoration not supported for entity type {req.entity_type}")

    # Execute restore -> creates a NEW EntityVersion row automatically
    restored_state = restore_version(
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        version_number=req.target_version,
        changed_by=admin_user_id,
        apply_fn=apply_fn
    )

    req.status = RollbackStatus.EXECUTED
    req.reviewed_by = admin_user_id
    req.reviewed_at = datetime.utcnow()
    req.review_notes = review_notes or "Approved and executed by Admin"

    log_action(
        action=AuditAction.ROLLBACK_APPROVED,
        user_id=admin_user_id,
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        description=f"Approved rollback request #{req.id} (restored v{req.target_version})",
    )
    db.session.commit()
    return req


def reject_rollback_request(request_id: int, admin_user_id: int, review_notes: str) -> RollbackRequest:
    req = db.session.get(RollbackRequest, request_id)
    if not req:
        raise ValidationError("Rollback request not found")
    if req.status != RollbackStatus.PENDING:
        raise ValidationError(f"Rollback request is already {req.status}")

    req.status = RollbackStatus.REJECTED
    req.reviewed_by = admin_user_id
    req.reviewed_at = datetime.utcnow()
    req.review_notes = review_notes

    log_action(
        action=AuditAction.ROLLBACK_REJECTED,
        user_id=admin_user_id,
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        description=f"Rejected rollback request #{req.id}: {review_notes}",
    )
    db.session.commit()
    return req


def review_risk_assessment(assessment_id: int, admin_user_id: int, approve: bool, review_notes: str = None):
    assessment = db.session.get(RiskAssessment, assessment_id)
    if not assessment:
        raise ValidationError("Risk assessment record not found")

    txn = db.session.get(Transaction, assessment.transaction_id) if assessment.transaction_id else None

    assessment.reviewed_by = admin_user_id
    assessment.reviewed_at = datetime.utcnow()
    assessment.review_notes = review_notes

    if approve:
        assessment.decision = RiskDecision.APPROVED
        if txn and txn.status == "BLOCKED_FOR_REVIEW":
            txn.status = TransactionStatus.COMPLETED
        log_action(
            action=AuditAction.RISK_REVIEW_APPROVED,
            user_id=admin_user_id,
            entity_type=EntityType.TRANSACTION,
            entity_id=txn.id if txn else None,
            description=f"High-risk transaction #{txn.id if txn else ''} approved by admin.",
        )
    else:
        assessment.decision = RiskDecision.BLOCKED
        if txn and txn.status == "BLOCKED_FOR_REVIEW":
            txn.status = TransactionStatus.FAILED
        log_action(
            action=AuditAction.RISK_REVIEW_REJECTED,
            user_id=admin_user_id,
            entity_type=EntityType.TRANSACTION,
            entity_id=txn.id if txn else None,
            description=f"High-risk transaction #{txn.id if txn else ''} rejected by admin.",
        )

    db.session.commit()
    return assessment
