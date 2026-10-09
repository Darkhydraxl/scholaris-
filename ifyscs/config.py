import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    _db_url = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "scholaris.db")
    )
    # SQLAlchemy 2.1+ defaults to psycopg (v3) for bare postgresql:// URLs.
    # Force psycopg2 explicitly since we ship psycopg2-binary, not psycopg.
    if _db_url.startswith("postgres://"):
        _db_url = "postgresql+psycopg2://" + _db_url[len("postgres://"):]
    elif _db_url.startswith("postgresql://"):
        _db_url = "postgresql+psycopg2://" + _db_url[len("postgresql://"):]
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Managed Postgres closes idle connections, and hosts that suspend idle
    # compute kill them outright. The pool does not notice, so it hands out a
    # dead connection and the request dies on "SSL SYSCALL error: EOF detected".
    # pre_ping tests a connection before use and transparently replaces a dead
    # one; recycle retires connections before the server does it for us.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB
    ALLOWED_UPLOAD_EXTENSIONS = {"pdf"}

    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_WARNING_AFTER = timedelta(minutes=25)
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT = "300 per minute"

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    # Port 465 speaks implicit SSL, 587 speaks STARTTLS. Deriving the flags from
    # the port avoids the silent connection hang a mismatched pair causes.
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "True" if MAIL_PORT == 465 else "False") == "True"
    MAIL_USE_TLS = False if MAIL_USE_SSL else os.environ.get("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "Scholaris <no-reply@scholaris.local>")
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "False") == "True"

    # Mail is sent over an HTTPS API rather than SMTP because hosts such as
    # Render block outbound SMTP ports entirely. Mailjet takes precedence over
    # Brevo when both are set; SMTP is the fallback. See active_transport().
    MAILJET_API_KEY = os.environ.get("MAILJET_API_KEY")
    MAILJET_SECRET_KEY = os.environ.get("MAILJET_SECRET_KEY")
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY")

    BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")

    DEADLINE_REMINDER_HOUR = int(os.environ.get("DEADLINE_REMINDER_HOUR", 8))
    DEADLINE_REMINDER_MINUTE = int(os.environ.get("DEADLINE_REMINDER_MINUTE", 0))

    WTF_CSRF_TIME_LIMIT = 3600

    # Subdomain routing — set in .env to enable admin.scholaris.* subdomain
    # Leave unset (None) to run all routes on a single host (default dev mode)
    SERVER_NAME = os.environ.get("SERVER_NAME")
    # None = host-scoped cookies; scholaris.localhost and admin.scholaris.localhost
    # keep separate sessions — never share across subdomains
    SESSION_COOKIE_DOMAIN = None

    # Google Meet (Calendar API via service account)
    GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    GOOGLE_SERVICE_ACCOUNT_INFO = os.environ.get("GOOGLE_SERVICE_ACCOUNT_INFO")
    GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")

    # Google OAuth 2.0 (for supervisors connecting their Google account to create Meet links)
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://127.0.0.1:5000/auth/google/callback")

    # Zoom (Server-to-Server OAuth)
    ZOOM_ACCOUNT_ID = os.environ.get("ZOOM_ACCOUNT_ID")
    ZOOM_CLIENT_ID = os.environ.get("ZOOM_CLIENT_ID")
    ZOOM_CLIENT_SECRET = os.environ.get("ZOOM_CLIENT_SECRET")
    ZOOM_USER_EMAIL = os.environ.get("ZOOM_USER_EMAIL", "me")

    # Opt-in only: demo mode returns placeholder links that no real meeting
    # service will accept, so it must never be what an unconfigured host falls
    # back to. Set MEETING_DEMO_MODE=true explicitly for local dev.
    MEETING_DEMO_MODE = os.environ.get("MEETING_DEMO_MODE", "false").lower() == "true"


class DevelopmentConfig(Config):
    DEBUG = True
    SEND_FILE_MAX_AGE_DEFAULT = 0


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
