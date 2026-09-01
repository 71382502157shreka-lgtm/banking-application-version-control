import pytest
from app.models.version import EntityType, ChangeType
from app.models.user import Role
from app.services import auth_service, beneficiary_service, version_service


def test_beneficiary_versioning_and_diff(app, db, customer):
    b = beneficiary_service.add_beneficiary(
        customer.id,
        {
            "name": "Alice Bob",
            "account_number": "987654321012",
            "bank_name": "Test Bank",
            "ifsc": "TEST0001234",
        },
    )
    assert b.version_number == 1

    # Update beneficiary
    beneficiary_service.update_beneficiary(
        b,
        {"bank_name": "Updated Bank", "ifsc": "TEST0005678"},
        customer.id,
    )
    assert b.version_number == 2

    # Verify history
    history = version_service.get_history(EntityType.BENEFICIARY, b.id)
    assert len(history) == 2
    assert history[0].version_number == 1
    assert history[1].version_number == 2

    # Compare versions
    diff = version_service.diff_versions(EntityType.BENEFICIARY, b.id, 1, 2)
    assert diff["fields"]["bank_name"]["old"] == "Test Bank"
    assert diff["fields"]["bank_name"]["new"] == "Updated Bank"
    assert diff["fields"]["bank_name"]["status"] == "modified"


def test_transaction_restore_rejected(app, db, customer):
    with pytest.raises(ValueError, match="Transactions cannot be restored"):
        version_service.restore_version(EntityType.TRANSACTION, 1, 1, customer.id, lambda s: s)
