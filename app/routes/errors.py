"""
Error handling blueprint for rendering server-side Jinja2 error templates or JSON error responses.
"""
from flask import Blueprint, render_template, request, jsonify

errors_bp = Blueprint("errors", __name__)


@errors_bp.app_errorhandler(404)
def not_found_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Resource not found"}), 404
    return render_template("errors/404.html", error=error), 404


@errors_bp.app_errorhandler(403)
def forbidden_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "You do not have permission to perform this action"}), 403
    return render_template("errors/403.html", error=error), 403


@errors_bp.app_errorhandler(500)
def internal_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "An unexpected server error occurred"}), 500
    return render_template("errors/500.html", error=error), 500
