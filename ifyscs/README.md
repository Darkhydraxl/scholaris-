# Scholaris — Final Year Project Supervision & Collaboration System

A Flask-based academic project management platform for tertiary institutions, with three roles: **Student**, **Supervisor**, and **Administrator**.

## Tech stack

- Python 3.10+ (built and tested on 3.14.6) / Flask 3.1
- Flask-SQLAlchemy (ORM), Flask-Migrate (Alembic migrations)
- Flask-Login (auth), Flask-Bcrypt (password hashing), Flask-WTF (forms + CSRF)
- Flask-Mail (email, suppressed by default for local dev)
- APScheduler (daily deadline reminder job)
- SQLite for local dev (MySQL-ready via `DATABASE_URL`)
- Bootstrap-free custom CSS design system, Jinja2, PDF.js, Chart.js, vanilla JS animations

> Note: the original spec referenced Flask 2.3; this project was built against the current Flask 3.1.x line (same APIs used here), since 2.3 is no longer the maintained release.

## Setup

```bash
cd scholaris
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### Environment variables

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

By default `DATABASE_URL` is empty, which makes the app fall back to a local SQLite database at `instance/scholaris.db`. To use MySQL instead, set:

```
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/scholaris
```

(install a MySQL server separately; no code changes are needed — models are written to be portable between SQLite and MySQL).

`MAIL_SUPPRESS_SEND=True` is on by default so the app runs without real SMTP credentials. Suppressed emails are still rendered and logged to the console so you can see what would have been sent.

### Database

```bash
flask db upgrade   # applies the migration in migrations/versions/
python seed.py      # populates demo data (idempotent — safe to re-run)
```

`seed.py` creates 1 admin, 3 supervisors, 8 students (assigned to supervisors), one project per student, generated chapter PDFs, submissions across pending/approved/rejected, a handful of pre-existing annotations, mixed read/unread notifications, and 3 upcoming deadlines.

**Demo login (password for all: `Password123!`):**

| Role | Email |
|---|---|
| Admin | admin@scholaris.edu |
| Supervisor | a.okafor@scholaris.edu, b.adeyemi@scholaris.edu, c.nwosu@scholaris.edu |
| Student | t.ogundimu@scholaris.edu, h.suleiman@scholaris.edu, e.chukwu@scholaris.edu, f.bello@scholaris.edu, d.okonkwo@scholaris.edu, n.eze@scholaris.edu, y.ibrahim@scholaris.edu, b.anyanwu@scholaris.edu |

### Run

```bash
python run.py
```

Visit http://127.0.0.1:5000 — you'll be redirected to `/login`.

## Project structure

```
scholaris/
├── app/
│   ├── __init__.py        # app factory, extension init, scheduler
│   ├── models.py          # 8 SQLAlchemy models
│   ├── forms.py           # WTForms
│   ├── extensions.py
│   ├── decorators.py      # role_required
│   ├── routes/             # auth, student, supervisor, admin, annotation, notification
│   ├── services/           # notification, progress, scheduler, audit, report (PDF) services
│   ├── templates/
│   └── static/{css,js,uploads}/
├── config.py
├── seed.py
├── requirements.txt
├── .env.example
├── run.py
└── migrations/             # Flask-Migrate / Alembic
```

## Key features

- **Annotation system**: supervisors highlight text in the in-browser PDF.js viewer and leave comments, which are stored as page-relative coordinates (`/annotation/save`, `GET /annotation/<submission_id>`, `PATCH /annotation/<id>/resolve`) and rendered back as colored overlays (yellow = open, green = resolved) for the student.
- **Dark mode**: toggled via the moon/sun icon, stored server-side in the session, applied as `data-theme` on `<html>`. Every color token (including the glass blur surfaces and the active sidebar pill) inverts.
- **Deadline reminders**: a daily APScheduler job (default 08:00) checks for chapters due in 7 days or 24 hours with no submission yet, and sends both an in-app notification and a (suppressed-by-default) email.
- **Admin progress report PDF export**: generated server-side with `reportlab` (not WeasyPrint, which needs a native GTK runtime that's unreliable to install on Windows).

## Known issues / possible follow-ups

- Multi-line text selections in the annotation tool are stored as a single bounding box (the union of all selection rects) rather than one highlight per line — adequate for the comment-anchoring use case here, but a future iteration could render one highlight `<div>` per line.
- `MAIL_SUPPRESS_SEND=True` by default means no real emails are sent locally; set real SMTP credentials and flip it to `False` to test actual delivery.
- The reportlab-based progress report PDF re-implements simple bar charts with `reportlab.graphics.charts` rather than mirroring the on-screen Chart.js styling exactly.
