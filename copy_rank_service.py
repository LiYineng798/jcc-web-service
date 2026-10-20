"""Uploader attribution shared by current rankings and report snapshots."""
from flask import current_app


def user_label(row):
    if not row or not row['username']:
        return '原上传账号不可用'
    nickname = row['nickname'] or row['username']
    return f"{nickname} (@{row['username']})"


def live_uploader(db, payload, season_id, target_id):
    from live_comp_manual_codes import load_manual_code_overlay
    release = (payload or {}).get('_release') or {}
    overlay = release.get('manual_codes')
    if overlay is None:
        overlay = load_manual_code_overlay(current_app.config['LIVE_COMPS_MANUAL_CODE_DIR'], season_id)
    manual = (overlay.get('items') or {}).get(str(target_id)) or {}
    item = next((item for tier in (payload or {}).get('tiers', {}).values()
                 for item in tier if str(item.get('id')) == str(target_id)), None)
    # Original codes win over any stale manual overlay when the payload is merged.
    manual_actor = manual.get('updated_by') if not item or item.get('codeSource') != 'original' else None
    user_id = manual_actor or release.get('created_by')
    if not user_id:
        return '数据导入（未记录上传账号）'
    row = db.execute('SELECT username, nickname FROM users WHERE id = ?', (user_id,)).fetchone()
    return user_label(row)


def enrich_legacy_uploaders(db, items):
    """Old snapshots retain their counts; attribution is explicitly current."""
    missing = [item for item in items if 'uploader' not in item]
    ids = [item['lineup_id'] for item in missing if item.get('lineup_id')]
    owners = {}
    if ids:
        marks = ','.join('?' for _ in ids)
        owners = {row['id']: row for row in db.execute(
            f'SELECT l.id, u.username, u.nickname FROM lineups l LEFT JOIN users u ON u.id=l.user_id WHERE l.id IN ({marks})', ids
        ).fetchall()}
    for item in missing:
        item['uploader'] = user_label(owners.get(item.get('lineup_id'))) if item['target_type'] == 'lineup' else '历史快照未记录'
        item['uploader_attribution'] = 'current' if item['target_type'] == 'lineup' else 'unknown'
