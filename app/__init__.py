"""
Application factory. Keeps extension objects module-level so models/services
can import `db` without circular imports, while initialization is deferred
to create_app().
"""
import logging
import os

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from config import config_by_name

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "development")

    flask_app = Flask(__name__, instance_relative_config=True)
    flask_app.config.from_object(config_by_name[config_name])

    os.makedirs(flask_app.instance_path, exist_ok=True)

    db.init_app(flask_app)
    login_manager.init_app(flask_app)
    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"
    csrf.init_app(flask_app)

    _configure_logging(flask_app)
    _register_blueprints(flask_app)
    _register_error_handlers(flask_app)
    _register_user_loader()

    with flask_app.app_context():
        from app import models  # noqa: F401
        db.create_all()

    return flask_app


def _configure_logging(app):
    log_dir = os.path.join(app.instance_path, "logs")
    os.makedirs(log_dir, exist_ok=True)
    handler = logging.FileHandler(os.path.join(log_dir, "app.log"))
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def _register_blueprints(app):
    from app.routes.auth import auth_bp
    from app.routes.customer import customer_bp
    from app.routes.employee import employee_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.api_v1 import api_v1_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")


def _register_error_handlers(app):
    from flask import request, render_template
    from flask_login import current_user
    from app.services.audit_service import log_action
    from app.models.audit_log import AuditAction

    @app.errorhandler(401)
    def unauthorized(e):
        if request.path.startswith('/api') or not request.accept_mimetypes.accept_html:
            return jsonify(error="Unauthorized access"), 401
        return render_template("errors/403.html"), 401

    @app.errorhandler(403)
    def forbidden(e):
        user_id = current_user.id if current_user and current_user.is_authenticated else None
        role = current_user.role if current_user and current_user.is_authenticated else "anonymous"
        log_action(
            AuditAction.SECURITY_EVENT,
            user_id=user_id,
            description=f"Access denied [403 Forbidden] for role '{role}' on route '{request.path}' [{request.method}]"
        )
        db.session.commit()

        if request.path.startswith('/api') or not request.accept_mimetypes.accept_html:
            return jsonify(error="You do not have permission to perform this action"), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api') or not request.accept_mimetypes.accept_html:
            return jsonify(error="Resource not found"), 404
        return render_template("errors/403.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server error")
        if request.path.startswith('/api') or not request.accept_mimetypes.accept_html:
            return jsonify(error="An unexpected error occurred. Please try again."), 500
        return render_template("errors/403.html"), 500


def _register_user_loader():
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
