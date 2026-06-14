# Live Comps Phase 2 Upload And Uploader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为实时阵容 JSON 增加独立上传接口和本地上传脚本，支持整包覆盖、旧文件备份和上传鉴权。

**Architecture:** 继续沿用 Phase 1 的文件型内容源。上传接口只接受完整 JSON，通过 `X-Upload-Token` 鉴权，先写临时文件，再备份旧文件并原子替换正式文件；本地通过一个独立 Python CLI 脚本上传。

**Tech Stack:** Flask, pathlib/shutil/json, pytest, Python standard library `argparse` + `urllib.request`

---

### Task 1: 为上传接口补齐失败测试

**Files:**
- Modify: `tests/test_live_comps.py`

- [ ] **Step 1: 先写上传鉴权与覆盖行为的失败测试**

```python
import json
from pathlib import Path


def test_live_comps_upload_requires_valid_token(client):
    response = client.post('/api/live-comps/upload', json={'tiers': {}})
    assert response.status_code == 401
    assert response.get_json()['error'] == '上传令牌无效'


def test_live_comps_upload_replaces_data_and_keeps_previous_backup(client):
    old_payload = {
        'meta': {'source': 'old'},
        'tiers': {
            'S': [{'id': 'old-s', 'title': '旧 S', 'tier': 'S', 'jccCode': '#OLD001', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'A': [], 'B': [], 'C': [], 'D': [],
        },
    }
    new_payload = {
        'meta': {'source': 'new'},
        'tiers': {
            'S': [{'id': 'new-s', 'title': '新 S', 'tier': 'S', 'jccCode': '#NEW001', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'A': [], 'B': [], 'C': [], 'D': [],
        },
    }
    data_path = Path(client.application.config['LIVE_COMPS_DATA_PATH'])
    backup_path = Path(client.application.config['LIVE_COMPS_BACKUP_PATH'])
    data_path.write_text(json.dumps(old_payload, ensure_ascii=False), encoding='utf-8')

    response = client.post(
        '/api/live-comps/upload',
        json=new_payload,
        headers={'X-Upload-Token': 'upload-secret'},
    )

    assert response.status_code == 200
    assert response.get_json()['ok'] is True
    assert json.loads(data_path.read_text(encoding='utf-8'))['meta']['source'] == 'new'
    assert json.loads(backup_path.read_text(encoding='utf-8'))['meta']['source'] == 'old'
```

