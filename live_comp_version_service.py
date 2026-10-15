"""File-backed releases. The live JSON is the single atomic publication point.

Inactive versions are snapshots; the live file is authoritative for the active
version. Always archive it before replacement, including its manual codes.
"""
import hashlib
import json
import os
import re
import shutil
import threading
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from flask import current_app

from audit import write_audit_best_effort
from db import now_text
from lineup_code import extract_lineup_code
from seasons import canonical_season_id

_thread_lock = threading.RLock()


class VersionError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _paths(season_id):
    from live_comps_helpers import season_data_path
    season_id = canonical_season_id(season_id)
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,39}', season_id or ''):
        raise VersionError('赛季 ID 无效')
    live = season_data_path(season_id)
    return live, live.parent / (live.stem + '.versions')


@contextmanager
def version_lock(season_id):
    """Serialize threads and OS processes; OS locks release on process exit."""
    _, root = _paths(season_id)
    root.mkdir(parents=True, exist_ok=True)
    with _thread_lock, (root / '.lock').open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if not handle.tell():
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _current(season_id):
    from live_comp_manual_codes import load_manual_code_overlay
    live, _ = _paths(season_id)
    if not live.exists():
        return None
    payload = _read(live)
    if '_release' not in payload:
        # Stable ID lets an existing deployment appear immediately in the UI.
        payload['_release'] = {
            'id': 'legacy', 'filename': '原线上版本.json',
            'created_at': datetime.fromtimestamp(live.stat().st_mtime).isoformat(timespec='seconds'), 'published_at': '原线上版本',
            'manual_codes': load_manual_code_overlay(
                current_app.config['LIVE_COMPS_MANUAL_CODE_DIR'], season_id),
        }
    return payload


def _snapshot_path(season_id, version_id):
    if not re.fullmatch(r'(?:[a-f0-9]{32}|legacy)', str(version_id)):
        raise VersionError('版本不存在', 404)
    return _paths(season_id)[1] / f'{version_id}.json'


def _get(season_id, version_id, current=None):
    current = current if current is not None else _current(season_id)
    if current and current['_release']['id'] == version_id:
        return current
    path = _snapshot_path(season_id, version_id)
    if not path.exists():
        raise VersionError('版本不存在或已删除', 404)
    return _read(path)


