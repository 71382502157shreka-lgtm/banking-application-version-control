"""
The version-control engine.

Every mutable, versioned entity (Account, Beneficiary, user profile fields)
goes through create_version() whenever it changes. This is the single
choke point that implements the "database-level version control" required
by the project brief:

    1. snapshot old state (old_data)
    2. snapshot new state (new_data)
    3. increment version_number
    4. record who changed it and when
    5. write a matching audit log row
    6. all inside the same DB transaction as the actual data mutation

Because everything is driven off a plain dict snapshot, this same code
diffs/handles accounts, beneficiaries, and profiles without needing three
copy-pasted "AccountVersionService" / "BeneficiaryVersionService" classes.
"""
from app import db
from app.models.version import EntityVersion, ChangeType
from app.models.audit_log import AuditAction
from app.services.audit_service import log_action


def _next_version_number(entity_type: str, entity_id: int) -> int:
    last = (
        EntityVersion.query
        .filter_by(entity_type=entity_type, entity_id=entity_id)
        .order_by(EntityVersion.version_number.desc())
        .first()
    )
    return (last.version_number + 1) if last else 1


def create_version(entity_type: str, entity_id: int, change_type: str,
                    old_data: dict | None, new_data: dict | None,
                    changed_by: int | None, change_summary: str = None,
                    audit_action: str = None):
    """
    Record one version row + one matching audit log row.
    Does NOT commit — caller commits alongside the actual data change so
    both succeed or fail together.
    """
    version_number = _next_version_number(entity_type, entity_id)

    version = EntityVersion(
        entity_type=entity_type,
        entity_id=entity_id,
        version_number=version_number,
        change_type=change_type,
        change_summary=change_summary or f"{change_type} on {entity_type} #{entity_id}",
        old_data=old_data,
        new_data=new_data,
        changed_by=changed_by,
    )
    db.session.add(version)

    log_action(
        action=audit_action or AuditAction.VERSION_CREATED,
        user_id=changed_by,
        entity_type=entity_type,
        entity_id=entity_id,
        old_data=old_data,
        new_data=new_data,
        description=version.change_summary,
    )

    return version


def get_history(entity_type: str, entity_id: int):
    return (
        EntityVersion.query
        .filter_by(entity_type=entity_type, entity_id=entity_id)
        .order_by(EntityVersion.version_number.asc())
        .all()
    )


def get_version(entity_type: str, entity_id: int, version_number: int):
    return EntityVersion.query.filter_by(
        entity_type=entity_type, entity_id=entity_id, version_number=version_number
    ).first()


def diff_versions(entity_type: str, entity_id: int, version_a: int, version_b: int) -> dict:
    """
    Return a field-level diff between two versions of the same entity.
    Each field is classified as added / removed / modified / unchanged,
    which is exactly the shape the version-compare UI needs.
    """
    va = get_version(entity_type, entity_id, version_a)
    vb = get_version(entity_type, entity_id, version_b)
    if not va or not vb:
        raise ValueError("One or both versions do not exist for this entity")

    data_a = va.new_data or {}
    data_b = vb.new_data or {}

    all_keys = set(data_a.keys()) | set(data_b.keys())
    diff = {}
    for key in sorted(all_keys):
        in_a, in_b = key in data_a, key in data_b
        val_a, val_b = data_a.get(key), data_b.get(key)

        if in_a and not in_b:
            status = "removed"
        elif in_b and not in_a:
            status = "added"
        elif val_a != val_b:
            status = "modified"
        else:
            status = "unchanged"

        diff[key] = {"old": val_a, "new": val_b, "status": status}

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "version_a": va.to_dict(),
        "version_b": vb.to_dict(),
        "fields": diff,
    }


def restore_version(entity_type: str, entity_id: int, version_number: int,
                     changed_by: int, apply_fn):
    """
    Restore a non-financial entity to a prior version's snapshot.

    apply_fn(snapshot_dict) -> new_data_dict: caller-supplied function that
    actually writes the snapshot back onto the live row (so this generic
    service never needs to know Account vs Beneficiary column names).

    Financial entities (TRANSACTION) must never be routed through this
    function — see banking_service.reverse_transaction() instead.
    """
    from app.models.version import EntityType

    if entity_type == EntityType.TRANSACTION:
        raise ValueError("Transactions cannot be restored; use a reversal transaction instead")

    target = get_version(entity_type, entity_id, version_number)
    if not target:
        raise ValueError("Target version not found")

    current_state = apply_fn(target.new_data)

    create_version(
        entity_type=entity_type,
        entity_id=entity_id,
        change_type=ChangeType.RESTORE,
        old_data=target.new_data,
        new_data=current_state,
        changed_by=changed_by,
        change_summary=f"Restored to version {version_number}",
        audit_action=AuditAction.VERSION_RESTORED,
    )
    return current_state
