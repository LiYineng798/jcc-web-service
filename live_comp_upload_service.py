"""Admin live-comps upload previews, jobs, progress, and background processing."""

from __future__ import annotations

import json
import shutil
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from flask import current_app

from audit import write_audit
from db import get_db, now_text
from live_comps_helpers import (
    TIER_ORDER,
    read_raw_live_comps_payload_for_season,
    season_data_path,
    validate_live_comps_payload,
    write_live_comps_payload_for_season,
)
from seasons import canonical_season_id

PREVIEW_STATUS = 'preview'
QUEUED_STATUS = 'queued'
RUNNING_STATUS = 'running'
COMPLETED_STATUS = 'completed'
FAILED_STATUS = 'failed'


def _job_root():
    root = Path(current_app.config['LIVE_COMPS_UPLOAD_JOB_DIR'])
    root.mkdir(parents=True, exist_ok=True)
    return root


def _job_input_path(job_id):
    path = _job_root() / str(job_id)
    path.mkdir(parents=True, exist_ok=True)
    return path / 'input.json'


def _safe_filename(filename):
    value = Path(str(filename or 'live-comps.json')).name.strip()
    return value[:180] or 'live-comps.json'


def _items_by_id(payload):
    return {
        str(item.get('id')): item
        for tier in TIER_ORDER
        for item in payload.get('tiers', {}).get(tier, [])
        if item.get('id') is not None
    }


def _item_fingerprint(item):
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _image_total(payload):
    return sum(
        1 + len(item.get('heroImages', []))
        for tier in TIER_ORDER
        for item in payload.get('tiers', {}).get(tier, [])
    )


def _copy_counts(season_id, ids):
    if not ids:
        return {}
    placeholders = ', '.join('?' for _ in ids)
    rows = get_db().execute(
        f'''
        SELECT target_id, COUNT(*) AS copies
        FROM copy_action_events
        WHERE target_type = 'live_comp'
          AND season_id = ?
          AND target_id IN ({placeholders})
          AND success = 1
        GROUP BY target_id
        ''',
        [season_id, *ids],
    ).fetchall()
    return {str(row['target_id']): int(row['copies'] or 0) for row in rows}


def build_upload_preview(season_id, payload):
    """Return a safe diff and copy-impact warning before a file is committed."""
    normalized = _normalize_for_preview(payload)
    old_payload, old_updated_at, old_valid, _, _ = read_raw_live_comps_payload_for_season(season_id)
    old_items = _items_by_id(old_payload)
    new_items = _items_by_id(normalized)
    old_ids = set(old_items)
    new_ids = set(new_items)
    added_ids = sorted(new_ids - old_ids)
    removed_ids = sorted(old_ids - new_ids)
    changed_ids = sorted(
        item_id
        for item_id in old_ids & new_ids
        if _item_fingerprint(old_items[item_id]) != _item_fingerprint(new_items[item_id])
    )
    code_changed_ids = sorted(
        item_id
        for item_id in old_ids & new_ids
        if str(old_items[item_id].get('jccCode') or '') != str(new_items[item_id].get('jccCode') or '')
    )
    missing_code_ids = sorted(
        item_id for item_id, item in new_items.items() if not str(item.get('jccCode') or '').strip()
    )
    impacted_ids = sorted(set(removed_ids) | set(code_changed_ids))
    copy_counts = _copy_counts(season_id, impacted_ids)
    warnings = []
    if missing_code_ids:
        warnings.append(f'{len(missing_code_ids)} 套阵容没有可复制的金铲铲阵容码')
    if code_changed_ids:
        warnings.append('已有复制记录的阵容码发生变化；历史复制事件按阵容 ID 保留')
    if removed_ids:
        warnings.append('被移除的阵容仍可能出现在历史复制排行中，但不再出现在当前列表')
    if any(copy_counts.values()):
        warnings.append('本次变更涉及已有复制记录，请确认 ID 复用是否符合预期')
    return {
        'season_id': season_id,
        'old_updated_at': old_updated_at,
        'old_is_valid': bool(old_valid),
        'new_counts': {tier: len(normalized['tiers'].get(tier, [])) for tier in TIER_ORDER},
        'total': sum(len(normalized['tiers'].get(tier, [])) for tier in TIER_ORDER),
        'image_total': _image_total(normalized),
        'added_ids': added_ids,
        'removed_ids': removed_ids,
        'changed_ids': changed_ids,
        'code_changed_ids': code_changed_ids,
        'missing_code_ids': missing_code_ids,
        'copy_counts': copy_counts,
        'warnings': warnings,
    }


