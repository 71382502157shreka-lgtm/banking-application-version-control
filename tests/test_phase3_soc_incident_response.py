from decimal import Decimal
import pytest
from app import db
from app.models.user import User, Role
from app.models.account import Account, AccountStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.fraud_alert import FraudAlert, FraudAlertSeverity, FraudAlertStatus
from app.models.security_incident import SecurityIncident, IncidentStatus, IncidentSeverity, AccountFreeze, FreezeType
from app.services import soc_service, mfa_service, banking_service


def login_client(client, username="admin_soc", password="password123"):
    client.get("/logout")
    return client.post("/login", data={"username": username, "password": password})


@pytest.fixture
def soc_setup(app):
    with app.app_context():
        admin = User.query.filter_by(username="admin_soc").first()
        if not admin:
            admin = User(username="admin_soc", email="admin_soc@bank.com", role=Role.ADMIN, full_name="SOC Admin")
            admin.set_password("password123")
            db.session.add(admin)

        c1 = User.query.filter_by(username="cust_soc1").first()
        if not c1:
            c1 = User(username="cust_soc1", email="cust_soc1@bank.com", role=Role.CUSTOMER, full_name="Customer SOC 1")
            c1.set_password("password123")
            db.session.add(c1)

        c2 = User.query.filter_by(username="cust_soc2").first()
        if not c2:
            c2 = User(username="cust_soc2", email="cust_soc2@bank.com", role=Role.CUSTOMER, full_name="Customer SOC 2")
            c2.set_password("password123")
            db.session.add(c2)

        db.session.commit()

        acc1 = Account.query.filter_by(user_id=c1.id).first()
        if not acc1:
            acc1 = Account(user_id=c1.id, balance=Decimal("10000.00"), available_balance=Decimal("10000.00"), status=AccountStatus.ACTIVE)
            db.session.add(acc1)

        acc2 = Account.query.filter_by(user_id=c2.id).first()
        if not acc2:
            acc2 = Account(user_id=c2.id, balance=Decimal("5000.00"), available_balance=Decimal("5000.00"), status=AccountStatus.ACTIVE)
            db.session.add(acc2)

        db.session.commit()
        return admin.id, c1.id, c2.id, acc1.id, acc2.id


def test_soc_dashboard_admin_access_and_metrics(client, soc_setup):
    admin_id, c1_id, _, _, _ = soc_setup
    login_client(client, "admin_soc")

    res = client.get("/api/v1/admin/soc/dashboard")
    assert res.status_code == 200
    data = res.get_json()
    assert "open_incidents" in data
    assert "new_fraud_alerts" in data
    assert data["system_health"] == "HEALTHY"

    # Customer user access blocked
    login_client(client, "cust_soc1")
    res2 = client.get("/api/v1/admin/soc/dashboard")
    assert res2.status_code == 403


def test_incident_creation_and_lifecycle_transitions(app, soc_setup):
    admin_id, c1_id, _, _, _ = soc_setup
    with app.app_context():
        # Create alert
        alert = FraudAlert(user_id=c1_id, alert_type="SUSPICIOUS_LOGIN", severity="HIGH", status="NEW")
        db.session.add(alert)
        db.session.commit()

        # Create Incident
        inc = soc_service.create_incident(
            title="Suspicious Multi-IP Account Access",
            description="Multiple concurrent logins detected from unrecognized ASN.",
            severity=IncidentSeverity.HIGH,
            user_id=c1_id,
            alert_ids=[alert.id],
            actor_id=admin_id
        )
        assert inc.id is not None
        assert inc.incident_number.startswith("INC-")
        assert inc.status == IncidentStatus.OPEN

        # Assign
        soc_service.assign_incident(inc.id, admin_id, admin_id)
        detail = soc_service.get_incident_detail(inc.id)
        assert detail["assigned_admin_id"] == admin_id

        # Update status
        updated = soc_service.update_incident_status(inc.id, IncidentStatus.RESOLVED, "Investigated and verified legitimate travel", admin_id)
        assert updated.status == IncidentStatus.RESOLVED
        assert updated.resolved_at is not None


