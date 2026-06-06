import json

from scripts.local import refresh_live_comps


def payload_with_items(items_by_tier):
    tiers = {'S': [], 'A': [], 'B': [], 'C': [], 'D': []}
    for tier, items in items_by_tier.items():
        tiers[tier] = items
    return {'tiers': tiers}


def test_refresh_runs_fetch_script_then_uploads_generated_json(tmp_path):
    output_path = tmp_path / 'team_codes_by_tier.verify.json'
    calls = {}
    output_path.write_text(json.dumps(payload_with_items({
        'S': [{'id': 'old', 'title': '旧阵容', 'tier': 'S', 'jccCode': '#OLD'}],
    })), encoding='utf-8')

    def fake_runner(command, cwd=None, check=False):
        calls['command'] = command
        calls['cwd'] = cwd
        calls['check'] = check
        output_path.write_text(json.dumps(payload_with_items({
            'S': [{
                'id': 'new',
                'title': '新阵容',
                'tier': 'S',
                'jccCode': '#NEW',
                'mainAvatar': 'https://static.datatft.com/a.jpg',
                'heroImages': ['https://static.datatft.com/b.jpg'],
            }],
        }), ensure_ascii=False), encoding='utf-8')

    class DummyResponse:
        def __init__(self, body=b'{"ok": true}'):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self.body

    def fake_opener(request, timeout=180):
        calls.setdefault('urls', []).append(request.full_url)
        calls.setdefault('tokens', []).append(request.get_header('X-upload-token'))
        calls.setdefault('timeouts', []).append(timeout)
        if request.full_url.endswith('/api/live-comps/assets/upload'):
            body = json.loads(request.data.decode('utf-8'))
            return DummyResponse(json.dumps({'ok': True, 'url': f"/api/live-comps/assets/{body['filename']}"}).encode('utf-8'))
        return DummyResponse()

    exit_code = refresh_live_comps.main([
        '--fetch-script', 'fetch.py',
        '--output', str(output_path),
        '--url', 'https://example.com/api/live-comps/upload',
        '--token', 'upload-token',
        '--upload-timeout', '240',
    ], runner=fake_runner, opener=fake_opener)

    assert exit_code == 0
    assert 'fetch.py' in calls['command']
    assert '--output' in calls['command']
    assert calls['urls'][-1] == 'https://example.com/api/live-comps/upload'
    assert calls['tokens'][-1] == 'upload-token'
    assert calls['timeouts'][-1] == 240


def test_precache_images_uploads_assets_and_rewrites_payload_urls():
    payload = payload_with_items({
        'S': [{
            'id': 'image',
            'title': '图片阵容',
            'tier': 'S',
            'jccCode': '#IMAGE',
            'mainAvatar': 'https://static.datatft.com/main.jpg',
            'heroImages': ['https://static.datatft.com/hero.png'],
        }],
    })
    args = refresh_live_comps.parse_args([
        '--token', 'token',
        '--url', 'https://example.com/api/live-comps/upload',
    ])

    class ImageResponse:
        headers = {'Content-Type': 'image/jpeg'}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'image-bytes'

    class UploadResponse:
        headers = {}

        def __init__(self, request):
            self.request = request

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            body = json.loads(self.request.data.decode('utf-8'))
            return json.dumps({'ok': True, 'url': f"/api/live-comps/assets/{body['filename']}"}).encode('utf-8')

    def fake_opener(request, timeout=20):
        if request.full_url.startswith('https://static.datatft.com'):
            return ImageResponse()
        return UploadResponse(request)

    rewritten, count = refresh_live_comps.precache_images(payload, args, opener=fake_opener)
    item = rewritten['tiers']['S'][0]

    assert count == 2
    assert item['mainAvatar'].startswith('/api/live-comps/assets/')
    assert item['heroImages'][0].startswith('/api/live-comps/assets/')


def test_compare_payloads_reports_added_removed_and_changed_items():
    old_payload = payload_with_items({
        'S': [
            {'id': 'keep', 'title': '旧名', 'tier': 'S', 'heroId': '1', 'jccCode': '#SAME'},
            {'id': 'code', 'title': '阵容码旧', 'tier': 'S', 'heroId': '2', 'jccCode': '#OLD'},
            {'id': 'gone', 'title': '移除', 'tier': 'S', 'heroId': '3', 'jccCode': '#GONE'},
        ],
    })
    new_payload = payload_with_items({
        'A': [
            {'id': 'keep', 'title': '新名', 'tier': 'A', 'heroId': '1', 'jccCode': '#SAME'},
            {'id': 'code', 'title': '阵容码旧', 'tier': 'S', 'heroId': '2', 'jccCode': '#NEW'},
            {'id': 'add', 'title': '新增', 'tier': 'A', 'heroId': '4', 'jccCode': '#ADD'},
        ],
    })

    diff = refresh_live_comps.compare_payloads(old_payload, new_payload)
    summary = refresh_live_comps.format_diff_summary(diff)

    assert [item['id'] for item in diff['added']] == ['add']
    assert [item['id'] for item in diff['removed']] == ['gone']
    assert diff['code_changed'][0]['before']['id'] == 'code'
    assert diff['info_changed'][0]['before']['id'] == 'keep'
    assert '新增阵容：1' in summary
    assert '阵容码变化：1' in summary
    assert '名称/段位变化：1' in summary


def test_refresh_requires_upload_token(tmp_path):
    output_path = tmp_path / 'team_codes_by_tier.verify.json'
    output_path.write_text('{}', encoding='utf-8')

    exit_code = refresh_live_comps.main([
        '--skip-fetch',
        '--output', str(output_path),
        '--token', '',
    ])

    assert exit_code == 1
