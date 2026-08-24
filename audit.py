import json

from flask import current_app

from db import get_db, now_text


def write_audit(actor_user_id, action, target_type, target_id=None, before=None, after=None, target_key=None):
    get_db().execute(
        '''INSERT INTO audit_logs (actor_user_id, action, target_type, target_id, target_key, before_json, after_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            actor_user_id,
            action,
            target_type,
            target_id,
            target_key,
            json.dumps(before, ensure_ascii=False) if before is not None else None,
            json.dumps(after, ensure_ascii=False) if after is not None else None,
            now_text(),
        ),
    )


def write_audit_best_effort(actor_user_id, action, target_type, target_id=None, before=None, after=None, target_key=None):
    """Record audit data without turning a completed side effect into a false failure."""
    try:
        write_audit(
            actor_user_id,
            action,
            target_type,
            target_id=target_id,
            before=before,
            after=after,
            target_key=target_key,
        )
        get_db().commit()
    except Exception:
        get_db().rollback()
        current_app.logger.exception('audit log write failed after side effect: %s', action)
