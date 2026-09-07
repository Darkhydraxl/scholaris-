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