def _normalize_for_preview(payload):
    from live_comps_helpers import normalize_live_comps_payload

    validate_live_comps_payload(payload)
    return normalize_live_comps_payload(payload)


def create_preview_job(admin_id, season_id, filename, raw_bytes, payload):
    season_id = canonical_season_id(season_id)
    if not season_id:
        raise ValueError('必须选择实时阵容赛季')
    normalized = _normalize_for_preview(payload)
    preview = build_upload_preview(season_id, normalized)
    job_id = uuid.uuid4().hex
    input_path = _job_input_path(job_id)
    input_path.write_bytes(raw_bytes)
    now = now_text()
    db = get_db()
    db.execute(
        '''
        INSERT INTO live_comp_upload_jobs (
            id, season_id, status, stage, filename, input_path,
            total_bytes, uploaded_bytes, item_total, image_total,
            result_json, created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            job_id,
            season_id,
            PREVIEW_STATUS,
            'validated',
            _safe_filename(filename),
            str(input_path),
            len(raw_bytes),
            len(raw_bytes),
            preview['total'],
            preview['image_total'],
            json.dumps({'preview': preview}, ensure_ascii=False),
            admin_id,
            now,
            now,
        ),
    )
    db.commit()
    return get_upload_job(job_id)


def start_upload_job(admin_id, job_id):
    db = get_db()
    row = db.execute('SELECT * FROM live_comp_upload_jobs WHERE id = ?', (str(job_id),)).fetchone()
    if not row:
        return None, '上传任务不存在'
    if row['status'] != PREVIEW_STATUS:
        return None, '该上传任务已经开始或已结束'
    now = now_text()
    cursor = db.execute(
        '''
        UPDATE live_comp_upload_jobs
        SET status = ?, stage = ?, message = ?, updated_at = ?
        WHERE id = ? AND status = ?
        ''',
        (QUEUED_STATUS, 'queued', '等待后台处理', now, str(job_id), PREVIEW_STATUS),
    )
    db.commit()
    if not cursor.rowcount:
        return None, '该上传任务已经开始或已结束'
    write_audit(
        admin_id,
        'queue_live_comp_upload',
        'live_comp_upload_job',
        str(job_id),
        after={'season_id': row['season_id'], 'filename': row['filename']},
    )
    db.commit()
    return get_upload_job(job_id), None


def _progress_percent(row):
    status = row['status']
    if status == COMPLETED_STATUS:
        return 100
    if status == FAILED_STATUS:
        if row['image_total']:
            return min(95, 10 + int(row['image_done'] * 80 / row['image_total']))
        return 0
    if status == PREVIEW_STATUS:
        return 0
    if row['stage'] == 'committing':
        return 95
    if row['image_total']:
        return min(90, 10 + int(row['image_done'] * 80 / row['image_total']))
    return 5 if status in {QUEUED_STATUS, RUNNING_STATUS} else 0


def get_upload_job(job_id):
    row = get_db().execute('SELECT * FROM live_comp_upload_jobs WHERE id = ?', (str(job_id),)).fetchone()
    if not row:
        return None
    result = {}
    try:
        result = json.loads(row['result_json'] or '{}')
    except (TypeError, json.JSONDecodeError):
        result = {}
    payload = {
        'job_id': row['id'],
        'season_id': row['season_id'],
        'filename': row['filename'],
        'status': row['status'],
        'stage': row['stage'],
        'percent': _progress_percent(row),
        'total_bytes': int(row['total_bytes'] or 0),
        'uploaded_bytes': int(row['uploaded_bytes'] or 0),
        'item_total': int(row['item_total'] or 0),
        'item_done': int(row['item_done'] or 0),
        'image_total': int(row['image_total'] or 0),
        'image_done': int(row['image_done'] or 0),
        'current_item': row['current_item'] or '',
        'message': row['message'] or '',
        'error': row['error_message'] or '',
        'created_at': row['created_at'],
        'started_at': row['started_at'],
        'finished_at': row['finished_at'],
        'updated_at': row['updated_at'],
        **result,
    }
    return payload


def _update_job(job_id, **fields):
    allowed = {
        'status', 'stage', 'uploaded_bytes', 'item_total', 'item_done',
        'image_total', 'image_done', 'current_item', 'message',
        'result_json', 'error_message', 'started_at', 'finished_at', 'updated_at',
    }
    fields = {key: value for key, value in fields.items() if key in allowed}
    if not fields:
        return
    fields['updated_at'] = fields.get('updated_at') or now_text()
    assignments = ', '.join(f'{key} = ?' for key in fields)
    values = [fields[key] for key in fields]
    values.append(str(job_id))
    db = get_db()
    db.execute(f'UPDATE live_comp_upload_jobs SET {assignments} WHERE id = ?', values)
    db.commit()


def _claim_next_job():
    db = get_db()
    row = db.execute(
        '''
        SELECT * FROM live_comp_upload_jobs
        WHERE status = ?
        ORDER BY created_at ASC, id ASC
        LIMIT 1
        ''',
        (QUEUED_STATUS,),
    ).fetchone()
    if not row:
        return None
    now = now_text()
    cursor = db.execute(
        '''
        UPDATE live_comp_upload_jobs
        SET status = ?, stage = ?, started_at = ?, message = ?, updated_at = ?
        WHERE id = ? AND status = ?
        ''',
        (RUNNING_STATUS, 'validating', now, '正在校验上传文件', now, row['id'], QUEUED_STATUS),
    )
    db.commit()
    return dict(row) if cursor.rowcount else None


def _versioned_backup_path(season_id):
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    path = Path(current_app.config['LIVE_COMPS_BACKUP_DIR']) / str(season_id) / f'{stamp}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _process_job(app, job):
    job_id = job['id']
    try:
        input_path = Path(job['input_path'])
        payload = json.loads(input_path.read_text(encoding='utf-8'))
        normalized = _normalize_for_preview(payload)
        item_total = sum(len(normalized['tiers'].get(tier, [])) for tier in TIER_ORDER)
        image_total = _image_total(normalized)
        _update_job(
            job_id,
            stage='downloading_images',
            item_total=item_total,
            item_done=0,
            image_total=image_total,
            image_done=0,
            current_item='',
            message='准备缓存远程图片',
        )

        def progress(update):
            _update_job(
                job_id,
                stage=update.get('stage', 'downloading_images'),
                image_done=int(update.get('image_done') or 0),
                image_total=int(update.get('image_total') or image_total),
                item_done=int(update.get('item_done') or 0),
                item_total=int(update.get('item_total') or item_total),
                current_item=str(update.get('current_item') or ''),
                message=f"正在缓存：{update.get('current_item') or '实时阵容'}",
            )

        backup_path = _versioned_backup_path(job['season_id'])
        data_path = season_data_path(job['season_id'])
        write_live_comps_payload_for_season(
            job['season_id'],
            normalized,
            progress_callback=progress,
            backup_path=backup_path,
        )
        _update_job(
            job_id,
            status=COMPLETED_STATUS,
            stage='completed',
            item_done=item_total,
            item_total=item_total,
            image_done=image_total,
            image_total=image_total,
            current_item='',
            message='实时阵容数据已发布',
            result_json=json.dumps({
                'result': {
                    'season_id': job['season_id'],
                    'total': item_total,
                    'backup_file': str(backup_path) if data_path.exists() and backup_path.exists() else None,
                },
            }, ensure_ascii=False),
            finished_at=now_text(),
        )
        write_audit(
            job.get('created_by'),
            'complete_live_comp_upload',
            'live_comp_upload_job',
            job_id,
            after={'season_id': job['season_id'], 'item_total': item_total},
        )
        get_db().commit()
    except Exception as exc:
        app.logger.exception('live comp upload job failed: %s', job_id)
        _update_job(
            job_id,
            status=FAILED_STATUS,
            stage='failed',
            message='上传失败，当前线上数据未主动替换',
            error_message=str(exc)[:1000],
            finished_at=now_text(),
        )
        write_audit(
            job.get('created_by'),
            'fail_live_comp_upload',
            'live_comp_upload_job',
            job_id,
            after={'season_id': job.get('season_id'), 'error': str(exc)[:500]},
        )
        get_db().commit()


def start_live_comp_upload_worker(app):
    """Start one DB-claiming daemon per Flask process; tests opt out."""
    if app.config.get('TESTING') or not app.config.get('LIVE_COMPS_UPLOAD_WORKER_ENABLED', True):
        return None
    if getattr(app, '_live_comp_upload_worker_started', False):
        return None
    stop_event = threading.Event()
    app._live_comp_upload_worker_stop = stop_event

    def loop():
        while not stop_event.is_set():
            job = None
            try:
                with app.app_context():
                    job = _claim_next_job()
                    if job:
                        _process_job(app, job)
            except Exception:
                app.logger.exception('live comp upload worker iteration failed')
            stop_event.wait(1 if job else 2)

    thread = threading.Thread(target=loop, name='live-comp-upload-worker', daemon=True)
    thread.start()
    app._live_comp_upload_worker_started = True
    return thread


def stop_live_comp_upload_worker(app):
    event = getattr(app, '_live_comp_upload_worker_stop', None)
    if event:
        event.set()
