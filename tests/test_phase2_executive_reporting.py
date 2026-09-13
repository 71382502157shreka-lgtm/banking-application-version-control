"""
Phase 2 - Feature 8 Automated Test Suite:
Executive Reporting, System Version Analytics, & Compliance Telemetry Center.

Tests Executive JSON/Text summaries, CSV Audit Ledger exports, Risk/Security Telemetry,
Version Control Analytics, and Customer Portfolio reports with IDOR protection.
"""

import pytest
from app import db
from app.models.user import User, Role
from app.models.account import AccountType
from app.models.security_session import LoginSession, SecurityEvent
from app.services import auth_service, banking_service, beneficiary_service, report_service


def test_executive_summary_json_endpoint(client, app):
    """Test GET /reports/executive-summary for authorized admin and employee roles."""
    with app.app_context():
        admin = auth_service.register_user("exadmin", "exadmin@bank.com", "Pass1234!", "Exec Admin", role=Role.ADMIN)
        cust = auth_service.register_user("excust", "excust@bank.com", "Pass1234!", "Exec Cust", role=Role.CUSTOMER)
        acc = banking_service.create_account(cust.id, AccountType.SAVINGS)
        banking_service.deposit(acc, 5000.0, "Initial Seed Deposit", admin.id)

    # Login as Admin
    client.post("/login", data={"username": "exadmin", "password": "Pass1234!"}, follow_redirects=True)

    resp = client.get("/reports/executive-summary")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    report = data["report"]
    assert "users_summary" in report
    assert report["users_summary"]["customers"] >= 1
    assert report["financial_summary"]["total_accounts"] >= 1
    assert report["financial_summary"]["total_system_balance"] >= 5000.0
    assert report["audit_integrity"]["chain_valid"] is True


def test_executive_summary_text_download(client, app):
    """Test GET /reports/executive-summary/text formatting and download headers."""
    with app.app_context():
        auth_service.register_user("exadmin2", "exadmin2@bank.com", "Pass1234!", "Exec Admin 2", role=Role.ADMIN)

    client.post("/login", data={"username": "exadmin2", "password": "Pass1234!"}, follow_redirects=True)

    resp = client.get("/reports/executive-summary/text")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith("text/plain")
    assert "attachment;filename=BankVCS_Executive_Summary.txt" in resp.headers["Content-Disposition"]
    body = resp.get_data(as_text=True)
    assert "BANKVCS 2.0 - EXECUTIVE FINANCIAL REPORT" in body
    assert "FINANCIAL LEDGER" in body
    assert "DATABASE VERSION CONTROL (VCS) LEDGER" in body


def test_audit_ledger_csv_export(client, app):
    """Test GET /reports/audit-log/export-csv for SHA-256 audit ledger CSV export."""
    with app.app_context():
        auth_service.register_user("csvadmin", "csvadmin@bank.com", "Pass1234!", "CSV Admin", role=Role.ADMIN)

    client.post("/login", data={"username": "csvadmin", "password": "Pass1234!"}, follow_redirects=True)

    resp = client.get("/reports/audit-log/export-csv")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith("text/csv")
    assert "attachment;filename=BankVCS_Audit_Ledger.csv" in resp.headers["Content-Disposition"]
    
    csv_text = resp.get_data(as_text=True)
    assert "Log_ID,Timestamp,User_ID,Action,Entity_Type,Entity_ID,Description,IP_Address,Hash,Previous_Hash" in csv_text


def test_risk_telemetry_endpoint(client, app):
    """Test GET /reports/risk-telemetry risk engine metrics endpoint."""
    with app.app_context():
        auth_service.register_user("riskemp", "riskemp@bank.com", "Pass1234!", "Risk Emp", role=Role.EMPLOYEE)

    client.post("/login", data={"username": "riskemp", "password": "Pass1234!"}, follow_redirects=True)

    resp = client.get("/reports/risk-telemetry")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    telemetry = data["telemetry"]
    assert "total_evaluations" in telemetry
    assert "risk_level_breakdown" in telemetry
    assert "decision_breakdown" in telemetry
    assert "frequent_risk_factors" in telemetry


def test_security_telemetry_endpoint(client, app):
    """Test GET /reports/security-telemetry for security events and active session metrics."""
    with app.app_context():
        sec_admin = auth_service.register_user("secadmin", "secadmin@bank.com", "Pass1234!", "Sec Admin", role=Role.ADMIN)
        LoginSession.create_session(sec_admin.id, "127.0.0.1", "Pytest Client")
        evt = SecurityEvent(user_id=sec_admin.id, event_type="LOGIN_SUCCESS", severity="INFO", description="Admin logged in", ip_address="127.0.0.1")
        db.session.add(evt)
        db.session.commit()

    client.post("/login", data={"username": "secadmin", "password": "Pass1234!"}, follow_redirects=True)

    resp = client.get("/reports/security-telemetry")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    sec_telem = data["security_telemetry"]
    assert "sessions" in sec_telem
    assert "security_events" in sec_telem
    assert sec_telem["sessions"]["total_tracked_sessions"] >= 1


