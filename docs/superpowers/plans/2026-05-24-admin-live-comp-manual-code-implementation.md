# Admin Live Comp Manual Code Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow admins to inspect live comps by season in the admin console and add a manual lineup code only to existing live-comp entries that currently have no code, while preserving manual codes across future uploads unless the new upload explicitly provides an original code.

**Architecture:** Keep the existing season JSON files as the raw source of truth and add a second file-backed overlay layer for admin-entered manual codes. `live_comps.py` merges that overlay into API-facing payloads and prunes stale overrides after uploads, while `admin.py` exposes season-scoped listing and a manual-code mutation endpoint consumed by `static/admin.js`.

**Tech Stack:** Flask, JSON file storage under `instance/`, existing audit logging, pytest, vanilla JavaScript admin UI.

---

## File Structure

- Modify: `claude_project/config.py` — add a config key for per-season manual-code overlay storage.
- Modify: `claude_project/tests/conftest.py` — provision and clean up the manual-code overlay directory for tests.
- Create: `claude_project/live_comp_manual_codes.py` — load/save overlay files, merge manual codes into payloads, prune stale overrides after uploads.
- Modify: `claude_project/live_comps.py` — read merged payloads, keep public API backward-compatible, and prune manual overrides after season uploads.
- Modify: `claude_project/admin.py` — add season-scoped admin listing and manual-code mutation endpoint.
- Modify: `claude_project/tests/test_live_comps.py` — cover merged read behavior and upload-pruning behavior.
- Modify: `claude_project/tests/test_admin.py` — cover admin listing, manual-code creation, and rejection cases.
- Modify: `claude_project/static/admin.js` — render season picker + live-comp rows +补码弹窗 in the admin workspace.
- Modify: `claude_project/static/styles.css` — optional small layout/status styles for the new admin list rows and badges.

## Execution Notes

- `claude_project` is not a standalone Git repository in this workspace. During execution, use the “commit” steps as checkpoints; do the actual commit after syncing the approved changes into `jcc_git`.
- Do not change the database schema for this feature.
- Do not add a new front-end test harness just for this admin page. Use pytest for API contracts and a manual QA checklist for the browser behavior.

### Task 1: Add manual-code overlay storage helpers

**Files:**
- Create: `claude_project/live_comp_manual_codes.py`
- Modify: `claude_project/config.py`
- Modify: `claude_project/tests/conftest.py`
- Create: `claude_project/tests/test_live_comp_manual_codes.py`

- [ ] **Step 1: Write the failing helper tests**

```python
from live_comp_manual_codes import (
    load_manual_code_overlay,
    merge_manual_codes_into_payload,
    prune_manual_codes_for_payload,
    save_manual_code_overlay,
    set_manual_code_overlay_value,
)


def test_merge_manual_codes_only_fills_blank_codes(tmp_path):
    payload = {
        'meta': {},
        'tiers': {
            'S': [
                {'id': 's-01', 'title': '缺码阵容', 'tier': 'S', 'jccCode': '', 'mainAvatar': 'a', 'heroImages': ['b']},
                {'id': 's-02', 'title': '原始有码阵容', 'tier': 'S', 'jccCode': '#ORIGINAL002', 'mainAvatar': 'a', 'heroImages': ['b']},
            ],
            'A': [],
            'B': [],
            'C': [],
            'D': [],
        },
    }
    overlay_dir = tmp_path / 'manual-codes'
    save_manual_code_overlay(overlay_dir, 's17-star-god', {
        'season': 's17-star-god',
        'updated_at': '2026-05-24T10:00:00',
        'items': {
            's-01': {'jccCode': '#MANUAL001', 'updated_at': '2026-05-24T10:00:00', 'updated_by': 1},
            's-02': {'jccCode': '#MANUAL002', 'updated_at': '2026-05-24T10:00:00', 'updated_by': 1},
        },
    })

    merged = merge_manual_codes_into_payload(payload, load_manual_code_overlay(overlay_dir, 's17-star-god'))

    assert merged['tiers']['S'][0]['originalJccCode'] == ''
    assert merged['tiers']['S'][0]['resolvedJccCode'] == '#MANUAL001'
    assert merged['tiers']['S'][0]['jccCode'] == '#MANUAL001'
    assert merged['tiers']['S'][0]['codeSource'] == 'manual'
    assert merged['tiers']['S'][0]['hasCode'] is True
    assert merged['tiers']['S'][1]['originalJccCode'] == '#ORIGINAL002'
    assert merged['tiers']['S'][1]['resolvedJccCode'] == '#ORIGINAL002'
    assert merged['tiers']['S'][1]['codeSource'] == 'original'


def test_prune_manual_codes_drops_entries_once_upload_has_original_code(tmp_path):
    overlay_dir = tmp_path / 'manual-codes'
    set_manual_code_overlay_value(overlay_dir, 's16-legends', 'comp-1', '【阵容码】##MANUAL001', admin_id=7, now_value='2026-05-24T10:00:00')
    set_manual_code_overlay_value(overlay_dir, 's16-legends', 'comp-2', '【阵容码】##MANUAL002', admin_id=7, now_value='2026-05-24T10:00:00')
    payload = {
        'meta': {},
        'tiers': {
            'S': [{'id': 'comp-1', 'title': '已有新码', 'tier': 'S', 'jccCode': '#NEW001', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'A': [{'id': 'comp-2', 'title': '仍旧缺码', 'tier': 'A', 'jccCode': '', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'B': [],
            'C': [],
            'D': [],
        },
    }

    pruned = prune_manual_codes_for_payload(overlay_dir, 's16-legends', payload)

    assert 'comp-1' not in pruned['items']
    assert pruned['items']['comp-2']['jccCode'] == '#MANUAL002'
```

