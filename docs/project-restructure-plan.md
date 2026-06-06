# JCC Project Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 JCC 项目从“多个副本 + 手工同步 + 脚本/部署/运行数据混杂”的状态，整理成一个可持续迭代、可安全部署、边界清晰的主仓库。

**Architecture:** 采用分阶段治理式重构：先固定项目边界和安全规则，再整理脚本/部署/文档，随后逐步拆分业务模块。每阶段都保持现有线上 API、页面路由和数据库兼容，避免一次性大改导致线上不可控。

**Tech Stack:** Python 3、Flask、SQLite、原生 HTML/CSS/JavaScript、pytest、GitHub、systemd、Nginx、CDN。

---

## 0. 背景与当前问题

当前项目已经能正常运行，但结构存在明显的长期维护风险：

- `claude_project`、`jcc_git`、`webApplication`、历史备份目录同时存在，缺少唯一事实源。
- `refresh_live_comps.py`、`upload_live_comps.py` 等本地上传/抓取脚本位于仓库根目录，和服务器应用混在一起。
- `webApplication` 是手工整理出来的交付包，后续容易和主仓库不一致。
- 运行数据 `instance/`、数据库、日志、证书等依赖 `.gitignore` 和人工记忆保护。
- 后端模块都在根目录，`lineups.py`、`admin.py`、`live_comps.py` 已经承载较多职责。
- 部署流程已有服务器脚本，但缺少仓库内标准模板、部署检查和回滚说明。
- 文档分散：交接、部署、API、CDN、数据库、实时阵容数据流没有统一入口。

本计划的目标不是一次性重写项目，而是以低风险方式建立长期秩序。

---

## 1. 目标目录结构

最终建议结构如下：

```text
jcc_git/
├─ app.py
├─ admin.py
├─ analytics.py
├─ auth.py
├─ captcha.py
├─ captcha_manifest.json
├─ config.py
├─ db.py
├─ history.py
├─ lineups.py
├─ lineup_code.py
├─ live_comps.py
├─ migrate.py
├─ rate_limit.py
├─ recommendation.py
├─ requirements.txt
├─ run_server.py
├─ scoring.py
├─ visits.py
├─ static/
├─ templates/
├─ tests/
├─ scripts/
│  ├─ local/
│  │  ├─ refresh_live_comps.py
│  │  └─ upload_live_comps.py
│  └─ maintenance/
│     ├─ export_web_application.py
│     ├─ check_deploy_safety.py
│     └─ backup_database.py
├─ deploy/
│  ├─ update.sh
│  ├─ jcc.service.example
│  └─ nginx.conf.example
├─ docs/
│  ├─ index.md
│  ├─ project-structure.md
│  ├─ development-workflow.md
│  ├─ deployment.md
│  ├─ database.md
│  ├─ api.md
│  ├─ cdn-config.md
│  ├─ live-comps.md
│  ├─ security.md
│  ├─ handover.md
│  └─ superpowers/
├─ instance/
├─ .env.example
├─ .gitignore
└─ README.md
```

后续更深入的代码层重构可以再演进到：

```text
src/jcc/
├─ routes/
├─ services/
├─ repositories/
├─ validators/
├─ db/
├─ templates/
└─ static/
```

但本计划前半部分不强制引入 `src/`，先确保低风险整理。

---

## 2. 文件归属规则

### 2.1 可以进入 Git 的内容

| 类型 | 示例 | 说明 |
|---|---|---|
| 服务端代码 | `app.py`、`lineups.py`、`live_comps.py` | 线上运行需要 |
| 前端资源 | `static/`、`templates/` | 线上运行需要 |
| 测试 | `tests/` | 保障迭代质量 |
| 文档 | `docs/`、`README.md` | 交接和维护 |
| 部署模板 | `deploy/*.example`、`deploy/update.sh` | 不包含真实密码 |
| 维护脚本 | `scripts/maintenance/` | 可以在开发或服务器安全运行 |
| 本地脚本 | `scripts/local/` | 允许进 Git，但默认不进服务器交付包 |

### 2.2 不允许进入 Git 的内容

