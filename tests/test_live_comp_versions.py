import io
import json
from pathlib import Path

import pytest

from live_comp_upload_service import _claim_next_job, _process_job
from live_comp_version_service import save_version, mutate_version
from live_comps_helpers import season_data_path
from live_comp_manual_codes import set_manual_code_overlay_value
from test_live_comp_upload_admin import login_admin, payload

SEASON = 's17-star-god'
BASE = f'/api/admin/live-comps/versions/{SEASON}'


def draft(app, name='candidate.json', code='', item_id='same-id', publish=False):
    with app.app_context():
        return save_version(SEASON, payload(item_id, code), name, publish=publish)['version_id']


def info(client, version):
    response = client.get(f'{BASE}/{version}')
    assert response.status_code == 200
    return response.get_json()


def action(client, headers, version, command, **extra):
    data = info(client, version)
    return client.post(f'{BASE}/{version}/{command}', headers=headers, json={
        'revision': data['revision'], 'active_revision': data['active_revision'], **extra,
    })


def public_code(client):
    rows = client.get(f'/api/live-comps?season={SEASON}').get_json()['items']
    return rows[0]['jccCode'] if rows else None


def test_full_release_lifecycle_isolates_codes_and_preserves_rollback(client, app):
    headers = login_admin(client)
    original = draft(app, 'original.json', '#ORIGINAL', publish=True)
    candidate = draft(app)
    assert public_code(client) == '#ORIGINAL'
    assert info(client, candidate)['missing'] == 1
    assert action(client, headers, candidate, 'code', item_id='same-id', code='#CANDIDATE').status_code == 200
    assert public_code(client) == '#ORIGINAL'
    assert action(client, headers, candidate, 'publish').status_code == 200
    assert public_code(client) == '#CANDIDATE'
    assert info(client, original)['status'] == 'history'
    assert action(client, headers, candidate, 'delete').status_code == 409
    assert action(client, headers, original, 'publish').status_code == 200
    assert public_code(client) == '#ORIGINAL'
    assert info(client, candidate)['payload']['tiers']['S'][0]['jccCode'] == '#CANDIDATE'
    assert action(client, headers, candidate, 'delete').status_code == 200
    assert client.get(f'{BASE}/{candidate}').status_code == 404
    assert public_code(client) == '#ORIGINAL'


def test_missing_code_confirmation_and_stale_mutations(client, app):
    headers = login_admin(client)
    original = draft(app, publish=True)
    version = draft(app)
    assert action(client, headers, version, 'publish').status_code == 409
    stale = info(client, version)
    assert action(client, headers, version, 'code', item_id='same-id', code='#ONE').status_code == 200
    assert client.post(f'{BASE}/{version}/publish', headers=headers, json={
        'revision': stale['revision'], 'active_revision': stale['active_revision'], 'allow_missing': True,
    }).status_code == 409
    before = info(client, version)
    assert action(client, headers, original, 'code', item_id='same-id', code='#EDITLIVE').status_code == 200
    assert client.post(f'{BASE}/{version}/publish', headers=headers, json={
        'revision': before['revision'], 'active_revision': before['active_revision'],
    }).status_code == 409
    empty = draft(app)
    assert action(client, headers, empty, 'publish', allow_missing=True).status_code == 200
    assert public_code(client) == ''


def test_legacy_snapshot_retains_manual_codes_and_existing_code_route(client, app):
    headers = login_admin(client)
    with app.app_context():
        season_data_path(SEASON).write_text(json.dumps(payload('same-id', '')), encoding='utf-8')
        set_manual_code_overlay_value(app.config['LIVE_COMPS_MANUAL_CODE_DIR'], SEASON,
                                      'same-id', '#LEGACY', 1, '2026-10-15')
    candidate = draft(app)
    assert info(client, 'legacy')['ready'] == 1
    assert info(client, 'legacy')['revision'] == info(client, 'legacy')['revision']
    assert info(client, candidate)['missing'] == 1
    assert action(client, headers, candidate, 'publish', allow_missing=True).status_code == 200
    assert client.post(f'/api/admin/live-comps/{SEASON}/same-id/manual-code', headers=headers,
                       json={'code': '#ACTIVECODE'}).status_code == 200
    assert public_code(client) == '#ACTIVECODE'
    assert action(client, headers, 'legacy', 'publish').status_code == 200
    assert public_code(client) == '#LEGACY'
    assert info(client, candidate)['payload']['tiers']['S'][0]['jccCode'] == '#ACTIVECODE'


def test_permissions_season_isolation_and_private_cache(client, app):
    version = draft(app)
    assert client.get(BASE).status_code == 401
    assert client.get(f'{BASE}/{version}').status_code == 401
    headers = login_admin(client)
    assert client.get(BASE).headers['Cache-Control'] == 'private, no-store'
    assert client.post(f'{BASE}/{version}/delete', json={}).status_code == 403
    assert client.get(f'/api/admin/live-comps/versions/s16-legends/{version}').status_code == 404
    assert client.get(f'{BASE}/not-a-version').status_code == 404
    assert action(client, headers, version, 'code', item_id='same-id', code='invalid').status_code == 400
    assert action(client, headers, version, 'code', item_id='missing', code='#CODE').status_code == 404


