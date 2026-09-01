import pytest
from decimal import Decimal
from app import create_app, db
from app.models.user import User, Role
from app.models.account import Account, AccountType
from app.models.beneficiary import Beneficiary
from app.models.notification import Notification
from app.models.version import EntityVersion, EntityType
from app.services import auth_service, banking_service, beneficiary_service, version_service


@pytest.fixture
def app_instance():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_customer_account_and_deposit_workflow(app_instance):
    with app_instance.app_context():
        user = auth_service.register_user("testuser", "test@bank.com", "SecretPass123", "Test User", "9876543210")
        account = banking_service.create_account(user.id, AccountType.SAVINGS)
        assert account.balance == Decimal("0.00")
        assert account.version_number == 1

        # Deposit
        txn = banking_service.deposit(account, 5000, "Initial Deposit", user.id)
        assert account.balance == Decimal("5000.00")
        assert account.version_number == 2
        assert txn.amount == Decimal("5000.00")

        # Notification check
        notifs = Notification.query.filter_by(user_id=user.id).all()
        assert len(notifs) >= 1
        assert any("Deposit" in n.title for n in notifs)


def test_transfer_creates_dual_versions(app_instance):
    with app_instance.app_context():
        user1 = auth_service.register_user("alice", "alice@bank.com", "Password123", "Alice Smith")
        user2 = auth_service.register_user("bob", "bob@bank.com", "Password123", "Bob Jones")

        acc1 = banking_service.create_account(user1.id, AccountType.SAVINGS)
        acc2 = banking_service.create_account(user2.id, AccountType.CURRENT)

        banking_service.deposit(acc1, 10000, "Deposit to Alice", user1.id)
        assert acc1.balance == Decimal("10000.00")

        debit, credit = banking_service.transfer(acc1, acc2, 3000, "Payment to Bob", user1.id)
        assert acc1.balance == Decimal("7000.00")
        assert acc2.balance == Decimal("3000.00")
        assert acc1.version_number == 3  # create(1) + deposit(2) + transfer(3)
        assert acc2.version_number == 2  # create(1) + transfer(2)

        # Verify EntityVersions
        versions_acc1 = EntityVersion.query.filter_by(entity_type=EntityType.ACCOUNT, entity_id=acc1.id).all()
        assert len(versions_acc1) == 3


def test_profile_update_and_version_diff(app_instance):
    with app_instance.app_context():
        user = auth_service.register_user("charlie", "charlie@bank.com", "Password123", "Charlie Old")
        auth_service.update_profile(user, full_name="Charlie New", phone="9988776655", email="new@bank.com")

        # Get diff
        diff = version_service.diff_versions(EntityType.USER_PROFILE, user.id, 1, 2)
        assert "full_name" in diff["fields"]
        assert diff["fields"]["full_name"]["old"] == "Charlie Old"
        assert diff["fields"]["full_name"]["new"] == "Charlie New"
        assert diff["fields"]["full_name"]["status"] == "modified"
