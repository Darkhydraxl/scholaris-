import re
from app.extensions import db, mail
from app.models import Notification, User
from flask_mail import Message
from flask import current_app, render_template


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
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return '\n'.join(line.strip() for line in text.splitlines()).strip()


def send_email(subject, recipients, template_name, **context):
    """Renders app/templates/email/<template_name>.html and sends it.
    Always includes a plain-text alternative to avoid spam filters.
    Returns the Message on success, None on delivery failure (so callers
    never crash due to SMTP issues).
    """
    html = render_template(f"email/{template_name}.html", **context)
    msg = Message(subject=subject, recipients=recipients)
    msg.html = html
    msg.body = _html_to_text(html)
    msg.extra_headers = {
        "X-Mailer": "Scholaris",
        "Precedence": "transactional",
        "X-Auto-Response-Suppress": "OOF, AutoReply",
    }
    try:
        mail.send(msg)
        if current_app.config.get("MAIL_SUPPRESS_SEND"):
            current_app.logger.info(
                "[mail:suppressed] to=%s subject=%s", recipients, subject
            )
    except Exception as exc:
        current_app.logger.warning(
            "[mail:failed] to=%s subject=%s error=%s", recipients, subject, exc
        )
        return None
    return msg


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


def notify_user_created(user, plain_password, login_url):
    first_name = user.full_name.split()[0] if user.full_name else "there"
    send_email(
        subject=f"Hi {first_name}, your Scholaris account is ready",
        recipients=[user.email],
        template_name="welcome_credentials",
        user=user,
        plain_password=plain_password,
        login_url=login_url,
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