| 类型 | 示例 | 风险 |
|---|---|---|
| 数据库 | `instance/lineups.sqlite3` | 覆盖线上数据 |
| SQLite WAL/SHM | `*.sqlite3-wal`、`*.sqlite3-shm` | 运行状态文件 |
| 日志 | `*.log` | 噪音和隐私 |
| 证书和私钥 | `*.pem`、`*.key`、`ssl-export/` | 严重安全风险 |
| 虚拟环境 | `.venv/` | 体积大且环境相关 |
| 缓存 | `__pycache__/`、`.pytest_cache/` | 无需版本控制 |
| 本地临时交付包 | `webApplication/` | 应由脚本生成 |

### 2.3 不进入服务器交付包的内容

即使某些内容进入 Git，也不应进入服务器交付包：

```text
scripts/local/
实时获取阵容码/
ssl-export/
.pytest_cache/
__pycache__/
instance/
*.sqlite3
*.db
*.log
*.pem
*.key
```

---

## 3. 分阶段实施计划

### Task 1: 固化项目边界和忽略规则

**Files:**
- Modify: `.gitignore`
- Create: `.env.example`
- Create: `docs/index.md`
- Create: `docs/project-structure.md`
- Create: `docs/development-workflow.md`

- [ ] **Step 1: 检查当前 Git 状态**

Run:

```powershell
cd D:\1\codex\jcc\jcc_git
git status --short --branch
```

Expected:

```text
## main...origin/main
```

如果存在未提交改动，先确认这些改动是否属于本阶段。

- [ ] **Step 2: 更新 `.gitignore`**

Modify `.gitignore` to include:

```gitignore
# Runtime data
instance/
*.sqlite3
*.sqlite3-wal
*.sqlite3-shm
*.db

# Logs
*.log
server.out.log
server.err.log
live-comps-server.out.log
live-comps-server.err.log

# Python cache/test cache
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.coverage
htmlcov/

# Local environments
.venv/
venv/
.env

# Secrets/certificates
ssl-export/
*.pem
*.key
*.crt

# Generated handoff package
webApplication/

# Test scratch files
test-tmp/
test-lineups.sqlite3
smoke.sqlite3
```

- [ ] **Step 3: 新增 `.env.example`**

Create `.env.example`:

```env
# Flask session secret. Use a long random value in production.
JCC_SECRET_KEY=change-me-to-a-random-long-string

# Initial/default admin account. Override in production.
JCC_ADMIN_USERNAME=admin
JCC_ADMIN_PASSWORD=change-me

# Token required by /api/live-comps/upload and /api/live-comps/assets/upload.
JCC_LIVE_COMPS_UPLOAD_TOKEN=change-me
```

- [ ] **Step 4: 新增 `docs/index.md`**

Create `docs/index.md`:

```markdown
# JCC 文档入口

## 项目治理

- [项目结构](project-structure.md)
- [开发流程](development-workflow.md)
- [部署说明](deployment.md)
- [数据库说明](database.md)
- [API 说明](api.md)
- [CDN 配置](cdn-config.md)
- [实时阵容说明](live-comps.md)
- [安全说明](security.md)
- [交接说明](handover.md)

## 历史计划

历史功能设计和实施计划保留在 `docs/superpowers/`。
```

- [ ] **Step 5: 新增 `docs/project-structure.md`**

Create `docs/project-structure.md` with the ownership rules from sections 1 and 2 of this plan.

Required headings:

```markdown
# 项目结构说明

## 唯一主仓库

## 目录职责

## 可以提交的内容

## 禁止提交的内容

## 不进入服务器交付包的内容

## 后续演进方向
```

- [ ] **Step 6: 新增 `docs/development-workflow.md`**

Create `docs/development-workflow.md`:

```markdown
# 开发流程

## 标准流程

1. 在 `jcc_git` 修改代码。
2. 运行相关测试。
3. 运行全量测试或必要子集。
4. 检查敏感文件。
5. 提交到 Git。
6. 推送到 GitHub。
7. 服务器运行更新脚本。

## 本地运行

```powershell
cd D:\1\codex\jcc\jcc_git
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python migrate.py
python run_server.py
```

## 测试

```powershell
pytest
```

## 不允许手工同步

不要再手工从 `claude_project` 拷贝文件到 `jcc_git`。如果确实需要同步，先说明原因，并使用脚本或明确文件清单。
```

- [ ] **Step 7: 运行安全检查命令**

Run:

```powershell
git status --short
git diff -- .gitignore .env.example docs/index.md docs/project-structure.md docs/development-workflow.md
```

Expected:

