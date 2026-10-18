import json
from pathlib import Path

from test_auth import register_user
from test_lineup_permissions import create_lineup


def test_detail_uses_dynamic_lineup_season_name_and_keeps_complete_code(client):
    manifest_path = Path(client.application.config['LIVE_COMPS_SEASON_MANIFEST_PATH'])
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['seasons'].append({
        'id': 's18-preview', 'name': '新赛季 · 示例', 'status': 'active',
        'order': 10, 'data_file': 's18-preview.json',
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    register_user(client, username='detailowner', email='detailowner@example.com')
    code = '#COMPLETE' + '0123456789' * 20
    response = create_lineup(client, name='新赛季阵容', code=code, season_id='s18-preview')
    assert response.status_code == 201
    lineup_id = response.get_json()['id']
    owner_html = client.get(f'/lineup/{lineup_id}').get_data(as_text=True)
    assert f'href="/lineup/{lineup_id}/edit"' in owner_html
    client.post('/api/logout')
    html = client.get(f'/lineup/{lineup_id}').get_data(as_text=True)
    assert '新赛季 · 示例' in html
    assert 's18-preview' not in html
    assert code in html
    assert f'href="/lineup/{lineup_id}/edit"' not in html
