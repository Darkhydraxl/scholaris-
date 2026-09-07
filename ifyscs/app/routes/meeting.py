from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, abort, current_app
from flask_login import current_user, login_required

from app.decorators import role_required
from app.extensions import db
from app.forms import ScheduleMeetingForm
from app.models import Meeting, SupervisorAssignment, meeting_students
from app.services import meeting_service
from app.services.notification_service import notify
from app.services.audit_service import log_action

meeting_bp = Blueprint("meeting", __name__)


def _supervisor_students():
    assignments = SupervisorAssignment.query.filter_by(supervisor_id=current_user.id).all()
    return [a.student for a in assignments]


# ── Supervisor: list ──────────────────────────────────────────────────────────

@meeting_bp.route("/")
@role_required("supervisor")
def my_meetings():
    meetings = (
        Meeting.query
        .filter_by(supervisor_id=current_user.id)
        .order_by(Meeting.date.desc(), Meeting.time.desc())
        .all()
    )
    upcoming = [m for m in meetings if m.computed_status in ("upcoming", "live")]
    past     = [m for m in meetings if m.computed_status == "completed"]
    cancelled = [m for m in meetings if m.computed_status == "cancelled"]
    return render_template(
        "supervisor/meetings.html",
        meetings=meetings,
        upcoming=upcoming,
        past=past,
        cancelled=cancelled,
    )


# ── Supervisor: schedule ──────────────────────────────────────────────────────

@meeting_bp.route("/schedule", methods=["GET", "POST"])
@role_required("supervisor")
def schedule():
    form = ScheduleMeetingForm()
    if form.validate_on_submit():
        meeting_date = form.date.data
        meeting_time = form.time.data
        meeting_dt = datetime.combine(meeting_date, meeting_time)

        if meeting_dt <= datetime.utcnow():
            flash("You cannot schedule a meeting in the past.", "error")
            return render_template("supervisor/schedule_meeting.html", form=form)

        platform = form.platform.data
        title = form.title.data.strip()
        description = (form.description.data or "").strip() or None
        duration = form.duration.data

        # Save the supervisor's Zoom email if provided (or reuse saved one)
        submitted_zoom_email = (form.zoom_email.data or "").strip() or None
        if submitted_zoom_email:
            current_user.zoom_email = submitted_zoom_email

        if platform == "zoom" and not current_user.zoom_email:
            flash("Please enter your Zoom email so we can set you as the meeting host.", "error")
            return render_template("supervisor/schedule_meeting.html", form=form)

        # Google Meet: requires connected Google account
        if platform == "google_meet" and not current_user.google_oauth_token:
            flash("Please connect your Google account first to create Google Meet links automatically.", "error")
            return render_template("supervisor/schedule_meeting.html", form=form)

        try:
            ext_id, link = meeting_service.create_meeting_link(
                platform, title, meeting_dt, duration, description or "",
                host_email=current_user.zoom_email if platform == "zoom" else None,
                google_oauth_token=current_user.google_oauth_token if platform == "google_meet" else None,
            )
        except Exception as exc:
            current_app.logger.error("Meeting API error (%s): %s", platform, exc)
            pname = "Google Meet" if platform == "google_meet" else "Zoom"
            flash(f"Could not create {pname} meeting: {str(exc)[:200]}", "error")
            return render_template("supervisor/schedule_meeting.html", form=form)

        meeting = Meeting(
            supervisor_id=current_user.id,
            title=title,
            description=description,
            platform=platform,
            meeting_link=link,
            meeting_id=ext_id,
            date=meeting_date,
            time=meeting_time,
            duration=duration,
        )
        db.session.add(meeting)

        students = _supervisor_students()
        for s in students:
            meeting.students.append(s)

        db.session.flush()

        pname = "Google Meet" if platform == "google_meet" else "Zoom"
        date_str = meeting_date.strftime("%b %d, %Y")
        time_str = meeting_time.strftime("%H:%M")
        for s in students:
            notify(
                s.id,
                f'Meeting scheduled: "{title}" on {date_str} at {time_str} via {pname}. Join: {link}',
                type="meeting",
            )

        db.session.commit()
        log_action(current_user.id, "schedule_meeting", f"Scheduled '{title}' on {meeting_date}")
        flash(f'Meeting "{title}" scheduled and students notified!', "success")
        return redirect(url_for("meeting.my_meetings"))

    return render_template("supervisor/schedule_meeting.html", form=form)


# ── Supervisor: cancel ────────────────────────────────────────────────────────

@meeting_bp.route("/<int:meeting_id>/cancel", methods=["POST"])
@role_required("supervisor")
def cancel(meeting_id):
    meeting = Meeting.query.filter_by(id=meeting_id, supervisor_id=current_user.id).first_or_404()

    if meeting.computed_status in ("completed", "cancelled"):
        flash("This meeting cannot be cancelled.", "error")
        return redirect(url_for("meeting.my_meetings"))

    meeting.status = "cancelled"
    pname = meeting.platform_display
    date_str = meeting.date.strftime("%b %d, %Y")
    time_str = meeting.time.strftime("%H:%M")
    for s in meeting.students:
        notify(
            s.id,
            f'Meeting cancelled: "{meeting.title}" scheduled for {date_str} at {time_str} via {pname} has been cancelled.',
            type="meeting",
        )

    db.session.commit()
    log_action(current_user.id, "cancel_meeting", f"Cancelled meeting '{meeting.title}'")
    flash("Meeting cancelled and students notified.", "success")
    return redirect(url_for("meeting.my_meetings"))


# ── Admin: all meetings ───────────────────────────────────────────────────────

@meeting_bp.route("/admin-all")
@role_required("admin")
def admin_all():
    meetings = Meeting.query.order_by(Meeting.date.desc(), Meeting.time.desc()).all()
    return render_template("admin/meetings.html", meetings=meetings)