def test_failed_atomic_publication_keeps_previous_live_data(client, app, monkeypatch):
    headers = login_admin(client)
    draft(app, 'original.json', '#ORIGINAL', publish=True)
    candidate = draft(app, code='#CANDIDATE')
    import live_comp_version_service as service
    real_replace = service.os.replace
    with app.app_context():
        live = season_data_path(SEASON)
    def fail_live(source, target):
        if Path(target) == live:
            raise OSError('simulated disk failure')
        return real_replace(source, target)
    monkeypatch.setattr(service.os, 'replace', fail_live)
    with pytest.raises(OSError):
        action(client, headers, candidate, 'publish')
    assert public_code(client) == '#ORIGINAL'
    assert info(client, candidate)['status'] == 'draft'


@pytest.mark.parametrize('publish,conflict,expected', [(False, False, 'draft'), (True, False, 'active'), (True, True, 'draft')])
def test_upload_worker_stages_by_default_and_guards_direct_publish(client, app, tmp_path, publish, conflict, expected):
    app.config['LIVE_COMPS_UPLOAD_JOB_DIR'] = str(tmp_path / 'jobs')
    headers = login_admin(client)
    original = draft(app, code='#ORIGINAL', publish=True)
    raw = json.dumps(payload('same-id', '')).encode()
    job = client.post('/api/admin/live-comps/uploads/preview', headers=headers,
                      data={'season_id': SEASON, 'file': (io.BytesIO(raw), 'candidate.json')}).get_json()
    response = client.post(f"/api/admin/live-comps/uploads/{job['job_id']}/start", headers=headers,
                           json={'publish': publish})
    assert response.status_code == 200
    if conflict:
        draft(app, code='#NEWER', publish=True)
    with app.app_context():
        queued = _claim_next_job()
        _process_job(app, queued)
    result = client.get(f"/api/admin/live-comps/uploads/{job['job_id']}").get_json()
    assert result['status'] == 'completed'
    assert info(client, result['result']['version_id'])['status'] == expected
    assert public_code(client) == ('' if expected == 'active' else '#NEWER' if conflict else '#ORIGINAL')
    assert info(client, original)['ready'] == 1


def test_failed_image_cache_never_replaces_live(client, app, tmp_path, monkeypatch):
    app.config['LIVE_COMPS_UPLOAD_JOB_DIR'] = str(tmp_path / 'jobs')
    headers = login_admin(client)
    draft(app, code='#ORIGINAL', publish=True)
    raw = json.dumps(payload()).encode()
    job = client.post('/api/admin/live-comps/uploads/preview', headers=headers,
                      data={'season_id': SEASON, 'file': (io.BytesIO(raw), 'bad-images.json')}).get_json()
    client.post(f"/api/admin/live-comps/uploads/{job['job_id']}/start", headers=headers, json={'publish': True})
    def fail(*args, **kwargs):
        raise ValueError('image download failed')
    monkeypatch.setattr('live_comps_helpers.cache_live_comps_payload_images', fail)
    with app.app_context():
        _process_job(app, _claim_next_job())
    assert client.get(f"/api/admin/live-comps/uploads/{job['job_id']}").get_json()['status'] == 'failed'
    assert public_code(client) == '#ORIGINAL'


def test_concurrent_edits_cannot_silently_overwrite_each_other(client, app):
    from concurrent.futures import ThreadPoolExecutor
    from live_comp_version_service import VersionError
    login_admin(client)
    version = draft(app)
    revision = info(client, version)['revision']
    def edit(code):
        with app.app_context():
            try:
                mutate_version(1, SEASON, version, 'code', {
                    'revision': revision, 'item_id': 'same-id', 'code': code,
                })
                return 200
            except VersionError as error:
                return error.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, ['#FIRST', '#SECOND'])) == [200, 409]


def test_direct_upload_checks_revision_from_preview_not_start(client, app, tmp_path):
    app.config['LIVE_COMPS_UPLOAD_JOB_DIR'] = str(tmp_path / 'jobs')
    headers = login_admin(client)
    draft(app, code='#ORIGINAL', publish=True)
    raw = json.dumps(payload()).encode()
    job = client.post('/api/admin/live-comps/uploads/preview', headers=headers,
                      data={'season_id': SEASON, 'file': (io.BytesIO(raw), 'candidate.json')}).get_json()
    draft(app, code='#NEWER', publish=True)
    client.post(f"/api/admin/live-comps/uploads/{job['job_id']}/start", headers=headers, json={'publish': True})
    with app.app_context():
        _process_job(app, _claim_next_job())
    result = client.get(f"/api/admin/live-comps/uploads/{job['job_id']}").get_json()
    assert result['result']['publication_conflict'] is True
    assert public_code(client) == '#NEWER'


def test_duplicate_ids_rejected_and_cli_preserves_current_manual_codes(client, app, tmp_path):
    app.config['LIVE_COMPS_UPLOAD_JOB_DIR'] = str(tmp_path / 'jobs')
    headers = login_admin(client)
    duplicate = payload()
    duplicate['tiers']['A'] = duplicate['tiers']['S']
    raw = json.dumps(duplicate).encode()
    assert client.post('/api/admin/live-comps/uploads/preview', headers=headers,
                       data={'season_id': SEASON, 'file': (io.BytesIO(raw), 'duplicate.json')}).status_code == 400
    version = draft(app, publish=True)
    action(client, headers, version, 'code', item_id='same-id', code='#CURRENT')
    response = app.test_client().post(f'/api/live-comps/upload?season={SEASON}',
                           headers={'X-Upload-Token': 'upload-secret'}, json=payload('same-id', ''))
    assert response.status_code == 200
    assert public_code(client) == '#CURRENT'