- 只出现本任务修改的文件。
- 不出现 `instance/`、证书、数据库、日志。

- [ ] **Step 8: Commit**

Run:

```powershell
git add .gitignore .env.example docs/index.md docs/project-structure.md docs/development-workflow.md
git commit -m "docs: define project structure and workflow"
```

---

### Task 2: 整理本地脚本和维护脚本目录

**Files:**
- Create: `scripts/local/`
- Create: `scripts/maintenance/`
- Move: `refresh_live_comps.py` -> `scripts/local/refresh_live_comps.py`
- Move: `upload_live_comps.py` -> `scripts/local/upload_live_comps.py`
- Modify: `tests/test_refresh_live_comps.py`
- Modify: `tests/test_upload_live_comps.py`
- Create: `scripts/maintenance/export_web_application.py`
- Create: `scripts/maintenance/check_deploy_safety.py`

- [ ] **Step 1: 移动本地上传脚本**

Run:

```powershell
mkdir scripts\local -Force
mkdir scripts\maintenance -Force
git mv refresh_live_comps.py scripts\local\refresh_live_comps.py
git mv upload_live_comps.py scripts\local\upload_live_comps.py
```

- [ ] **Step 2: 修复 `scripts/local/refresh_live_comps.py` 的 import 路径**

At top of `scripts/local/refresh_live_comps.py`, insert after imports:

```python
PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
```

Ensure it imports:

```python
import upload_live_comps
```

from the moved local script location. If direct import fails, change to:

```python
from scripts.local import upload_live_comps
```

- [ ] **Step 3: 更新上传脚本测试 import**

Modify `tests/test_refresh_live_comps.py`:

```python
from scripts.local import refresh_live_comps
```

Modify `tests/test_upload_live_comps.py`:

```python
from scripts.local import upload_live_comps
```

- [ ] **Step 4: 新增 `scripts/maintenance/check_deploy_safety.py`**

Create a script that fails if sensitive files are tracked or present in staged changes:

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FORBIDDEN_SUFFIXES = ('.sqlite3', '.db', '.pem', '.key', '.crt', '.log')
FORBIDDEN_PARTS = {'instance', 'ssl-export', '__pycache__', '.pytest_cache'}


