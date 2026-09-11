import io
import json
import stat
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from db import get_db
from season_package_format import PackageError, dump, inspect_zip, extract_package, validate_data
from season_package_service import run_one_job, release_payload, active_state
from scripts.season_library.build_upload_package import build_package
from scripts.season_library.import_from_archive import compact_champion, compact_trait


@pytest.fixture()
def prepared(tmp_path):
    root = tmp_path / 'source'
    (root / 'assets').mkdir(parents=True)
    Image.new('RGB', (8, 8), 'blue').save(root / 'assets/icon.png')
    img = {'local_path': 'assets/icon.png'}
    champion = {
        'id': '100',
        'name': '测试弈子',
        'cost': 1,
        'trait_ids': ['tr1'],
        'images': {'icon': img, 'splash': img},
        'skills': [],
        'stats_by_star': {},
    }
    trait = {
        'id': 'tr1',
        'name': '测试羁绊',
        'category': 'origin',
        'description': '测试效果',
        'image': img,
        'breakpoints': [{'min_units': 1, 'max_units': None, 'style': 1, 'effect': '效果'}],
    }
    item = {
        'id': 'it1',
        'name': '测试装备',
        'category': 'basic',
        'image': img,
        'recipe': {'component_ids': []},
    }
    version = 's18__18_18_3'
    for name, rows in {
        'champions': [champion],
        'traits': [trait],
        'items': [item],
        'augments': [],
        'board_units': [],
    }.items():
        dump(root / f'{name}.json', {'version_id': version, name: rows})
    dump(
        root / 'index.json',
        {
            'season_id': 's18',
            'display_name': 'S18',
            'game_version': '18.18.3',
            'version_id': version,
            'champions': [compact_champion(champion)],
            'traits': [compact_trait(trait)],
            'augments': [],
            'mechanics': [],
        },
    )
    return root


def package(prepared, suffix='one', revision=1):
    path = prepared.parent / f'{suffix}.zip'
    build_package(
        prepared,
        path,
        revision,
        {
            'title': '测试更新',
            'summary': '本地处理完成',
            'sections': [{'title': '调整', 'items': ['更新弈子']}],
        },
    )
    return path


def rewrite_zip(path, replacements=None, extra=None):
    with zipfile.ZipFile(path) as z:
        contents = {i.filename: z.read(i) for i in z.infolist()}
    contents.update(replacements or {})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in contents.items():
            z.writestr(name, data)
        if extra:
            z.writestr(*extra)
    return stream.getvalue()


@pytest.fixture()
def manager(client, app, tmp_path):
    app.config['SEASON_PACKAGE_ROOT'] = str(tmp_path / 'packages')
    data = client.post(
        '/api/login', json={'username': 'adminxlx', 'password': 'Admin1234'}
    ).get_json()
    return client, {'X-CSRF-Token': data['csrf_token']}


def upload(manager, path):
    client, headers = manager
    return client.post(
        '/api/admin/season-packages',
        headers=headers,
        data={'file': (io.BytesIO(path.read_bytes()), path.name)},
        content_type='multipart/form-data',
    )


def work(app, rid):
    with app.app_context():
        assert run_one_job()
        return release_payload(rid)


def test_offline_builder_roundtrip_and_no_mechanics(prepared, tmp_path, monkeypatch):
    import urllib.request

    monkeypatch.setattr(
        urllib.request, 'urlopen', lambda *a, **kw: pytest.fail('packaging must be offline')
    )
    path = package(prepared)
    manifest = inspect_zip(path)
    assert manifest['mechanics'] == []
    assert manifest['modules']['augments']['state'] == 'absent'
    target = tmp_path / 'unpacked'
    extract_package(path, target, manifest)
    report = validate_data(target, manifest)
    assert report['counts']['champions'] == 1
    assert report['images'] == 1


@pytest.mark.parametrize(
    'name',
    [
        '../escape.json',
        '/root.json',
        'data\\escape.json',
        'assets/CON.png',
        'data/foo/../escape.json',
        'data/x.js',
        'assets/nested.zip',
    ],
)
def test_unsafe_zip_paths_and_code_are_rejected(prepared, tmp_path, name):
    path = package(prepared)
    bad = tmp_path / 'bad.zip'
    bad.write_bytes(rewrite_zip(path, extra=(name, b'{}')))
    with pytest.raises(PackageError):
        inspect_zip(bad)


