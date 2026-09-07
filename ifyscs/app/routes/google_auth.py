import json
import os

from flask import Blueprint, redirect, url_for, request, flash, current_app, session
from flask_login import current_user, login_required

from app.extensions import db
from app.decorators import role_required

google_auth_bp = Blueprint("google_auth", __name__)

_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _allow_insecure_transport_in_dev(app):
    """Permit plain-HTTP OAuth only when running in debug/dev mode."""
    if app.debug or os.environ.get("FLASK_ENV") == "development":
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    else:
        os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)


def _load_credentials(token_json: str):
    """Reconstruct Google Credentials from stored token, injecting client_secret from config."""
    from google.oauth2.credentials import Credentials
    data = json.loads(token_json)
    data.setdefault("client_secret", current_app.config.get("GOOGLE_CLIENT_SECRET"))
    return Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data["client_secret"],
        scopes=data.get("scopes", _SCOPES),
    )


def _flow():
    from google_auth_oauthlib.flow import Flow
    return Flow.from_client_config(
        {
            "web": {
                "client_id":     current_app.config["GOOGLE_CLIENT_ID"],
                "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
                "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                "token_uri":     "https://oauth2.googleapis.com/token",
                "redirect_uris": [current_app.config["GOOGLE_REDIRECT_URI"]],
            }
        },
        scopes=_SCOPES,
        redirect_uri=current_app.config["GOOGLE_REDIRECT_URI"],
    )


@google_auth_bp.route("/auth/google/connect")
@role_required("supervisor")
def connect():
    _allow_insecure_transport_in_dev(current_app._get_current_object())
    flow = _flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session["google_oauth_state"] = state
    session["google_code_verifier"] = flow.code_verifier
    return redirect(auth_url)


@google_auth_bp.route("/auth/google/callback")
@role_required("supervisor")
def callback():
    _allow_insecure_transport_in_dev(current_app._get_current_object())
    state = session.pop("google_oauth_state", None)
    if not state or request.args.get("state") != state:
        flash("Google authorisation failed — please try again.", "error")
        return redirect(url_for("meeting.schedule"))

    code_verifier = session.pop("google_code_verifier", None)
    flow = _flow()
    try:
        # Reconstruct the authorization_response URL from the configured redirect URI +
        # the query string Google sent back. This is necessary when Flask sits behind a
        # reverse proxy (ngrok, nginx) because request.url shows the internal URL
        # (http://127.0.0.1:5000/...) while GOOGLE_REDIRECT_URI is the public URL,
        # causing a redirect_uri mismatch in the token exchange.
        qs = request.query_string.decode("utf-8")
        auth_response = current_app.config["GOOGLE_REDIRECT_URI"] + ("?" + qs if qs else "")
        flow.fetch_token(authorization_response=auth_response, code_verifier=code_verifier)
    except Exception as exc:
        current_app.logger.error("Google OAuth token fetch failed: %s: %s", type(exc).__name__, exc)
        flash("Google authorisation failed — please try again.", "error")
        return redirect(url_for("meeting.schedule"))

    creds = flow.credentials
    # client_secret is NOT stored here — it is injected from config at use-time via _load_credentials()
    token_data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "scopes":        list(creds.scopes or _SCOPES),
    }
    current_user.google_oauth_token = json.dumps(token_data)
    db.session.commit()
    flash("Google account connected! Google Meet links will now be created automatically.", "success")
    return redirect(url_for("meeting.schedule"))


@google_auth_bp.route("/auth/google/disconnect", methods=["POST"])
@role_required("supervisor")
def disconnect():
    current_user.google_oauth_token = None
    db.session.commit()
    flash("Google account disconnected.", "info")
    return redirect(url_for("meeting.schedule"))
