import hashlib
import os
from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session, current_app, abort, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db, bcrypt, limiter
from app.models import User, ChapterSubmission
from app.forms import LoginForm, RegisterForm, ChangePasswordForm, ProfileForm
from app.services.audit_service import log_action
from app import first_name

_IMG_SIGNATURES = {
    b'\xff\xd8\xff': 'jpg',
    b'\x89PNG':      'png',
}

_IMG_MIMES = {'jpg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}


def _detect_image(header12: bytes):
    for sig, ext in _IMG_SIGNATURES.items():
        if header12.startswith(sig):
            return ext
    if header12[:4] == b'RIFF' and header12[8:12] == b'WEBP':
        return 'webp'
    return None


def _save_avatar_file(user, av_file):
    """Validate and persist an uploaded avatar. Returns error string or None."""
    header = av_file.read(12)
    av_file.seek(0)
    ext = _detect_image(header)
    if ext is None:
        return "Only JPG, PNG, or WebP images are accepted."
    av_file.seek(0, 2)
    if av_file.tell() > 5 * 1024 * 1024:
        return "Image must be under 5 MB."
    av_file.seek(0)

    data = av_file.read()
    if not data:
        return "That image appears to be empty."

    # Stored in the database rather than on disk — an ephemeral host filesystem
    # loses the file on the next restart while the row survives, which made
    # pictures silently disappear. `avatar` stays as the cache-busting token.
    user.avatar_data = data
    user.avatar_mime = _IMG_MIMES[ext]
    # Token is derived from the image bytes, not the clock: the served response
    # is cached for a week, so the URL must change whenever the picture changes
    # (a second-resolution timestamp collides on same-second replacements).
    user.avatar = f"uid_{user.id}_{hashlib.sha256(data).hexdigest()[:16]}.{ext}"
    return None

# Pre-computed bcrypt hash for constant-time dummy checks (prevents timing-based email enumeration)
_DUMMY_HASH = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"

auth_bp = Blueprint("auth", __name__)


def _redirect_for_role(user):
    if user.role == "student":
        return redirect(url_for("student.dashboard"))
    if user.role == "supervisor":
        return redirect(url_for("supervisor.dashboard"))
    return redirect(url_for("admin.dashboard"))


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user)

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        # Always run bcrypt to prevent email enumeration via timing side-channel
        candidate_hash = user.password_hash if (user and user.is_active) else _DUMMY_HASH
        password_ok = bcrypt.check_password_hash(candidate_hash, form.password.data)
        if user and user.is_active and password_ok:
            if user.role == "admin":
                flash("Admin accounts must sign in through the admin portal.", "info")
                return redirect(url_for("admin_auth.login"))
            login_user(user, remember=form.remember.data)
            # Rotate session ID to prevent session fixation
            _keys = {k: v for k, v in session.items() if k.startswith("_")}
            session.clear()
            session.update(_keys)
            session.permanent = True
            log_action(user.id, "login", f"User {user.email} logged in")
            flash(f"Welcome back, {first_name(user.full_name)}!", "success")
            return _redirect_for_role(user)
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.exempt
def register():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user)

    form = RegisterForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if existing:
            flash("An account with that email already exists.", "error")
        else:
            user = User(
                full_name=form.full_name.data.strip(),
                email=form.email.data.lower().strip(),
                department=form.department.data.strip(),
                role="student",  # hardcoded — public signup is students only
                password_hash=bcrypt.generate_password_hash(form.password.data).decode("utf-8"),
            )
            db.session.add(user)
            db.session.commit()
            log_action(user.id, "register", f"New {user.role} account created")
            flash("Account created. You can now log in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    log_action(current_user.id, "logout", f"User {current_user.email} logged out")
    logout_user()
    flash("You have been logged out.", "info")
    resp = redirect(url_for("auth.login"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    # Admins must use the admin-auth profile route
    if current_user.role == "admin":
        return redirect(url_for("admin_auth.profile"))
    form = ProfileForm(obj=current_user)
    password_form = ChangePasswordForm()
    if request.method == "POST" and request.form.get("form_name") == "profile" and form.validate_on_submit():
        current_user.full_name = form.full_name.data.strip()
        if not current_user.is_super_admin:
            current_user.email = form.email.data.lower().strip()
        if current_user.role == "admin" and not current_user.is_super_admin:
            current_user.department = form.department.data.strip() if form.department.data else None
        db.session.commit()
        log_action(current_user.id, "update_profile", "Updated profile details")
        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))

    if request.method == "POST" and request.form.get("form_name") == "password" and password_form.validate_on_submit():
        if not bcrypt.check_password_hash(current_user.password_hash, password_form.current_password.data):
            flash("Current password is incorrect.", "error")
        else:
            current_user.password_hash = bcrypt.generate_password_hash(
                password_form.new_password.data
            ).decode("utf-8")
            db.session.commit()
            log_action(current_user.id, "change_password", "Changed account password")
            flash("Password changed.", "success")
            return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html", form=form, password_form=password_form)



@auth_bp.route("/session/extend", methods=["POST"])
@login_required
def extend_session():
    lifetime = current_app.config["PERMANENT_SESSION_LIFETIME"]
    session.permanent = True
    expires_at = datetime.now(timezone.utc) + lifetime
    session["session_expires_at"] = expires_at.isoformat()
    return jsonify({"expires_at": session["session_expires_at"]})


@auth_bp.route("/profile/avatar", methods=["POST"])
@login_required
def upload_avatar():
    try:
        f = request.files.get("avatar")
        if not f or not f.filename:
            return jsonify({"error": "No file received."}), 400
        try:
            err = _save_avatar_file(current_user, f)
        except Exception:
            current_app.logger.exception("Avatar save failed")
            db.session.rollback()
            return jsonify({"error": "Upload failed. Please try again."}), 500
        if err:
            return jsonify({"error": err}), 400
        db.session.commit()
        try:
            log_action(current_user.id, "update_avatar", "Updated profile picture")
        except Exception:
            current_app.logger.exception("Avatar audit log failed — ignored")
        return jsonify({"url": url_for("auth.avatar", user_id=current_user.id, v=current_user.avatar)})
    except Exception:
        current_app.logger.exception("Avatar upload unexpected error")
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"error": "An unexpected error occurred."}), 500