- [ ] **Step 2: Run the helper tests to verify they fail**

Run: `pytest D:\1\codex\jcc\claude_project\tests\test_live_comp_manual_codes.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'live_comp_manual_codes'`.

- [ ] **Step 3: Write the minimal helper implementation**

```python
# claude_project/config.py
LIVE_COMPS_MANUAL_CODE_DIR=os.path.join(app.instance_path, 'live-comps-manual-codes')
```

```python
# claude_project/live_comp_manual_codes.py
import json
from copy import deepcopy
from pathlib import Path

from lineup_code import extract_lineup_code

TIER_ORDER = ('S', 'A', 'B', 'C', 'D')


def manual_code_overlay_path(base_dir, season_id):
    return Path(base_dir) / f'{season_id}.json'


def load_manual_code_overlay(base_dir, season_id):
    path = manual_code_overlay_path(base_dir, season_id)
    if not path.exists():
        return {'season': str(season_id), 'updated_at': None, 'items': {}}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {'season': str(season_id), 'updated_at': None, 'items': {}}
    items = data.get('items') if isinstance(data.get('items'), dict) else {}
    return {
        'season': str(data.get('season') or season_id),
        'updated_at': data.get('updated_at'),
        'items': items,
    }


def save_manual_code_overlay(base_dir, season_id, overlay):
    path = manual_code_overlay_path(base_dir, season_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'season': str(overlay.get('season') or season_id),
        'updated_at': overlay.get('updated_at'),
        'items': dict(overlay.get('items') or {}),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return payload


def set_manual_code_overlay_value(base_dir, season_id, live_comp_id, code, admin_id, now_value):
    normalized = extract_lineup_code(code)
    if not normalized:
        raise ValueError('阵容码格式无法识别')
    overlay = load_manual_code_overlay(base_dir, season_id)
    overlay['updated_at'] = now_value
    overlay['items'][str(live_comp_id)] = {
        'jccCode': normalized,
        'updated_at': now_value,
        'updated_by': int(admin_id),
    }
    return save_manual_code_overlay(base_dir, season_id, overlay)


def merge_manual_codes_into_payload(payload, overlay):
    merged = deepcopy(payload)
    overlay_items = dict((overlay or {}).get('items') or {})
    for tier in TIER_ORDER:
        normalized_items = []
        for item in merged.get('tiers', {}).get(tier, []):
            row = dict(item)
            original_code = extract_lineup_code(row.get('jccCode')) or ''
            manual_entry = overlay_items.get(str(row.get('id'))) or {}
            manual_code = extract_lineup_code(manual_entry.get('jccCode')) or ''
            resolved_code = original_code or manual_code
            row['originalJccCode'] = original_code
            row['resolvedJccCode'] = resolved_code
            row['jccCode'] = resolved_code
            row['hasCode'] = bool(resolved_code)
            row['codeSource'] = 'original' if original_code else ('manual' if manual_code else 'none')
            normalized_items.append(row)
        merged['tiers'][tier] = normalized_items
    return merged


def prune_manual_codes_for_payload(base_dir, season_id, payload):
    overlay = load_manual_code_overlay(base_dir, season_id)
    live_comp_map = {}
    for tier in TIER_ORDER:
        for item in payload.get('tiers', {}).get(tier, []):
            live_comp_map[str(item.get('id'))] = item
    kept_items = {}
    for live_comp_id, meta in overlay['items'].items():
        candidate = live_comp_map.get(str(live_comp_id))
        original_code = extract_lineup_code((candidate or {}).get('jccCode')) or ''
        if candidate and not original_code:
            kept_items[str(live_comp_id)] = meta
    overlay['items'] = kept_items
    return save_manual_code_overlay(base_dir, season_id, overlay)
```