def test_duplicate_and_symlink_rejected(prepared, tmp_path):
    path = package(prepared)
    bad = tmp_path / 'bad.zip'
    with pytest.warns(UserWarning):
        bad.write_bytes(rewrite_zip(path, extra=('manifest.json', b'{}')))
    with pytest.raises(PackageError):
        inspect_zip(bad)
    link = zipfile.ZipInfo('assets/link.png')
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    bad.write_bytes(rewrite_zip(path, extra=(link, b'/etc/passwd')))
    with pytest.raises(PackageError):
        inspect_zip(bad)


def test_unsupported_capability_and_manifest_duplicate_keys(prepared, tmp_path):
    path = package(prepared)
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read('manifest.json'))
    manifest['required_capabilities'].append('simulator.arbitrary_script.v1')
    bad = tmp_path / 'bad.zip'
    bad.write_bytes(rewrite_zip(path, {'manifest.json': json.dumps(manifest).encode()}))
    with pytest.raises(PackageError, match='能力'):
        inspect_zip(bad)
    bad.write_bytes(rewrite_zip(path, {'manifest.json': b'{"x":1,"x":2}'}))
    with pytest.raises(PackageError, match='重复'):
        inspect_zip(bad)


def test_builder_rejects_inconsistent_index_and_missing_image(prepared):
    index = json.loads((prepared / 'index.json').read_text('utf8'))
    index['champions'][0]['name'] = '伪造紧凑名称'
    dump(prepared / 'index.json', index)
    with pytest.raises(PackageError, match='不一致'):
        package(prepared)
    index['champions'][0]['name'] = '测试弈子'
    dump(prepared / 'index.json', index)
    (prepared / 'assets/icon.png').unlink()
    with pytest.raises(PackageError, match='缺少资源'):
        package(prepared)


@pytest.mark.parametrize('presentation', ['cards.v1', 'variants.v1', 'stages.v1', 'table.v1'])
def test_generic_mechanics_and_supplement_provenance(prepared, presentation):
    index = json.loads((prepared / 'index.json').read_text('utf8'))
    data = {'rounds': ['2-1'], 'requires': ['拥有测试弈子']}
    if presentation in ('variants.v1', 'stages.v1'):
        data[presentation.split('.')[0]] = [
            {'label': '阶段一', 'effect': '测试效果', 'cost': 2, 'requirements': ['条件']}
        ]
    if presentation == 'table.v1':
        data.update(columns=['等级', '奖励'], rows=[[1, '金币']])
    index['mechanics'] = [
        {
            'id': 'new-play',
            'kind': 'future',
            'display_name': '新赛季玩法',
            'presentation': presentation,
            'entries': [
                {
                    'id': 'play1',
                    'name': '玩法记录',
                    'image': 'assets/icon.png',
                    'description': '说明',
                    'data': data,
                }
            ],
        }
    ]
    dump(prepared / 'index.json', index)
    path = package(prepared)
    manifest = inspect_zip(path)
    target = prepared.parent / 'extracted'
    extract_package(path, target, manifest)
    report = validate_data(target, manifest)
    assert report['inherited_count'] == 2
    assert report['warnings']
    assert manifest['mechanics'][0]['kind'] == 'future'


def test_upload_permissions_csrf_dedup_and_size(manager, app, prepared):
    client, headers = manager
    guest = app.test_client()
    assert guest.get('/api/admin/season-packages').status_code == 401
    assert client.post('/api/admin/season-packages').status_code == 403
    path = package(prepared)
    first = upload(manager, path)
    assert first.status_code == 202
    second = upload(manager, path)
    assert second.status_code == 200 and second.json['reused']
    assert second.json['package']['id'] == first.json['package']['id']
    app.config['SEASON_PACKAGE_MAX_BYTES'] = 10
    assert upload(manager, path).status_code == 400
    assert len(list((Path(app.config['SEASON_PACKAGE_ROOT']) / 'uploads').glob('*.zip'))) == 1


