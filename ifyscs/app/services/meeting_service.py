"""
Meeting link creation for Google Meet and Zoom.

MEETING_DEMO_MODE=true (default in .env) generates placeholder links so the
feature works immediately without API credentials.  Set it to false and
supply the appropriate environment variables to use real APIs.

Google Meet  — needs GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_INFO
               plus the google-api-python-client package.
Zoom         — needs ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET.
               Uses only stdlib (no extra packages required).
"""

import base64
import json
import uuid
import urllib.request
import urllib.parse
import urllib.error
from datetime import timedelta

from flask import current_app


# ── helpers ───────────────────────────────────────────────────────────────────

def _demo_link(platform):
    import random
    if platform == "google_meet":
        import string
        letters = string.ascii_lowercase
        def seg(n): return "".join(random.choices(letters, k=n))
        mid = f"{seg(3)}-{seg(4)}-{seg(3)}"
        return mid, f"https://meet.google.com/{mid}"
    meeting_id = str(random.randint(80_000_000_000, 89_999_999_999))
    return meeting_id, f"https://zoom.us/j/{meeting_id}"


# ── Google Meet ───────────────────────────────────────────────────────────────

def _create_google_meet(title, start_dt, duration_minutes, description, oauth_token_json=None):
    """
    Creates a Google Calendar event with a Google Meet link using the
    supervisor's OAuth credentials (stored as JSON in oauth_token_json).
    """
    if not oauth_token_json:
        raise RuntimeError("Google account not connected. Please connect your Google account first.")

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GRequest
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError("google-api-python-client is not installed.")

    from flask import current_app
    token_data = json.loads(oauth_token_json)
    # client_secret is not stored in the token — read it from app config
    client_secret = token_data.get("client_secret") or current_app.config.get("GOOGLE_CLIENT_SECRET")
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=client_secret,
        scopes=token_data.get("scopes"),
    )
    if creds.expired or not creds.valid:
        creds.refresh(GRequest())

    service = build("calendar", "v3", credentials=creds)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    event = {
        "summary": title,
        "description": description or "",
        "start": {"dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "UTC"},
        "end":   {"dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),   "timeZone": "UTC"},
        "conferenceData": {
            "createRequest": {
                "requestId": uuid.uuid4().hex,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    try:
        result = service.events().insert(
            calendarId="primary", body=event, conferenceDataVersion=1,
        ).execute()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Google Calendar API error {exc.code}: {exc.read().decode()[:300]}") from exc

    entry_points = result.get("conferenceData", {}).get("entryPoints", [])
    link = next(
        (ep["uri"] for ep in entry_points if ep.get("entryPointType") == "video"),
        result.get("hangoutLink"),
    )
    if not link:
        raise RuntimeError("Google Calendar created the event but returned no Meet link.")

    return result["id"], link


# ── Zoom ──────────────────────────────────────────────────────────────────────

def _zoom_access_token():
    account_id = current_app.config["ZOOM_ACCOUNT_ID"]
    client_id = current_app.config["ZOOM_CLIENT_ID"]
    client_secret = current_app.config["ZOOM_CLIENT_SECRET"]

    creds_b64 = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urllib.parse.urlencode(
        {"grant_type": "account_credentials", "account_id": account_id}
    ).encode()
    req = urllib.request.Request(
        "https://zoom.us/oauth/token",
        data=body,
        headers={
            "Authorization": f"Basic {creds_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]


def _create_zoom(title, start_dt, duration_minutes, description, host_email=None):
    if not all([
        current_app.config.get("ZOOM_ACCOUNT_ID"),
        current_app.config.get("ZOOM_CLIENT_ID"),
        current_app.config.get("ZOOM_CLIENT_SECRET"),
    ]):
        raise RuntimeError(
            "Zoom credentials not configured. Set ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, "
            "and ZOOM_CLIENT_SECRET in your .env file."
        )

    token = _zoom_access_token()
    # Use the supervisor's own Zoom email so they are the meeting host.
    # Falls back to the configured account email if none was supplied.
    user_email = host_email or current_app.config.get("ZOOM_USER_EMAIL", "me")

    payload = json.dumps({
        "topic": title,
        "type": 2,
        "start_time": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration": duration_minutes,
        "agenda": description or "",
        "settings": {
            "host_video": True,
            "participant_video": True,
            "join_before_host": True,
            "waiting_room": False,
        },
    }).encode()

    req = urllib.request.Request(
        f"https://api.zoom.us/v2/users/{user_email}/meetings",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"Zoom API error {exc.code}: {body[:300]}") from exc

    return str(data["id"]), data["join_url"]


# ── public entry point ────────────────────────────────────────────────────────

def create_meeting_link(platform, title, start_dt, duration_minutes, description="",
                        host_email=None, google_oauth_token=None):
    """Returns (external_meeting_id, meeting_url). Raises RuntimeError on failure."""
    if current_app.config.get("MEETING_DEMO_MODE"):
        return _demo_link(platform)

    if platform == "google_meet":
        return _create_google_meet(title, start_dt, duration_minutes, description,
                                   oauth_token_json=google_oauth_token)
    if platform == "zoom":
        return _create_zoom(title, start_dt, duration_minutes, description, host_email=host_email)
    raise ValueError(f"Unknown meeting platform: {platform!r}")