- [ ] **Step 2: 运行测试，确认上传接口尚未实现**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -q -p no:cacheprovider`
Expected: FAIL，因为 `POST /api/live-comps/upload` 尚不存在。

- [ ] **Step 3: 再补一条结构校验失败测试**

```python
def test_live_comps_upload_rejects_invalid_payload_without_overwriting_existing_data(client):
    original = {
        'meta': {'source': 'safe'},
        'tiers': {
            'S': [{'id': 'safe-s', 'title': '保留 S', 'tier': 'S', 'jccCode': '#SAFE001', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'A': [], 'B': [], 'C': [], 'D': [],
        },
    }
    data_path = Path(client.application.config['LIVE_COMPS_DATA_PATH'])
    data_path.write_text(json.dumps(original, ensure_ascii=False), encoding='utf-8')

    response = client.post(
        '/api/live-comps/upload',
        json={'meta': {'source': 'broken'}, 'tiers': {'S': 'bad'}},
        headers={'X-Upload-Token': 'upload-secret'},
    )

    assert response.status_code == 400
    assert 'S 段位必须是数组' in response.get_json()['error']
    assert json.loads(data_path.read_text(encoding='utf-8'))['meta']['source'] == 'safe'


def test_live_comps_upload_rejects_oversized_request(client):
    client.application.config['LIVE_COMPS_MAX_UPLOAD_BYTES'] = 20
    response = client.post(
        '/api/live-comps/upload',
        data='x' * 21,
        headers={
            'Content-Type': 'application/json',
            'X-Upload-Token': 'upload-secret',
        },
    )
    assert response.status_code == 413
    assert response.get_json()['error'] == '上传文件过大'
```

- [ ] **Step 4: 重新运行测试，固定失败面**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -q -p no:cacheprovider`
Expected: FAIL，但失败点集中在上传逻辑与文件写入逻辑。

### Task 2: 实现上传鉴权、临时写入、备份与原子替换

**Files:**
- Modify: `live_comps.py`
- Test: `tests/test_live_comps.py`

- [ ] **Step 1: 补充上传结果摘要测试**

```python
def test_live_comps_upload_returns_tier_counts(client):
    payload = {
        'meta': {'source': 'summary-check'},
        'tiers': {
            'S': [{'id': 's1', 'title': 'S1', 'tier': 'S', 'jccCode': '#S1', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'A': [{'id': 'a1', 'title': 'A1', 'tier': 'A', 'jccCode': '#A1', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'B': [], 'C': [], 'D': [],
        },
    }
    response = client.post(
        '/api/live-comps/upload',
        json=payload,
        headers={'X-Upload-Token': 'upload-secret'},
    )
    data = response.get_json()
    assert data['tiers'] == {'S': 1, 'A': 1, 'B': 0, 'C': 0, 'D': 0}
    assert data['total'] == 2
```

- [ ] **Step 2: 运行测试，确认需要实现完整写入流程**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -q -p no:cacheprovider`
Expected: FAIL，因为上传结果摘要与文件替换逻辑未实现。

- [ ] **Step 3: 在 `live_comps.py` 中实现上传令牌校验和原子写入**

```python
import os
import shutil
from pathlib import Path


def require_live_comps_upload_token(request):
    expected = current_app.config.get('LIVE_COMPS_UPLOAD_TOKEN', '')
    provided = request.headers.get('X-Upload-Token', '')
    if not expected or provided != expected:
        return jsonify({'error': '上传令牌无效'}), 401
    return None


def write_live_comps_payload(payload):
    validate_live_comps_payload(payload)
    data_path = Path(current_app.config['LIVE_COMPS_DATA_PATH'])
    backup_path = Path(current_app.config['LIVE_COMPS_BACKUP_PATH'])
    data_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = data_path.with_suffix('.tmp')
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    json.loads(temp_path.read_text(encoding='utf-8'))
    if data_path.exists():
        shutil.copyfile(data_path, backup_path)
    os.replace(temp_path, data_path)


@live_comps_bp.post('/api/live-comps/upload')
def upload_live_comps():
    auth_error = require_live_comps_upload_token(request)
    if auth_error:
        return auth_error
    if (request.content_length or 0) > int(current_app.config['LIVE_COMPS_MAX_UPLOAD_BYTES']):
        return jsonify({'error': '上传文件过大'}), 413
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({'error': '请求体必须是 JSON'}), 400
    try:
        write_live_comps_payload(payload)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    counts = {tier: len(payload['tiers'].get(tier, [])) for tier in TIER_ORDER}
    return jsonify({'ok': True, 'tiers': counts, 'total': sum(counts.values())})
```

- [ ] **Step 4: 重跑测试**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -q -p no:cacheprovider`
Expected: PASS

### Task 3: 新增本地上传脚本

**Files:**
- Create: `upload_live_comps.py`
- Modify: `README.md`

- [ ] **Step 1: 先为脚本写一个最小使用说明**

```markdown
## 实时阵容上传

命令示例：`python upload_live_comps.py --file team_codes_by_tier.verify.json --url https://jcc.np5.top/api/live-comps/upload --token YOUR_UPLOAD_TOKEN`
```

- [ ] **Step 2: 用标准库实现上传脚本，避免引入新依赖**

```python
import argparse
import json
import sys
import urllib.request


def parse_args():
    parser = argparse.ArgumentParser(description='Upload live comps JSON to JCC server.')
    parser.add_argument('--file', required=True, help='Path to team_codes_by_tier.verify.json')
    parser.add_argument('--url', required=True, help='Upload endpoint URL')
    parser.add_argument('--token', required=True, help='Upload token sent via X-Upload-Token')
    return parser.parse_args()


def main():
    args = parse_args()
    with open(args.file, 'r', encoding='utf-8') as file:
        payload = json.load(file)
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        args.url,
        data=body,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'X-Upload-Token': args.token,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode('utf-8')
    print(text)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'upload failed: {exc}', file=sys.stderr)
        raise
```

- [ ] **Step 3: 本地用错误令牌做一次失败验证**

Run: `python D:\1\codex\jcc\claude_project\upload_live_comps.py --file D:\1\codex\jcc\claude_project\实时获取阵容码\阵容码代理获取\team_codes_by_tier.verify.json --url http://127.0.0.1:5000/api/live-comps/upload --token wrong-token`
Expected: 输出 401 或 `upload failed`，说明鉴权生效。

- [ ] **Step 4: 本地用正确令牌做一次成功验证**

Run: `python D:\1\codex\jcc\claude_project\upload_live_comps.py --file D:\1\codex\jcc\claude_project\实时获取阵容码\阵容码代理获取\team_codes_by_tier.verify.json --url http://127.0.0.1:5000/api/live-comps/upload --token upload-secret`
Expected: 输出 `{"ok": true, ...}`，服务端正式文件被覆盖，旧文件进入备份。

### Task 4: Phase 2 验证与同步准备

**Files:**
- Modify: `live_comps.py`
- Modify: `README.md`
- Modify: `tests/test_live_comps.py`
- Create: `upload_live_comps.py`

- [ ] **Step 1: 跑实时阵容完整后端测试**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 2: 手工检查上传后摘要接口**

Run: `curl http://127.0.0.1:5000/api/live-comps/summary`
Expected: 各段位数量与刚上传的 JSON 一致。

- [ ] **Step 3: 如用户确认，再同步到 `jcc_git`**

```bash
robocopy D:\1\codex\jcc\claude_project D:\1\codex\jcc\jcc_git /MIR /XD instance __pycache__ .pytest_cache
git -C D:\1\codex\jcc\jcc_git status --short
```