```python
# claude_project/tests/conftest.py
live_comps_manual_code_dir = ROOT / 'test-live-comps-manual-codes'
...
for directory in [live_comps_asset_dir, live_comps_season_dir, live_comps_manual_code_dir]:
    if directory.exists():
        shutil.rmtree(directory)
...
'LIVE_COMPS_MANUAL_CODE_DIR': str(live_comps_manual_code_dir),
...
for directory in [live_comps_asset_dir, live_comps_season_dir, live_comps_manual_code_dir]:
    if directory.exists():
        shutil.rmtree(directory)
```

- [ ] **Step 4: Run the helper tests to verify they pass**

Run: `pytest D:\1\codex\jcc\claude_project\tests\test_live_comp_manual_codes.py -q`

Expected: `2 passed`.

- [ ] **Step 5: Checkpoint the helper layer**

Run: `git -C D:\1\codex\jcc\jcc_git status --short`

Expected: no change yet in `jcc_git`; note that the next sync checkpoint should include `live_comp_manual_codes.py`, `config.py`, `tests/conftest.py`, and `tests/test_live_comp_manual_codes.py`.

### Task 2: Merge manual codes into public live-comps reads and uploads

**Files:**
- Modify: `claude_project/live_comps.py`
- Modify: `claude_project/tests/test_live_comps.py`

- [ ] **Step 1: Write the failing public API tests**

```python
from pathlib import Path

from live_comp_manual_codes import set_manual_code_overlay_value
from test_live_comps import sample_live_comps_payload, write_live_comps_seed


def test_live_comps_list_uses_manual_code_when_original_code_is_missing(client):
    payload = sample_live_comps_payload()
    payload['tiers']['A'][0]['jccCode'] = ''
    write_live_comps_seed(client, payload)
    set_manual_code_overlay_value(
        client.application.config['LIVE_COMPS_MANUAL_CODE_DIR'],
        's17-star-god',
        'a-01',
        '【阵容码】##MANUALA01',
        admin_id=1,
        now_value='2026-05-24T10:00:00',
    )

    data = client.get('/api/live-comps').get_json()
    item = next(row for row in data['items'] if row['id'] == 'a-01')

    assert item['jccCode'] == '#MANUALA01'
    assert item['resolvedJccCode'] == '#MANUALA01'
    assert item['originalJccCode'] == ''
    assert item['codeSource'] == 'manual'
    assert item['hasCode'] is True


def test_live_comps_upload_prunes_manual_code_only_when_new_upload_provides_original_code(client):
    import live_comps

    def fake_download(url):
        return b'image-bytes', 'image/png'

    live_comps.download_live_comp_image = fake_download
    set_manual_code_overlay_value(
        client.application.config['LIVE_COMPS_MANUAL_CODE_DIR'],
        's16-legends',
        's16-s-01',
        '【阵容码】##MANUALS16',
        admin_id=3,
        now_value='2026-05-24T10:00:00',
    )
    keep_payload = {
        'meta': {'source': 'keep'},
        'tiers': {
            'S': [{'id': 's16-s-01', 'title': 'S16 阵容 1', 'tier': 'S', 'jccCode': '', 'mainAvatar': 'https://example.com/a.png', 'heroImages': ['https://example.com/b.png']}],
            'A': [],
            'B': [],
            'C': [],
            'D': [],
        },
    }
    replace_payload = {
        'meta': {'source': 'replace'},
        'tiers': {
            'S': [{'id': 's16-s-01', 'title': 'S16 阵容 1', 'tier': 'S', 'jccCode': '#UPLOADED001', 'mainAvatar': 'https://example.com/a.png', 'heroImages': ['https://example.com/b.png']}],
            'A': [],
            'B': [],
            'C': [],
            'D': [],
        },
    }

    keep = client.post('/api/live-comps/upload?season=s16-legends', json=keep_payload, headers={'X-Upload-Token': 'upload-secret'})
    keep_listing = client.get('/api/live-comps?season=s16-legends').get_json()
    replace = client.post('/api/live-comps/upload?season=s16-legends', json=replace_payload, headers={'X-Upload-Token': 'upload-secret'})
    replace_listing = client.get('/api/live-comps?season=s16-legends').get_json()

    assert keep.status_code == 200
    assert next(row for row in keep_listing['items'] if row['id'] == 's16-s-01')['jccCode'] == '#MANUALS16'
    assert replace.status_code == 200
    assert next(row for row in replace_listing['items'] if row['id'] == 's16-s-01')['jccCode'] == '#UPLOADED001'
```

