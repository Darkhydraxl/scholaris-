import os
import uuid
import json
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort, jsonify
from flask_login import current_user

from app.decorators import role_required
from app.extensions import db
from app.models import Project, ChapterSubmission, SupervisorAssignment, Meeting, User
from app.forms import SubmitChapterForm, ResubmitChapterForm
from app.services import progress_service
from app.services.notification_service import notify_chapter_submitted, notify_chapter_resubmitted
from app.models import utcnow
from app.services.audit_service import log_action

student_bp = Blueprint("student", __name__)


@student_bp.before_request
def _gate_unassigned_students():
    """Block students who have not yet been assigned a supervisor from accessing
    any student feature.  Redirect them to the pending page instead."""
    if not current_user.is_authenticated:
        return  # Flask-Login / role_required will handle this
    # Only gate students; don't interfere if somehow another role hits this blueprint
    if current_user.role != "student":
        return
    # Allow the pending page itself to avoid an infinite redirect loop
    if request.endpoint == "student.pending":
        return
    has_assignment = SupervisorAssignment.query.filter_by(
        student_id=current_user.id
    ).first() is not None
    if not has_assignment:
        return redirect(url_for("student.pending"))

CHAPTER_TITLES = {
    1: "Introduction",
    2: "Literature Review",
    3: "Research Methodology",
    4: "Implementation and Results",
    5: "Conclusion and Recommendations",
}


def _current_project():
    project = Project.query.filter_by(student_id=current_user.id).first()
    if project is None:
        # Student has an assignment (gate passed) but no project — auto-create it
        assignment = SupervisorAssignment.query.filter_by(student_id=current_user.id).first()
        if not assignment:
            abort(404, "No project found for this student. Contact an administrator.")
        project = Project(
            student_id=current_user.id,
            supervisor_id=assignment.supervisor_id,
            title="FYP Project",
        )
        db.session.add(project)
        db.session.commit()
    return project


def _validate_pdf_signature(file_storage):
    """Server-side content sniffing -- never trust the client-supplied extension/MIME alone."""
    head = file_storage.stream.read(5)
    file_storage.stream.seek(0)
    return head == b"%PDF-"


def _weekly_activity_chart(project):
    """Submitted vs approved counts for each of the last 7 calendar days
    (oldest → today), so clicking a day shows that specific date's activity."""
    from datetime import date as date_type
    today = datetime.utcnow().date()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    day_to_idx = {d: i for i, d in enumerate(days)}

    day_abbrevs = ["M", "T", "W", "T", "F", "S", "S"]
    labels = [day_abbrevs[d.weekday()] for d in days]

    submitted_by_day = [0] * 7
    approved_by_day = [0] * 7
    for s in project.submissions:
        idx = day_to_idx.get(s.submitted_at.date())
        if idx is not None:
            submitted_by_day[idx] += 1
        if s.status == "approved" and s.reviewed_at:
            idx2 = day_to_idx.get(s.reviewed_at.date())
            if idx2 is not None:
                approved_by_day[idx2] += 1

    return {
        "labels": labels,
        "submitted": submitted_by_day,
        "approved": approved_by_day,
        "today_index": 6,
        "day_names": [d.strftime("%a, %b %d") for d in days],
    }


def _progress_trend(project):
    """Percentage-point change in completion vs 30 days ago, from real
    reviewed_at timestamps (chapters approved more than 30 days ago count
    toward the "before" snapshot)."""
    cutoff = datetime.utcnow() - timedelta(days=30)
    approved_now = sum(1 for s in project.submissions if s.status == "approved")
    approved_before = sum(
        1 for s in project.submissions
        if s.status == "approved" and s.reviewed_at and s.reviewed_at <= cutoff
    )
    total = progress_service.TOTAL_CHAPTERS
    return round((approved_now - approved_before) / total * 100)


@student_bp.route("/dashboard")
@role_required("student")
def dashboard():
    project = _current_project()
    counts = progress_service.submission_counts(project)
    breakdown = progress_service.project_chapter_breakdown(project)
    percent = progress_service.project_progress_percent(project)
    recent_submissions = sorted(project.submissions, key=lambda s: s.submitted_at, reverse=True)[:4]
    from app.models import Deadline
    from datetime import date as date_cls
    today_date = date_cls.today()
    approved_chapters = {
        s.chapter_number for s in project.submissions if s.status == "approved"
    }
    upcoming_deadlines = (
        Deadline.query
        .filter(
            Deadline.due_date >= today_date,
            Deadline.chapter_number.notin_(approved_chapters),
        )
        .order_by(Deadline.due_date.asc())
        .all()
    )
    deadline_cards = []
    for d in upcoming_deadlines:
        days_left = (d.due_date - today_date).days
        pct = max(0, min(100, int((30 - days_left) / 30 * 100)))
        if days_left <= 5:
            urgency = 'critical'
        elif days_left <= 14:
            urgency = 'warning'
        else:
            urgency = 'ok'
        deadline_cards.append({'d': d, 'days_left': days_left, 'pct': pct, 'urgency': urgency})
    weekly_chart = _weekly_activity_chart(project)
    trend = _progress_trend(project)
    return render_template(
        "student/dashboard.html",
        project=project, counts=counts, breakdown=breakdown, percent=percent,
        recent_submissions=recent_submissions, deadline_cards=deadline_cards,
        weekly_chart=json.dumps(weekly_chart), trend=trend,
    )


