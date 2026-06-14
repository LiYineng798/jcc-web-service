# Live Comps Phase 1 Read API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为首页“实时阵容排行”新增独立的文件型数据源和只读接口，支持摘要查询与按段位分页查询。

**Architecture:** 不改现有 `lineups` 数据表，也不把实时阵容混进普通阵容接口。新增 `live_comps.py` Blueprint，直接读取 `instance/live-comps.json`，对外暴露 `/api/live-comps/summary` 和 `/api/live-comps` 两个只读接口。

**Tech Stack:** Flask, JSON file storage, pytest, vanilla JavaScript-compatible API shape

---

### Task 1: 补齐配置项与只读测试基线

**Files:**
- Modify: `config.py`
- Modify: `tests/conftest.py`
- Create: `tests/test_live_comps.py`

- [ ] **Step 1: 先写缺失文件与分页接口的失败测试**

```python
import json
from pathlib import Path


def sample_live_comps_payload():
    return {
        'meta': {'source': 'unit-test'},
        'tiers': {
            'S': [
                {
                    'id': f's-{index:02d}',
                    'title': f'S 阵容 {index}',
                    'tier': 'S',
                    'jccCode': f'#SCODE{index:02d}',
                    'mainAvatar': f'https://example.com/s-{index}.png',
                    'heroImages': [f'https://example.com/s-{index}-1.png'],
                }
                for index in range(1, 7)
            ],
            'A': [],
            'B': [],
            'C': [],
            'D': [],
        },
    }


def write_live_comps_seed(client, payload):
    data_path = Path(client.application.config['LIVE_COMPS_DATA_PATH'])
    data_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def test_live_comps_summary_returns_empty_totals_when_file_missing(client):
    data = client.get('/api/live-comps/summary').get_json()
    assert data['tiers'] == [
        {'tier': 'S', 'total': 0},
        {'tier': 'A', 'total': 0},
        {'tier': 'B', 'total': 0},
        {'tier': 'C', 'total': 0},
        {'tier': 'D', 'total': 0},
    ]
    assert data['updated_at'] is None


def test_live_comps_list_returns_second_page_for_single_tier(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    data = client.get('/api/live-comps?tier=S&page=2').get_json()
    assert data['tier'] == 'S'
    assert data['page'] == 2
    assert data['page_size'] == 5
    assert data['total'] == 6
    assert data['total_pages'] == 2
    assert [item['id'] for item in data['items']] == ['s-06']
```

- [ ] **Step 2: 运行测试，确认接口当前尚不存在**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -q -p no:cacheprovider`
Expected: FAIL，因为 `live-comps` 接口与测试专用配置项还没有实现。

- [ ] **Step 3: 在应用配置和测试夹具中补齐实时阵容配置**

```python
app.config.from_mapping(
    LIVE_COMPS_DATA_PATH=os.path.join(app.instance_path, 'live-comps.json'),
    LIVE_COMPS_BACKUP_PATH=os.path.join(app.instance_path, 'live-comps.previous.json'),
    LIVE_COMPS_PAGE_SIZE=5,
    LIVE_COMPS_MAX_UPLOAD_BYTES=5 * 1024 * 1024,
    LIVE_COMPS_UPLOAD_TOKEN=os.environ.get('JCC_LIVE_COMPS_UPLOAD_TOKEN', ''),
)
```

```python
live_comps_path = ROOT / 'test-live-comps.json'
live_comps_backup_path = ROOT / 'test-live-comps.previous.json'
for path in [db_path, live_comps_path, live_comps_backup_path]:
    if path.exists():
        path.unlink()

app = create_app({
    'TESTING': True,
    'DATABASE': str(db_path),
    'LIVE_COMPS_DATA_PATH': str(live_comps_path),
    'LIVE_COMPS_BACKUP_PATH': str(live_comps_backup_path),
    'LIVE_COMPS_PAGE_SIZE': 5,
    'LIVE_COMPS_UPLOAD_TOKEN': 'upload-secret',
})
```

- [ ] **Step 4: 重新运行测试，确认现在失败点收敛到后端逻辑缺失**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -q -p no:cacheprovider`
Expected: FAIL，但不再因为测试环境缺配置而失败。

### Task 2: 新增实时阵容读取与校验模块

**Files:**
- Create: `live_comps.py`
- Test: `tests/test_live_comps.py`

- [ ] **Step 1: 补充段位校验与损坏文件兜底测试**

```python
def test_live_comps_list_rejects_unknown_tier(client):
    response = client.get('/api/live-comps?tier=Z&page=1')
    assert response.status_code == 400
    assert response.get_json()['error'] == '无效段位'


def test_live_comps_summary_falls_back_to_empty_when_payload_invalid(client):
    data_path = Path(client.application.config['LIVE_COMPS_DATA_PATH'])
    data_path.write_text('{"tiers":{"S":"broken"}}', encoding='utf-8')
    payload = client.get('/api/live-comps/summary').get_json()
    assert payload['tiers'][0] == {'tier': 'S', 'total': 0}
    assert payload['source_meta']['is_valid'] is False
```

- [ ] **Step 2: 运行测试，确认需要实现读文件与校验逻辑**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -q -p no:cacheprovider`
Expected: FAIL，因为还没有 `validate_live_comps_payload()`、分页和兜底逻辑。

- [ ] **Step 3: 实现读取、校验、摘要与分页函数**

```python
from datetime import datetime
from pathlib import Path
import json

from flask import Blueprint, current_app, jsonify, request

live_comps_bp = Blueprint('live_comps', __name__)
TIER_ORDER = ('S', 'A', 'B', 'C', 'D')


