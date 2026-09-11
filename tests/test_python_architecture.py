"""
Unit tests for Python-first architecture components:
- Field diff utility (app.utils.diff)
- Formatting utility (app.utils.formatting)
- Statement service (app.services.statement_service)
- Notification service (app.services.notification_service)
- Security service (app.services.security_service)
- Risk service (app.services.risk_service)
- Error handlers (app.routes.errors)
- Python SDK wrapper (bankvcs)
"""
import pytest
from datetime import datetime, timedelta
from app.utils.diff import compute_field_diff
from app.utils.formatting import format_currency, mask_account_number, format_datetime
from app import create_app, db
from app.models.user import User
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.notification import Notification
from app.models.security_session import SecurityEvent
from app.services.statement_service import generate_account_statement, export_statement_csv
from app.services.notification_service import create_notification, get_user_notifications, mark_all_read
from app.services.security_service import log_security_event, verify_session_validity
from app.services.risk_service import evaluate_transaction_risk
import bankvcs


@pytest.fixture
def app_instance():
    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


def test_diff_utilities():
    v1 = {"balance": 1000.0, "status": "active", "holder_name": "Alice"}
    v2 = {"balance": 1500.0, "status": "active", "holder_name": "Alice Smith"}

    diffs = compute_field_diff(v1, v2)
    assert len(diffs) == 3
    assert diffs["balance"]["status"] == "modified"
    assert diffs["balance"]["old"] == 1000.0
    assert diffs["balance"]["new"] == 1500.0
    assert diffs["holder_name"]["status"] == "modified"
    assert diffs["status"]["status"] == "unchanged"


def test_formatting_utilities():
    assert format_currency(1234.56, "Rs. ") == "Rs. 1,234.56"
    assert format_currency(0, "Rs. ") == "Rs. 0.00"

    masked = mask_account_number("ACC1234567890")
    assert "7890" in masked
    assert "XXXX" in masked

    now = datetime(2026, 9, 11, 12, 0, 0)
    assert "2026" in format_datetime(now)
    assert format_datetime(None) == "N/A"


def test_notification_service(app_instance):
    with app_instance.app_context():
        user = User(username="notif_user", email="notif@example.com", role="customer")
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()

        n1 = create_notification(user.id, "Welcome", "Welcome to BankVCS 2.0", "INFO")
        assert n1.id is not None
        assert n1.is_read is False

        n2 = create_notification(user.id, "Security Alert", "New login detected", "SECURITY")
        db.session.commit()

        notifs = get_user_notifications(user.id)
        assert len(notifs) == 2

        count = mark_all_read(user.id)
        assert count == 2

        unread = get_user_notifications(user.id, unread_only=True)
        assert len(unread) == 0


def test_security_service(app_instance):
    with app_instance.app_context():
        user = User(username="sec_user", email="sec@example.com", role="customer")
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()

        event = log_security_event(user.id, "TEST_EVENT", "127.0.0.1", "pytest-agent", {"detail": "unit test"})
        assert event.id is not None
        assert event.event_type == "TEST_EVENT"

        valid = verify_session_validity(user.id)
        assert valid is True


def test_risk_service(app_instance):
    with app_instance.app_context():
        sender = User(username="risk_sender", email="rsender@example.com", role="customer")
        sender.set_password("Password123!")
        db.session.add(sender)
        db.session.commit()

        acc = Account(account_number="ACC_RISK_01", user_id=sender.id, balance=50000.0, status="ACTIVE")
        db.session.add(acc)
        db.session.commit()

        # High amount to new beneficiary -> should evaluate risk score
        res = evaluate_transaction_risk(sender.id, acc.id, "ACC_BENEF_99", 35000.0)
        assert "risk_score" in res
        assert "risk_level" in res
        assert "decision" in res
        assert res["risk_score"] > 0


def test_statement_service(app_instance):
    with app_instance.app_context():
        user = User(username="stmt_user", email="stmt@example.com", role="customer")
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()

        acc = Account(account_number="ACC_STMT_01", user_id=user.id, balance=10000.0, status="ACTIVE")
        db.session.add(acc)
        db.session.commit()

        tx1 = Transaction(
            reference_number="TX_STMT_1",
            account_id=acc.id,
            transaction_type="DEPOSIT",
            amount=5000.0,
            balance_after=15000.0,
            status="COMPLETED"
        )
        db.session.add(tx1)
        db.session.commit()

        stmt_data = generate_account_statement(acc.id)
        assert stmt_data["success"] is True
        assert len(stmt_data["transactions"]) == 1

        csv_str = export_statement_csv(acc.id)
        assert "Reference" in csv_str
        assert "TX_STMT_1" in csv_str


def test_error_handlers(client):
    res_404 = client.get("/nonexistent-page-url-12345")
    assert res_404.status_code == 404
    assert b"404" in res_404.data

    res_api_404 = client.get("/api/nonexistent-endpoint")
    assert res_api_404.status_code == 404
    assert res_api_404.is_json
    assert res_api_404.json["error"] == "Resource not found"


def test_bankvcs_sdk_import():
    api = bankvcs.BankVCSAPI()
    assert api is not None