- [ ] **Step 2: Run the public API tests to verify they fail**

Run: `pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -k "manual_code or prunes_manual_code" -q`

Expected: FAIL because `read_live_comps_payload_for_season()` currently returns only raw `jccCode`, and uploads do not prune overlay files.

- [ ] **Step 3: Write the minimal public API integration**

```python
# claude_project/live_comps.py
from live_comp_manual_codes import (
    load_manual_code_overlay,
    merge_manual_codes_into_payload,
    prune_manual_codes_for_payload,
)
```

```python
# claude_project/live_comps.py
def manual_code_dir():
    return Path(current_app.config['LIVE_COMPS_MANUAL_CODE_DIR'])


def read_raw_live_comps_payload_for_season(season_id=None):
    manifest = load_live_comps_manifest()
    selected_id = canonical_season_id(season_id) or manifest['default_season_id']
    season = next((item for item in manifest['seasons'] if item['id'] == selected_id), None)
    if season is None:
        season = next((item for item in manifest['seasons'] if item['id'] == manifest['default_season_id']), None)
    if season is None:
        season = manifest['seasons'][0]
    data_path = season_data_path(season['id'])
    if not data_path.exists() and season['id'] == manifest['default_season_id']:
        data_path = Path(current_app.config['LIVE_COMPS_DATA_PATH'])
    if not data_path.exists():
        return empty_live_comps_payload(), None, False, manifest, season
    updated_at = datetime.fromtimestamp(data_path.stat().st_mtime).isoformat(timespec='seconds')
    try:
        payload = json.loads(data_path.read_text(encoding='utf-8'))
        validate_live_comps_payload(payload)
        return normalize_live_comps_payload(payload), updated_at, True, manifest, season
    except Exception:
        return empty_live_comps_payload(), updated_at, False, manifest, season


def read_live_comps_payload_for_season(season_id=None):
    payload, updated_at, is_valid, manifest, season = read_raw_live_comps_payload_for_season(season_id)
    overlay = load_manual_code_overlay(manual_code_dir(), season['id'])
    merged_payload = merge_manual_codes_into_payload(payload, overlay)
    return merged_payload, updated_at, is_valid, manifest, season
```

```python
# claude_project/live_comps.py
def write_live_comps_payload_for_season(season_id, payload):
    validate_live_comps_payload(payload)
    payload = cache_live_comps_payload_images(payload)
    ensure_live_comps_season(season_id)
    data_path = season_data_path(season_id)
    backup_path = Path(current_app.config['LIVE_COMPS_BACKUP_PATH'])
    data_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = data_path.with_suffix('.tmp')
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    json.loads(temp_path.read_text(encoding='utf-8'))
    if data_path.exists():
        shutil.copyfile(data_path, backup_path)
    os.replace(temp_path, data_path)
    prune_manual_codes_for_payload(manual_code_dir(), canonical_season_id(season_id), payload)
```

```python
# claude_project/live_comps.py
@live_comps_bp.post('/api/live-comps/<live_comp_id>/copy')
def copy_live_comp(live_comp_id):
    season_id = request.args.get('season')
    payload, _, _, _, _ = read_live_comps_payload_for_season(season_id)
    item = find_live_comp(payload, live_comp_id)
    if not item:
        return jsonify({'error': '实时阵容不存在'}), 404
    if not str(item.get('resolvedJccCode') or item.get('jccCode') or '').strip():
        return jsonify({'error': '当前阵容暂无可复制的阵容码'}), 400
    stat = increment_live_comp_global_copy_count()
    return jsonify({'ok': True, 'live_comp_id': str(live_comp_id), 'today_copy_count': int(stat['today_copy_count']), 'total_copy_count': int(stat['total_copy_count'])})
```