def test_user_aggregated_risk_timeline(app, soc_setup):
    admin_id, c1_id, _, _, _ = soc_setup
    with app.app_context():
        timeline = soc_service.get_user_timeline(c1_id)
        assert isinstance(timeline, list)


def test_account_freeze_requires_step_up_mfa(client, soc_setup):
    admin_id, _, _, acc1_id, _ = soc_setup
    login_client(client, "admin_soc")

    # Freeze without Step-Up MFA token -> 403
    res_no_mfa = client.post(
        f"/api/v1/admin/soc/accounts/{acc1_id}/freeze",
        json={"freeze_type": FreezeType.TOTAL_FREEZE, "reason": "Suspicious activity detected"}
    )
    assert res_no_mfa.status_code == 403
    assert res_no_mfa.get_json()["step_up_required"] is True

    # Generate and verify Step-Up MFA OTP
    res_challenge = client.post("/api/v1/mfa/step-up-challenge", json={"action_type": "ADMIN_SOC_ACTION"})
    assert res_challenge.status_code == 200
    otp = res_challenge.get_json()["demo_otp"]

    res_verify = client.post("/api/v1/mfa/verify-step-up", json={"action_type": "ADMIN_SOC_ACTION", "otp_code": otp})
    token = res_verify.get_json()["step_up_token"]

    # Freeze with Step-Up MFA token -> 200
    res_freeze = client.post(
        f"/api/v1/admin/soc/accounts/{acc1_id}/freeze",
        json={"freeze_type": FreezeType.TOTAL_FREEZE, "reason": "Suspicious activity detected"},
        headers={"X-Step-Up-Token": token}
    )
    assert res_freeze.status_code == 200
    assert res_freeze.get_json()["is_active"] is True


def test_frozen_account_transfer_rejection(app, soc_setup):
    admin_id, c1_id, _, acc1_id, acc2_id = soc_setup
    with app.app_context():
        acc1 = db.session.get(Account, acc1_id)
        acc2 = db.session.get(Account, acc2_id)

        # Freeze acc1
        soc_service.freeze_account(acc1.id, FreezeType.TOTAL_FREEZE, "Security Lock", admin_id)

        # Attempt transfer from frozen acc1
        with pytest.raises(Exception, match="frozen"):
            banking_service.transfer(acc1, acc2, Decimal("100.00"), "Transfer from frozen", c1_id)

        # Unfreeze acc1
        soc_service.unfreeze_account(acc1.id, "Security Investigation Passed", admin_id)
        db.session.refresh(acc1)
        assert acc1.status == AccountStatus.ACTIVE


def test_account_unfreeze_workflow(client, soc_setup):
    admin_id, _, _, acc1_id, _ = soc_setup
    login_client(client, "admin_soc")

    # Step-Up MFA for Freeze
    c1 = client.post("/api/v1/mfa/step-up-challenge", json={"action_type": "ADMIN_SOC_ACTION"})
    t1 = client.post("/api/v1/mfa/verify-step-up", json={"action_type": "ADMIN_SOC_ACTION", "otp_code": c1.get_json()["demo_otp"]}).get_json()["step_up_token"]
    client.post(f"/api/v1/admin/soc/accounts/{acc1_id}/freeze", json={"reason": "Freeze for test"}, headers={"X-Step-Up-Token": t1})

    # Step-Up MFA for Unfreeze
    c2 = client.post("/api/v1/mfa/step-up-challenge", json={"action_type": "ADMIN_SOC_ACTION"})
    t2 = client.post("/api/v1/mfa/verify-step-up", json={"action_type": "ADMIN_SOC_ACTION", "otp_code": c2.get_json()["demo_otp"]}).get_json()["step_up_token"]

    res_unfreeze = client.post(
        f"/api/v1/admin/soc/accounts/{acc1_id}/unfreeze",
        json={"reason": "Unfreeze after verification"},
        headers={"X-Step-Up-Token": t2}
    )
    assert res_unfreeze.status_code == 200
    assert res_unfreeze.get_json()["status"] == AccountStatus.ACTIVE


