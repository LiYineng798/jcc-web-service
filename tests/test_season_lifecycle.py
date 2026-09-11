"""Full existing-data rehearsal of initial registration, update and hotfix."""

import io
import json
import urllib.request

import pytest

from season_lifecycle_support import rehearsal, live_payload, SID
from season_package_service import run_one_job, release_payload
from live_comp_upload_service import _claim_next_job, _process_job
from season_package_format import read_json


def test_full_season_lifecycle_with_existing_s18_assets(tmp_path, monkeypatch):
    monkeypatch.setattr(
        urllib.request, 'urlopen', lambda *a, **kw: pytest.fail('rehearsal must be offline')
    )
    with rehearsal(tmp_path) as env:
        app = env.app
        admin, guest = app.test_client(), app.test_client()
        login = admin.post(
            '/api/login', json={'username': 'previewadmin', 'password': 'Preview1234'}
        )
        assert login.status_code == 200
        headers = {'X-CSRF-Token': login.get_json()['csrf_token']}

        def post(url, data):
            return admin.post(url, json=data, headers=headers)

        def upload(path):
            with path.open('rb') as stream:
                return admin.post(
                    '/api/admin/season-packages',
                    headers=headers,
                    data={'file': (stream, path.name)},
                )

        def ready(path):
            response = upload(path)
            assert response.status_code == 202, response.get_json()
            rid = response.get_json()['package']['id']
            with app.app_context():
                assert run_one_job()
                value = release_payload(rid)
            assert value['state'] == 'ready', value
            return value

        def publish(value, revision):
            response = post(
                f"/api/admin/season-packages/{value['id']}/publish",
                {'expected_revision': revision, 'acknowledge_warnings': True},
            )
            assert response.status_code == 200, response.get_json()
            return response.get_json()['active']

        def set_surface(surface, status):
            response = admin.put(
                f'/api/admin/season-display/{surface}/{SID}',
                headers=headers,
                json={'status': status},
            )
            assert response.status_code == 200, response.get_json()

        def season(surface='library'):
            return next(
                s
                for s in guest.get(f'/api/season-catalog?surface={surface}').get_json()['seasons']
                if s['season_id'] == SID
            )

        before = guest.get('/api/season-catalog').get_json()['seasons'][0]
        # An array entry in live-comps is not a library registration.
        response = post(
            '/api/admin/live-comps/seasons', {'id': SID, 'name': 'S99 演练', 'status': 'hidden'}
        )
        assert response.status_code == 200
        assert post('/api/admin/live-comps/seasons', {'id': SID, 'name': '重复'}).status_code == 400
        assert upload(env.packages[0]).status_code == 400
        assert (
            post(
                '/api/lineups', {'name': '演练', 'code': '#REHEARSALONLY1', 'season_id': SID}
            ).status_code
            == 400
        )
        # Simulate deploying the importer-generated catalog and baseline files.
        env.register()
        assert guest.get(f'/tools/seasons/{SID}').status_code == 404
        assert guest.get(f'/static/season-data/{SID}/index.json').status_code == 404
        for surface in ('library', 'simulator'):
            assert SID not in [
                s['season_id']
                for s in guest.get(f'/api/season-catalog?surface={surface}').get_json()['seasons']
            ]
        assert f'/tools/seasons/{SID}' not in guest.get('/sitemap.xml').get_data(as_text=True)
        initial = ready(env.packages[0])
        preview = initial['preview_url']
        assert admin.get(preview).status_code == 200
        assert guest.get(preview).status_code == 401
        assert admin.get(preview).headers['Cache-Control'] == 'private, no-store'
        assert guest.get(f"/season-assets/{initial['id']}/data/champions.json").status_code == 404
        publish(initial, 0)
        assert guest.get(f'/tools/seasons/{SID}').status_code == 404
        assert upload(env.packages[0]).get_json()['reused'] is True
        set_surface('library', 'active')
        assert season()['release_id'] == initial['id']
        assert SID not in [
            s['season_id']
            for s in guest.get('/api/season-catalog?surface=simulator').get_json()['seasons']
        ]
        set_surface('simulator', 'active')
        assert (
            admin.put(
                f'/api/admin/season-display/simulator/{SID}',
                headers=headers,
                json={'is_default': True},
            ).status_code
            == 200
        )
        assert (
            guest.get('/api/season-catalog?surface=simulator').get_json()['default_season_id']
            == SID
        )
        assert f'/tools/seasons/{SID}' in guest.get('/').get_data(as_text=True)
        assert f'/tools/seasons/{SID}' in guest.get('/sitemap.xml').get_data(as_text=True)

        # Use the real administrator JSON preview/start/worker path for rankings.
        response = admin.post(
            '/api/admin/live-comps/uploads/preview',
            headers=headers,
            data={
                'season_id': SID,
                'file': (io.BytesIO(json.dumps(live_payload()).encode()), 'live.json'),
            },
        )
        assert response.status_code == 201, response.get_json()
        jid = response.get_json()['job_id']
        assert post(f'/api/admin/live-comps/uploads/{jid}/start', {}).status_code == 200
        with app.app_context():
            job = _claim_next_job()
            assert job['id'] == jid
            _process_job(app, job)
        assert admin.get(f'/api/admin/live-comps/uploads/{jid}').get_json()['status'] == 'completed'
        assert guest.get(f'/api/live-comps?season={SID}').status_code == 404
        assert (
            admin.put(
                f'/api/admin/live-comps/seasons/{SID}',
                headers=headers,
                json={'status': 'active', 'default_season_id': SID},
            ).status_code
            == 200
        )
        assert SID in [s['id'] for s in guest.get('/api/lineup-seasons').get_json()['seasons']]
        normal = post(
            '/api/lineups', {'name': '演练普通阵容', 'code': '#REHEARSALONLY1', 'season_id': SID}
        )
        assert normal.status_code == 201
        normal = normal.get_json()
        details_url = f'/api/live-comps/rehearsal/details?season={SID}'
        assert guest.get(details_url).get_json()['season_data_id'] == SID
        assert guest.get('/api/live-comps/assets/rehearsal.webp').status_code == 200

        update = ready(env.packages[1])
        assert update['report']['diff']['champions']['added'][0]['id'] == 'rehearsalbonus'
        assert len(update['report']['diff']['mechanics']['added']) == 2
        assert 'rehearsalbonus' not in guest.get('/sitemap.xml').get_data(as_text=True)
        assert (
            admin.get(
                f"/tools/seasons/{SID}/champions/rehearsalbonus?preview_release={update['id']}"
            ).status_code
            == 200
        )
        assert season()['release_id'] == initial['id']
        publish(update, 1)
        assert season()['release_id'] == season('simulator')['release_id'] == update['id']
        assert 'rehearsalbonus' in guest.get('/sitemap.xml').get_data(as_text=True)
        assert guest.get(f'/tools/seasons/{SID}/champions/rehearsalbonus').status_code == 200

        hotfix = ready(env.packages[2])
        assert hotfix['game_version'] == update['game_version']
        assert hotfix['data_revision'] == 2
        assert hotfix['report']['diff']['mechanics']['removed'] == ['rehearsal-table']
        assert hotfix['report']['warnings']
        conflict = post(
            f"/api/admin/season-packages/{hotfix['id']}/publish", {'expected_revision': 1}
        )
        assert conflict.status_code == 409
        publish(hotfix, 2)
        index = guest.get(season()['data_root'] + '/index.json').get_json()
        assert index['champions'][0]['name'] == '演练弈子补丁2'
        assert [m['id'] for m in index['mechanics']] == ['rehearsal-reward']
        assert season('simulator')['release_id'] == hotfix['id']
        # Data publication never rewrites game codes or their chosen classification.
        assert guest.get(f"/api/lineups/{normal['id']}").get_json()['code'] == normal['code']
        assert guest.get(details_url).get_json()['season_data_id'] == SID
        assert (
            guest.post(f'/api/live-comps/rehearsal/copy?season={SID}', json={}).status_code == 200
        )
        response = post(
            f'/api/admin/seasons/{SID}/rollback',
            {'expected_revision': 3, 'release_id': initial['id']},
        )
        assert response.status_code == 200, response.get_json()
        assert season()['release_id'] == initial['id']
        assert 'rehearsalbonus' not in guest.get('/sitemap.xml').get_data(as_text=True)
        assert guest.get(f'/tools/seasons/{SID}/champions/rehearsalbonus').status_code == 404
        assert guest.get(season()['data_root'] + '/index.json').get_json()['mechanics'] == []
        set_surface('library', 'hidden')
        set_surface('simulator', 'hidden')
        assert f'/tools/seasons/{SID}' not in guest.get('/sitemap.xml').get_data(as_text=True)
        assert guest.get(f"/season-assets/{initial['id']}/data/index.json").status_code == 404
        after = guest.get('/api/season-catalog').get_json()['seasons'][0]
        assert {k: v for k, v in after.items() if k != 'order'} == {
            k: v for k, v in before.items() if k != 'order'
        }
        assert read_json(env.library / 's18/index.json')['game_version'] == before['game_version']
