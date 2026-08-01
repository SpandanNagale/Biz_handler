from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import UserMixin, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from app.extensions import limiter, login_manager

auth_bp = Blueprint("auth", __name__)


class AdminUser(UserMixin):
    id = "admin"


@login_manager.user_loader
def load_user(user_id):
    return AdminUser() if user_id == "admin" else None


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        valid = username == current_app.config["ADMIN_USERNAME"] and check_password_hash(
            current_app.config["ADMIN_PASSWORD_HASH"], password
        )
        if valid:
            login_user(AdminUser())
            return redirect(request.args.get("next") or url_for("reports.dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