def test_transaction_release_from_hold_with_step_up(client, soc_setup):
    admin_id, c1_id, _, acc1_id, acc2_id = soc_setup
    login_client(client, "admin_soc")

    with client.application.app_context():
        acc1 = db.session.get(Account, acc1_id)
        acc2 = db.session.get(Account, acc2_id)
        # Create held transaction
        debit_txn = Transaction(
            account_id=acc1.id,
            transaction_type=TransactionType.TRANSFER,
            transaction_mode="TRANSFER",
            amount=Decimal("1500.00"),
            description="[REVIEW REQUIRED] High risk transfer",
            status="BLOCKED_FOR_REVIEW",
            counterparty_account_id=acc2.id,
            balance_after=acc1.balance,
        )
        db.session.add(debit_txn)
        db.session.commit()
        txn_id = debit_txn.id

    # Release without Step-Up -> 403
    res_no_token = client.post(f"/api/v1/admin/soc/transactions/{txn_id}/release", json={"notes": "Release test"})
    assert res_no_token.status_code == 403

    # Step-Up MFA Token
    c = client.post("/api/v1/mfa/step-up-challenge", json={"action_type": "ADMIN_SOC_ACTION"})
    t = client.post("/api/v1/mfa/verify-step-up", json={"action_type": "ADMIN_SOC_ACTION", "otp_code": c.get_json()["demo_otp"]}).get_json()["step_up_token"]

    # Release with Step-Up Token -> 200
    res_release = client.post(
        f"/api/v1/admin/soc/transactions/{txn_id}/release",
        json={"notes": "Release test"},
        headers={"X-Step-Up-Token": t}
    )
    assert res_release.status_code == 200
    assert res_release.get_json()["debit"]["status"] == TransactionStatus.COMPLETED


def test_transaction_rejection_workflow(client, soc_setup):
    admin_id, c1_id, _, acc1_id, acc2_id = soc_setup
    login_client(client, "admin_soc")

    with client.application.app_context():
        acc1 = db.session.get(Account, acc1_id)
        acc2 = db.session.get(Account, acc2_id)
        debit_txn = Transaction(
            account_id=acc1.id,
            transaction_type=TransactionType.TRANSFER,
            transaction_mode="TRANSFER",
            amount=Decimal("500.00"),
            description="[REVIEW REQUIRED] Suspicious transfer",
            status="BLOCKED_FOR_REVIEW",
            counterparty_account_id=acc2.id,
            balance_after=acc1.balance,
        )
        db.session.add(debit_txn)
        db.session.commit()
        txn_id = debit_txn.id

    res_reject = client.post(
        f"/api/v1/admin/soc/transactions/{txn_id}/reject",
        json={"reason": "Confirmed unauthorized attempt"}
    )
    assert res_reject.status_code == 200
    assert res_reject.get_json()["status"] == TransactionStatus.FAILED


def test_false_positive_alert_review(client, soc_setup):
    admin_id, c1_id, _, _, _ = soc_setup
    login_client(client, "admin_soc")

    with client.application.app_context():
        alert = FraudAlert(user_id=c1_id, alert_type="DUPLICATE_ATTEMPT", severity="MEDIUM", status="NEW")
        db.session.add(alert)
        db.session.commit()
        alert_id = alert.id

    res_fp = client.post(
        f"/api/v1/admin/soc/alerts/{alert_id}/mark-false-positive",
        json={"notes": "User confirmed intentional burst transfers"}
    )
    assert res_fp.status_code == 200
    assert res_fp.get_json()["status"] == FraudAlertStatus.DISMISSED


def test_evidence_snapshot_integrity_verification(app, soc_setup):
    admin_id, c1_id, _, _, _ = soc_setup
    with app.app_context():
        inc = soc_service.create_incident(
            title="Evidence Integrity Test",
            description="Testing SHA-256 evidence digest calculation",
            severity=IncidentSeverity.MEDIUM,
            user_id=c1_id,
            actor_id=admin_id
        )

        bundle = soc_service.export_evidence_bundle(inc.id)
        assert "digest_sha256" in bundle
        assert len(bundle["digest_sha256"]) == 64  # Valid SHA-256 hex length
