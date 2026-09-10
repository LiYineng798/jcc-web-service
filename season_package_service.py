"""Persisted offline package jobs and compare-and-swap season publishing."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import uuid
from datetime import datetime, timedelta

from flask import current_app
from psycopg import IntegrityError as PostgresIntegrityError

from db import get_db, now_text
from season_data_repository import (
    baseline_catalog,
    clear_request_selection,
    data_directory,
    package_root,
    release_root,
)
from season_package_format import (
    PackageError,
    inspect_zip,
    validate_data,
    extract_package,
    read_json,
    structural_diff,
    sha256,
    require,
)


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def limits():
    c = current_app.config
    return {
        'bytes': c['SEASON_PACKAGE_MAX_BYTES'],
        'expanded': c['SEASON_PACKAGE_MAX_EXPANDED_BYTES'],
        'files': c['SEASON_PACKAGE_MAX_FILES'],
        'json': c['SEASON_PACKAGE_MAX_JSON_BYTES'],
    }


def _event(season_id, release_id, action, actor, detail=None, previous=None, status='completed'):
    event_id = uuid.uuid4().hex
    get_db().execute(
        '''INSERT INTO season_release_events
        (id,season_id,release_id,previous_release_id,action,status,actor_id,detail_json,created_at)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (
            event_id,
            season_id,
            release_id,
            previous,
            action,
            status,
            actor,
            encode(detail or {}),
            now_text(),
        ),
    )
    return event_id


def active_state(season_id):
    row = (
        get_db()
        .execute(
            '''SELECT a.*,p.package_id,p.game_version,p.data_revision FROM season_active_releases a
        LEFT JOIN season_release_packages p ON p.id=a.release_id WHERE a.season_id=?''',
            (season_id,),
        )
        .fetchone()
    )
    return (
        dict(row)
        if row
        else {
            'season_id': season_id,
            'release_id': None,
            'previous_release_id': None,
            'revision': 0,
        }
    )


def release_payload(release_id):
    row = (
        get_db()
        .execute('SELECT * FROM season_release_packages WHERE id=?', (release_id,))
        .fetchone()
    )
    if row is None:
        return None
    result = dict(row)
    result['manifest'] = json.loads(result.pop('manifest_json'))
    result['report'] = json.loads(result.pop('report_json'))
    job = (
        get_db()
        .execute('SELECT * FROM season_import_jobs WHERE release_id=?', (release_id,))
        .fetchone()
    )
    result['job'] = {k: v for k, v in dict(job).items() if k != 'lease_token'} if job else None
    result['active'] = active_state(row['season_id'])
    result['preview_url'] = f'/tools/seasons/{row["season_id"]}?preview_release={release_id}'
    result['simulator_url'] = (
        f'/tools/lineup-simulator?preview_release={release_id}&season_id={row["season_id"]}'
    )
    return result


def receive_package(stream, filename, actor):
    root = package_root() / 'uploads'
    root.mkdir(parents=True, exist_ok=True)
    require(
        shutil.disk_usage(root).free >= limits()['bytes'] + 256 * 1024**2,
        '资料磁盘空间不足，请先扩容或归档旧资料',
    )
    release_id = uuid.uuid4().hex
    path = root / f'{release_id}.zip'
    try:
        size = 0
        with path.open('xb') as output:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                size += len(chunk)
                require(size <= limits()['bytes'], '更新包超过上传限制')
                output.write(chunk)
        manifest = inspect_zip(path, limits())
        known = {s['season_id'] for s in baseline_catalog()}
        require(manifest['season_id'] in known, '请先通过代码登记此赛季及官方映射')
        digest = sha256(path)
        db = get_db()
        old = db.execute(
            'SELECT id,zip_sha256 FROM season_release_packages WHERE package_id=? OR zip_sha256=?',
            (manifest['package_id'], digest),
        ).fetchone()
        if old:
            require(old['zip_sha256'] == digest, '相同包 ID 的内容不同，请提高资料修订号')
            path.unlink()
            return release_payload(old['id']), False
        collision = db.execute(
            'SELECT id FROM season_release_packages WHERE season_id=? AND game_version=? AND data_revision=?',
            (manifest['season_id'], manifest['game_version'], manifest['data_revision']),
        ).fetchone()
        require(not collision, '此赛季的补丁与资料修订号已存在，请提高资料修订号')
        stamp = now_text()
        db.execute(
            '''INSERT INTO season_release_packages
            (id,package_id,season_id,game_version,data_revision,zip_sha256,filename,total_bytes,state,manifest_json,created_by,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (
                release_id,
                manifest['package_id'],
                manifest['season_id'],
                manifest['game_version'],
                manifest['data_revision'],
                digest,
                os.path.basename(filename.replace('\\', '/'))[:180],
                size,
                'queued',
                encode(manifest),
                actor,
                stamp,
            ),
        )
        db.execute(
            '''INSERT INTO season_import_jobs (id,release_id,status,created_at,updated_at)
                      VALUES (?,?,?,?,?)''',
            (release_id, release_id, 'queued', stamp, stamp),
        )
        _event(manifest['season_id'], release_id, 'upload', actor, {'sha256': digest})
        db.commit()
        return release_payload(release_id), True
    except (sqlite3.IntegrityError, PostgresIntegrityError):
        get_db().rollback()
        path.unlink(missing_ok=True)
        # A concurrent retry may have committed the identical ZIP after our first lookup.
        old = (
            get_db()
            .execute('SELECT id FROM season_release_packages WHERE zip_sha256=?', (digest,))
            .fetchone()
        )
        if old:
            return release_payload(old['id']), False
        raise PackageError('包 ID 或赛季资料修订号已被使用，请提高资料修订号')
    except Exception:
        get_db().rollback()
        path.unlink(missing_ok=True)
        raise


def change_job(release_id, action, actor):
    db = get_db()
    row = db.execute(
        'SELECT * FROM season_import_jobs WHERE release_id=?', (release_id,)
    ).fetchone()
    require(row is not None, '任务不存在')
    if action == 'cancel':
        changed = db.execute(
            "UPDATE season_import_jobs SET cancel_requested=1,updated_at=? WHERE release_id=? AND status IN ('queued','running')",
            (now_text(), release_id),
        ).rowcount
        require(changed == 1, '任务已结束，不能取消')
    else:
        changed = db.execute(
            """UPDATE season_import_jobs SET status='queued',stage='queued',progress=0,
             cancel_requested=0,lease_token=NULL,message='',updated_at=? WHERE release_id=? AND status IN ('failed','cancelled')""",
            (now_text(), release_id),
        ).rowcount
        require(changed == 1, '仅失败或已取消的任务可以重试')
        db.execute("UPDATE season_release_packages SET state='queued' WHERE id=?", (release_id,))
    sid = db.execute(
        'SELECT season_id FROM season_release_packages WHERE id=?', (release_id,)
    ).fetchone()['season_id']
    _event(sid, release_id, action, actor)
    db.commit()
    return release_payload(release_id)


def _comparison_warnings(report):
    report['warnings'] = [w for w in report['warnings'] if not w.startswith('比较：')]
    if report['diff']['mechanics']['removed']:
        report['warnings'].append(
            '比较：将移除玩法：' + '、'.join(report['diff']['mechanics']['removed'])
        )
    for name, label in [
        ('champions', '弈子'),
        ('traits', '羁绊'),
        ('items', '装备'),
        ('augments', '强化符文'),
        ('board_units', '棋盘对象'),
    ]:
        diff = report['diff'][name]
        removed = len(diff['removed'])
        old_count = report['counts'][name] - len(diff['added']) + removed
        if removed >= 3 and removed >= old_count * 0.25:
            report['warnings'].append(
                f'比较：{label}移除 {removed}/{old_count} 条，请核实完整快照是否正确'
            )


def run_one_job():
    """Claim an idle/expired lease using a conditional update, fencing every final write."""
    db = get_db()
    cutoff = (datetime.now() - timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
    job = db.execute(
        """SELECT * FROM season_import_jobs WHERE status='queued'
         OR (status='running' AND heartbeat_at<?) ORDER BY created_at LIMIT 1""",
        (cutoff,),
    ).fetchone()
    if not job:
        db.rollback()
        return False
    token, stamp = uuid.uuid4().hex, now_text()
    changed = db.execute(
        """UPDATE season_import_jobs SET status='running',stage='checking',lease_token=?,
        heartbeat_at=?,updated_at=?,attempt=attempt+1 WHERE id=? AND
        (status='queued' OR (status='running' AND heartbeat_at<?))""",
        (token, stamp, stamp, job['id'], cutoff),
    ).rowcount
    if changed != 1:
        db.rollback()
        return True
    db.execute(
        "UPDATE season_release_packages SET state='validating' WHERE id=?", (job['release_id'],)
    )
    db.commit()
    rid = job['release_id']
    staging = package_root() / 'staging' / f'{rid}-{token}'
    last = [0.0]
    started = time.monotonic()

    def progress(stage, percent, message):
        require(time.monotonic() - started < 30 * 60, '校验超过 30 分钟，请检查资料后重试')
        if time.monotonic() - last[0] < 1.5 and percent != 100:
            return
        last[0] = time.monotonic()
        owned = db.execute(
            """UPDATE season_import_jobs SET stage=?,progress=?,message=?,heartbeat_at=?,updated_at=?
            WHERE id=? AND lease_token=? AND status='running' AND cancel_requested=0""",
            (stage, percent, message[:240], now_text(), now_text(), job['id'], token),
        ).rowcount
        db.commit()
        require(owned == 1, '任务已取消或已由另一个进程接管')

    try:
        progress('checking', 1, '检查压缩包和文件清单')
        path = package_root() / 'uploads' / f'{rid}.zip'
        manifest = inspect_zip(path, limits())
        require(
            shutil.disk_usage(package_root()).free
            >= sum(m['bytes'] for m in manifest['files'].values()) + 256 * 1024**2,
            '解包空间不足，请先扩容或归档旧资料',
        )
        package = db.execute(
            'SELECT zip_sha256 FROM season_release_packages WHERE id=?', (rid,)
        ).fetchone()
        require(sha256(path) == package['zip_sha256'], '上传包发生变化')
        extract_package(path, staging, manifest, progress)
        report = validate_data(staging, manifest, progress)
        clear_request_selection()
        state = active_state(manifest['season_id'])
        report['compared_active'] = state
        report['diff'] = structural_diff(data_directory(manifest['season_id']), staging / 'data')
        _comparison_warnings(report)
        progress('finalizing', 100, '完整性检查通过')
        # The claim update holds the job row lock until immutable files + metadata are ready.
        owned = db.execute(
            """UPDATE season_import_jobs SET status='completed',stage='ready',progress=100,
            message='等待审核发布',updated_at=? WHERE id=? AND lease_token=? AND cancel_requested=0 AND status='running'""",
            (now_text(), job['id'], token),
        ).rowcount
        require(owned == 1, '任务已取消或租约失效')
        final = release_root(rid)
        final.parent.mkdir(parents=True, exist_ok=True)
        # A crash after rename but before commit can leave a complete orphan directory.
        if final.exists():
            require(read_json(final / 'manifest.json') == manifest, '候选版本目录冲突')
            validate_data(final, manifest)
        else:
            staging.replace(final)
        db.execute(
            "UPDATE season_release_packages SET state='ready',report_json=? WHERE id=?",
            (encode(report), rid),
        )
        _event(manifest['season_id'], rid, 'validated', None, {'warnings': report['warnings']})
        db.commit()
    except Exception as exc:
        db.rollback()
        current = db.execute('SELECT * FROM season_import_jobs WHERE id=?', (job['id'],)).fetchone()
        if current and current['lease_token'] == token and current['status'] == 'running':
            cancelled = bool(current['cancel_requested'])
            message = (
                str(exc)[:1200]
                if isinstance(exc, PackageError)
                else f'处理失败：{type(exc).__name__}；请检查文件格式后重试'
            )
            db.execute(
                '''UPDATE season_import_jobs SET status=?,stage=?,message=?,updated_at=?
                          WHERE id=? AND lease_token=?''',
                (
                    'cancelled' if cancelled else 'failed',
                    'cancelled' if cancelled else 'failed',
                    message,
                    now_text(),
                    job['id'],
                    token,
                ),
            )
            db.execute(
                'UPDATE season_release_packages SET state=? WHERE id=?',
                ('cancelled' if cancelled else 'rejected', rid),
            )
            sid = db.execute(
                'SELECT season_id FROM season_release_packages WHERE id=?', (rid,)
            ).fetchone()['season_id']
            _event(
                sid,
                rid,
                'validation',
                None,
                {'message': message},
                status='cancelled' if cancelled else 'failed',
            )
            db.commit()
            current_app.logger.warning('Season package %s validation failed: %s', rid, message)
    finally:
        # This path is generated locally, owned solely by this fenced attempt.
        if staging.exists() and staging.parent.resolve() == (package_root() / 'staging').resolve():
            shutil.rmtree(staging)
    return True


def refresh_report(release_id):
    payload = release_payload(release_id)
    require(payload and payload['state'] == 'ready', '版本尚未通过校验')
    report = payload['report']
    clear_request_selection()
    report['compared_active'] = active_state(payload['season_id'])
    report['diff'] = structural_diff(
        data_directory(payload['season_id']), release_root(release_id) / 'data'
    )
    _comparison_warnings(report)
    get_db().execute(
        'UPDATE season_release_packages SET report_json=? WHERE id=?', (encode(report), release_id)
    )
    get_db().commit()
    return release_payload(release_id)


def _smoke(season_id, release_id):
    """Real read/render path in a new request, without third-party requests or analytics."""
    app = current_app._get_current_object()
    with app.app_context(), app.test_client() as client:
        client.environ_base['HTTP_USER_AGENT'] = 'jcc-release-smoke-bot'
        response = client.get('/api/season-catalog?surface=library')
        require(response.status_code == 200, '发布后的资料索引检查失败')
        seasons = response.get_json()['seasons']
        if any(s['season_id'] == season_id for s in seasons):
            response = client.get(f'/tools/seasons/{season_id}')
            require(response.status_code == 200, '发布后的资料页检查失败')
            index = read_json(data_directory(season_id) / 'index.json')
            from season_data_repository import asset_url

            icon = index['champions'][0].get('icon')
            if icon:
                require(
                    client.get(f'{asset_url(season_id)}/{icon}').status_code == 200,
                    '发布后的图片检查失败',
                )
            champion_id = index['champions'][0]['id']
            response = client.get(f'/tools/seasons/{season_id}/champions/{champion_id}')
            require(response.status_code == 200, '发布后的弈子详情检查失败')
        from season_data_repository import data_url
        from season_visibility import get_season

        if get_season('simulator', season_id):
            for name in ('champions', 'traits', 'items', 'augments', 'board_units'):
                response = client.get(f'{data_url(season_id)}/{name}.json')
                require(
                    response.status_code == 200 and isinstance(response.get_json(), dict),
                    '模拟器资料检查失败',
                )
        response = client.get('/api/health')
        require(response.status_code == 200 and response.get_json().get('ok'), '健康检查失败')
    # No external CDN involved: verify the actual version selected in a fresh context.
    with app.app_context():
        require(active_state(season_id)['release_id'] == release_id, '发布版本指向发生变化')


def publish(season_id, target, expected_revision, actor, acknowledge=False, rollback=False):
    db = get_db()
    require(type(expected_revision) is int, '缺少预期发布修订号')
    require(season_id in {s['season_id'] for s in baseline_catalog()}, '赛季不存在')
    package = release_payload(target) if target else None
    if target:
        require(
            package and package['state'] == 'ready' and package['season_id'] == season_id,
            '目标版本不可发布',
        )
        if not rollback:
            require(
                package['report']['compared_active']['revision'] == expected_revision,
                '比较报告已过期，请重新比较',
            )
            require(
                not package['report']['warnings'] or acknowledge, '请确认报告中的继承或删除告警'
            )
        root = release_root(target)
        require(read_json(root / 'manifest.json') == package['manifest'], '发布包清单已改变')
        for name, meta in package['manifest']['files'].items():
            path = root / name
            require(
                path.is_file()
                and path.stat().st_size == meta['bytes']
                and sha256(path) == meta['sha256'],
                f'发布包文件缺失或改变：{name}',
            )
    else:
        require(rollback, '只能通过回滚恢复随代码部署的基准版本')
    old = active_state(season_id)
    require(old['revision'] == expected_revision, '线上版本已变化，请刷新后重试')
    if old['release_id'] == target:
        return old
    db.execute(
        '''INSERT INTO season_active_releases (season_id,revision,updated_at) VALUES (?,0,?)
                  ON CONFLICT (season_id) DO NOTHING''',
        (season_id, now_text()),
    )
    changed = db.execute(
        '''UPDATE season_active_releases SET previous_release_id=release_id,release_id=?,
        revision=revision+1,updated_at=? WHERE season_id=? AND revision=?''',
        (target, now_text(), season_id, expected_revision),
    ).rowcount
    if changed != 1:
        db.rollback()
        raise PackageError('线上版本已变化，请刷新后重试')
    if target:
        db.execute(
            'UPDATE season_release_packages SET published_at=COALESCE(published_at,?) WHERE id=?',
            (now_text(), target),
        )
    event_id = _event(
        season_id,
        target,
        'rollback' if rollback else 'publish',
        actor,
        {'revision': expected_revision + 1},
        previous=old['release_id'],
        status='verifying',
    )
    db.commit()
    clear_request_selection()
    try:
        _smoke(season_id, target)
        db.execute("UPDATE season_release_events SET status='completed' WHERE id=?", (event_id,))
        db.commit()
    except Exception:
        db.rollback()
        restored = db.execute(
            '''UPDATE season_active_releases SET release_id=?,previous_release_id=?,revision=revision+1,updated_at=?
            WHERE season_id=? AND revision=?''',
            (old['release_id'], target, now_text(), season_id, expected_revision + 1),
        ).rowcount
        db.execute(
            "UPDATE season_release_events SET status='failed',detail_json=? WHERE id=?",
            (encode({'auto_restored': bool(restored)}), event_id),
        )
        db.commit()
        clear_request_selection()
        raise PackageError(
            '发布验证失败；' + ('已恢复旧版本' if restored else '版本已再次变化，未覆盖后续发布')
        )
    return active_state(season_id)


def recover_publications():
    """Resume verification after process interruption; don't overwrite newer publications."""
    db = get_db()
    cutoff = (datetime.now() - timedelta(minutes=2)).strftime('%Y-%m-%d %H:%M:%S')
    events = db.execute(
        "SELECT * FROM season_release_events WHERE status='verifying' AND created_at<? ORDER BY created_at LIMIT 10",
        (cutoff,),
    ).fetchall()
    for event in events:
        revision = json.loads(event['detail_json'])['revision']
        state = active_state(event['season_id'])
        if state['revision'] != revision:
            db.execute(
                "UPDATE season_release_events SET status='superseded' WHERE id=?", (event['id'],)
            )
        else:
            try:
                _smoke(event['season_id'], event['release_id'])
                db.execute(
                    "UPDATE season_release_events SET status='completed' WHERE id=?", (event['id'],)
                )
            except Exception:
                db.execute(
                    '''UPDATE season_active_releases SET release_id=?,previous_release_id=?,revision=revision+1,updated_at=?
                    WHERE season_id=? AND revision=?''',
                    (
                        event['previous_release_id'],
                        event['release_id'],
                        now_text(),
                        event['season_id'],
                        revision,
                    ),
                )
                db.execute(
                    "UPDATE season_release_events SET status='failed' WHERE id=?", (event['id'],)
                )
        db.commit()
