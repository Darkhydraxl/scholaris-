import re
from datetime import datetime, timezone
from email.utils import parseaddr
from html import unescape
from urllib.parse import urlsplit

import requests

from app.extensions import db, mail
from app.models import Notification, User
from flask_mail import Message
from flask import current_app, render_template, request, has_request_context

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
MAILJET_ENDPOINT = "https://api.mailjet.com/v3.1/send"


def active_transport():
    """Which transport send_email will use, given the current config.

    Single source of truth: the boot log and the admin-facing error message
    both report this, and SMTP is unusable on hosts that block its ports, so
    the three must never disagree about what actually ran.
    """
    cfg = current_app.config
    if cfg.get("MAILJET_API_KEY") and cfg.get("MAILJET_SECRET_KEY"):
        return "mailjet"
    if cfg.get("BREVO_API_KEY"):
        return "brevo"
    return "smtp"


def _sender_pair():
    name, email = parseaddr(current_app.config.get("MAIL_DEFAULT_SENDER") or "")
    if not email:
        raise RuntimeError("MAIL_DEFAULT_SENDER has no usable email address")
    return (name or "Scholaris"), email


def notify(user_id, message, type="submission"):
    notification = Notification(user_id=user_id, message=message, type=type)
    db.session.add(notification)
    db.session.commit()
    return notification


def notify_many(user_ids, message, type="broadcast"):
    notifications = [Notification(user_id=uid, message=message, type=type) for uid in user_ids]
    db.session.bulk_save_objects(notifications)
    db.session.commit()
    return len(notifications)


def _html_to_text(html):
    """Strip HTML tags to produce a plain-text fallback for multipart emails."""
    text = re.sub(r'<(style|script)[^>]*>.*?</\1>', '', html, flags=re.S | re.I)
    # Carry link targets through. Stripping tags alone leaves a text part whose
    # call to action reads "Sign in" with no address attached to it.
    text = re.sub(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        lambda m: f"{m.group(2)} ({m.group(1)})",
        text, flags=re.S | re.I,
    )
    text = re.sub(r'<[^>]+>', ' ', text)
    # Otherwise the text part shows "&copy;" and "&middot;" literally.
    text = unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return '\n'.join(line.strip() for line in text.splitlines()).strip()


def _send_via_mailjet(subject, recipients, html, text):
    """POSTs the email to Mailjet's Send API v3.1 over HTTPS."""
    sender_name, sender_email = _sender_pair()

    message = {
        "From": {"Email": sender_email, "Name": sender_name},
        "To": [{"Email": r} for r in recipients],
        "Subject": subject,
        "HTMLPart": html,
        "TextPart": text,
    }

    response = requests.post(
        MAILJET_ENDPOINT,
        auth=(current_app.config["MAILJET_API_KEY"],
              current_app.config["MAILJET_SECRET_KEY"]),
        json={"Messages": [message]},
        timeout=30,
    )
    if response.status_code >= 300:
        raise RuntimeError(
            f"Mailjet API returned {response.status_code}: {response.text[:400]}"
        )

    # v3.1 answers 200 even when a message was rejected, so the per-message
    # Status is what actually confirms delivery was accepted.
    try:
        messages = response.json().get("Messages", [])
    except ValueError:
        raise RuntimeError(f"Mailjet returned unparseable response: {response.text[:300]}")

    failed = [m for m in messages if str(m.get("Status", "")).lower() != "success"]
    if failed or not messages:
        raise RuntimeError(f"Mailjet rejected the message: {str(failed or messages)[:400]}")


