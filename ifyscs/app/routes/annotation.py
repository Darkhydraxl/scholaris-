from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import ChapterAnnotation, ChapterSubmission
from app.services.notification_service import notify_annotation_added
from app.services.audit_service import log_action

annotation_bp = Blueprint("annotation", __name__)


def _require_supervisor_owns_submission(submission):
    if current_user.role != "supervisor" or submission.project.supervisor_id != current_user.id:
        abort(403)


@annotation_bp.route("/save", methods=["POST"])
@login_required
def save_annotation():
    data = request.get_json(silent=True) or {}
    required = ("submission_id", "page_number", "x", "y", "width", "height", "selected_text", "comment")
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields."}), 400

    submission = ChapterSubmission.query.get_or_404(int(data["submission_id"]))
    _require_supervisor_owns_submission(submission)

    annotation = ChapterAnnotation(
        submission_id=submission.id,
        supervisor_id=current_user.id,
        page_number=int(data["page_number"]),
        x_position=float(data["x"]),
        y_position=float(data["y"]),
        width=float(data["width"]),
        height=float(data["height"]),
        selected_text=str(data["selected_text"])[:2000],
        comment=str(data["comment"])[:2000],
    )
    db.session.add(annotation)
    db.session.commit()

    notify_annotation_added(annotation)
    log_action(current_user.id, "add_annotation", f"Commented on Chapter {submission.chapter_number} (submission {submission.id})")

    return jsonify(annotation.to_dict()), 201


@annotation_bp.route("/<int:submission_id>", methods=["GET"])
@login_required
def list_annotations(submission_id):
    submission = ChapterSubmission.query.get_or_404(submission_id)
    is_owner_student = current_user.role == "student" and submission.project.student_id == current_user.id
    is_owner_supervisor = current_user.role == "supervisor" and submission.project.supervisor_id == current_user.id
    if not (is_owner_student or is_owner_supervisor or current_user.role == "admin"):
        abort(403)

    annotations = ChapterAnnotation.query.filter_by(submission_id=submission_id).order_by(
        ChapterAnnotation.created_at.asc()
    ).all()
    return jsonify([a.to_dict() for a in annotations])


@annotation_bp.route("/<int:annotation_id>/resolve", methods=["PATCH"])
@login_required
def resolve_annotation(annotation_id):
    annotation = ChapterAnnotation.query.get_or_404(annotation_id)
    submission = annotation.submission
    is_owner_student = current_user.role == "student" and submission.project.student_id == current_user.id
    is_owner_supervisor = current_user.role == "supervisor" and submission.project.supervisor_id == current_user.id
    if not (is_owner_student or is_owner_supervisor):
        abort(403)

    data = request.get_json(silent=True) or {}
    annotation.is_resolved = bool(data.get("is_resolved", True))
    db.session.commit()
    log_action(current_user.id, "resolve_annotation", f"Annotation {annotation.id} resolved={annotation.is_resolved}")
    return jsonify(annotation.to_dict())


@annotation_bp.route("/<int:annotation_id>", methods=["DELETE"])
@login_required
def delete_annotation(annotation_id):
    annotation = ChapterAnnotation.query.get_or_404(annotation_id)
    _require_supervisor_owns_submission(annotation.submission)
    db.session.delete(annotation)
    db.session.commit()
    log_action(current_user.id, "delete_annotation", f"Deleted annotation {annotation_id}")
    return jsonify({"success": True})