def run_git(args: list[str]) -> list[str]:
    result = subprocess.run(['git', *args], capture_output=True, text=True, check=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_forbidden(path: str) -> bool:
    normalized = path.replace('\\', '/')
    parts = set(normalized.split('/'))
    return normalized.endswith(FORBIDDEN_SUFFIXES) or bool(parts & FORBIDDEN_PARTS)


def main() -> int:
    tracked = run_git(['ls-files'])
    staged = run_git(['diff', '--cached', '--name-only'])
    problems = sorted({path for path in tracked + staged if is_forbidden(path)})
    if problems:
        print('发现禁止提交的文件：', file=sys.stderr)
        for path in problems:
            print(f'- {path}', file=sys.stderr)
        return 1
    print('部署安全检查通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 5: 新增 `scripts/maintenance/export_web_application.py`**

Create a script that exports a clean server package to `../webApplication`:

```python
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT.parent / 'webApplication'

INCLUDE_FILES = {
    '.gitignore', 'README.md', 'admin.py', 'analytics.py', 'app.py', 'audit.py',
    'auth.py', 'captcha.py', 'captcha_manifest.json', 'config.py', 'db.py',
    'history.py', 'lineups.py', 'lineup_code.py', 'live_comps.py', 'migrate.py',
    'rate_limit.py', 'recommendation.py', 'requirements.txt', 'run_server.py',
    'scoring.py', 'visits.py', '.env.example',
}
INCLUDE_DIRS = {'static', 'templates', 'tests', 'docs', 'deploy'}
EXCLUDE_PARTS = {'instance', '__pycache__', '.pytest_cache', '.git', 'scripts'}
EXCLUDE_SUFFIXES = {'.pyc', '.pyo', '.sqlite3', '.db', '.log', '.pem', '.key', '.crt'}


def should_copy(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if set(rel.parts) & EXCLUDE_PARTS:
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    return rel.parts[0] in INCLUDE_DIRS or rel.as_posix() in INCLUDE_FILES


def clean_target() -> None:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.mkdir(parents=True)


def export() -> int:
    clean_target()
    copied = 0
    for path in ROOT.rglob('*'):
        if not path.is_file() or not should_copy(path):
            continue
        rel = path.relative_to(ROOT)
        target = TARGET / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    print(f'已导出 {copied} 个文件到 {TARGET}')
    return 0


if __name__ == '__main__':
    raise SystemExit(export())
```

- [ ] **Step 6: 运行脚本测试**

Run:

```powershell
python scripts\maintenance\check_deploy_safety.py
python scripts\maintenance\export_web_application.py
```

Expected:

```text
部署安全检查通过
已导出 ... 个文件到 D:\1\codex\jcc\webApplication
```

- [ ] **Step 7: 运行相关测试**

Run:

```powershell
pytest tests/test_refresh_live_comps.py tests/test_upload_live_comps.py tests/test_live_comps.py
```

Expected:

```text
passed
```

- [ ] **Step 8: Commit**

Run:

```powershell
git add scripts tests
git commit -m "chore: separate local scripts from server app"
```

---

### Task 3: 标准化部署文档和部署模板

**Files:**
- Create: `deploy/update.sh`
- Create: `deploy/jcc.service.example`
- Create: `deploy/nginx.conf.example`
- Create: `docs/deployment.md`
- Create: `docs/security.md`
- Create: `docs/cdn-config.md`

- [ ] **Step 1: 新增 `deploy/update.sh`**

Create:

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/jcc/jcc_git"
BACKUP_DIR="/opt/jcc/backups"
SERVICE_NAME="jcc"
HEALTH_URL="https://jcc.np5.top/api/health"

cd "$PROJECT_DIR"

mkdir -p "$BACKUP_DIR"
if [ -f "instance/lineups.sqlite3" ]; then
  cp "instance/lineups.sqlite3" "$BACKUP_DIR/lineups.$(date +%Y%m%d-%H%M%S).sqlite3"
fi

git fetch origin main
git reset --hard origin/main

source .venv/bin/activate
pip install -r requirements.txt
python migrate.py

systemctl restart "$SERVICE_NAME"
curl -fsS "$HEALTH_URL"
echo "JCC update completed"
```

- [ ] **Step 2: 新增 `deploy/jcc.service.example`**

Create:

```ini
[Unit]
Description=JCC Lineup Manager
After=network.target

[Service]
WorkingDirectory=/opt/jcc/jcc_git
Environment="JCC_SECRET_KEY=replace-with-random-secret"
Environment="JCC_ADMIN_USERNAME=replace-admin-user"
Environment="JCC_ADMIN_PASSWORD=replace-admin-password"
Environment="JCC_LIVE_COMPS_UPLOAD_TOKEN=replace-upload-token"
ExecStart=/opt/jcc/jcc_git/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: 新增 `deploy/nginx.conf.example`**

Create:

```nginx
server {
    listen 80;
    server_name jcc.np5.top;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name jcc.np5.top;

    ssl_certificate /etc/letsencrypt/live/jcc.np5.top/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/jcc.np5.top/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

- [ ] **Step 4: 新增 `docs/deployment.md`**

Required sections:

```markdown
# 部署说明

## 服务器信息

## 首次部署

## 日常更新

## 数据库备份

## 回滚

## 健康检查
```

Include commands:

```bash
/usr/local/bin/jcc-update
systemctl status jcc
journalctl -u jcc -f
curl -fsS https://jcc.np5.top/api/health
```

- [ ] **Step 5: 新增 `docs/security.md`**

Required topics:

```markdown
# 安全说明

## 禁止提交的敏感文件

## 环境变量

## 上传令牌

## 管理员账号

## 数据库保护

## CDN 缓存安全
```

- [ ] **Step 6: 新增 `docs/cdn-config.md`**

Include current CDN rules:

```markdown
# CDN 配置

## 域名

- 业务域名：`jcc.np5.top`
- CDN CNAME：`nrnx2qs8.free-hw.fusionscdn.com`
- 源站 IP：`45.113.1.61`

## 推荐缓存规则

| 路径 | 策略 |
|---|---|
| `/static/*` | 强制缓存 7-30 天 |
| `/api/live-comps/assets/*` | 强制缓存 7-30 天 |
| `/favicon.ico` | 强制缓存 30 天 |
| `/api/*` | 不缓存 |
| `/admin*` | 不缓存 |
| `/auth*` | 不缓存 |
| `/me*` | 不缓存 |
| `/lineup/*` | 不缓存 |
| `/` | 不缓存或极短缓存 |
```

- [ ] **Step 7: Commit**

Run:

```powershell
git add deploy docs/deployment.md docs/security.md docs/cdn-config.md
git commit -m "docs: add deployment and cdn guidance"
```

---

### Task 4: 补全文档体系

**Files:**
- Create: `docs/database.md`
- Create: `docs/api.md`
- Create: `docs/live-comps.md`
- Create: `docs/handover.md`
- Modify: `docs/index.md`

- [ ] **Step 1: 新增 `docs/database.md`**

Include tables:

```markdown
# 数据库说明

## 数据库位置

`instance/lineups.sqlite3`

## 运行数据

- `instance/lineups.sqlite3`
- `instance/live-comps.json`
- `instance/live-comps.previous.json`
- `instance/live-comps-assets/`

## 主要表

| 表名 | 作用 |
|---|---|
| `users` | 用户和管理员账号 |
| `lineups` | 用户上传阵容 |
| `likes` | 点赞记录 |
| `copy_events` | 普通阵容复制记录 |
| `favorites` | 收藏记录 |
| `reports` | 举报记录 |
| `recent_lineup_views` | 最近浏览 |
| `recent_lineup_copies` | 最近复制 |
| `visit_events` | 每日 UV |
| `audit_logs` | 管理员审计日志 |
| `growth_events` | 增长漏斗事件 |
| `live_comp_global_stats` | 实时阵容累计复制 |
| `live_comp_global_daily_stats` | 实时阵容当日复制 |

## 迁移

运行：`python migrate.py`

## 备份

运行服务器更新脚本前必须备份 `instance/lineups.sqlite3`。
```

- [ ] **Step 2: 新增 `docs/api.md`**

Document current API groups:

```markdown
# API 说明

## 认证

- `GET /api/me`
- `POST /api/register`
- `POST /api/login`
- `POST /api/logout`

## 验证码

- `GET /api/captcha`
- `POST /api/captcha/verify`

## 阵容

- `GET /api/lineups`
- `GET /api/lineups/<id>`
- `POST /api/lineups`
- `PUT /api/lineups/<id>`
- `DELETE /api/lineups/<id>`
- `POST /api/lineups/<id>/hide`
- `POST /api/lineups/<id>/view`
- `POST /api/lineups/<id>/like`
- `POST /api/lineups/<id>/copy`
- `POST /api/lineups/<id>/favorite`
- `DELETE /api/lineups/<id>/favorite`
- `POST /api/lineups/<id>/report`

## 个人中心

- `GET /api/me/recent-views`
- `GET /api/me/recent-copies`
- `POST /api/me/history/sync`
- `GET /api/me/dashboard`
- `GET /api/me/reports`

## 实时阵容

- `GET /api/live-comps/summary`
- `GET /api/live-comps`
- `POST /api/live-comps/<live_comp_id>/copy`
- `POST /api/live-comps/upload`
- `POST /api/live-comps/assets/upload`
- `GET /api/live-comps/assets/<filename>`

## 管理员

- `GET /api/admin/users`
- `POST /api/admin/users`
- `PUT /api/admin/users/<id>`
- `DELETE /api/admin/users/<id>`
- `GET /api/admin/lineups`
- `PUT /api/admin/lineups/<id>`
- `POST /api/admin/lineups/<id>/adjust-score`
- `GET /api/admin/live-comps`
- `GET /api/admin/stats`
- `GET /api/admin/overview`
- `GET /api/admin/growth`
- `GET /api/admin/audit-logs`
- `GET /api/admin/reports`
- `POST /api/admin/reports/<id>/resolve`
```

- [ ] **Step 3: 新增 `docs/live-comps.md`**

Include:

```markdown
# 实时阵容说明

## 数据流

1. 本地脚本获取 DataTFT 数据。
2. 本地脚本下载图片。
3. 本地脚本调用 `/api/live-comps/assets/upload` 上传图片。
4. 本地脚本重写 JSON 图片地址为 `/api/live-comps/assets/<filename>`。
5. 本地脚本调用 `/api/live-comps/upload` 上传 JSON。
6. 网站首页从 `/api/live-comps` 读取展示。

## 统计逻辑

实时阵容复制不按单个阵容统计，只统计全局：

- 当日复制次数
- 历史累计复制次数

## 注意事项

本地上传脚本属于 `scripts/local/`，不应进入服务器交付包。
```

- [ ] **Step 4: 新增 `docs/handover.md`**

Summarize for new teammate:

```markdown
# 交接说明

## 项目是什么

## 如何本地运行

## 如何部署

## 数据库在哪里

## 管理员后台在哪里

## 实时阵容如何工作

## 哪些文件不能动

## 常见问题
```

- [ ] **Step 5: 更新 `docs/index.md`**

Ensure it links all documents created in this task.

- [ ] **Step 6: Commit**

Run:

```powershell
git add docs
git commit -m "docs: add operations handover documentation"
```

---

### Task 5: 引入数据库迁移版本化设计文档

**Files:**
- Create: `docs/database-migration-plan.md`

This task only writes the design. It does not change database behavior yet.

- [ ] **Step 1: 新增迁移设计文档**

Create `docs/database-migration-plan.md`:

```markdown
# 数据库迁移版本化计划

## 目标

将当前 `db.py` 中的自动补字段迁移，逐步升级为可追踪、可回放的版本化迁移。

## 目标表

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
```

## 目标目录

```text
migrations/
├─ 001_initial.sql
├─ 002_add_reports.sql
├─ 003_add_history.sql
├─ 004_add_growth_events.sql
├─ 005_add_live_comp_stats.sql
└─ 006_add_visibility_fields.sql
```

## 执行流程

1. 读取 `schema_migrations`。
2. 找出未执行的 SQL 文件。
3. 按文件名顺序执行。
4. 每执行成功一个文件，写入 `schema_migrations`。
5. 任一文件失败，停止迁移。

## 上线策略

第一步只加入 `schema_migrations` 表，不删除当前 `migrate_schema` 逻辑。
第二步将已有 schema 快照标记为 baseline。
第三步之后的新数据库变更使用 SQL 文件。
```

- [ ] **Step 2: Commit**

Run:

```powershell
git add docs/database-migration-plan.md
git commit -m "docs: plan versioned database migrations"
```

---

### Task 6: 为业务拆分建立代码重构计划

**Files:**
- Create: `docs/backend-refactor-plan.md`

This task only writes the next-stage code refactor plan.

- [ ] **Step 1: 新增后端拆分计划**

Create `docs/backend-refactor-plan.md`:

```markdown
# 后端模块拆分计划

## 原则

- API 路径保持不变。
- 页面路由保持不变。
- 数据库结构保持兼容。
- 每次只拆一个模块。
- 每次拆分前先补回归测试。

## 推荐顺序

1. `live_comps.py`
2. `lineups.py`
3. `admin.py`
4. `db.py`

## 目标职责分离

- Routes：处理 HTTP 请求和响应。
- Services：处理业务规则。
- Repositories：处理 SQL 查询。
- Validators：处理参数校验。

## 实时阵容拆分目标

```text
routes/live_comp_routes.py
services/live_comp_service.py
repositories/live_comp_stats_repo.py
validators/live_comp_validator.py
```

## 阵容模块拆分目标

```text
routes/lineup_routes.py
services/lineup_service.py
services/visibility_service.py
services/interaction_service.py
repositories/lineup_repo.py
repositories/interaction_repo.py
validators/lineup_validator.py
```

## 管理员模块拆分目标

```text
routes/admin_routes.py
services/admin_user_service.py
services/admin_lineup_service.py
services/admin_report_service.py
services/admin_dashboard_service.py
```

## 验收标准

- 所有现有测试通过。
- API 响应字段不变。
- 前端无需修改或只做路径引用调整。
- 线上更新不需要手工处理数据库。
```

- [ ] **Step 2: Commit**

Run:

```powershell
git add docs/backend-refactor-plan.md
git commit -m "docs: plan backend module refactor"
```

---

### Task 7: 执行全量验证和导出包验证

**Files:**
- No production code changes.

- [ ] **Step 1: 运行全量测试**

Run:

```powershell
pytest
```

Expected:

```text
passed
```

- [ ] **Step 2: 运行部署安全检查**

Run:

```powershell
python scripts\maintenance\check_deploy_safety.py
```

Expected:

```text
部署安全检查通过
```

- [ ] **Step 3: 导出 `webApplication`**

Run:

```powershell
python scripts\maintenance\export_web_application.py
```

Expected:

```text
已导出 ... 个文件到 D:\1\codex\jcc\webApplication
```

- [ ] **Step 4: 检查交付包不含敏感文件**

Run:

```powershell
cd D:\1\codex\jcc\webApplication
Get-ChildItem -Recurse -Force | Where-Object {
  $_.Name -in @('refresh_live_comps.py','upload_live_comps.py') -or
  $_.FullName -match '\\(instance|__pycache__|\.pytest_cache|scripts|ssl-export)(\\|$)' -or
  $_.Extension -in @('.sqlite3','.db','.log','.pyc','.pem','.key','.crt')
} | Select-Object FullName
```

Expected:

```text
# no output
```

- [ ] **Step 5: Commit final doc adjustments if any**

If Step 1-4 reveal documentation or script issues, fix and commit:

```powershell
git add docs scripts deploy .gitignore .env.example tests
git commit -m "chore: finalize project governance setup"
```

If there are no changes, do not create an empty commit.

---

## 4. 数据库保护策略

所有阶段必须遵守：

- 不提交 `instance/`。
- 不提交 `*.sqlite3`。
- 不在部署包中包含数据库。
- 服务器更新前备份 `instance/lineups.sqlite3`。
- 数据库迁移必须通过 `python migrate.py` 执行。
- 任何修改 `db.py` 或 `migrate.py` 的任务，必须先运行数据库相关测试。

推荐服务器备份命令：

```bash
mkdir -p /opt/jcc/backups
cp /opt/jcc/jcc_git/instance/lineups.sqlite3 /opt/jcc/backups/lineups.$(date +%Y%m%d-%H%M%S).sqlite3
```

---

## 5. 回滚策略

### 5.1 代码回滚

服务器上：

```bash
cd /opt/jcc/jcc_git
git log --oneline -5
git reset --hard <previous_commit>
source .venv/bin/activate
python migrate.py
systemctl restart jcc
curl -fsS https://jcc.np5.top/api/health
```

### 5.2 数据库回滚

只有在确认数据库损坏或错误迁移时才使用数据库回滚：

```bash
systemctl stop jcc
cp /opt/jcc/backups/lineups.YYYYMMDD-HHMMSS.sqlite3 /opt/jcc/jcc_git/instance/lineups.sqlite3
systemctl start jcc
curl -fsS https://jcc.np5.top/api/health
```

注意：数据库回滚会丢失备份时间点之后的新用户、新阵容、新点赞、复制和访问数据。

---

## 6. 验收标准

本计划第一轮完成后，应满足：

- `jcc_git` 是唯一主仓库。
- `.gitignore` 明确保护数据库、日志、证书、缓存。
- `.env.example` 明确列出生产环境变量。
- `scripts/local/` 和 `scripts/maintenance/` 分离。
- `deploy/` 存放部署模板。
- `docs/` 有统一入口和维护文档。
- `webApplication` 可以由脚本自动生成。
- 导出的 `webApplication` 不含数据库、日志、证书、本地脚本和缓存。
- 现有测试通过。
- 服务器更新流程有备份、迁移、重启、健康检查。

---

## 7. 暂不处理的事项

以下事项不在第一轮治理重构中处理：

- 不把 Flask 改成 FastAPI。
- 不把原生前端改成 Vue/React。
- 不把 SQLite 迁移到 MySQL/PostgreSQL。
- 不重写管理员后台 UI。
- 不改变任何现有公开 API 路径。
- 不改变当前线上数据库结构，除非后续单独创建迁移任务。

---

## 8. 执行建议

推荐执行顺序：

1. Task 1：文档和 `.gitignore`，风险最低。
2. Task 2：脚本目录整理，解决当前最大混乱点。
3. Task 3：部署模板和安全文档。
4. Task 4：补全文档体系。
5. Task 5：数据库迁移版本化设计。
6. Task 6：后端模块拆分设计。
7. Task 7：全量验证和导出包验证。

每个 Task 单独提交，不要混在一个大提交中。

---

## 9. Self-Review

- 本计划覆盖了当前项目混乱的主要来源：多副本、脚本混杂、部署边界不清、运行数据保护不足、文档分散、后端模块膨胀。
- 第一轮任务以治理和文档为主，避免直接大改业务代码。
- 计划包含具体文件路径、命令、预期结果和提交建议。
- 数据库和证书保护策略明确。
- 后端业务拆分只作为后续设计文档，不在第一轮直接执行，降低风险。
