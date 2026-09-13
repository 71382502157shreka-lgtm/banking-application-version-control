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
from flask_migrate import Migrate

from config import config_by_name

class BaseModel:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


db = SQLAlchemy(model_class=BaseModel)
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


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
    migrate.init_app(flask_app, db)

    _configure_logging(flask_app)
    _register_blueprints(flask_app)
    _register_error_handlers(flask_app)
    _register_security_middleware(flask_app)
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
    from app.routes.auditor import auditor_bp
    from app.routes.api import api_bp
    from app.routes.errors import errors_bp
    from app.routes.reports import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auditor_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(errors_bp)
    app.register_blueprint(reports_bp)


def _register_security_middleware(app):
    from app.utils.security_utils import apply_security_headers, check_global_rate_limit
    app.before_request(check_global_rate_limit)
    app.after_request(apply_security_headers)


def _register_error_handlers(app):
    @app.errorhandler(429)
    def too_many_requests(e):
        return jsonify({
            "error": "Too Many Requests",
            "message": "Rate limit exceeded. Please try again later.",
        }), 429


def _register_user_loader():
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