def _send_via_brevo(subject, recipients, html, text):
    """POSTs the email to Brevo over HTTPS. Raises on any non-2xx response.

    Used instead of SMTP because hosts such as Render block outbound SMTP
    ports outright, which surfaces as an unroutable-network error.
    """
    sender_name, sender_email = _sender_pair()

    response = requests.post(
        BREVO_ENDPOINT,
        headers={
            "api-key": current_app.config["BREVO_API_KEY"],
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={
            "sender": {"name": sender_name or "Scholaris", "email": sender_email},
            "to": [{"email": r} for r in recipients],
            "subject": subject,
            "htmlContent": html,
            "textContent": text,
        },
        timeout=20,
    )
    if response.status_code >= 300:
        raise RuntimeError(
            f"Brevo API returned {response.status_code}: {response.text[:400]}"
        )


def _send_via_smtp(subject, recipients, html, text):
    msg = Message(subject=subject, recipients=recipients)
    msg.html = html
    msg.body = text
    msg.extra_headers = {
        "X-Mailer": "Scholaris",
        "Precedence": "transactional",
        "X-Auto-Response-Suppress": "OOF, AutoReply",
    }
    mail.send(msg)


def send_email(subject, recipients, template_name, raise_on_error=False, **context):
    """Renders app/templates/email/<template_name>.html and sends it.
    Always includes a plain-text alternative to avoid spam filters.
    Transport is chosen by active_transport(): Mailjet or Brevo over HTTPS
    where configured, else SMTP. Returns True on success, None on delivery
    failure (so callers never crash due to mail issues). Pass
    raise_on_error=True where the caller needs to report the error to the user.
    """
    transport = active_transport()

    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        current_app.logger.info("[mail:suppressed] to=%s subject=%s", recipients, subject)
        return True

    senders = {
        "mailjet": _send_via_mailjet,
        "brevo": _send_via_brevo,
        "smtp": _send_via_smtp,
    }
    try:
        # Rendering is inside the try on purpose: a template error is a mail
        # failure as far as the caller is concerned, and this function promises
        # not to crash them.
        html = render_template(f"email/{template_name}.html", **context)
        text = _html_to_text(html)
        senders[transport](subject, recipients, html, text)
        current_app.logger.info(
            "[mail:sent] via=%s to=%s subject=%s", transport, recipients, subject
        )
    except Exception as exc:
        import traceback
        current_app.logger.error(
            "[mail:failed] via=%s to=%s subject=%s\nerror=%r\n%s",
            transport, recipients, subject, exc, traceback.format_exc(),
        )
        if raise_on_error:
            raise
        return None
    return True


def notify_chapter_submitted(submission):
    supervisor = submission.project.supervisor
    notify(
        supervisor.id,
        f"{submission.project.student.full_name} submitted Chapter {submission.chapter_number}: {submission.chapter_title}",
        type="submission",
    )


def notify_chapter_reviewed(submission):
    student = submission.project.student
    verb = "approved" if submission.status == "approved" else "rejected"
    notify(
        student.id,
        f"Chapter {submission.chapter_number} ({submission.chapter_title}) was {verb} by your supervisor.",
        type="approval" if submission.status == "approved" else "rejection",
    )
    send_email(
        subject=f"Chapter {submission.chapter_number} {verb}",
        recipients=[student.email],
        template_name="chapter_reviewed",
        submission=submission,
        verb=verb,
    )


def notify_chapter_resubmitted(submission):
    supervisor = submission.project.supervisor
    notify(
        supervisor.id,
        f"{submission.project.student.full_name} resubmitted Chapter {submission.chapter_number}: {submission.chapter_title}.",
        type="submission",
    )


def notify_annotation_added(annotation):
    student = annotation.submission.project.student
    notify(
        student.id,
        f"New comment from your supervisor on Chapter {annotation.submission.chapter_number}.",
        type="annotation",
    )


def notify_supervisor_assigned(student, new_supervisor, is_reassignment=False):
    verb = "reassigned to" if is_reassignment else "assigned to"
    notify(
        student.id,
        f"You have been {verb} {new_supervisor.full_name}.",
        type="general",
    )
    notify(
        new_supervisor.id,
        f"{student.full_name} has been assigned to you.",
        type="general",
    )


def notify_user_created(user, plain_password, login_url, raise_on_error=False):
    first_name = user.full_name.split()[0] if user.full_name else "there"
    # Mail clients fetch images over the network, so assets and links must be
    # absolute. Prefer the host actually serving this request: BASE_URL is
    # operator-set and can point somewhere stale, which would aim every image
    # at a dead host. Fall back to login_url's origin outside a request.
    origin = ""
    if has_request_context():
        origin = request.url_root.rstrip("/")
    if not origin:
        parts = urlsplit(login_url)
        origin = f"{parts.scheme}://{parts.netloc}" if parts.netloc else ""
    current_app.logger.info("[mail:assets] origin=%s", origin)

    return send_email(
        subject=f"Hi {first_name}, your Scholaris account is ready",
        recipients=[user.email],
        template_name="welcome_credentials",
        raise_on_error=raise_on_error,
        user=user,
        plain_password=plain_password,
        login_url=login_url,
        year=datetime.now(timezone.utc).year,
        assets={
            "masthead": f"{origin}/static/img/email/masthead.png",
            "hero": f"{origin}/static/img/email/hero.jpg",
            "headline": f"{origin}/static/img/email/headline.png",
        },
        site={
            "privacy": f"{origin}/privacy-policy",
            "terms": f"{origin}/terms-of-service",
        },
    )


def notify_deadline_reminder(user, deadline, days_left):
    notify(
        user.id,
        f"Chapter {deadline.chapter_number} is due in {days_left} day(s) ({deadline.due_date}).",
        type="deadline",
    )
    send_email(
        subject=f"Deadline approaching: Chapter {deadline.chapter_number}",
        recipients=[user.email],
        template_name="deadline_reminder",
        user=user,
        deadline=deadline,
        days_left=days_left,
    )
