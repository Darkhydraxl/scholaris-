from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Notification, Meeting, meeting_students

notification_bp = Blueprint("notification", __name__)


@notification_bp.route("/")
@login_required
def list_notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).all()

    upcoming_meetings = []
    past_meetings = []

    if current_user.role == "student":
        all_meetings = (
            db.session.query(Meeting)
            .join(meeting_students, meeting_students.c.meeting_id == Meeting.id)
            .filter(meeting_students.c.student_id == current_user.id)
            .filter(Meeting.status != "cancelled")
            .order_by(Meeting.date.asc(), Meeting.time.asc())
            .all()
        )
        upcoming_meetings = [m for m in all_meetings if m.computed_status in ("upcoming", "live")]
        past_meetings = [m for m in all_meetings if m.computed_status == "completed"]

    return render_template(
        "notifications.html",
        notifications=notifications,
        upcoming_meetings=upcoming_meetings,
        past_meetings=past_meetings,
    )


@notification_bp.route("/unread-count")
@login_required
def unread_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({"unread_count": count})


@notification_bp.route("/<int:notification_id>/read", methods=["PATCH", "POST"])
@login_required
def mark_read(notification_id):
    notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    notification.is_read = True
    db.session.commit()
    return jsonify({"success": True})


@notification_bp.route("/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"success": True})
