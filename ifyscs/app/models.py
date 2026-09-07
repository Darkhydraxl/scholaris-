from datetime import datetime, timezone
from flask_login import UserMixin

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


ROLES = ("student", "supervisor", "admin")
TOPIC_STATUSES = ("proposed", "approved", "in_progress", "completed")
SUBMISSION_STATUSES = ("pending", "approved", "rejected")
NOTIFICATION_TYPES = (
    "submission", "approval", "rejection", "annotation",
    "deadline", "broadcast", "assignment", "meeting", "general",
)

meeting_students = db.Table(
    "meeting_students",
    db.Column("meeting_id", db.Integer, db.ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True),
    db.Column("student_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(120), nullable=True)
    avatar             = db.Column(db.String(255), nullable=True)
    zoom_email         = db.Column(db.String(120), nullable=True)
    google_email       = db.Column(db.String(120), nullable=True)
    google_oauth_token = db.Column(db.Text, nullable=True)  # JSON refresh token
    created_at         = db.Column(db.DateTime, default=utcnow, nullable=False)
    is_active       = db.Column(db.Boolean, default=True,  nullable=False)
    is_super_admin  = db.Column(db.Boolean, default=False, nullable=False)

    projects_as_student = db.relationship(
        "Project", foreign_keys="Project.student_id", back_populates="student",
        cascade="all, delete-orphan",
    )
    projects_as_supervisor = db.relationship(
        "Project", foreign_keys="Project.supervisor_id", back_populates="supervisor",
    )
    notifications = db.relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan",
        order_by="desc(Notification.created_at)",
    )

    def get_id(self):
        return str(self.id)

    @property
    def is_student(self):
        return self.role == "student"

    @property
    def is_supervisor(self):
        return self.role == "supervisor"

    @property
    def is_admin(self):
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class SupervisorAssignment(db.Model):
    __tablename__ = "supervisor_assignments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    student = db.relationship("User", foreign_keys=[student_id])
    supervisor = db.relationship("User", foreign_keys=[supervisor_id])

    def __repr__(self):
        return f"<SupervisorAssignment student={self.student_id} supervisor={self.supervisor_id}>"


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    topic_status = db.Column(db.String(30), default="proposed", nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    expected_submission_date = db.Column(db.Date, nullable=True)
    current_stage = db.Column(db.String(120), default="Chapter 1", nullable=False)

    student = db.relationship("User", foreign_keys=[student_id], back_populates="projects_as_student")
    supervisor = db.relationship("User", foreign_keys=[supervisor_id], back_populates="projects_as_supervisor")
    submissions = db.relationship(
        "ChapterSubmission", back_populates="project", cascade="all, delete-orphan",
        order_by="ChapterSubmission.chapter_number",
    )

    def __repr__(self):
        return f"<Project {self.title!r} student={self.student_id}>"


class ChapterSubmission(db.Model):
    __tablename__ = "chapter_submissions"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    chapter_number = db.Column(db.Integer, nullable=False)
    chapter_title = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    submitted_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    overall_comment = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    project = db.relationship("Project", back_populates="submissions")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])
    annotations = db.relationship(
        "ChapterAnnotation", back_populates="submission", cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<ChapterSubmission ch{self.chapter_number} project={self.project_id} {self.status}>"


class ChapterAnnotation(db.Model):
    __tablename__ = "chapter_annotations"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("chapter_submissions.id"), nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    page_number = db.Column(db.Integer, nullable=False)
    x_position = db.Column(db.Float, nullable=False)
    y_position = db.Column(db.Float, nullable=False)
    width = db.Column(db.Float, nullable=False)
    height = db.Column(db.Float, nullable=False)
    selected_text = db.Column(db.Text, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    is_resolved = db.Column(db.Boolean, default=False, nullable=False)

    submission = db.relationship("ChapterSubmission", back_populates="annotations")
    supervisor = db.relationship("User", foreign_keys=[supervisor_id])

    def to_dict(self):
        return {
            "id": self.id,
            "submission_id": self.submission_id,
            "supervisor_id": self.supervisor_id,
            "supervisor_name": self.supervisor.full_name if self.supervisor else None,
            "page_number": self.page_number,
            "x_position": self.x_position,
            "y_position": self.y_position,
            "width": self.width,
            "height": self.height,
            "selected_text": self.selected_text,
            "comment": self.comment,
            "created_at": self.created_at.isoformat(),
            "is_resolved": self.is_resolved,
        }

    def __repr__(self):
        return f"<ChapterAnnotation submission={self.submission_id} page={self.page_number}>"


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    type = db.Column(db.String(30), nullable=False, default="submission")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", back_populates="notifications")

    def __repr__(self):
        return f"<Notification to={self.user_id} read={self.is_read}>"


class Deadline(db.Model):
    __tablename__ = "deadlines"

    id = db.Column(db.Integer, primary_key=True)
    chapter_number = db.Column(db.Integer, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    set_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    setter = db.relationship("User", foreign_keys=[set_by])

    def __repr__(self):
        return f"<Deadline ch{self.chapter_number} due={self.due_date}>"


class Meeting(db.Model):
    __tablename__ = "meetings"

    id = db.Column(db.Integer, primary_key=True)
    supervisor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    platform = db.Column(db.String(20), nullable=False)       # "google_meet" | "zoom"
    meeting_link = db.Column(db.String(500), nullable=True)
    meeting_id = db.Column(db.String(200), nullable=True)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    duration = db.Column(db.Integer, nullable=False)           # minutes
    status = db.Column(db.String(20), default="active", nullable=False)  # "active" | "cancelled"
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    supervisor = db.relationship("User", foreign_keys=[supervisor_id], backref="meetings_as_supervisor")
    students = db.relationship("User", secondary="meeting_students", backref="meetings_as_student")

    @property
    def computed_status(self):
        if self.status == "cancelled":
            return "cancelled"
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        meeting_dt = datetime.combine(self.date, self.time)
        end_dt = meeting_dt + timedelta(minutes=self.duration)
        if now < meeting_dt:
            return "upcoming"
        if now <= end_dt:
            return "live"
        return "completed"

    @property
    def meeting_datetime(self):
        from datetime import datetime
        return datetime.combine(self.date, self.time)

    @property
    def end_datetime(self):
        from datetime import timedelta
        return self.meeting_datetime + timedelta(minutes=self.duration)

    @property
    def platform_display(self):
        return "Google Meet" if self.platform == "google_meet" else "Zoom"

    @property
    def duration_display(self):
        if self.duration < 60:
            return f"{self.duration} min"
        h, m = divmod(self.duration, 60)
        return f"{h}h" if m == 0 else f"{h}h {m}min"

    def __repr__(self):
        return f"<Meeting {self.title!r} {self.date}>"


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    detail = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=utcnow, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<AuditLog {self.action} user={self.user_id}>"
