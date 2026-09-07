import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",      # required for SERVER_NAME subdomain routing to work
        debug=app.config.get("DEBUG", True),
        use_reloader=True,    # auto-restarts when any .py file changes; _register_scheduler guards against double-start
        port=int(os.environ.get("PORT", 5000)),
    )
