from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import current_user

from app.decorators import role_required
from app.extensions import db
from app.models import SupervisorAssignment, Project, ChapterSubmission
from app.forms import ReviewSubmissionForm
from app.services import progress_service
from app.services.notification_service import notify_chapter_reviewed
from app.services.audit_service import log_action

supervisor_bp = Blueprint("supervisor", __name__)


def _assigned_students():
    assignments = SupervisorAssignment.query.filter_by(supervisor_id=current_user.id).all()
    return [a.student for a in assignments]


def _assigned_projects():
    students = _assigned_students()
    student_ids = [s.id for s in students]
    if not student_ids:
        return []
    return Project.query.filter(Project.student_id.in_(student_ids)).all()


@supervisor_bp.route("/dashboard")
@role_required("supervisor")
def dashboard():
    projects = _assigned_projects()
    all_submissions = [s for p in projects for s in p.submissions]
    pending = [s for s in all_submissions if s.status == "pending"]
    approved = [s for s in all_submissions if s.status == "approved"]
    rejected = [s for s in all_submissions if s.status == "rejected"]

    student_rows = []
    for p in projects:
        approved_ch = sum(1 for s in p.submissions if s.status == "approved")
        student_rows.append({
            "project": p,
            "student": p.student,
            "percent": progress_service.project_progress_percent(p),
            "approved_chapters": approved_ch,
            "latest": sorted(p.submissions, key=lambda s: s.submitted_at, reverse=True)[0] if p.submissions else None,
        })

    recent_activity = sorted(all_submissions, key=lambda s: s.submitted_at, reverse=True)[:4]

    return render_template(
        "supervisor/dashboard.html",
        students_count=len(projects), pending_count=len(pending),
        approved_count=len(approved), rejected_count=len(rejected),
        student_rows=student_rows, recent_activity=recent_activity,
    )


@supervisor_bp.route("/my-students")
@role_required("supervisor")
def my_students():
    projects = _assigned_projects()
    rows = []
    for p in projects:
        rows.append({
            "project": p,
            "student": p.student,
            "percent": progress_service.project_progress_percent(p),
            "counts": progress_service.submission_counts(p),
            "latest": sorted(p.submissions, key=lambda s: s.submitted_at, reverse=True)[0] if p.submissions else None,
        })
    return render_template("supervisor/my_students.html", rows=rows)


@supervisor_bp.route("/review/<int:submission_id>", methods=["GET", "POST"])
@role_required("supervisor")
def review(submission_id):
    submission = ChapterSubmission.query.get_or_404(submission_id)
    if submission.project.supervisor_id != current_user.id:
        abort(403)

    form = ReviewSubmissionForm()
    if form.validate_on_submit():
        decision = form.decision.data
        if decision not in ("approved", "rejected"):
            abort(400)
        submission.status = decision
        submission.overall_comment = (form.overall_comment.data or '').strip() or None
        from app.models import utcnow
        submission.reviewed_at = utcnow()
        submission.reviewed_by = current_user.id

        db.session.commit()

        notify_chapter_reviewed(submission)
        log_action(
            current_user.id, f"{decision}_submission",
            f"{decision.capitalize()} Chapter {submission.chapter_number} for {submission.project.student.full_name}",
        )
        flash(f"Submission {decision}.", "success")
        return redirect(url_for("supervisor.my_students"))

    return render_template("supervisor/review.html", submission=submission, form=form)


@supervisor_bp.route("/review-queue")
@role_required("supervisor")
def review_queue():
    projects = _assigned_projects()
    pending = []
    for p in projects:
        for s in p.submissions:
            if s.status == "pending":
                pending.append(s)
    pending.sort(key=lambda s: s.submitted_at)
    return render_template("supervisor/review_queue.html", pending=pending)


@supervisor_bp.route("/student/<int:student_id>")
@role_required("supervisor")
def student_detail(student_id):
    student_ids = [s.id for s in _assigned_students()]
    if student_id not in student_ids:
        abort(403)
    from app.models import User
    student = User.query.get_or_404(student_id)
    project = Project.query.filter_by(student_id=student_id).first_or_404()
    submissions = sorted(project.submissions, key=lambda s: s.submitted_at, reverse=True)
    percent = progress_service.project_progress_percent(project)
    counts = progress_service.submission_counts(project)
    return render_template(
        "supervisor/student_detail.html",
        student=student, project=project,
        submissions=submissions, percent=percent, counts=counts,
    )


@supervisor_bp.route("/feedback-history")
@role_required("supervisor")
def feedback_history():
    projects = _assigned_projects()
    project_ids = [p.id for p in projects]
    query = ChapterSubmission.query.filter(
        ChapterSubmission.project_id.in_(project_ids),
        ChapterSubmission.status.in_(("approved", "rejected")),
    )
    status_filter = request.args.get("status")
    if status_filter in ("approved", "rejected"):
        query = query.filter(ChapterSubmission.status == status_filter)
    items = query.order_by(ChapterSubmission.reviewed_at.desc()).all()
    return render_template("supervisor/feedback_history.html", items=items, status_filter=status_filter)
