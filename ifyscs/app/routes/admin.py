import calendar
import json
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, Response, current_app
from flask_login import current_user

from app.decorators import role_required, super_admin_required
from app.extensions import db, bcrypt
from app.models import User, Project, ChapterSubmission, ChapterAnnotation, Deadline, AuditLog, SupervisorAssignment
from app.forms import UserForm, DeadlineForm, BroadcastForm
from app.services import progress_service, report_service
from app.services.notification_service import notify_many, notify_supervisor_assigned, notify_user_created
from app.services.audit_service import log_action

admin_bp = Blueprint("admin", __name__)

_ROLE_CHOICES = [("student", "Student"), ("supervisor", "Supervisor")]


def _set_role_choices(form):
    form.role.choices = _ROLE_CHOICES


def _guard_super_admin_target(user):
    """Prevent any action on a super-admin account by a non-super-admin, and block self-modification."""
    if user.is_super_admin and not current_user.is_super_admin:
        log_action(
            current_user.id, "unauthorized_super_admin_access",
            f"{current_user.email} attempted to modify super-admin {user.email}",
        )
        flash("You cannot modify a super-admin account.", "error")
        return False
    if user.id == current_user.id and user.is_super_admin:
        flash("Super admins cannot modify their own account through this panel.", "error")
        return False
    return True


@admin_bp.route("/dashboard")
@role_required("admin")
def dashboard():
    students_count = User.query.filter_by(role="student").count()
    supervisors_count = User.query.filter_by(role="supervisor").count()
    submissions = ChapterSubmission.query.all()
    pending_count = sum(1 for s in submissions if s.status == "pending")
    approved_count = sum(1 for s in submissions if s.status == "approved")
    rejected_count = sum(1 for s in submissions if s.status == "rejected")

    total = pending_count + approved_count + rejected_count
    approved_pct = round(approved_count / total * 100) if total else 0
    pending_pct  = round(pending_count  / total * 100) if total else 0
    rejected_pct = 100 - approved_pct - pending_pct if total else 0

    by_chapter = {n: 0 for n in range(1, 6)}
    for s in submissions:
        by_chapter[s.chapter_number] = by_chapter.get(s.chapter_number, 0) + 1

    chart_data = {
        "bar": {"labels": [f"Ch {n}" for n in by_chapter], "values": list(by_chapter.values())},
        "pie": {
            "labels": ["Approved", "Pending", "Rejected"],
            "values": [approved_count, pending_count, rejected_count],
        },
    }

    return render_template(
        "admin/dashboard.html",
        students_count=students_count, supervisors_count=supervisors_count,
        pending_count=pending_count, approved_count=approved_count, rejected_count=rejected_count,
        approved_pct=approved_pct, pending_pct=pending_pct, rejected_pct=rejected_pct,
        chart_data=json.dumps(chart_data),
    )


@admin_bp.route("/users")
@role_required("admin")
def user_management():
    students = User.query.filter_by(role="student").order_by(User.full_name).all()
    supervisors = User.query.filter_by(role="supervisor").order_by(User.full_name).all()
    all_assignments = SupervisorAssignment.query.all()
    assignments = {a.student_id: a.supervisor for a in all_assignments}
    student_count_by_supervisor = {}
    for a in all_assignments:
        student_count_by_supervisor[a.supervisor_id] = student_count_by_supervisor.get(a.supervisor_id, 0) + 1
    form = UserForm()
    _set_role_choices(form)
    return render_template(
        "admin/user_management.html",
        students=students, supervisors=supervisors, assignments=assignments,
        student_count_by_supervisor=student_count_by_supervisor, form=form,
    )


@admin_bp.route("/users/create", methods=["POST"])
@super_admin_required
def create_user():
    form = UserForm()
    _set_role_choices(form)
    if form.validate_on_submit():
        # Explicit server-side guard: only super admins may mint admin accounts
        if form.role.data == "admin" and not current_user.is_super_admin:
            log_action(current_user.id, "unauthorized_admin_creation",
                       f"{current_user.email} attempted to create an admin account")
            flash("You are not allowed to create admin accounts.", "error")
            return redirect(url_for("admin.user_management"))

        if User.query.filter_by(email=form.email.data.lower().strip()).first():
            flash("A user with that email already exists.", "error")
        elif not form.password.data:
            flash("Password is required for new users.", "error")
        else:
            user = User(
                full_name=form.full_name.data.strip(),
                email=form.email.data.lower().strip(),
                department=form.department.data.strip() if form.department.data else None,
                role=form.role.data,
                is_active=form.is_active.data,
                password_hash=bcrypt.generate_password_hash(form.password.data).decode("utf-8"),
            )
            db.session.add(user)
            db.session.commit()
            log_action(current_user.id, "create_user", f"Created {user.role} account for {user.email}")
            try:
                base = current_app.config.get("BASE_URL", "")
                login_url = (base + url_for("auth.login")) if base else url_for("auth.login", _external=True)
                notify_user_created(user, plain_password=form.password.data, login_url=login_url)
            except Exception:
                current_app.logger.exception("Failed to send welcome email to %s", user.email)
            flash(f"{user.role.title()} account created. Login details sent to {user.email}.", "success")
    else:
        flash("Could not create user — check the form.", "error")
    return redirect(url_for("admin.user_management"))


