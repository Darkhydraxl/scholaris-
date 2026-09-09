import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

app = create_app(os.environ.get("FLASK_ENV", "production"))

# Run database migrations on every startup.
# flask_migrate's upgrade() is idempotent — if the DB is already current it does nothing.
# PostgreSQL's advisory locks prevent race conditions when multiple workers start together.
with app.app_context():
    from flask_migrate import upgrade
    upgrade()

    # Create super admin on first run if not already in the database.
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