- [ ] **Step 4: Run the public API tests to verify they pass**

Run: `pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -k "manual_code or prunes_manual_code" -q`

Expected: the two new tests pass, with no regressions in `jccCode` compatibility.

- [ ] **Step 5: Checkpoint the public API behavior**

Run: `pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -q`

Expected: all live-comps tests pass before moving on to admin routes.

### Task 3: Add admin season-scoped listing and manual-code mutation endpoint

**Files:**
- Modify: `claude_project/admin.py`
- Modify: `claude_project/tests/test_admin.py`

- [ ] **Step 1: Write the failing admin API tests**

```python
from pathlib import Path
import json

from test_admin import login_admin
from test_live_comps import sample_live_comps_payload


def test_admin_live_comps_returns_selected_season_items_with_code_source(client):
    headers = login_admin(client)
    season_dir = Path(client.application.config['LIVE_COMPS_SEASON_DIR'])
    season_dir.mkdir(parents=True, exist_ok=True)
    payload = sample_live_comps_payload()
    payload['tiers']['S'][0]['jccCode'] = ''
    (season_dir / 's16-legends.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')

    response = client.get('/api/admin/live-comps?season=s16-legends&page=1&page_size=10', headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data['season']['id'] == 's16-legends'
    assert data['total'] >= 1
    assert next(item for item in data['items'] if item['id'] == 's-01')['codeSource'] == 'none'


def test_admin_can_add_manual_code_for_missing_live_comp(client):
    headers = login_admin(client)
    season_dir = Path(client.application.config['LIVE_COMPS_SEASON_DIR'])
    season_dir.mkdir(parents=True, exist_ok=True)
    payload = sample_live_comps_payload()
    payload['tiers']['S'][0]['jccCode'] = ''
    (season_dir / 's16-legends.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')

    created = client.post(
        '/api/admin/live-comps/s16-legends/s-01/manual-code',
        json={'code': '【阵容码】##ADMIN001'},
        headers=headers,
    )
    listed = client.get('/api/admin/live-comps?season=s16-legends&page=1&page_size=10', headers=headers)

    assert created.status_code == 200
    assert created.get_json()['resolvedJccCode'] == '#ADMIN001'
    item = next(row for row in listed.get_json()['items'] if row['id'] == 's-01')
    assert item['codeSource'] == 'manual'
    assert item['resolvedJccCode'] == '#ADMIN001'


def test_admin_rejects_manual_code_for_live_comp_that_already_has_original_code(client):
    headers = login_admin(client)
    season_dir = Path(client.application.config['LIVE_COMPS_SEASON_DIR'])
    season_dir.mkdir(parents=True, exist_ok=True)
    (season_dir / 's17-star-god.json').write_text(json.dumps(sample_live_comps_payload(), ensure_ascii=False), encoding='utf-8')

    response = client.post(
        '/api/admin/live-comps/s17-star-god/s-01/manual-code',
        json={'code': '【阵容码】##SHOULDFAIL'},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.get_json()['error'] == '当前条目已有原始阵容码，无需补码'


def test_admin_live_comp_copy_metrics_still_work_when_listing_is_present(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    csrf = client.get('/api/me').get_json()['csrf_token']
    client.post('/api/live-comps/a-02/copy', headers={'X-CSRF-Token': csrf})
    headers = login_admin(client)

    payload = client.get('/api/admin/live-comps?season=s17-star-god&page=1&page_size=10', headers=headers).get_json()

    assert payload['today_copy_count'] == 1
    assert payload['total_copy_count'] == 1
    assert payload['season']['id'] == 's17-star-god'
    assert payload['total'] >= 1
```

- [ ] **Step 2: Run the admin API tests to verify they fail**

Run: `pytest D:\1\codex\jcc\claude_project\tests\test_admin.py -k "selected_season_items or add_manual_code or rejects_manual_code" -q`

Expected: FAIL because `/api/admin/live-comps` does not accept season-scoped listing yet and `/manual-code` route does not exist.

- [ ] **Step 3: Write the minimal admin backend implementation**

```python
# claude_project/admin.py
from flask import Blueprint, jsonify, render_template, request, current_app

from live_comp_manual_codes import set_manual_code_overlay_value
from live_comps import (
    build_admin_live_comp_stats_payload,
    find_live_comp,
    load_live_comps_manifest,
    read_live_comps_payload_for_season,
    read_raw_live_comps_payload_for_season,
)
```

