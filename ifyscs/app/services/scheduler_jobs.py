from datetime import date

from app.extensions import db
from app.models import Deadline, Project, ChapterSubmission
from app.services.notification_service import notify_deadline_reminder

REMINDER_THRESHOLDS_DAYS = (7, 1)  # 7 days out, and 24 hours out


def check_deadline_reminders(app):
    """Runs daily at the configured hour. Notifies students who have not yet
    submitted a given chapter, for deadlines landing on one of the reminder
    thresholds. Safe to call directly (e.g. from a shell) for verification.
    """
    with app.app_context():
        today = date.today()
        deadlines = Deadline.query.all()
        sent = 0
        for deadline in deadlines:
            days_left = (deadline.due_date - today).days
            if days_left not in REMINDER_THRESHOLDS_DAYS:
                continue

            projects = Project.query.all()
            for project in projects:
                already_submitted = ChapterSubmission.query.filter_by(
                    project_id=project.id, chapter_number=deadline.chapter_number
                ).first()
                if already_submitted:
                    continue
                notify_deadline_reminder(project.student, deadline, days_left)
                sent += 1
        return sent
