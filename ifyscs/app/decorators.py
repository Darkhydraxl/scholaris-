from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user, login_required

from app.services.audit_service import log_action


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def super_admin_required(view_func):
    """Allow only the super-admin. Unauthenticated → login. Authenticated but not super → own dashboard."""
    @wraps(view_func)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin" or not current_user.is_super_admin:
            log_action(
                current_user.id,
                "unauthorized_super_admin_access",
                f"{current_user.email} attempted to access super-admin-only endpoint",
            )
            flash("You don't have permission to access that page.", "error")
            # Redirect each role to their own dashboard, not the admin one
            if current_user.role == "student":
                return redirect(url_for("student.dashboard"))
            if current_user.role == "supervisor":
                return redirect(url_for("supervisor.dashboard"))
            return redirect(url_for("admin.dashboard"))
        return view_func(*args, **kwargs)
    return wrapped