```python
# claude_project/admin.py
@admin_bp.get('/api/admin/live-comps')
def admin_live_comps():
    admin, error = admin_required()
    if error:
        return error
    season_id = request.args.get('season')
    payload, updated_at, is_valid, manifest, season = read_live_comps_payload_for_season(season_id)
    return jsonify(build_admin_live_comp_stats_payload(
        payload,
        updated_at,
        is_valid,
        season=season,
        manifest=manifest,
        page=_parse_page(),
        page_size=_parse_page_size(default=20, maximum=100),
    ))


@admin_bp.post('/api/admin/live-comps/<season_id>/<live_comp_id>/manual-code')
def admin_add_live_comp_manual_code(season_id, live_comp_id):
    admin, error = admin_required()
    if error:
        return error
    payload, _, _, manifest, season = read_raw_live_comps_payload_for_season(season_id)
    target = find_live_comp(payload, live_comp_id)
    if not target:
        return jsonify({'error': '实时阵容不存在'}), 404
    original_code = str(target.get('jccCode') or '').strip()
    if original_code:
        return jsonify({'error': '当前条目已有原始阵容码，无需补码'}), 400
    data = request.get_json(silent=True) or {}
    overlay = set_manual_code_overlay_value(
        current_app.config['LIVE_COMPS_MANUAL_CODE_DIR'],
        season['id'],
        live_comp_id,
        str(data.get('code') or ''),
        admin_id=admin['id'],
        now_value=now_text(),
    )
    merged_payload, _, _, _, _ = read_live_comps_payload_for_season(season['id'])
    merged_item = find_live_comp(merged_payload, live_comp_id)
    write_audit(
        admin['id'],
        'admin_add_live_comp_manual_code',
        'live_comp',
        f'{season["id"]}:{live_comp_id}',
        before={'jccCode': '', 'resolvedJccCode': ''},
        after={'resolvedJccCode': merged_item['resolvedJccCode'], 'season_id': season['id'], 'overlay_updated_at': overlay['updated_at']},
    )
    return jsonify(merged_item)
```

```python
# claude_project/live_comps.py
def build_admin_live_comp_stats_payload(payload, updated_at, is_valid, season=None, manifest=None, page=1, page_size=20):
    listing = get_combined_live_comps_page(payload, page, page_size)
    return {
        'items': listing['items'],
        'total': listing['total'],
        'page': listing['page'],
        'page_size': listing['page_size'],
        'total_pages': listing['total_pages'],
        'updated_at': updated_at,
        'season': {
            'id': (season or {}).get('id'),
            'name': (season or {}).get('name'),
            'status': (season or {}).get('status'),
        },
        'source_meta': {**payload.get('meta', {}), 'is_valid': is_valid},
        **load_live_comp_global_stats(),
    }
```

- [ ] **Step 4: Run the admin API tests to verify they pass**

Run: `pytest D:\1\codex\jcc\claude_project\tests\test_admin.py -k "selected_season_items or add_manual_code or rejects_manual_code" -q`

Expected: `3 passed`.

- [ ] **Step 5: Checkpoint the admin backend**

Run: `pytest D:\1\codex\jcc\claude_project\tests\test_admin.py -k "live_comps" -q`

Expected: all live-comp-related admin tests pass, including the existing global copy-count test.

### Task 4: Wire the admin UI for season switching and补码

**Files:**
- Modify: `claude_project/static/admin.js`
- Modify: `claude_project/static/styles.css`

- [ ] **Step 1: Lock the API contract before UI work**

Run: `pytest D:\1\codex\jcc\claude_project\tests\test_admin.py -k "live_comps" -q`

Expected: PASS. This is the guardrail for the UI task because the repo does not contain a browser test harness.

- [ ] **Step 2: Implement the admin workspace rendering**

```javascript
// claude_project/static/admin.js
const state = {
  ...,
  liveComps: {
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    total_pages: 1,
    query: '',
    updated_at: null,
    source_meta: null,
    selectedSeasonId: '',
    loadedAt: 0,
  },
  liveCompManualCodeTarget: null,
  liveCompManualCodeError: '',
};
```