def test_publish_preview_conflict_rollback_and_visibility(manager, app, prepared):
    client, headers = manager
    guest = app.test_client()
    rid = upload(manager, package(prepared)).json['package']['id']
    ready = work(app, rid)
    assert ready['state'] == 'ready', ready['job']
    assert guest.get(ready['preview_url']).status_code == 401
    assert guest.get(f'/season-assets/{rid}/data/index.json').status_code == 404
    preview = client.get(ready['preview_url'])
    assert preview.status_code == 200
    assert preview.headers['Cache-Control'] == 'private, no-store'
    assert preview.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert rid in preview.text
    before = guest.get('/api/season-catalog?surface=library').json
    assert next(s for s in before['seasons'] if s['season_id'] == 's18')['release_id'] is None
    assert (
        client.post(
            f'/api/admin/season-packages/{rid}/publish',
            headers=headers,
            json={'expected_revision': 99},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f'/api/admin/season-packages/{rid}/publish',
            headers=headers,
            json={'expected_revision': 0},
        ).status_code
        == 400
    )
    published = client.post(
        f'/api/admin/season-packages/{rid}/publish',
        headers=headers,
        json={'expected_revision': 0, 'acknowledge_warnings': True},
    )
    assert published.status_code == 200, published.json
    assert guest.get(f'/season-assets/{rid}/data/index.json').status_code == 200
    after = guest.get('/api/season-catalog?surface=simulator').json
    season = next(s for s in after['seasons'] if s['season_id'] == 's18')
    assert season['game_version'] == '18.18.3' and rid in season['data_root']
    assert guest.get('/tools/seasons/s18/champions/100').status_code == 200
    assert guest.get(f'/season-assets/{rid}/provenance.json').status_code == 404
    rollback = client.post(
        '/api/admin/seasons/s18/rollback', headers=headers, json={'expected_revision': 1}
    )
    assert rollback.status_code == 200, rollback.json
    assert rollback.json['active']['release_id'] is None
    assert guest.get('/tools/seasons/s18/champions/100').status_code == 404
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) AS n FROM visit_events').fetchone()['n'] == 0


def test_failed_hash_cancel_retry_and_lease_recovery(manager, app, prepared):
    rid = upload(manager, package(prepared)).json['package']['id']
    client, headers = manager
    assert (
        client.post(
            f'/api/admin/season-packages/{rid}/cancel', headers=headers, json={}
        ).status_code
        == 200
    )
    assert work(app, rid)['job']['status'] == 'cancelled'
    assert (
        client.post(f'/api/admin/season-packages/{rid}/retry', headers=headers, json={}).status_code
        == 200
    )
    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE season_import_jobs SET status='running',heartbeat_at='2000-01-01 00:00:00',lease_token='expired' WHERE id=?",
            (rid,),
        )
        db.commit()
    assert work(app, rid)['state'] == 'ready'
    rid2 = upload(manager, package(prepared, 'two', 2)).json['package']['id']
    path = Path(app.config['SEASON_PACKAGE_ROOT']) / 'uploads' / f'{rid2}.zip'
    with zipfile.ZipFile(path) as z:
        raw = z.read('data/items.json')
    path.write_bytes(rewrite_zip(path, {'data/items.json': raw.replace(b'it1', b'it2')}))
    assert work(app, rid2)['state'] == 'rejected'
    with app.app_context():
        assert active_state('s18')['release_id'] is None


def test_failed_publication_restores_baseline(manager, app, prepared, monkeypatch):
    import season_package_service as service

    client, headers = manager
    rid = upload(manager, package(prepared)).json['package']['id']
    work(app, rid)
    monkeypatch.setattr(
        service, '_smoke', lambda *a: (_ for _ in ()).throw(PackageError('smoke failed'))
    )
    response = client.post(
        f'/api/admin/season-packages/{rid}/publish',
        headers=headers,
        json={'expected_revision': 0, 'acknowledge_warnings': True},
    )
    assert response.status_code == 400 and '已恢复旧版本' in response.json['error']
    with app.app_context():
        assert active_state('s18')['release_id'] is None
        assert active_state('s18')['revision'] == 2


def test_compared_revision_must_be_refreshed(manager, app, prepared):
    client, headers = manager
    first = upload(manager, package(prepared)).json['package']['id']
    work(app, first)
    second = upload(manager, package(prepared, 'two', 2)).json['package']['id']
    work(app, second)
    assert (
        client.post(
            f'/api/admin/season-packages/{first}/publish',
            headers=headers,
            json={'expected_revision': 0, 'acknowledge_warnings': True},
        ).status_code
        == 200
    )
    stale = client.post(
        f'/api/admin/season-packages/{second}/publish',
        headers=headers,
        json={'expected_revision': 1, 'acknowledge_warnings': True},
    )
    assert stale.status_code == 400 and '过期' in stale.json['error']
    assert (
        client.post(
            f'/api/admin/season-packages/{second}/compare', headers=headers, json={}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f'/api/admin/season-packages/{second}/publish',
            headers=headers,
            json={'expected_revision': 1, 'acknowledge_warnings': True},
        ).status_code
        == 200
    )