def empty_live_comps_payload():
    return {'meta': {}, 'tiers': {tier: [] for tier in TIER_ORDER}}


def validate_live_comps_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError('实时阵容数据必须是对象')
    tiers = payload.get('tiers')
    if not isinstance(tiers, dict):
        raise ValueError('实时阵容数据缺少 tiers')
    for tier in TIER_ORDER:
        items = tiers.get(tier, [])
        if not isinstance(items, list):
            raise ValueError(f'{tier} 段位必须是数组')
        for item in items:
            if not isinstance(item, dict):
                raise ValueError('阵容项必须是对象')
            for field in ['id', 'title', 'tier', 'jccCode', 'mainAvatar', 'heroImages']:
                if not item.get(field):
                    raise ValueError(f'缺少字段 {field}')
            if not isinstance(item['heroImages'], list):
                raise ValueError('heroImages 必须是数组')


def read_live_comps_payload():
    data_path = Path(current_app.config['LIVE_COMPS_DATA_PATH'])
    if not data_path.exists():
        return empty_live_comps_payload(), None, False
    try:
        payload = json.loads(data_path.read_text(encoding='utf-8'))
        validate_live_comps_payload(payload)
        updated_at = datetime.fromtimestamp(data_path.stat().st_mtime).isoformat(timespec='seconds')
        return payload, updated_at, True
    except Exception:
        updated_at = datetime.fromtimestamp(data_path.stat().st_mtime).isoformat(timespec='seconds')
        return empty_live_comps_payload(), updated_at, False


def build_live_comps_summary(payload, updated_at, is_valid):
    return {
        'tiers': [{'tier': tier, 'total': len(payload['tiers'].get(tier, []))} for tier in TIER_ORDER],
        'updated_at': updated_at,
        'source_meta': {
            **payload.get('meta', {}),
            'is_valid': is_valid,
        },
    }


def get_live_comps_page(payload, tier, page, page_size):
    items = payload['tiers'].get(tier, [])
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    safe_page = min(max(page, 1), total_pages)
    start = (safe_page - 1) * page_size
    end = start + page_size
    return {
        'tier': tier,
        'items': items[start:end],
        'total': total,
        'page': safe_page,
        'page_size': page_size,
        'total_pages': total_pages,
    }
```

- [ ] **Step 4: 重跑实时阵容测试**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -q -p no:cacheprovider`
Expected: 仍然 FAIL，但失败点应只剩 Blueprint 尚未注册或路由尚未补齐。

### Task 3: 暴露公开只读接口并挂到应用

**Files:**
- Modify: `app.py`
- Modify: `live_comps.py`
- Test: `tests/test_live_comps.py`

- [ ] **Step 1: 补齐接口响应形状测试**

```python
def test_live_comps_summary_exposes_meta_and_totals(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    payload = client.get('/api/live-comps/summary').get_json()
    assert payload['tiers'][0] == {'tier': 'S', 'total': 6}
    assert payload['source_meta']['source'] == 'unit-test'


def test_live_comps_list_uses_default_page_size_from_config(client):
    write_live_comps_seed(client, sample_live_comps_payload())
    payload = client.get('/api/live-comps?tier=S').get_json()
    assert len(payload['items']) == 5
    assert payload['page_size'] == 5
```

- [ ] **Step 2: 运行测试，确认只剩路由层实现**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -q -p no:cacheprovider`
Expected: FAIL，因为 `/api/live-comps/summary` 和 `/api/live-comps` 还没正式注册。

- [ ] **Step 3: 实现 GET 路由并在应用工厂注册 Blueprint**

```python
from live_comps import live_comps_bp

app.register_blueprint(live_comps_bp)
```

```python
@live_comps_bp.get('/api/live-comps/summary')
def live_comps_summary():
    payload, updated_at, is_valid = read_live_comps_payload()
    return jsonify(build_live_comps_summary(payload, updated_at, is_valid))


@live_comps_bp.get('/api/live-comps')
def live_comps_list():
    tier = (request.args.get('tier') or 'S').upper()
    if tier not in TIER_ORDER:
        return jsonify({'error': '无效段位'}), 400
    page = max(int(request.args.get('page', 1) or 1), 1)
    page_size = int(current_app.config['LIVE_COMPS_PAGE_SIZE'])
    payload, _, _ = read_live_comps_payload()
    return jsonify(get_live_comps_page(payload, tier, page, page_size))
```

- [ ] **Step 4: 重跑测试，确认 Phase 1 闭环**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py -q -p no:cacheprovider`
Expected: PASS

### Task 4: Phase 1 验证与交接说明

**Files:**
- Modify: `app.py`
- Modify: `config.py`
- Modify: `tests/conftest.py`
- Create: `live_comps.py`
- Create: `tests/test_live_comps.py`

- [ ] **Step 1: 运行与实时阵容相关的完整测试集**

Run: `python -m pytest D:\1\codex\jcc\claude_project\tests\test_live_comps.py D:\1\codex\jcc\claude_project\tests\test_ui_routes.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 2: 启动本地服务，手工确认空态接口可用**

Run: `python D:\1\codex\jcc\claude_project\run_server.py`
Expected: `GET /api/live-comps/summary` 返回 200，且在未上传数据时各段位总数为 0。

- [ ] **Step 3: 如用户要求，再同步到 `jcc_git`**

```bash
robocopy D:\1\codex\jcc\claude_project D:\1\codex\jcc\jcc_git /MIR /XD instance __pycache__ .pytest_cache
git -C D:\1\codex\jcc\jcc_git status --short
```
