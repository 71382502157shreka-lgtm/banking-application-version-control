"""
Executive Reports & System Diagnostics Blueprint for BankVCS 2.0.
Provides RESTful & Web endpoints for downloading financial reports, risk telemetry,
audit chain CSV exports, and entity version analytics.
"""

from flask import Blueprint, jsonify, Response, request
from flask_login import login_required, current_user

from app.models.user import Role
from app.services import report_service, telemetry_service, version_analytics_service
from app.utils.decorators import roles_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/executive-summary", methods=["GET"])
@login_required
@roles_required(Role.ADMIN, Role.EMPLOYEE)
def executive_summary():
    """Returns JSON executive summary report for staff and admins."""
    report = report_service.generate_executive_summary_report()
    return jsonify({"success": True, "report": report}), 200


@reports_bp.route("/executive-summary/text", methods=["GET"])
@login_required
@roles_required(Role.ADMIN, Role.EMPLOYEE)
def executive_summary_text():
    """Returns formatted plain-text executive summary report for downloading."""
    text_report = report_service.export_executive_summary_text()
    return Response(
        text_report,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment;filename=BankVCS_Executive_Summary.txt"}
    )


@reports_bp.route("/audit-log/export-csv", methods=["GET"])
@login_required
@roles_required(Role.ADMIN)
def export_audit_csv():
    """Exports full SHA-256 audit ledger as CSV for Administrators."""
    csv_data = report_service.export_audit_log_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=BankVCS_Audit_Ledger.csv"}
    )


@reports_bp.route("/risk-telemetry", methods=["GET"])
@login_required
@roles_required(Role.ADMIN, Role.EMPLOYEE)
def risk_telemetry():
    """Returns detailed risk engine telemetry report."""
    telemetry = report_service.generate_risk_telemetry_report()
    return jsonify({"success": True, "telemetry": telemetry}), 200


@reports_bp.route("/security-telemetry", methods=["GET"])
@login_required
@roles_required(Role.ADMIN)
def security_telemetry():
    """Returns system security telemetry report for Administrators."""
    telemetry = telemetry_service.generate_security_telemetry_summary()
    return jsonify({"success": True, "security_telemetry": telemetry}), 200


@reports_bp.route("/customer/<int:customer_id>", methods=["GET"])
@login_required
def customer_portfolio(customer_id):
    """Returns customer portfolio report for authorized user or staff."""
    if current_user.role == Role.CUSTOMER and current_user.id != customer_id:
        from flask import abort
        abort(403)
    
    try:
        portfolio = report_service.generate_customer_portfolio_summary(customer_id)
        return jsonify({"success": True, "portfolio": portfolio}), 200
    except ValueError as err:
        return jsonify({"success": False, "error": str(err)}), 404


@reports_bp.route("/version-analytics", methods=["GET"])
@login_required
@roles_required(Role.ADMIN, Role.EMPLOYEE)
def version_analytics():
    """Returns entity version control analytics summary."""
    analytics = version_analytics_service.generate_version_analytics_summary()
    return jsonify({"success": True, "analytics": analytics}), 200
