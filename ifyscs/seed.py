"""Seeds the Scholaris database with realistic demo data: 1 super admin (from env),
1 ordinary admin, 3 supervisors, 8 students, projects, PDFs, submissions, annotations,
notifications, and deadlines.

Run with: python seed.py

Environment variables required (load from .env):
  SUPER_ADMIN_EMAIL     — email for the super-admin account
  SUPER_ADMIN_PASSWORD  — password for the super-admin account
"""
import os
import shutil
from datetime import date, timedelta, datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER

from app import create_app
from app.extensions import db, bcrypt
from app.models import (
    User, Project, SupervisorAssignment, ChapterSubmission,
    ChapterAnnotation, Notification, Deadline, AuditLog, Meeting, meeting_students,
)

CHAPTER_TITLES = {
    1: "Introduction",
    2: "Literature Review",
    3: "Research Methodology",
    4: "Implementation and Results",
    5: "Conclusion and Recommendations",
}

SEED_UPLOAD_DIR = None  # set inside main() once app context is available


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_chapter_pdf(path, project_title, chapter_number, chapter_title, student_name, department):
    styles = getSampleStyleSheet()
    title_style   = ParagraphStyle("TitleCenter", parent=styles["Title"],   alignment=TA_CENTER)
    sub_style     = ParagraphStyle("SubCenter",   parent=styles["Normal"],  alignment=TA_CENTER, fontSize=11, spaceAfter=6)
    body_style    = ParagraphStyle("Body",        parent=styles["Normal"],  fontSize=11, leading=16, spaceAfter=12)
    heading_style = ParagraphStyle("Heading",     parent=styles["Heading2"], spaceAfter=10)

    sentences = [
        f"This chapter presents the {chapter_title.lower()} for the project titled \"{project_title}\".",
        "The increasing reliance on digital systems within tertiary institutions has created a pressing "
        "need for tools that are both efficient and verifiable in their outcomes.",
        "Existing solutions in this domain are often fragmented, requiring users to reconcile data across "
        "multiple disconnected platforms before any meaningful analysis can take place.",
        "This study addresses that gap by proposing an integrated approach that consolidates the relevant "
        "processes into a single, coherent system.",
        "The remainder of this chapter is organised as follows: background context, problem framing, and "
        "the specific objectives this work sets out to achieve.",
        "Data for this study was gathered through a combination of structured interviews and analysis of "
        "existing institutional records over a six-month period.",
        "The proposed system was evaluated against three criteria: correctness, responsiveness under load, "
        "and ease of adoption by non-technical staff.",
        "Results indicate a measurable improvement over the baseline approach, with particularly strong "
        "gains observed in the areas of data consistency and turnaround time.",
        "These findings are consistent with prior work in the field, while also extending it by accounting "
        "for constraints specific to the Nigerian tertiary education context.",
        "Further validation across additional departments is recommended before any institution-wide rollout.",
    ]

    doc = SimpleDocTemplate(path, pagesize=letter, topMargin=0.9 * inch, bottomMargin=0.9 * inch)
    story = []

    story.append(Spacer(1, 1.6 * inch))
    story.append(Paragraph(project_title, title_style))
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(f"Chapter {chapter_number}: {chapter_title}", sub_style))
    story.append(Spacer(1, 0.6 * inch))
    story.append(Paragraph(f"By {student_name}", sub_style))
    story.append(Paragraph(department, sub_style))
    story.append(Paragraph(date.today().strftime("%B %Y"), sub_style))
    story.append(PageBreak())

    story.append(Paragraph(f"{chapter_number}.1 &nbsp; {chapter_title}", heading_style))
    for s in sentences[:5]:
        story.append(Paragraph(s, body_style))
    story.append(PageBreak())

    story.append(Paragraph(f"{chapter_number}.2 &nbsp; Discussion", heading_style))
    for s in sentences[5:]:
        story.append(Paragraph(s, body_style))

    doc.build(story)
    return sentences


