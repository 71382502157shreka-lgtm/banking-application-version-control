from app import db
from app.models.beneficiary import Beneficiary, BeneficiaryStatus
from app.models.audit_log import AuditAction
from app.models.version import EntityType, ChangeType
from app.services.version_service import create_version
from app.utils.validators import require_fields, validate_ifsc, ValidationError


def add_beneficiary(user_id: int, data: dict) -> Beneficiary:
    require_fields(data, ["name", "account_number", "bank_name", "ifsc"])
    validate_ifsc(data["ifsc"])

    beneficiary = Beneficiary(
        user_id=user_id,
        name=data["name"],
        account_number=data["account_number"],
        bank_name=data["bank_name"],
        ifsc=data["ifsc"].upper(),
    )
    db.session.add(beneficiary)
    db.session.flush()

    create_version(
        entity_type=EntityType.BENEFICIARY,
        entity_id=beneficiary.id,
        change_type=ChangeType.CREATE,
        old_data=None,
        new_data=beneficiary.to_dict(),
        changed_by=user_id,
        change_summary="Beneficiary added",
        audit_action=AuditAction.BENEFICIARY_CREATED,
    )
    db.session.commit()
    return beneficiary


def update_beneficiary(beneficiary: Beneficiary, data: dict, actor_user_id: int) -> Beneficiary:
    old_data = beneficiary.to_dict()

    if "name" in data:
        beneficiary.name = data["name"]
    if "account_number" in data:
        beneficiary.account_number = data["account_number"]
    if "bank_name" in data:
        beneficiary.bank_name = data["bank_name"]
    if "ifsc" in data:
        validate_ifsc(data["ifsc"])
        beneficiary.ifsc = data["ifsc"].upper()

    beneficiary.version_number += 1
    new_data = beneficiary.to_dict()

    create_version(
        entity_type=EntityType.BENEFICIARY,
        entity_id=beneficiary.id,
        change_type=ChangeType.UPDATE,
        old_data=old_data,
        new_data=new_data,
        changed_by=actor_user_id,
        change_summary="Beneficiary details updated",
        audit_action=AuditAction.BENEFICIARY_UPDATED,
    )
    db.session.commit()
    return beneficiary


def deactivate_beneficiary(beneficiary: Beneficiary, actor_user_id: int) -> Beneficiary:
    old_data = beneficiary.to_dict()
    beneficiary.status = BeneficiaryStatus.INACTIVE
    beneficiary.version_number += 1
    new_data = beneficiary.to_dict()

    create_version(
        entity_type=EntityType.BENEFICIARY,
        entity_id=beneficiary.id,
        change_type=ChangeType.DELETE,
        old_data=old_data,
        new_data=new_data,
        changed_by=actor_user_id,
        change_summary="Beneficiary deactivated",
        audit_action=AuditAction.BENEFICIARY_DELETED,
    )
    db.session.commit()
    return beneficiary
