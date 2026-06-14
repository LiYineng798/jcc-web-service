import json

from db import get_db, now_text


def write_audit(actor_user_id, action, target_type, target_id=None, before=None, after=None):
    get_db().execute(
        '''INSERT INTO audit_logs (actor_user_id, action, target_type, target_id, before_json, after_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (
            actor_user_id,
            action,
            target_type,
            target_id,
            json.dumps(before, ensure_ascii=False) if before is not None else None,
            json.dumps(after, ensure_ascii=False) if after is not None else None,
            now_text(),
        ),
    )
