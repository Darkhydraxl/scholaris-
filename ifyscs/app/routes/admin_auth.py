from datetime import datetime, timezone

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify, session, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db, bcrypt, limiter
from app.models import User
from app.forms import LoginForm, ChangePasswordForm, ProfileForm
from app.services.audit_service import log_action
from app import first_name

# Same dummy hash used in auth.py to prevent timing-based enumeration
_DUMMY_HASH = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"

admin_auth_bp = Blueprint("admin_auth", __name__)


@admin_auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("auth.login"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        candidate_hash = user.password_hash if (user and user.is_active) else _DUMMY_HASH
        password_ok = bcrypt.check_password_hash(candidate_hash, form.password.data)
        if user and user.is_active and password_ok and user.role == "admin" and user.is_super_admin:
            login_user(user, remember=form.remember.data)
            # Rotate session ID to prevent session fixation
            _keys = {k: v for k, v in session.items() if k.startswith("_")}
            session.clear()
            session.update(_keys)
            session.permanent = True
            log_action(user.id, "login", f"Admin {user.email} logged in via admin portal")
            flash(f"Welcome back, {first_name(user.full_name)}!", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Invalid credentials or insufficient privileges.", "error")
    return render_template("admin/login.html", form=form)


@admin_auth_bp.route("/logout")
@login_required
def logout():
    log_action(current_user.id, "logout", f"Admin {current_user.email} logged out")
    logout_user()
    flash("You have been signed out.", "info")
    resp = redirect(url_for("admin_auth.login"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@admin_auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    # Only admins should reach this endpoint
    if current_user.role != "admin":
        return redirect(url_for("auth.profile"))
    form = ProfileForm(obj=current_user)
    password_form = ChangePasswordForm()
    if request.method == "POST" and request.form.get("form_name") == "profile" and form.validate_on_submit():
        current_user.full_name = form.full_name.data.strip()
        if not current_user.is_super_admin:
            current_user.email = form.email.data.lower().strip()
        db.session.commit()
        log_action(current_user.id, "update_profile", "Admin updated profile")
        flash("Profile updated.", "success")
        return redirect(url_for("admin_auth.profile"))

    if request.method == "POST" and request.form.get("form_name") == "password" and password_form.validate_on_submit():
        if not bcrypt.check_password_hash(current_user.password_hash, password_form.current_password.data):
            flash("Current password is incorrect.", "error")
        else:
            current_user.password_hash = bcrypt.generate_password_hash(
                password_form.new_password.data
            ).decode("utf-8")
            db.session.commit()
            log_action(current_user.id, "change_password", "Admin changed password")
            flash("Password changed.", "success")
            return redirect(url_for("admin_auth.profile"))

    return render_template("auth/profile.html", form=form, password_form=password_form)


@admin_auth_bp.route("/theme/toggle", methods=["POST"])
def toggle_theme():
    """Mirrors the main-app toggle_theme so admin-subdomain pages can call it relative."""
    current = session.get("theme", "light")
    session["theme"] = "dark" if current == "light" else "light"
    return jsonify({"theme": session["theme"]})


@admin_auth_bp.route("/session/extend", methods=["POST"])
@login_required
def extend_session():
    """Mirrors auth.extend_session for the admin subdomain."""
    lifetime = current_app.config["PERMANENT_SESSION_LIFETIME"]
    session.permanent = True
    expires_at = datetime.now(timezone.utc) + lifetime
    session["session_expires_at"] = expires_at.isoformat()
    return jsonify({"expires_at": session["session_expires_at"]})
