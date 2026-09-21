from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user

from app.models.user import Role
from app.services import auth_service
from app.utils.validators import ValidationError

auth_bp = Blueprint("auth", __name__)


def get_role_dashboard(role):
    if role == Role.CUSTOMER:
        return url_for("customer.dashboard")
    elif role == Role.EMPLOYEE:
        return url_for("employee.dashboard")
    elif role == Role.ADMIN:
        return url_for("admin.dashboard")
    return url_for("auth.login")


@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(get_role_dashboard(current_user.role))
    return render_template("index.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(get_role_dashboard(current_user.role))

    if request.method == "GET":
        return render_template("auth/login.html", target_role="customer")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    try:
        user = auth_service.authenticate(username, password)
    except auth_service.AuthError as e:
        flash(str(e), "error")
        return render_template("auth/login.html", target_role="customer"), 401

    login_user(user)
    return redirect(get_role_dashboard(user.role))


@auth_bp.route("/auth/login", methods=["GET", "POST"])
def auth_login_alias():
    return login()


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(get_role_dashboard(current_user.role))

    if request.method == "GET":
        return render_template("auth/register.html", target_role="customer")

    form = request.form
    try:
        user = auth_service.register_user(
            username=form.get("username", "").strip(),
            email=form.get("email", "").strip(),
            password=form.get("password", ""),
            full_name=form.get("full_name", "").strip(),
            phone=form.get("phone", "").strip(),
            role=Role.CUSTOMER,
        )
    except ValidationError as e:
        flash(e.message, "error")
        return render_template("auth/register.html", target_role="customer"), 400

    login_user(user)
    flash("Welcome! Your Customer account has been created.", "success")
    return redirect(url_for("customer.dashboard"))


# Dedicated Role Login Routes
@auth_bp.route("/auth/customer/login", methods=["GET", "POST"])
def customer_login():
    return login()


@auth_bp.route("/auth/employee/login", methods=["GET", "POST"])
def employee_login():
    if current_user.is_authenticated:
        return redirect(get_role_dashboard(current_user.role))

    if request.method == "GET":
        return render_template("auth/login.html", target_role="employee")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    try:
        user = auth_service.authenticate(username, password)
    except auth_service.AuthError as e:
        flash(str(e), "error")
        return render_template("auth/login.html", target_role="employee"), 401

    login_user(user)
    return redirect(get_role_dashboard(user.role))


@auth_bp.route("/auth/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated:
        return redirect(get_role_dashboard(current_user.role))

    if request.method == "GET":
        return render_template("auth/login.html", target_role="admin")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    try:
        user = auth_service.authenticate(username, password)
    except auth_service.AuthError as e:
        flash(str(e), "error")
        return render_template("auth/login.html", target_role="admin"), 401

    login_user(user)
    return redirect(get_role_dashboard(user.role))


# Dedicated Role Registration Routes
@auth_bp.route("/auth/employee/register", methods=["GET", "POST"])
def employee_register():
    from app.models.system_setting import SystemSetting
    if current_user.is_authenticated:
        return redirect(get_role_dashboard(current_user.role))

    default_key = current_app.config.get("EMPLOYEE_AUTH_KEY", "ChangeMe_Employee123!")
    expected_key = SystemSetting.get("EMPLOYEE_AUTH_KEY", default_key)

    if request.method == "GET":
        return render_template("auth/register_staff.html", role_title="Employee / Bank Officer", target_role=Role.EMPLOYEE, auth_key_hint=expected_key)

    form = request.form
    auth_key = form.get("auth_key", "").strip()

    if auth_key != expected_key:
        flash("Invalid Staff Authorization Key.", "error")
        return render_template("auth/register_staff.html", role_title="Employee / Bank Officer", target_role=Role.EMPLOYEE, auth_key_hint=expected_key), 403

    try:
        user = auth_service.register_user(
            username=form.get("username", "").strip(),
            email=form.get("email", "").strip(),
            password=form.get("password", ""),
            full_name=form.get("full_name", "").strip(),
            phone=form.get("phone", "").strip(),
            role=Role.EMPLOYEE,
        )
    except ValidationError as e:
        flash(e.message, "error")
        return render_template("auth/register_staff.html", role_title="Employee / Bank Officer", target_role=Role.EMPLOYEE, auth_key_hint=expected_key), 400

    login_user(user)
    flash("Employee account successfully registered and activated.", "success")
    return redirect(url_for("employee.dashboard"))


@auth_bp.route("/auth/admin/register", methods=["GET", "POST"])
def admin_register():
    from app.models.system_setting import SystemSetting
    if current_user.is_authenticated:
        return redirect(get_role_dashboard(current_user.role))

    default_key = current_app.config.get("ADMIN_AUTH_KEY", "ChangeMe_Admin123!")
    expected_key = SystemSetting.get("ADMIN_AUTH_KEY", default_key)

    if request.method == "GET":
        return render_template("auth/register_staff.html", role_title="System Administrator", target_role=Role.ADMIN, auth_key_hint=expected_key)

    form = request.form
    auth_key = form.get("auth_key", "").strip()

    if auth_key != expected_key:
        flash("Invalid Admin Master Authorization Key.", "error")
        return render_template("auth/register_staff.html", role_title="System Administrator", target_role=Role.ADMIN, auth_key_hint=expected_key), 403

    try:
        user = auth_service.register_user(
            username=form.get("username", "").strip(),
            email=form.get("email", "").strip(),
            password=form.get("password", ""),
            full_name=form.get("full_name", "").strip(),
            phone=form.get("phone", "").strip(),
            role=Role.ADMIN,
        )
    except ValidationError as e:
        flash(e.message, "error")
        return render_template("auth/register_staff.html", role_title="System Administrator", target_role=Role.ADMIN, auth_key_hint=expected_key), 400

    login_user(user)
    flash("Administrator account successfully registered and activated.", "success")
    return redirect(url_for("admin.dashboard"))


@auth_bp.route("/logout")
@login_required
def logout():
    auth_service.logout_event(current_user.id)
    logout_user()
    return redirect(url_for("auth.login"))
