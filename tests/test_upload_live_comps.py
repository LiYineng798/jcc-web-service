import io
import json
from pathlib import Path
from urllib.error import HTTPError

from scripts.local import upload_live_comps


def sample_payload():
    return {
        'meta': {'source': 'script-test'},
        'tiers': {
            'S': [{'id': 's1', 'title': 'S1', 'tier': 'S', 'jccCode': '#S1', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'A': [],
            'B': [],
            'C': [],
            'D': [],
        },
    }


def test_upload_payload_posts_json_with_token(tmp_path):
    payload_path = tmp_path / 'payload.json'
    payload_path.write_text(json.dumps(sample_payload(), ensure_ascii=False), encoding='utf-8')
    captured = {}

    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok": true, "total": 1}'

    def fake_opener(request, timeout=30):
        captured['url'] = request.full_url
        captured['method'] = request.get_method()
        captured['body'] = request.data.decode('utf-8')
        captured['token'] = request.get_header('X-upload-token')
        return DummyResponse()

    result = upload_live_comps.upload_payload(
        file_path=str(payload_path),
        url='https://example.com/api/live-comps/upload',
        token='upload-secret',
        opener=fake_opener,
    )

    assert captured['url'] == 'https://example.com/api/live-comps/upload'
    assert captured['method'] == 'POST'
    assert captured['token'] == 'upload-secret'
    assert json.loads(captured['body'])['meta']['source'] == 'script-test'
    assert json.loads(result)['ok'] is True


def test_main_returns_one_and_prints_error_when_upload_fails(tmp_path, capsys):
    payload_path = tmp_path / 'payload.json'
    payload_path.write_text(json.dumps(sample_payload(), ensure_ascii=False), encoding='utf-8')

    def failing_opener(request, timeout=30):
        raise HTTPError(
            url=request.full_url,
            code=401,
            msg='Unauthorized',
            hdrs=None,
            fp=io.BytesIO(b'{"error":"bad token"}'),
        )

    exit_code = upload_live_comps.main([
        '--file', str(payload_path),
        '--url', 'https://example.com/api/live-comps/upload',
        '--token', 'wrong-token',
    ], opener=failing_opener)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert 'upload failed' in captured.err