@student_bp.route("/submit-chapter", methods=["GET", "POST"])
@role_required("student")
def submit_chapter():
    project = _current_project()
    supervisor = User.query.get(project.supervisor_id) if project else None

    approved_chapters = {
        s.chapter_number for s in
        ChapterSubmission.query.filter_by(project_id=project.id, status="approved").all()
    } if project else set()
    all_approved = {1, 2, 3, 4, 5}.issubset(approved_chapters)

    form = SubmitChapterForm()
    if form.validate_on_submit():
        file = form.file.data
        if not _validate_pdf_signature(file):
            flash("That file doesn't look like a valid PDF.", "error")
            return render_template("student/submit_chapter.html", form=form, supervisor=supervisor, all_approved=all_approved)

        upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "submissions")
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.pdf"
        file.save(os.path.join(upload_dir, filename))

        chapter_numbers = sorted(int(n) for n in form.chapter_numbers.data)
        submissions = []
        for chapter_number in chapter_numbers:
            # Reuse an existing rejected submission rather than duplicating
            existing = ChapterSubmission.query.filter_by(
                project_id=project.id,
                chapter_number=chapter_number,
                status="rejected",
            ).order_by(ChapterSubmission.submitted_at.desc()).first()

            if existing:
                existing.file_path       = f"uploads/submissions/{filename}"
                existing.status          = "pending"
                existing.submitted_at    = utcnow()
                existing.overall_comment = form.notes.data.strip() if form.notes.data else None
                existing.reviewed_at     = None
                existing.reviewed_by     = None
                submission = existing
            else:
                submission = ChapterSubmission(
                    project_id=project.id,
                    chapter_number=chapter_number,
                    chapter_title=f"Chapter {chapter_number}",
                    file_path=f"uploads/submissions/{filename}",
                    status="pending",
                    overall_comment=form.notes.data.strip() if form.notes.data else None,
                )
                db.session.add(submission)
            submissions.append(submission)

        if chapter_numbers:
            project.current_stage = f"Chapter {chapter_numbers[-1]}"
        db.session.commit()

        for submission in submissions:
            notify_chapter_submitted(submission)
        chapters_str = ", ".join(f"Chapter {n}" for n in chapter_numbers)
        log_action(current_user.id, "submit_chapter", f"Submitted {chapters_str}")

        count = len(chapter_numbers)
        flash(f"{'Chapter' if count == 1 else f'{count} chapters'} submitted successfully.", "success")
        return redirect(url_for("student.submissions"))

    return render_template("student/submit_chapter.html", form=form, supervisor=supervisor, all_approved=all_approved)


@student_bp.route("/weekly-chart-data")
@role_required("student")
def weekly_chart_data():
    project = _current_project()
    return jsonify(_weekly_activity_chart(project))


@student_bp.route("/submissions")
@role_required("student")
def submissions():
    project = _current_project()
    items = sorted(project.submissions, key=lambda s: s.submitted_at, reverse=True)
    return render_template("student/submissions.html", project=project, submissions=items)


@student_bp.route("/submissions/<int:submission_id>/annotations")
@role_required("student")
def annotation_viewer(submission_id):
    submission = ChapterSubmission.query.get_or_404(submission_id)
    if submission.project.student_id != current_user.id:
        abort(403)
    resubmit_form = ResubmitChapterForm()
    return render_template("student/annotation_viewer.html", submission=submission, resubmit_form=resubmit_form)


@student_bp.route("/submissions/<int:submission_id>/resubmit", methods=["POST"])
@role_required("student")
def resubmit(submission_id):
    submission = ChapterSubmission.query.get_or_404(submission_id)
    if submission.project.student_id != current_user.id:
        abort(403)
    if submission.status == "approved":
        flash("This chapter is already approved and cannot be resubmitted.", "error")
        return redirect(url_for("student.annotation_viewer", submission_id=submission_id))

    form = ResubmitChapterForm()
    if form.validate_on_submit():
        file = form.file.data
        if not _validate_pdf_signature(file):
            flash("That file doesn't look like a valid PDF.", "error")
            return redirect(url_for("student.annotation_viewer", submission_id=submission_id))

        upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "submissions")
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.pdf"
        file.save(os.path.join(upload_dir, filename))

        # Remove previous file from disk (best-effort)
        old_abs = os.path.join(current_app.root_path, "static", submission.file_path)
        try:
            if os.path.isfile(old_abs):
                os.remove(old_abs)
        except OSError:
            pass

        submission.file_path     = f"uploads/submissions/{filename}"
        submission.status        = "pending"
        submission.submitted_at  = utcnow()
        submission.overall_comment = None
        submission.reviewed_at   = None
        submission.reviewed_by   = None
        db.session.commit()

        notify_chapter_resubmitted(submission)
        log_action(current_user.id, "resubmit_chapter",
                   f"Resubmitted Chapter {submission.chapter_number}")

        flash(f"Chapter {submission.chapter_number} resubmitted — your supervisor has been notified.", "success")
    else:
        flash("Please select a valid PDF file to resubmit.", "error")

    return redirect(url_for("student.annotation_viewer", submission_id=submission_id))


@student_bp.route("/pending")
@role_required("student")
def pending():
    return render_template("student/pending.html")


@student_bp.route("/meetings")
@role_required("student")
def meetings():
    all_meetings = (
        Meeting.query
        .filter(Meeting.students.any(id=current_user.id))
        .order_by(Meeting.date.desc(), Meeting.time.desc())
        .all()
    )
    upcoming  = [m for m in all_meetings if m.computed_status in ("upcoming", "live")]
    past      = [m for m in all_meetings if m.computed_status == "completed"]
    cancelled = [m for m in all_meetings if m.computed_status == "cancelled"]
    return render_template(
        "student/meetings.html",
        meetings=all_meetings,
        upcoming=upcoming,
        past=past,
        cancelled=cancelled,
    )