def reset_database():
    # Delete in FK-safe order; meeting_students has ON DELETE CASCADE from meetings
    db.session.execute(meeting_students.delete())
    Meeting.query.delete()
    ChapterAnnotation.query.delete()
    ChapterSubmission.query.delete()
    Project.query.delete()
    SupervisorAssignment.query.delete()
    Notification.query.delete()
    Deadline.query.delete()
    AuditLog.query.delete()
    User.query.delete()
    db.session.commit()


def make_user(full_name, email, role, department, password="Password123!", is_super_admin=False):
    user = User(
        full_name=full_name,
        email=email,
        role=role,
        department=department,
        is_super_admin=is_super_admin,
        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
    )
    db.session.add(user)
    return user


def ensure_super_admin():
    """Create the super-admin from env vars if they don't already exist.

    Idempotent: a second call does nothing if the account is found.
    Never resets the password of an existing super admin.
    """
    email    = os.environ.get("SUPER_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("SUPER_ADMIN_PASSWORD", "").strip()

    if not email or not password:
        print("WARNING: SUPER_ADMIN_EMAIL or SUPER_ADMIN_PASSWORD not set — skipping super admin.")
        return None

    existing = User.query.filter_by(email=email).first()
    if existing:
        # Promote to super admin if flag somehow got cleared, but never reset password
        if not existing.is_super_admin:
            existing.is_super_admin = True
            existing.role = "admin"
            db.session.commit()
            print(f"Super admin flag restored for existing account: {email}")
        else:
            print(f"Super admin already exists ({email}) — skipping.")
        return existing

    super_admin = User(
        full_name="Super Administrator",
        email=email,
        role="admin",
        department="Computer Science",
        is_super_admin=True,
        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
    )
    db.session.add(super_admin)
    db.session.commit()
    print(f"Super admin created: {email}")
    return super_admin


def main():
    app = create_app("development")
    with app.app_context():
        global SEED_UPLOAD_DIR
        SEED_UPLOAD_DIR = os.path.join(app.config["UPLOAD_FOLDER"], "seed")
        if os.path.isdir(SEED_UPLOAD_DIR):
            shutil.rmtree(SEED_UPLOAD_DIR)
        os.makedirs(SEED_UPLOAD_DIR, exist_ok=True)

        print("Resetting database...")
        reset_database()

        print("Creating super admin from environment variables...")
        super_admin = ensure_super_admin()

        supervisors = [
            make_user("Dr. Adaeze Okafor",   "a.okafor@scholaris.edu",  "supervisor", "Computer Science"),
            make_user("Dr. Bankole Adeyemi", "b.adeyemi@scholaris.edu", "supervisor", "Information Technology"),
            make_user("Dr. Chiamaka Nwosu",  "c.nwosu@scholaris.edu",   "supervisor", "Software Engineering"),
        ]

        student_data = [
            ("Tobiloba Ogundimu", "t.ogundimu@scholaris.edu", "Computer Science",
             "Design and Implementation of an AI-Powered Academic Advising Chatbot"),
            ("Halima Suleiman", "h.suleiman@scholaris.edu", "Computer Science",
             "A Machine Learning Approach to Predicting Student Academic Performance"),
            ("Emeka Chukwu", "e.chukwu@scholaris.edu", "Computer Science",
             "Blockchain-Based Land Registry System for Nigerian States"),
            ("Fatima Bello", "f.bello@scholaris.edu", "Information Technology",
             "IoT-Based Smart Irrigation System for Smallholder Farmers"),
            ("David Okonkwo", "d.okonkwo@scholaris.edu", "Information Technology",
             "Web-Based Hospital Management Information System"),
            ("Ngozi Eze", "n.eze@scholaris.edu", "Information Technology",
             "A Comparative Study of Deep Learning Models for Fraud Detection in Mobile Banking"),
            ("Yusuf Ibrahim", "y.ibrahim@scholaris.edu", "Software Engineering",
             "Development of a Campus Navigation Mobile Application Using Augmented Reality"),
            ("Blessing Anyanwu", "b.anyanwu@scholaris.edu", "Software Engineering",
             "Cybersecurity Risk Assessment Framework for Small and Medium Enterprises"),
        ]
        students = [make_user(name, email, "student", dept) for name, email, dept, _ in student_data]
        db.session.flush()

        print("Assigning supervisors...")
        supervisor_for_student = [
            supervisors[0], supervisors[0], supervisors[0],
            supervisors[1], supervisors[1], supervisors[1],
            supervisors[2], supervisors[2],
        ]
        for student, supervisor in zip(students, supervisor_for_student):
            db.session.add(SupervisorAssignment(student_id=student.id, supervisor_id=supervisor.id))

        print("Creating projects...")
        projects = []
        for (student, (name, email, dept, title), supervisor) in zip(students, student_data, supervisor_for_student):
            project = Project(
                student_id=student.id,
                supervisor_id=supervisor.id,
                title=title,
                topic_status="approved",
                start_date=date.today() - timedelta(days=120),
                expected_submission_date=date.today() + timedelta(days=60),
                current_stage="Chapter 1",
            )
            db.session.add(project)
            projects.append(project)
        db.session.flush()

        progress_plan = [
            ([1, 2, 3], "pending"),
            ([1, 2],    "rejected"),
            ([1],       "pending"),
            ([1, 2, 3, 4], "pending"),
            ([],        "pending"),
            ([1, 2, 3, 4, 5], None),
            ([1, 2, 3], "rejected"),
            ([],        "rejected"),
        ]

        print("Generating chapter PDFs and submissions...")
        annotation_seeds = []

        for idx, (project, (name, email, dept, title)) in enumerate(zip(projects, student_data)):
            approved_chapters, last_status = progress_plan[idx]
            chapters_to_submit = list(approved_chapters)
            if last_status is not None:
                next_chapter = (max(approved_chapters) if approved_chapters else 0) + 1
                if next_chapter <= 5:
                    chapters_to_submit.append(next_chapter)

            for ch in chapters_to_submit:
                status = "approved" if ch in approved_chapters else last_status
                chapter_title = CHAPTER_TITLES[ch]
                filename = f"project{project.id}_ch{ch}.pdf"
                filepath = os.path.join(SEED_UPLOAD_DIR, filename)
                sentences = generate_chapter_pdf(filepath, title, ch, chapter_title, name, dept)

                submitted_days_ago = max(1, (5 - ch + 1) + (idx % 3))
                submission = ChapterSubmission(
                    project_id=project.id,
                    chapter_number=ch,
                    chapter_title=chapter_title,
                    file_path=f"uploads/seed/{filename}",
                    submitted_at=utcnow() - timedelta(days=submitted_days_ago),
                    status=status,
                )
                if status in ("approved", "rejected"):
                    submission.overall_comment = (
                        "Solid structure and clear methodology — approved as submitted."
                        if status == "approved" else
                        "Please revisit the literature review section: several claims need citations. Resubmit after revision."
                    )
                    submission.reviewed_at = submission.submitted_at + timedelta(days=1)
                    submission.reviewed_by = project.supervisor_id

                db.session.add(submission)
                db.session.flush()
                annotation_seeds.append((submission, sentences, project.supervisor_id))

            project.current_stage = f"Chapter {min(max(chapters_to_submit, default=1), 5)}"
            if approved_chapters == [1, 2, 3, 4, 5]:
                project.current_stage = "Completed"
                project.topic_status = "completed"

        print("Creating annotations...")
        viable          = [s for s in annotation_seeds if len(s[1]) >= 2]
        rejected_viable = [s for s in viable if s[0].status == "rejected"]
        other_viable    = [s for s in viable if s[0].status != "rejected"]
        chosen = (other_viable[:3] + rejected_viable[:1]) if rejected_viable else viable[:4]
        annotation_specs = [
            (chosen[0], 2, 220, 320, 1, False),
            (chosen[0], 2, 380, 480, 2, True),
            (chosen[1], 2, 220, 360, 0, False),
            (chosen[2], 3, 220, 300, 0, True),
            (chosen[3], 2, 220, 420, 1, False),
            (chosen[3], 2,  60, 200, 0, False),
        ] if len(chosen) >= 4 else [(c, 2, 220, 320, 0, False) for c in chosen]
        for (submission, sentences, supervisor_id), page, x, y, sent_idx, resolved in annotation_specs:
            safe_idx = min(sent_idx, len(sentences) - 1)
            db.session.add(ChapterAnnotation(
                submission_id=submission.id,
                supervisor_id=supervisor_id,
                page_number=page,
                x_position=float(x),
                y_position=float(y),
                width=420.0,
                height=18.0,
                selected_text=sentences[safe_idx],
                comment=(
                    "Good point — well supported." if resolved else
                    "Can you expand on this with a citation or supporting data?"
                ),
                is_resolved=resolved,
            ))

        db.session.flush()

        print("Creating notifications...")
        notif_messages = [
            ("submission", "Your Chapter {ch} submission was received and is pending review."),
            ("approval",   "Chapter {ch} was approved by your supervisor."),
            ("rejection",  "Chapter {ch} was rejected — please review supervisor feedback."),
            ("annotation", "Your supervisor left a new comment on Chapter {ch}."),
            ("deadline",   "Chapter {ch} deadline is approaching."),
        ]
        for i, student in enumerate(students):
            for j, (ntype, template) in enumerate(notif_messages[: (i % 4) + 2]):
                db.session.add(Notification(
                    user_id=student.id,
                    message=template.format(ch=(j % 5) + 1),
                    type=ntype,
                    created_at=utcnow() - timedelta(days=j, hours=i),
                    is_read=(j % 2 == 0),
                ))
        for supervisor in supervisors:
            db.session.add(Notification(
                user_id=supervisor.id,
                message="A student submitted a new chapter for review.",
                type="submission",
                created_at=utcnow() - timedelta(hours=4),
                is_read=False,
            ))
            db.session.add(Notification(
                user_id=supervisor.id,
                message="Reminder: 2 submissions are awaiting your review.",
                type="deadline",
                created_at=utcnow() - timedelta(days=1),
                is_read=True,
            ))
        if super_admin:
            db.session.add(Notification(
                user_id=super_admin.id, message="Weekly department progress report is ready.",
                type="broadcast", created_at=utcnow() - timedelta(hours=2), is_read=False,
            ))

        print("Creating deadlines...")
        db.session.add(Deadline(chapter_number=2, due_date=date.today() + timedelta(days=7),  set_by=super_admin.id))
        db.session.add(Deadline(chapter_number=3, due_date=date.today() + timedelta(days=14), set_by=super_admin.id))
        db.session.add(Deadline(chapter_number=4, due_date=date.today() + timedelta(days=21), set_by=super_admin.id))

        db.session.add(AuditLog(user_id=super_admin.id, action="seed_database", detail="Database seeded with demo data"))

        db.session.commit()
        print("Seed complete.")

        print("\n--- Row counts ---")
        print("users:", User.query.count())
        print("supervisor_assignments:", SupervisorAssignment.query.count())
        print("projects:", Project.query.count())
        print("chapter_submissions:", ChapterSubmission.query.count())
        print("chapter_annotations:", ChapterAnnotation.query.count())
        print("notifications:", Notification.query.count())
        print("deadlines:", Deadline.query.count())
        print("audit_logs:", AuditLog.query.count())

        print("\nLogin credentials:")
        if super_admin:
            print(f"  Super Admin: {super_admin.email}  (from SUPER_ADMIN_PASSWORD env var)")
        for s in supervisors:
            print(f"  Supervisor:  {s.email}  / Password123!")
        for s in students:
            print(f"  Student:     {s.email}  / Password123!")


if __name__ == "__main__":
    main()