@auth_bp.route("/avatar/<int:user_id>")
@login_required
def avatar(user_id):
    """Serves an avatar from the database.

    Falls back to the legacy on-disk copy so avatars uploaded before the move
    to database storage keep working wherever the file still exists.
    """
    user = User.query.get_or_404(user_id)

    if user.avatar_data:
        return current_app.response_class(
            user.avatar_data,
            mimetype=user.avatar_mime or "image/jpeg",
            headers={"Cache-Control": "private, max-age=604800"},
        )

    if user.avatar:
        legacy = os.path.join(current_app.config["UPLOAD_FOLDER"], "avatars", user.avatar)
        if os.path.isfile(legacy):
            return send_from_directory(
                os.path.join(current_app.config["UPLOAD_FOLDER"], "avatars"), user.avatar
            )

    abort(404)


@auth_bp.route("/files/upload/<path:filepath>")
@login_required
def serve_upload(filepath):
    """Auth-gated file serving. Replaces direct /static/uploads/ access."""
    if filepath.startswith("uploads/submissions/"):
        filename = filepath[len("uploads/submissions/"):]
        submission = ChapterSubmission.query.filter_by(file_path=filepath).first_or_404()
        ok = (
            (current_user.role == "student" and submission.project.student_id == current_user.id)
            or (current_user.role == "supervisor" and submission.project.supervisor_id == current_user.id)
            or current_user.role == "admin"
        )
        if not ok:
            abort(403)
        return send_from_directory(
            os.path.join(current_app.config["UPLOAD_FOLDER"], "submissions"),
            filename,
            mimetype="application/pdf",
        )
    elif filepath.startswith("uploads/avatars/"):
        filename = filepath[len("uploads/avatars/"):]
        return send_from_directory(
            os.path.join(current_app.config["UPLOAD_FOLDER"], "avatars"),
            filename,
        )
    abort(403)