def test_version_analytics_endpoint(client, app):
    """Test GET /reports/version-analytics for entity version snapshots and trajectories."""
    with app.app_context():
        auth_service.register_user("vanalyst", "vanalyst@bank.com", "Pass1234!", "V Analyst", role=Role.EMPLOYEE)

    client.post("/login", data={"username": "vanalyst", "password": "Pass1234!"}, follow_redirects=True)

    resp = client.get("/reports/version-analytics")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    analytics = data["analytics"]
    assert "total_snapshots_recorded" in analytics
    assert "snapshot_distribution_by_entity" in analytics


def test_customer_portfolio_report_access_and_idor_protection(client, app):
    """
    Test customer portfolio report:
    - Customer 1 can access their own portfolio.
    - Customer 1 is DENIED (403) when attempting to access Customer 2's portfolio.
    - Admin/Employee can access any customer's portfolio.
    """
    with app.app_context():
        c1 = auth_service.register_user("portcust1", "portcust1@bank.com", "Pass1234!", "Port Cust 1", role=Role.CUSTOMER)
        c2 = auth_service.register_user("portcust2", "portcust2@bank.com", "Pass1234!", "Port Cust 2", role=Role.CUSTOMER)
        emp = auth_service.register_user("portemp", "portemp@bank.com", "Pass1234!", "Port Emp", role=Role.EMPLOYEE)
        
        a1 = banking_service.create_account(c1.id, AccountType.SAVINGS)
        banking_service.deposit(a1, 1200.0, "c1 deposit", emp.id)
        
        c1_id, c2_id = c1.id, c2.id

    # 1. Customer 1 logs in and requests own portfolio
    client.post("/login", data={"username": "portcust1", "password": "Pass1234!"}, follow_redirects=True)
    resp_own = client.get(f"/reports/customer/{c1_id}")
    assert resp_own.status_code == 200
    data_own = resp_own.get_json()
    assert data_own["success"] is True
    assert data_own["portfolio"]["customer"]["id"] == c1_id
    assert data_own["portfolio"]["financial_summary"]["total_balance"] == 1200.0

    # 2. Customer 1 attempts IDOR access to Customer 2's portfolio -> 403 Forbidden
    resp_idor = client.get(f"/reports/customer/{c2_id}")
    assert resp_idor.status_code == 403

    # 3. Employee logs in and requests Customer 1's portfolio -> 200 OK
    client.get("/logout", follow_redirects=True)
    client.post("/login", data={"username": "portemp", "password": "Pass1234!"}, follow_redirects=True)
    resp_emp = client.get(f"/reports/customer/{c1_id}")
    assert resp_emp.status_code == 200
    assert resp_emp.get_json()["portfolio"]["customer"]["id"] == c1_id


def test_unauthorized_reports_access_prevention(client, app):
    """Test that customer role cannot access admin-only reports (CSV audit export & security telemetry)."""
    with app.app_context():
        auth_service.register_user("plaincust", "plaincust@bank.com", "Pass1234!", "Plain Cust", role=Role.CUSTOMER)

    client.post("/login", data={"username": "plaincust", "password": "Pass1234!"}, follow_redirects=True)

    # Customer accessing admin CSV export -> 403
    resp_csv = client.get("/reports/audit-log/export-csv")
    assert resp_csv.status_code == 403

    # Customer accessing security telemetry -> 403
    resp_sec = client.get("/reports/security-telemetry")
    assert resp_sec.status_code == 403


def test_empty_reports_graceful_handling(client, app):
    """Test that report service functions handle an empty database gracefully without crashing."""
    with app.app_context():
        summary = report_service.generate_executive_summary_report()
        assert summary["financial_summary"]["total_system_balance"] >= 0.0
        assert summary["users_summary"]["total_users"] >= 0

        txt_report = report_service.export_executive_summary_text()
        assert len(txt_report) > 0

        csv_report = report_service.export_audit_log_csv()
        assert "Log_ID" in csv_report


def test_invalid_customer_portfolio_404(client, app):
    """Test GET /reports/customer/99999 for a non-existent customer ID returns 404."""
    with app.app_context():
        auth_service.register_user("admin99", "admin99@bank.com", "Pass1234!", "Admin 99", role=Role.ADMIN)

    client.post("/login", data={"username": "admin99", "password": "Pass1234!"}, follow_redirects=True)
    resp = client.get("/reports/customer/999999")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["success"] is False
    assert "not found" in data["error"].lower()
