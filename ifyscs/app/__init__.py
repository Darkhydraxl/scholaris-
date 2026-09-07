import os
import time
from datetime import datetime, timezone

from flask import Flask, render_template, session, request
from flask_login import current_user, login_required

from config import config_by_name
from app.extensions import db, login_manager, bcrypt, mail, csrf, migrate, limiter, scheduler

_BUILD_VER = str(int(time.time()))


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    os.makedirs(os.path.join(app.root_path, "..", "instance"), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    _warn_insecure_secret_key(app)

    db.init_app(app)
    login_manager.init_app(app)
    # login_view is unset; unauthorized_handler below handles per-host redirection
    login_manager.login_message_category = "info"
    bcrypt.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    _register_blueprints(app)
    _register_user_loader()
    _register_context_processors(app)
    _register_request_hooks(app)
    _register_error_handlers(app)
    _register_scheduler(app)
    _register_template_globals(app)
    _ensure_schema(app)

    return app


TITLE_PREFIXES = ("dr.", "dr", "prof.", "prof", "mr.", "mr", "mrs.", "mrs", "ms.", "ms", "engr.", "engr")


def first_name(full_name):
    parts = (full_name or "").split()
    for part in parts:
        if part.lower().strip(".") not in [p.strip(".") for p in TITLE_PREFIXES]:
            return part
    return parts[0] if parts else ""


def _warn_insecure_secret_key(app):
    _INSECURE_DEFAULT = "dev-secret-key-change-me"
    if not app.debug and app.config.get("SECRET_KEY") == _INSECURE_DEFAULT:
        raise RuntimeError(
            "SECRET_KEY is set to the insecure default value. "
            "Set a strong SECRET_KEY environment variable before running in production."
        )
    if app.config.get("SECRET_KEY") == _INSECURE_DEFAULT:
        app.logger.warning("SECRET_KEY is using the insecure default — set SECRET_KEY in .env for production.")


def _register_template_globals(app):
    from flask import url_for as _flask_url_for

    def _url_for(endpoint, **values):
        if endpoint == "static":
            values.setdefault("_v", _BUILD_VER)
        return _flask_url_for(endpoint, **values)

    app.jinja_env.globals["url_for"] = _url_for
    app.jinja_env.globals["first_name"] = first_name


def _register_blueprints(app):
    from app.routes.auth import auth_bp
    from app.routes.student import student_bp
    from app.routes.supervisor import supervisor_bp
    from app.routes.admin import admin_bp
    from app.routes.admin_auth import admin_auth_bp
    from app.routes.annotation import annotation_bp
    from app.routes.notification import notification_bp
    from app.routes.meeting import meeting_bp
    from app.routes.google_auth import google_auth_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(google_auth_bp)
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(supervisor_bp, url_prefix="/supervisor")
    app.register_blueprint(annotation_bp, url_prefix="/annotation")
    app.register_blueprint(notification_bp, url_prefix="/notification")
    app.register_blueprint(meeting_bp, url_prefix="/meeting")

    if app.config.get("SERVER_NAME"):
        # Subdomain mode: admin panel at admin.<SERVER_NAME>
        app.register_blueprint(admin_bp, subdomain="admin")
        app.register_blueprint(admin_auth_bp, subdomain="admin")
    else:
        # Single-host fallback: admin panel at /admin prefix (original behaviour)
        app.register_blueprint(admin_bp, url_prefix="/admin")
        app.register_blueprint(admin_auth_bp, url_prefix="/admin-auth")

    @app.route("/theme/toggle", methods=["POST"])
    def toggle_theme():
        from flask import jsonify
        current = session.get("theme", "light")
        session["theme"] = "dark" if current == "light" else "light"
        return jsonify({"theme": session["theme"]})

    @app.route("/")
    def index():
        from flask_login import current_user
        if not current_user.is_authenticated:
            from flask import redirect, url_for
            return redirect(url_for("auth.login"))
        from flask import redirect, url_for
        if current_user.role == "student":
            return redirect(url_for("student.dashboard"))
        if current_user.role == "supervisor":
            return redirect(url_for("supervisor.dashboard"))
        return redirect(url_for("admin.dashboard"))


def _register_user_loader():
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request, redirect, url_for, current_app
        if current_app.config.get("SERVER_NAME") and request.host.startswith("admin."):
            return redirect(url_for("admin_auth.login"))
        return redirect(url_for("auth.login"))


def _register_context_processors(app):
    @app.context_processor
    def inject_globals():
        from datetime import date as date_cls
        from flask import has_request_context, url_for as _url_for
        unread_count = 0
        session_expires_at = None
        supervisor_pending_count = 0
        logout_url = None
        profile_url = None
        if has_request_context() and current_user.is_authenticated:
            from app.models import Notification
            unread_count = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
            expiry = session.get("session_expires_at")
            session_expires_at = expiry
            # Admin users always use admin_auth routes regardless of hosting mode
            use_admin_auth = current_user.role == "admin"
            logout_url = _url_for("admin_auth.logout") if use_admin_auth else _url_for("auth.logout")
            profile_url = _url_for("admin_auth.profile") if use_admin_auth else _url_for("auth.profile")
            if current_user.role == "supervisor":
                from app.models import SupervisorAssignment, Project, ChapterSubmission
                assigned_ids = [
                    a.student_id for a in
                    SupervisorAssignment.query.filter_by(supervisor_id=current_user.id).all()
                ]
                if assigned_ids:
                    project_ids = [
                        p.id for p in
                        Project.query.filter(Project.student_id.in_(assigned_ids)).all()
                    ]
                    if project_ids:
                        supervisor_pending_count = ChapterSubmission.query.filter(
                            ChapterSubmission.project_id.in_(project_ids),
                            ChapterSubmission.status == "pending",
                        ).count()
        return dict(
            unread_count=unread_count,
            session_expires_at=session_expires_at,
            today=date_cls.today(),
            supervisor_pending_count=supervisor_pending_count,
            logout_url=logout_url,
            profile_url=profile_url,
        )


def _register_request_hooks(app):
    @app.before_request
    def make_session_permanent_and_track_expiry():
        if current_user.is_authenticated:
            session.permanent = True
            lifetime = app.config["PERMANENT_SESSION_LIFETIME"]
            expires_at = datetime.now(timezone.utc) + lifetime
            session["session_expires_at"] = expires_at.isoformat()

    @app.after_request
    def cache_static(response):
        if request.path.startswith("/static/uploads/"):
            # User-uploaded files (avatars, PDFs) — never cache via shared proxies
            response.headers["Cache-Control"] = "private, no-store"
        elif request.path.startswith("/static/"):
            # Versioned static assets (_v= query param changes on every server restart)
            # Safe to cache for 1 year — a new _v ensures clients always get fresh files
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            response.headers.pop("Pragma", None)
            response.headers.pop("Expires", None)
        return response


def _register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404


def _register_scheduler(app):
    if app.config.get("TESTING"):
        return
    # Avoid double-registration when Werkzeug's debug reloader spawns a child process.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    if scheduler.running:
        return

    from app.services.scheduler_jobs import check_deadline_reminders

    scheduler.add_job(
        func=lambda: check_deadline_reminders(app),
        trigger="cron",
        hour=app.config["DEADLINE_REMINDER_HOUR"],
        minute=app.config["DEADLINE_REMINDER_MINUTE"],
        id="deadline_reminder_job",
        replace_existing=True,
    )
    scheduler.start()
    app.logger.info(
        "Deadline reminder scheduler started (daily at %02d:%02d).",
        app.config["DEADLINE_REMINDER_HOUR"], app.config["DEADLINE_REMINDER_MINUTE"],
    )


def _ensure_schema(app):
    """Add any columns that didn't exist when the DB was first created.
    Runs only on SQLite (local dev). PostgreSQL gets these columns via Alembic migration."""
    if "sqlite" not in app.config["SQLALCHEMY_DATABASE_URI"]:
        return
    from sqlalchemy import inspect, text
    with app.app_context():
        inspector = inspect(db.engine)
        existing = {col["name"] for col in inspector.get_columns("users")}
        with db.engine.begin() as conn:
            if "avatar" not in existing:
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar VARCHAR(255)"))
                app.logger.info("Schema: added users.avatar column.")
            if "zoom_email" not in existing:
                conn.execute(text("ALTER TABLE users ADD COLUMN zoom_email VARCHAR(120)"))
                app.logger.info("Schema: added users.zoom_email column.")
            if "google_email" not in existing:
                conn.execute(text("ALTER TABLE users ADD COLUMN google_email VARCHAR(120)"))
                app.logger.info("Schema: added users.google_email column.")
            if "google_oauth_token" not in existing:
                conn.execute(text("ALTER TABLE users ADD COLUMN google_oauth_token TEXT"))
                app.logger.info("Schema: added users.google_oauth_token column.")
            if "is_super_admin" not in existing:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_super_admin BOOLEAN NOT NULL DEFAULT 0"))
                app.logger.info("Schema: added users.is_super_admin column.")