def test_preview_hidden_season_stays_private_and_cannot_write(manager, app, prepared):
    client, headers = manager
    rid = upload(manager, package(prepared)).json['package']['id']
    work(app, rid)
    from season_visibility import load_policy, save_policy

    with app.app_context():
        policy = load_policy()
        for surface in ('library', 'simulator'):
            policy[surface]['s18']['status'] = 'hidden'
        save_policy(policy)
    assert app.test_client().get('/tools/seasons/s18').status_code == 404
    assert client.get(f'/tools/seasons/s18?preview_release={rid}').status_code == 200
    catalog = client.get(f'/api/season-catalog?surface=simulator&preview_release={rid}').json
    assert catalog['default_season_id'] == 's18'
    assert next(s for s in catalog['seasons'] if s['season_id'] == 's18')['release_id'] == rid
    blocked = client.post(
        f'/api/admin/season-packages/{rid}/compare?preview_release={rid}', headers=headers, json={}
    )
    assert blocked.status_code == 400


def test_tampered_ready_resource_blocks_publication(manager, app, prepared):
    client, headers = manager
    rid = upload(manager, package(prepared)).json['package']['id']
    work(app, rid)
    path = Path(app.config['SEASON_PACKAGE_ROOT']) / 'releases' / rid / 'assets/icon.png'
    path.write_bytes(b'broken')
    response = client.post(
        f'/api/admin/season-packages/{rid}/publish',
        headers=headers,
        json={'expected_revision': 0, 'acknowledge_warnings': True},
    )
    assert response.status_code == 400 and '文件缺失或改变' in response.json['error']
    with app.app_context():
        assert active_state('s18')['revision'] == 0


def test_lost_worker_lease_cannot_finalize(manager, app, prepared, monkeypatch):
    import season_package_service as service

    rid = upload(manager, package(prepared)).json['package']['id']
    validate = service.validate_data

    def stolen(*args):
        result = validate(*args)
        get_db().execute(
            "UPDATE season_import_jobs SET lease_token='new-owner' WHERE release_id=?", (rid,)
        )
        get_db().commit()
        return result

    monkeypatch.setattr(service, 'validate_data', stolen)
    result = work(app, rid)
    assert result['job']['status'] == 'running'
    assert result['state'] == 'validating'
    assert not (Path(app.config['SEASON_PACKAGE_ROOT']) / 'releases' / rid).exists()


def test_recover_interrupted_publication(manager, app, prepared):
    from season_package_service import recover_publications

    rid = upload(manager, package(prepared)).json['package']['id']
    work(app, rid)
    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE season_release_packages SET published_at='2000-01-01 00:00:00' WHERE id=?",
            (rid,),
        )
        db.execute(
            "INSERT INTO season_active_releases(season_id,release_id,revision,updated_at) VALUES ('s18',?,1,'2000-01-01 00:00:00')",
            (rid,),
        )
        db.execute(
            """INSERT INTO season_release_events(id,season_id,release_id,action,status,detail_json,created_at)
            VALUES ('interrupted','s18',?,'publish','verifying','{"revision":1}','2000-01-01 00:00:00')""",
            (rid,),
        )
        db.commit()
        recover_publications()
        assert (
            db.execute(
                "SELECT status FROM season_release_events WHERE id='interrupted'"
            ).fetchone()['status']
            == 'completed'
        )
        assert active_state('s18')['release_id'] == rid


def test_same_patch_revision_cannot_be_reused_with_other_package_id(manager, prepared):
    assert upload(manager, package(prepared)).status_code == 202
    path = prepared.parent / 'renamed.zip'
    build_package(
        prepared, path, 1, {'title': '新版', 'sections': []}, package_id='renamed-package'
    )
    assert upload(manager, path).status_code == 400


@pytest.mark.parametrize('raw', [b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}'])
def test_nonfinite_json_is_rejected(raw):
    from season_package_format import parse_json

    with pytest.raises(PackageError):
        parse_json(raw)


def test_image_changes_are_in_review_diff(prepared, tmp_path):
    from season_package_format import structural_diff

    first = package(prepared)
    before = tmp_path / 'before'
    extract_package(first, before, inspect_zip(first))
    Image.new('RGB', (8, 8), 'red').save(prepared / 'assets/icon.png')
    after = tmp_path / 'after'
    second = package(prepared, 'two', 2)
    extract_package(second, after, inspect_zip(second))
    diff = structural_diff(before / 'data', after / 'data')
    assert diff['assets']['changed'] == ['icon.png']
    assert not diff['champions']['changed']
