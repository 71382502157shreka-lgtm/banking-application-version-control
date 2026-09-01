from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.services import auth_service
from app.utils.validators import ValidationError

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for(f"{current_user.role}.dashboard"))
    return render_template("index.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    try:
        user = auth_service.authenticate(username, password)
    except auth_service.AuthError as e:
        flash(str(e), "error")
        return render_template("auth/login.html"), 401

    login_user(user)
    return redirect(url_for(f"{user.role}.dashboard"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("auth/register.html")

    form = request.form
    try:
        user = auth_service.register_user(
            username=form.get("username", "").strip(),
            email=form.get("email", "").strip(),
            password=form.get("password", ""),
            full_name=form.get("full_name", "").strip(),
            phone=form.get("phone", "").strip(),
        )
    except ValidationError as e:
        flash(e.message, "error")
        return render_template("auth/register.html"), 400

    login_user(user)
    flash("Welcome! Your account has been created.", "success")
    return redirect(url_for("customer.dashboard"))


@auth_bp.route("/logout")
@login_required
def logout():
    auth_service.logout_event(current_user.id)
    logout_user()
    return redirect(url_for("auth.login"))