```javascript
// claude_project/static/admin.js
async function loadAdminLiveComps({ force = false } = {}) {
  if (!state.liveComps.selectedSeasonId) {
    state.liveComps.selectedSeasonId = state.liveCompsSeasons.default_season_id || (state.liveCompsSeasons.seasons[0] || {}).id || '';
  }
  if (!force && isFresh(state.liveComps.loadedAt)) return;
  abortRequest('liveComps');
  state.controllers.liveComps = new AbortController();
  const query = new URLSearchParams({
    season: state.liveComps.selectedSeasonId,
    page: String(state.liveComps.page),
    page_size: String(state.liveComps.page_size),
  });
  const payload = await api(`/api/admin/live-comps?${query.toString()}`, { signal: state.controllers.liveComps.signal });
  state.liveComps = { ...state.liveComps, ...payload, loadedAt: Date.now() };
}
```

```javascript
// claude_project/static/admin.js
function renderLiveCompsWorkspace() {
  const panel = workbenchPanel('实时阵容', '按赛季查看实时阵容，并给缺少阵容码的条目补码');
  const body = panel.querySelector('.admin-workspace-body');
  body.append(renderLiveCompSeasonPicker());
  body.append(el('p', 'admin-meta', state.liveComps.updated_at ? `实时阵容数据更新时间：${state.liveComps.updated_at}` : '实时阵容数据更新时间：暂无'));
  body.append(renderLiveCompMetrics());
  body.append(renderLiveCompItemList());
  body.append(renderPagination('liveComps'));
  body.append(renderLiveCompSeasonManager());
  return panel;
}


function renderLiveCompItemList() {
  const list = el('div', 'admin-list compact');
  if (!state.liveComps.items.length) {
    list.append(empty('当前赛季暂无实时阵容'));
    return list;
  }
  state.liveComps.items.forEach((item) => {
    const card = el('article', 'admin-row-card');
    const info = el('div');
    info.append(
      el('strong', '', `${item.tier} · ${item.title}`),
      el('p', 'admin-meta', `ID：${item.id} · 阵容码状态：${item.hasCode ? '有' : '无'} · 来源：${item.codeSource === 'manual' ? '管理员补码' : item.codeSource === 'original' ? '原始阵容码' : '暂无阵容码'}`),
    );
    if (item.hasCode) {
      info.append(el('pre', 'admin-code', item.resolvedJccCode));
    }
    const actions = el('div', 'card-actions');
    if (!item.hasCode && !item.originalJccCode) {
      actions.append(button('补码', async () => openLiveCompManualCodeDialog(item)));
    }
    card.append(info, actions);
    list.append(card);
  });
  return list;
}
```

