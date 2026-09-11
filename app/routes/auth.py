from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.models.user import Role
from app.services import auth_service, banking_service
from app.utils.validators import ValidationError

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for(f"{current_user.role}.dashboard"))
    return render_template("index.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@auth_bp.route("/login/<role>", methods=["GET", "POST"])
def login(role=None):
    if current_user.is_authenticated:
        return redirect(url_for(f"{current_user.role}.dashboard"))

    selected_role = (role or "customer").lower()
    if selected_role not in (Role.CUSTOMER, Role.EMPLOYEE, Role.ADMIN):
        selected_role = Role.CUSTOMER

    if request.method == "GET":
        return render_template("auth/login.html", selected_role=selected_role)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    try:
        user = auth_service.authenticate(username, password)
    except auth_service.AuthError as e:
        flash(str(e), "error")
        return render_template("auth/login.html", selected_role=selected_role), 401

    login_user(user)
    flash(f"Welcome back, {user.full_name or user.username}!", "success")
    return redirect(url_for(f"{user.role}.dashboard"))


@auth_bp.route("/register", methods=["GET", "POST"])
@auth_bp.route("/register/<role>", methods=["GET", "POST"])
def register(role=None):
    if current_user.is_authenticated:
        return redirect(url_for(f"{current_user.role}.dashboard"))

    selected_role = (role or "customer").lower()
    if selected_role not in (Role.CUSTOMER, Role.EMPLOYEE, Role.ADMIN):
        selected_role = Role.CUSTOMER

    if request.method == "GET":
        return render_template("auth/register.html", selected_role=selected_role)

    form = request.form
    # Public self-registration always creates CUSTOMER account to prevent role escalation via form or query params
    target_role = Role.CUSTOMER

    try:
        user = auth_service.register_user(
            username=form.get("username", "").strip(),
            email=form.get("email", "").strip(),
            password=form.get("password", ""),
            full_name=form.get("full_name", "").strip(),
            phone=form.get("phone", "").strip(),
            role=target_role,
        )

        if target_role == Role.CUSTOMER:
            try:
                banking_service.create_account(user.id)
            except Exception:
                pass
    except ValidationError as e:
        flash(e.message, "error")
        return render_template("auth/register.html", selected_role=target_role), 400

    login_user(user)
    flash(f"Welcome {user.full_name or user.username}! Your {target_role.upper()} profile has been activated.", "success")
    return redirect(url_for(f"{user.role}.dashboard"))


@auth_bp.route("/logout")
@login_required
def logout():
    auth_service.logout_event(current_user.id)
    logout_user()
    return redirect(url_for("auth.login"))
