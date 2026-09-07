from flask import request

from app.extensions import db
from app.models import AuditLog


def log_action(user_id, action, detail=None):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        detail=detail,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(entry)
    db.session.commit()
    return entry
