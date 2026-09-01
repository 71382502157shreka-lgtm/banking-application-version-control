from datetime import datetime

from app import db


class EntityType:
    ACCOUNT = "ACCOUNT"
    BENEFICIARY = "BENEFICIARY"
    USER_PROFILE = "USER_PROFILE"
    TRANSACTION = "TRANSACTION"


class ChangeType:
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    RESTORE = "RESTORE"


class EntityVersion(db.Model):
    """
    A single, generic version table used for every versioned entity
    (accounts, beneficiaries, user profiles, and — for read-only history
    purposes only — transactions). Using one polymorphic table instead of
    N per-entity tables keeps the version-control engine (see
    services/version_service.py) entity-agnostic: one code path creates,
    lists, and diffs versions for any entity_type/entity_id pair.

    old_data / new_data store full JSON snapshots so any two versions can
    be diffed directly without replaying history.
    """
    __tablename__ = "entity_versions"

    id = db.Column(db.Integer, primary_key=True)

    entity_type = db.Column(db.String(30), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False)

    change_type = db.Column(db.String(20), nullable=False)
    change_summary = db.Column(db.String(255))

    old_data = db.Column(db.JSON, nullable=True)
    new_data = db.Column(db.JSON, nullable=True)

    changed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint("entity_type", "entity_id", "version_number", name="uq_entity_version"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "version_number": self.version_number,
            "change_type": self.change_type,
            "change_summary": self.change_summary,
            "old_data": self.old_data,
            "new_data": self.new_data,
            "changed_by": self.changed_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
