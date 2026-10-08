import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Ensure Flask app errors are visible in Render's log stream
logging.basicConfig(
    stream=sys.stderr,
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from app import create_app  # noqa: E402

app = create_app(os.environ.get("FLASK_ENV", "production"))

# Run database migrations and seed the super admin on every startup.
#
# Both steps are best-effort. They used to run bare at import time, so an
# unreachable database raised here, gunicorn could not import wsgi:app, and the
# deploy failed outright — which meant a database outage also blocked deploying
# the fix for it. Booting and reporting the fault via /health is strictly more
# useful than refusing to start, and the next boot retries both steps.
_logger = logging.getLogger(__name__)

with app.app_context():
    try:
        # Idempotent: a current database is a no-op, and PostgreSQL advisory
        # locks keep concurrent workers from racing each other.
        from flask_migrate import upgrade
        upgrade()
    except Exception:
        _logger.exception("STARTUP: database migration failed — app starting anyway; check /health")

    try:
        from app.models import User
        from app.extensions import db, bcrypt

        _email = os.environ.get("SUPER_ADMIN_EMAIL", "").strip().lower()
        _password = os.environ.get("SUPER_ADMIN_PASSWORD", "").strip()
        if _email and _password and not User.query.filter_by(email=_email).first():
            admin = User(
                full_name="Super Admin",
                email=_email,
                password_hash=bcrypt.generate_password_hash(_password).decode("utf-8"),
                role="admin",
                is_super_admin=True,
                is_active=True,
            )
            db.session.add(admin)
            db.session.commit()
            _logger.warning("STARTUP: created super admin %s", _email)
    except Exception:
        _logger.exception("STARTUP: super admin bootstrap failed — app starting anyway")
        try:
            from app.extensions import db as _db
            _db.session.rollback()
        except Exception:
            pass