def _revision(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _summary(payload, active_id):
    from live_comp_manual_codes import merge_manual_codes_into_payload
    from live_comps_helpers import TIER_ORDER
    release = payload['_release']
    merged = merge_manual_codes_into_payload(payload, release.get('manual_codes'))
    items = [item for tier in TIER_ORDER for item in merged['tiers'].get(tier, [])]
    missing = sum(not item['hasCode'] for item in items)
    return {
        'id': release['id'], 'filename': release['filename'],
        'created_at': release['created_at'], 'published_at': release.get('published_at'),
        'status': 'active' if release['id'] == active_id else ('history' if release.get('published_at') else 'draft'),
        'total': len(items), 'missing': missing, 'ready': len(items) - missing,
        'revision': _revision(payload),
    }


def list_versions(season_id):
    with version_lock(season_id):
        current = _current(season_id)
        active_id = current['_release']['id'] if current else None
        entries = {p.stem: _read(p) for p in _paths(season_id)[1].glob('*.json')}
        if current:
            entries[active_id] = current
        items = [_summary(payload, active_id) for payload in entries.values()]
        items.sort(key=lambda item: (item['status'] == 'active', item['created_at'], item['id']), reverse=True)
        return {'items': items, 'active_id': active_id,
                'active_revision': _revision(current) if current else None}


def preview_version(season_id, version_id):
    from live_comp_manual_codes import merge_manual_codes_into_payload
    from live_comp_upload_service import build_upload_preview
    with version_lock(season_id):
        current = _current(season_id)
        payload = _get(season_id, version_id, current)
        merged = merge_manual_codes_into_payload(payload, payload['_release'].get('manual_codes'))
        result = _summary(payload, current['_release']['id'] if current else None)
        result.update(payload={'meta': merged.get('meta', {}), 'tiers': merged['tiers']},
                      diff=build_upload_preview(season_id, merged),
                      active_revision=_revision(current) if current else None)
        return result


def _publish(season_id, payload):
    current = _current(season_id)
    if current:
        _atomic_write(_snapshot_path(season_id, current['_release']['id']), current)
    payload = deepcopy(payload)
    payload['_release']['published_at'] = now_text()
    # No fallible file mutation after this publication point.
    _atomic_write(_paths(season_id)[0], payload)


def save_version(season_id, payload, filename, admin_id=None, publish=False, version_id=None,
                 expected_active_revision=None, check_active=False, manual_codes=None,
                 inherit_codes=False, backup_path=None):
    """Images must already be cached. A staged upload never touches live data."""
    from live_comps_helpers import normalize_live_comps_payload, validate_live_comps_payload
    validate_live_comps_payload(payload)
    payload = normalize_live_comps_payload(payload)
    payload['_release'] = {
        'id': version_id or uuid.uuid4().hex, 'filename': Path(filename).name[:180],
        'created_at': now_text(), 'created_by': admin_id,
        'manual_codes': manual_codes or {'items': {}},
    }
    with version_lock(season_id):
        path = _snapshot_path(season_id, payload['_release']['id'])
        if path.exists():
            raise VersionError('该上传已生成版本，请刷新版本库', 409)
        current = _current(season_id)
        if inherit_codes and current:
            payload['_release']['manual_codes'] = deepcopy(current['_release'].get('manual_codes', {'items': {}}))
        codes = payload['_release']['manual_codes']
        missing_ids = {str(item['id']) for rows in payload['tiers'].values() for item in rows if not item.get('jccCode')}
        codes['items'] = {key: value for key, value in codes.get('items', {}).items() if key in missing_ids}
        _atomic_write(path, payload)
        conflict = check_active and expected_active_revision != (_revision(current) if current else None)
        if publish and not conflict:
            if backup_path and _paths(season_id)[0].exists():
                Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(_paths(season_id)[0], backup_path)
            _publish(season_id, payload)
    return {'version_id': payload['_release']['id'], 'published': publish and not conflict,
            'publication_conflict': bool(publish and conflict)}


def mutate_version(admin_id, season_id, version_id, action, data):
    from live_comps_helpers import TIER_ORDER
    code_item = None
    with version_lock(season_id):
        current = _current(season_id)
        payload = _get(season_id, version_id, current)
        active_id = current['_release']['id'] if current else None
        if data.get('revision') != _revision(payload):
            raise VersionError('版本已更新，请刷新预览后重试', 409)
        if action == 'publish':
            if data.get('active_revision') != (_revision(current) if current else None):
                raise VersionError('线上版本已变化，请刷新预览后再上线', 409)
            if active_id == version_id:
                raise VersionError('该版本已经在线上', 409)
            if _summary(payload, active_id)['missing'] and data.get('allow_missing') is not True:
                raise VersionError('此版本仍有缺码阵容，请确认后上线', 409)
            _publish(season_id, payload)
        elif action == 'delete':
            if active_id == version_id:
                raise VersionError('不能删除当前线上版本，请先切换到其他版本', 409)
            _snapshot_path(season_id, version_id).unlink()
        elif action == 'code':
            if data.get('require_active') and active_id != version_id:
                raise VersionError('线上版本已变化，请刷新后重试', 409)
            item = next((item for tier in TIER_ORDER for item in payload['tiers'].get(tier, [])
                         if str(item['id']) == str(data.get('item_id'))), None)
            if item is None:
                raise VersionError('阵容不存在', 404)
            if item.get('jccCode'):
                raise VersionError('当前条目已有原始阵容码，无需补码')
            code = extract_lineup_code(data.get('code'))
            if not code:
                raise VersionError('阵容码格式无法识别')
            payload['_release'].setdefault('manual_codes', {'items': {}})['items'][str(item['id'])] = {
                'jccCode': code, 'updated_at': now_text(), 'updated_by': admin_id,
            }
            path = _paths(season_id)[0] if active_id == version_id else _snapshot_path(season_id, version_id)
            _atomic_write(path, payload)
            code_item = {**item, 'originalJccCode': '', 'resolvedJccCode': code,
                         'jccCode': code, 'codeSource': 'manual', 'hasCode': True}
        else:
            raise VersionError('操作无效')
    write_audit_best_effort(admin_id, f'{action}_live_comp_version', 'live_comp_version',
                            target_key=f'{season_id}:{version_id}',
                            after={'filename': payload['_release']['filename'], 'item_id': data.get('item_id')})
    return {'ok': True, 'version_id': version_id, 'item': code_item}