```javascript
// claude_project/static/admin.js
function renderLiveCompSeasonPicker() {
  const wrap = el('div', 'admin-filter-pills');
  (state.liveCompsSeasons.seasons || []).forEach((season) => {
    wrap.append(button(season.name, async () => {
      state.liveComps.selectedSeasonId = season.id;
      state.liveComps.page = 1;
      await loadAdminLiveComps({ force: true });
      render();
    }, `small-button ${state.liveComps.selectedSeasonId === season.id ? 'is-active' : ''}`.trim()));
  });
  return wrap;
}


function renderLiveCompMetrics() {
  const metrics = el('div', 'traffic-grid');
  metrics.append(
    trafficMetric('今日复制', state.liveComps.today_copy_count || 0, '今天实时阵容专区所有复制点击'),
    trafficMetric('累计复制', state.liveComps.total_copy_count || 0, '从统计开始至今的所有复制点击'),
  );
  return metrics;
}


function renderLiveCompSeasonManager() {
  const panel = el('div', 'admin-subpanel');
  const header = el('div', 'admin-subpanel-head');
  header.append(el('h3', '', '赛季管理'));
  header.append(button('刷新赛季', async () => {
    await loadAdminLiveCompsSeasons({ force: true });
    render();
  }));
  panel.append(header);
  const seasonList = el('div', 'admin-season-list');
  (state.liveCompsSeasons.seasons || []).forEach((season) => {
    const card = el('article', 'admin-season-card');
    const info = el('div', 'admin-season-info');
    info.append(
      el('strong', '', season.name || season.id),
      el('p', 'admin-meta', `${season.id} · ${statusText[season.status] || season.status || '正常'} · ${season.description || '无说明'}`),
    );
    const controls = el('div', 'admin-season-controls');
    liveSeasonStatusOptions.forEach(([status, label]) => {
      controls.append(button(label, async () => {
        await api(`/api/admin/live-comps/seasons/${encodeURIComponent(season.id)}`, {
          method: 'PUT',
          body: JSON.stringify({ status }),
        });
        await loadAdminLiveCompsSeasons({ force: true });
        render();
      }, `small-button${season.status === status ? ' is-active' : ''}`));
    });
    if (season.id !== state.liveCompsSeasons.default_season_id) {
      controls.append(button('设为默认', async () => {
        await api(`/api/admin/live-comps/seasons/${encodeURIComponent(season.id)}`, {
          method: 'PUT',
          body: JSON.stringify({ default_season_id: season.id }),
        });
        await loadAdminLiveCompsSeasons({ force: true });
        render();
      }));
    }
    card.append(info, controls);
    seasonList.append(card);
  });
  panel.append(seasonList);
  return panel;
}


function openLiveCompManualCodeDialog(item) {
  state.liveCompManualCodeTarget = item;
  state.liveCompManualCodeError = '';
  renderLiveCompManualCodeDialog();
}


function closeLiveCompManualCodeDialog() {
  state.liveCompManualCodeTarget = null;
  state.liveCompManualCodeError = '';
  renderLiveCompManualCodeDialog();
}


function renderLiveCompManualCodeDialog() {
  if (!dialogRoot) return;
  dialogRoot.replaceChildren();
  if (!state.liveCompManualCodeTarget) return;
  const overlay = el('div', 'modal-backdrop');
  const card = el('section', 'modal-card');
  const header = el('div', 'modal-header');
  const titleWrap = el('div');
  titleWrap.append(
    el('h2', '', '补录实时阵容码'),
    el('p', 'admin-meta', `${state.liveCompManualCodeTarget.tier} · ${state.liveCompManualCodeTarget.title} · ${state.liveCompManualCodeTarget.id}`),
  );
  header.append(titleWrap, button('取消', async () => closeLiveCompManualCodeDialog()));

  const form = el('form', 'modal-form');
  form.innerHTML = `
    <label class="field">
      <span>阵容码</span>
      <textarea id="liveCompManualCodeInput" name="code" rows="4" placeholder="粘贴阵容码"></textarea>
    </label>
    <div class="message" id="liveCompManualCodeMessage">${state.liveCompManualCodeError || ''}</div>
    <div class="editor-actions">
      <button class="primary-button" type="submit">保存</button>
      <button class="ghost-button" type="button" id="cancelLiveCompManualCodeButton">取消</button>
    </div>
  `;
  form.addEventListener('submit', submitLiveCompManualCode);
  form.querySelector('#cancelLiveCompManualCodeButton').addEventListener('click', closeLiveCompManualCodeDialog);
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) closeLiveCompManualCodeDialog();
  });
  card.append(header, form);
  overlay.append(card);
  dialogRoot.append(overlay);
}


async function submitLiveCompManualCode(event) {
  event.preventDefault();
  const code = event.currentTarget.querySelector('#liveCompManualCodeInput').value;
  try {
    await api(`/api/admin/live-comps/${encodeURIComponent(state.liveComps.selectedSeasonId)}/${encodeURIComponent(state.liveCompManualCodeTarget.id)}/manual-code`, {
      method: 'POST',
      body: JSON.stringify({ code }),
    });
  } catch (error) {
    state.liveCompManualCodeError = error.message || '保存失败';
    renderLiveCompManualCodeDialog();
    return;
  }
  closeLiveCompManualCodeDialog();
  await loadAdminLiveComps({ force: true });
  setNotice('实时阵容补码已保存');
}
```

- [ ] **Step 3: Add only the styles the new list actually needs**

```css
/* claude_project/static/styles.css */
.admin-live-comp-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.admin-code-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
}

.admin-code-status strong {
  color: var(--text);
}
```

- [ ] **Step 4: Re-run the targeted backend contract tests after the UI changes**

Run: `pytest D:\1\codex\jcc\claude_project\tests\test_admin.py -k "live_comps" -q`

Expected: PASS. The UI task must not break the already-green API behavior.

- [ ] **Step 5: Manual QA in the browser**

Run:

```bash
cd /d D:\1\codex\jcc\claude_project
python .\run_server.py
```

Manual checklist:

- Log in as admin and open `/admin`
- Switch to “实时阵容” Tab
- Switch between `S17·星神` and `S16·英雄联盟传奇`
- Confirm rows appear for the selected season only
- Confirm only “当前没有阵容码”的条目显示“补码”按钮
- Add a code to one missing-code row
- Confirm the row refreshes to “管理员补码” and the button disappears
- Open the homepage for the same season and confirm that the live-comp copy button becomes available for that row

Expected: all checklist items pass before syncing to `jcc_git`.
