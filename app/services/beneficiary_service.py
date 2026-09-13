from datetime import datetime, timedelta
from app import db
from app.models.beneficiary import Beneficiary, BeneficiaryStatus
from app.models.account import Account
from app.models.audit_log import AuditAction
from app.models.version import EntityType, ChangeType
from app.services.version_service import create_version
from app.utils.validators import require_fields, validate_ifsc, validate_account_number, ValidationError


def add_beneficiary(user_id: int, data: dict, cool_off_minutes: int = 30) -> Beneficiary:
    require_fields(data, ["name", "account_number", "bank_name", "ifsc"])

    name = str(data["name"]).strip()
    bank_name = str(data["bank_name"]).strip()
    account_number = str(data["account_number"]).strip()
    ifsc = str(data["ifsc"]).strip().upper()

    if not name:
        raise ValidationError("Beneficiary name is required", field="name")
    if not bank_name:
        raise ValidationError("Bank name is required", field="bank_name")

    validate_account_number(account_number)
    validate_ifsc(ifsc)

    if "confirm_account_number" in data:
        confirm_acc = str(data["confirm_account_number"]).strip()
        if account_number != confirm_acc:
            raise ValidationError("Account number and confirmation do not match", field="confirm_account_number")

    # Prevent adding own account
    own_acc = Account.query.filter_by(user_id=user_id, account_number=account_number).first()
    if own_acc:
        raise ValidationError("Cannot add your own account as a beneficiary", field="account_number")

    # Prevent duplicate beneficiary
    existing = Beneficiary.query.filter_by(user_id=user_id, account_number=account_number, status=BeneficiaryStatus.ACTIVE).first()
    if existing:
        raise ValidationError("Beneficiary with this account number already exists", field="account_number")

    beneficiary = Beneficiary(
        user_id=user_id,
        name=name,
        account_number=account_number,
        bank_name=bank_name,
        ifsc=ifsc,
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
        change_summary=f"Beneficiary added ({cool_off_minutes}m cooling-off)",
        audit_action=AuditAction.BENEFICIARY_CREATED,
    )
    try:
        from app.models.behavioral_profile import UserBehavioralProfile
        profile = UserBehavioralProfile.get_or_create(user_id)
        profile.record_beneficiary_added()
    except Exception:
        pass

    db.session.commit()
    return beneficiary


def update_beneficiary(beneficiary: Beneficiary, data: dict, actor_user_id: int) -> Beneficiary:
    if beneficiary.user_id != actor_user_id:
        raise ValidationError("Unauthorized beneficiary modification", field="user_id")

    old_data = beneficiary.to_dict()

    if "name" in data:
        name = str(data["name"]).strip()
        if not name:
            raise ValidationError("Beneficiary name cannot be empty", field="name")
        beneficiary.name = name

    if "bank_name" in data:
        bank = str(data["bank_name"]).strip()
        if not bank:
            raise ValidationError("Bank name cannot be empty", field="bank_name")
        beneficiary.bank_name = bank

    if "account_number" in data:
        account_number = str(data["account_number"]).strip()
        validate_account_number(account_number)

        if "confirm_account_number" in data:
            confirm_acc = str(data["confirm_account_number"]).strip()
            if account_number != confirm_acc:
                raise ValidationError("Account number and confirmation do not match", field="confirm_account_number")

        # Check own account
        own_acc = Account.query.filter_by(user_id=actor_user_id, account_number=account_number).first()
        if own_acc:
            raise ValidationError("Cannot add your own account as a beneficiary", field="account_number")

        # Check duplicate other beneficiary
        existing = Beneficiary.query.filter(
            Beneficiary.user_id == actor_user_id,
            Beneficiary.account_number == account_number,
            Beneficiary.id != beneficiary.id,
            Beneficiary.status == BeneficiaryStatus.ACTIVE,
        ).first()
        if existing:
            raise ValidationError("Beneficiary with this account number already exists", field="account_number")

        beneficiary.account_number = account_number

    if "ifsc" in data:
        ifsc = str(data["ifsc"]).strip().upper()
        validate_ifsc(ifsc)
        beneficiary.ifsc = ifsc

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
    if beneficiary.user_id != actor_user_id:
        raise ValidationError("Unauthorized beneficiary action", field="user_id")

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

