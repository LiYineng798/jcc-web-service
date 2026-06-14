import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path('scripts/convert_and_upload_s16_live_comps.py')


def load_module():
    spec = importlib.util.spec_from_file_location('convert_and_upload_s16_live_comps', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_convert_and_upload_writes_json_and_calls_uploader(tmp_path):
    module = load_module()
    raw_path = tmp_path / 'datatft_s16_raw.json'
    output_path = tmp_path / 'team_codes_by_tier.s16.json'
    raw_path.write_text(json.dumps({
        'data': {
            'list': [{
                'id': 16001,
                'title': '暗影岛佛爷',
                'tier': 'B',
                'heroId': '916234',
                'score': 266.0,
                'strategyId': 16001,
                'tags': ['速升8级'],
                'heros': [{'id': '916234'}, {'id': '916083'}],
            }],
        },
    }, ensure_ascii=False), encoding='utf-8')
    calls = {}

    def fake_upload(file_path, url, token, timeout=180, season_id='', opener=None):
        calls['file_path'] = file_path
        calls['url'] = url
        calls['token'] = token
        calls['timeout'] = timeout
        calls['season_id'] = season_id
        payload = json.loads(Path(file_path).read_text(encoding='utf-8'))
        assert payload['tiers']['B'][0]['jccCode'] == ''
        return '{"ok": true}'

    exit_code = module.main([
        '--input', str(raw_path),
        '--output', str(output_path),
        '--url', 'https://example.com/api/live-comps/upload',
        '--token', 'secret-token',
    ], upload_func=fake_upload)

    assert exit_code == 0
    assert output_path.exists()
    assert calls == {
        'file_path': str(output_path),
        'url': 'https://example.com/api/live-comps/upload',
        'token': 'secret-token',
        'timeout': 180,
        'season_id': 's16-legends',
    }