@admin_bp.route("/users/<int:user_id>/edit", methods=["POST"])
@role_required("admin")
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if not _guard_super_admin_target(user):
        return redirect(url_for("admin.user_management"))

    form = UserForm()
    _set_role_choices(form)
    if not form.validate_on_submit():
        flash("Could not update user — check the form.", "error")
        return redirect(url_for("admin.user_management"))
    user.full_name = form.full_name.data.strip()
    if not user.is_super_admin:
        new_email = form.email.data.lower().strip()
        if new_email != user.email and User.query.filter_by(email=new_email).first():
            flash("That email is already in use by another account.", "error")
            return redirect(url_for("admin.user_management"))
        user.email = new_email
    user.department = form.department.data.strip() if form.department.data else None
    if form.password.data:
        user.password_hash = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
    db.session.commit()
    log_action(current_user.id, "edit_user", f"Edited user {user.email}")
    flash("User updated.", "success")
    return redirect(url_for("admin.user_management"))


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@role_required("admin")
def toggle_active(user_id):
    user = User.query.get_or_404(user_id)

    if not _guard_super_admin_target(user):
        return redirect(url_for("admin.user_management"))

    if user.id == current_user.id:
        abort(400)

    user.is_active = not user.is_active
    db.session.commit()
    log_action(current_user.id, "toggle_active",
               f"{'Activated' if user.is_active else 'Deactivated'} {user.email}")
    flash(f"{user.full_name} {'activated' if user.is_active else 'deactivated'}.", "success")
    return redirect(url_for("admin.user_management"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@role_required("admin")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if not _guard_super_admin_target(user):
        return redirect(url_for("admin.user_management"))

    if user.id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin.user_management"))

    name, email, role = user.full_name, user.email, user.role

    if role == "supervisor":
        projects = Project.query.filter_by(supervisor_id=user.id).all()
        if any(p.submissions for p in projects):
            flash(
                f"Cannot delete {name} — they have students with active submissions. "
                "Reassign those students first, then delete.",
                "error",
            )
            return redirect(url_for("admin.user_management"))
        for p in projects:
            db.session.delete(p)
        SupervisorAssignment.query.filter_by(supervisor_id=user.id).delete()
        ChapterAnnotation.query.filter_by(supervisor_id=user.id).delete()
        ChapterSubmission.query.filter_by(reviewed_by=user.id).update({"reviewed_by": None})

    if role == "student":
        SupervisorAssignment.query.filter_by(student_id=user.id).delete()

    AuditLog.query.filter_by(user_id=user.id).update({"user_id": None})
    db.session.delete(user)
    db.session.commit()

    log_action(current_user.id, "delete_user", f"Permanently deleted {role} account {email}")
    flash(f"{name}'s account has been permanently deleted.", "success")
    return redirect(url_for("admin.user_management"))


@admin_bp.route("/users/assign", methods=["POST"])
@role_required("admin")
def assign_supervisor():
    student_id = request.form.get("student_id", type=int)
    supervisor_id = request.form.get("supervisor_id", type=int)
    student = User.query.filter_by(id=student_id, role="student").first_or_404()
    supervisor = User.query.filter_by(id=supervisor_id, role="supervisor").first_or_404()

    assignment = SupervisorAssignment.query.filter_by(student_id=student.id).first()
    is_reassignment = assignment is not None and assignment.supervisor_id != supervisor.id
    supervisor_changed = assignment is None or assignment.supervisor_id != supervisor.id

    if assignment:
        assignment.supervisor_id = supervisor.id
    else:
        db.session.add(SupervisorAssignment(student_id=student.id, supervisor_id=supervisor.id))

    project = Project.query.filter_by(student_id=student.id).first()
    if project:
        project.supervisor_id = supervisor.id
    else:
        project = Project(student_id=student.id, supervisor_id=supervisor.id, title="FYP Project")
        db.session.add(project)

    db.session.commit()

    if supervisor_changed:
        notify_supervisor_assigned(student, supervisor, is_reassignment=is_reassignment)

    log_action(current_user.id, "assign_supervisor", f"Assigned {supervisor.full_name} to {student.full_name}")
    flash(f"{supervisor.full_name} assigned to {student.full_name}.", "success")
    return redirect(url_for("admin.user_management"))


@admin_bp.route("/deadlines", methods=["GET", "POST"])
@role_required("admin")
def deadlines():
    form = DeadlineForm()
    if form.validate_on_submit():
        deadline = Deadline(
            chapter_number=form.chapter_number.data,
            due_date=form.due_date.data,
            set_by=current_user.id,
        )
        db.session.add(deadline)
        db.session.commit()
        log_action(current_user.id, "create_deadline",
                   f"Set Chapter {deadline.chapter_number} deadline for {deadline.due_date}")
        flash("Deadline added.", "success")
        return redirect(url_for("admin.deadlines"))

    items = Deadline.query.order_by(Deadline.due_date.asc()).all()
    today = date.today()
    cal = calendar.Calendar(firstweekday=6)
    weeks = cal.monthdayscalendar(today.year, today.month)
    deadlines_by_day = {}
    for d in items:
        if d.due_date.year == today.year and d.due_date.month == today.month:
            deadlines_by_day.setdefault(d.due_date.day, []).append(d)

    return render_template(
        "admin/deadlines.html", deadlines=items, form=form, weeks=weeks,
        deadlines_by_day=deadlines_by_day, month_name=today.strftime("%B %Y"), today_day=today.day,
        today_year=today.year, today_month=today.month,
    )


@admin_bp.route("/deadlines/<int:deadline_id>/edit", methods=["POST"])
@role_required("admin")
def edit_deadline(deadline_id):
    deadline = Deadline.query.get_or_404(deadline_id)
    chapter = request.form.get("chapter_number", type=int)
    due = request.form.get("due_date", "").strip()
    if not chapter or not due:
        flash("Chapter number and due date are required.", "error")
        return redirect(url_for("admin.deadlines"))
    from datetime import date as date_cls
    try:
        deadline.due_date = date_cls.fromisoformat(due)
    except ValueError:
        flash("Invalid date format.", "error")
        return redirect(url_for("admin.deadlines"))
    deadline.chapter_number = chapter
    db.session.commit()
    log_action(current_user.id, "edit_deadline", f"Updated Chapter {chapter} deadline to {due}")
    flash("Deadline updated.", "success")
    return redirect(url_for("admin.deadlines"))


@admin_bp.route("/deadlines/<int:deadline_id>/delete", methods=["POST"])
@role_required("admin")
def delete_deadline(deadline_id):
    deadline = Deadline.query.get_or_404(deadline_id)
    db.session.delete(deadline)
    db.session.commit()
    log_action(current_user.id, "delete_deadline",
               f"Deleted Chapter {deadline.chapter_number} deadline")
    flash("Deadline removed.", "success")
    return redirect(url_for("admin.deadlines"))


@admin_bp.route("/progress-report")
@role_required("admin")
def progress_report():
    projects = Project.query.all()
    rows = []
    for p in projects:
        rows.append({
            "student": p.student,
            "supervisor": p.supervisor,
            "project": p,
            "percent": progress_service.project_progress_percent(p),
            "stage": p.current_stage,
        })
    rows.sort(key=lambda r: r["student"].full_name)
    return render_template("admin/progress_report.html", rows=rows)


@admin_bp.route("/progress-report/export.pdf")
@role_required("admin")
def export_progress_report():
    projects = Project.query.all()
    pdf_bytes = report_service.build_progress_report_pdf(projects)
    log_action(current_user.id, "export_progress_report", "Exported department progress report PDF")
    return Response(
        pdf_bytes, mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=scholaris_progress_report.pdf"},
    )


@admin_bp.route("/broadcast", methods=["GET", "POST"])
@role_required("admin")
def broadcast():
    form = BroadcastForm()
    if form.validate_on_submit():
        if form.target.data == "students":
            recipients = User.query.filter_by(role="student").all()
        elif form.target.data == "supervisors":
            recipients = User.query.filter_by(role="supervisor").all()
        else:
            recipients = User.query.filter(User.role.in_(("student", "supervisor"))).all()

        notify_many([u.id for u in recipients], form.message.data.strip(), type="broadcast")
        log_action(current_user.id, "broadcast",
                   f"Broadcast to {form.target.data}: {form.message.data[:80]}")
        flash(f"Broadcast sent to {len(recipients)} user(s).", "success")
        return redirect(url_for("admin.broadcast"))

    return render_template("admin/broadcast.html", form=form)


@admin_bp.route("/audit-log")
@super_admin_required
def audit_log():
    action_filter = request.args.get("action")
    query = AuditLog.query
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    items = query.order_by(AuditLog.timestamp.desc()).limit(200).all()
    distinct_actions = [r[0] for r in db.session.query(AuditLog.action).distinct().all()]
    return render_template(
        "admin/audit_log.html", logs=items, actions=distinct_actions, action_filter=action_filter,
    )
