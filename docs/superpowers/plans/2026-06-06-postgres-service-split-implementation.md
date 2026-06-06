# PostgreSQL Service Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split JCC into a web service repository and a PostgreSQL database service repository, then migrate production data from SQLite to PostgreSQL with a short controlled write freeze and a tested rollback path.

**Architecture:** `jcc-web-service` owns Flask, Jinja templates, static assets, API routes, and Web deployment. `jcc-db-service` owns PostgreSQL deployment, schema migrations, backups, restore tooling, and SQLite-to-PostgreSQL migration verification. Phase A runs one Web instance against `database.np5.top`; later multi-instance Web deployment reuses the same database endpoint after moving file-backed live-comps data to PostgreSQL/object storage.

**Tech Stack:** Python 3, Flask, SQLite source database, PostgreSQL 16 target database, psycopg 3, Docker Compose for local/database service deployment, pytest.

---

## Current Facts

- Current production database is SQLite at `instance/lineups.sqlite3`, configured by `config.py`.
- `db.py` uses Python `sqlite3`, `sqlite3.Row`, `?` placeholders, `executescript()`, `lastrowid`, and SQLite PRAGMAs.
- `db_schema.py` contains SQLite DDL with `AUTOINCREMENT`, `INSERT OR IGNORE`, `strftime(...)`, triggers, `PRAGMA table_info`, and `sqlite_master`.
- Web runtime data also includes file-backed live-comps state under `instance/`, especially JSON payloads, manual codes, and cached assets.
- `deploy/update.sh` currently backs up SQLite, hard resets the repo, runs `python migrate.py`, restarts `jcc`, then checks `/api/health`.
- Existing new repositories:
  - `D:\1\codex\jcc-new\jcc-db-service`
  - `D:\1\codex\jcc-new\jcc-web-service`

## Repository Responsibilities

### `jcc-db-service`

Create and maintain:

- `docker-compose.yml`: local and single-server PostgreSQL service.
- `.env.example`: documented database passwords, host ports, backup directory.
- `migrations/0001_initial_schema.sql`: PostgreSQL version of the current SQLite schema.
- `migrations/0002_seed_defaults.sql`: default `cache_state` and `app_settings` rows.
- `scripts/apply_migrations.py`: idempotent migration runner using `schema_migrations`.
- `scripts/migrate_sqlite_to_postgres.py`: one-shot data migration preserving integer IDs.
- `scripts/verify_counts.py`: table count comparison between SQLite and PostgreSQL.
- `scripts/verify_integrity.py`: foreign key and critical business invariant checks.
- `scripts/backup_postgres.ps1` and `scripts/backup_postgres.sh`: `pg_dump` backup wrappers.
- `scripts/restore_postgres.sh`: tested restore path.
- `docs/deployment.md`: production setup for `database.np5.top`.
- `docs/cutover-runbook.md`: exact production cutover and rollback steps.

### `jcc-web-service`

Create and maintain:

- Flask application files copied from the current `jcc_git` repository.
- `requirements.txt` including Flask, pytest, psycopg, and database adapter dependencies.
- `config.py` updated to prefer `JCC_DATABASE_URL`.
- `db.py` changed to create a SQLite or PostgreSQL connection based on `JCC_DATABASE_URL`.
- `db_sql.py`: minimal SQL dialect helpers for placeholders, conflict clauses, row conversion, scripts, table metadata, and inserted IDs.
- PostgreSQL-aware versions of schema init and migrations.
- Web deployment templates that set `JCC_DATABASE_URL=postgresql://jcc_app:...@database.np5.top:5432/jcc`.

## Implementation Tasks

### Task 1: Initialize `jcc-db-service`

**Files:**
- Create: `D:\1\codex\jcc-new\jcc-db-service\.gitignore`
- Create: `D:\1\codex\jcc-new\jcc-db-service\README.md`
- Create: `D:\1\codex\jcc-new\jcc-db-service\.env.example`
- Create: `D:\1\codex\jcc-new\jcc-db-service\docker-compose.yml`
- Create: `D:\1\codex\jcc-new\jcc-db-service\requirements.txt`

- [ ] **Step 1: Write repository bootstrap files**

Create `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
backups/
*.dump
*.sql.gz
*.sqlite3
```

Create `requirements.txt`:

```text
psycopg[binary]>=3.2
python-dotenv>=1.0
pytest>=8.0
```

Create `.env.example`:

```text
POSTGRES_DB=jcc
POSTGRES_USER=jcc_app
POSTGRES_PASSWORD=replace-with-strong-password
POSTGRES_PORT=5432
DATABASE_URL=postgresql://jcc_app:replace-with-strong-password@127.0.0.1:5432/jcc
BACKUP_DIR=./backups
```

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-jcc}
      POSTGRES_USER: ${POSTGRES_USER:-jcc_app}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./backups:/backups
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-jcc_app} -d ${POSTGRES_DB:-jcc}"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres-data:
```

Create `README.md`:

```markdown
# JCC Database Service

PostgreSQL deployment, schema migrations, backups, and SQLite-to-PostgreSQL migration tooling for JCC.

Local start:

```bash
cp .env.example .env
docker compose up -d
python scripts/apply_migrations.py --database-url "$DATABASE_URL"
```

Production should restrict port `5432` to trusted Web service IPs only.
```

- [ ] **Step 2: Verify files are staged cleanly**

Run:

```powershell
git -C D:\1\codex\jcc-new\jcc-db-service status --short
```

Expected: only the new files from this task are listed.

- [ ] **Step 3: Commit**

```powershell
git -C D:\1\codex\jcc-new\jcc-db-service add .
git -C D:\1\codex\jcc-new\jcc-db-service commit -m "chore: initialize database service"
```

### Task 2: Add PostgreSQL Schema Migrations

**Files:**
- Create: `D:\1\codex\jcc-new\jcc-db-service\migrations\0001_initial_schema.sql`
- Create: `D:\1\codex\jcc-new\jcc-db-service\migrations\0002_seed_defaults.sql`
- Create: `D:\1\codex\jcc-new\jcc-db-service\scripts\apply_migrations.py`
- Test: `D:\1\codex\jcc-new\jcc-db-service\tests\test_migrations.py`

- [ ] **Step 1: Write failing migration test**

Create `tests/test_migrations.py`:

```python
from pathlib import Path


def test_migrations_have_schema_migrations_table():
    sql = Path('migrations/0001_initial_schema.sql').read_text(encoding='utf-8')
    assert 'CREATE TABLE IF NOT EXISTS schema_migrations' in sql


def test_initial_schema_contains_current_business_tables():
    sql = Path('migrations/0001_initial_schema.sql').read_text(encoding='utf-8')
    for table in [
        'users',
        'lineups',
        'likes',
        'copy_events',
        'copy_action_events',
        'live_comp_global_stats',
        'live_comp_global_daily_stats',
        'cache_state',
        'app_settings',
        'favorites',
        'reports',
        'recent_lineup_views',
        'recent_lineup_copies',
        'login_events',
        'visit_events',
        'audit_logs',
        'rate_limits',
        'growth_events',
        'guestbook_messages',
        'patch_notes',
    ]:
        assert f'CREATE TABLE IF NOT EXISTS {table}' in sql
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\1\codex\jcc-new\jcc-db-service
python -m pytest tests/test_migrations.py -q
```

Expected: FAIL because migration files do not exist yet.

- [ ] **Step 3: Write PostgreSQL schema**

Create `migrations/0001_initial_schema.sql` with PostgreSQL DDL equivalent to current `db_schema.py`. Use:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
```

Use `BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY` for integer IDs, `TEXT` for existing text timestamps, `INTEGER` for existing numeric counters, and preserve all unique constraints and foreign keys. Recreate current indexes from `db_schema.py` and `EXTRA_INDEX_STATEMENTS`. Recreate cache invalidation triggers with PostgreSQL trigger functions that set `updated_at = to_char(now(), 'YYYY-MM-DD HH24:MI:SS')`.

Create `migrations/0002_seed_defaults.sql`:

```sql
INSERT INTO cache_state (cache_key, revision, created_at, updated_at) VALUES
('home', 0, to_char(now(), 'YYYY-MM-DD HH24:MI:SS'), to_char(now(), 'YYYY-MM-DD HH24:MI:SS')),
('score', 0, to_char(now(), 'YYYY-MM-DD HH24:MI:SS'), to_char(now(), 'YYYY-MM-DD HH24:MI:SS'))
ON CONFLICT (cache_key) DO NOTHING;

INSERT INTO app_settings (setting_key, setting_value, updated_at) VALUES
('simulator_enabled', 'true', to_char(now(), 'YYYY-MM-DD HH24:MI:SS')),
('notice_enabled', 'false', to_char(now(), 'YYYY-MM-DD HH24:MI:SS')),
('notice_data', '{}', to_char(now(), 'YYYY-MM-DD HH24:MI:SS'))
ON CONFLICT (setting_key) DO NOTHING;
```

- [ ] **Step 4: Write migration runner**

Create `scripts/apply_migrations.py`:

```python
import argparse
from datetime import datetime
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / 'migrations'


def apply_migrations(database_url):
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                '''
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                '''
            )
            for path in sorted(MIGRATIONS.glob('*.sql')):
                version = path.stem
                cur.execute('SELECT 1 FROM schema_migrations WHERE version = %s', (version,))
                if cur.fetchone():
                    continue
                cur.execute(path.read_text(encoding='utf-8'))
                cur.execute(
                    'INSERT INTO schema_migrations (version, applied_at) VALUES (%s, %s)',
                    (version, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                )
        conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database-url', required=True)
    args = parser.parse_args()
    apply_migrations(args.database_url)


if __name__ == '__main__':
    main()
```

- [ ] **Step 5: Run tests**

Run:

```powershell
cd D:\1\codex\jcc-new\jcc-db-service
python -m pytest tests/test_migrations.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git -C D:\1\codex\jcc-new\jcc-db-service add .
git -C D:\1\codex\jcc-new\jcc-db-service commit -m "feat: add postgres schema migrations"
```

### Task 3: Add SQLite-to-PostgreSQL Migration Tooling

**Files:**
- Create: `D:\1\codex\jcc-new\jcc-db-service\scripts\migrate_sqlite_to_postgres.py`
- Create: `D:\1\codex\jcc-new\jcc-db-service\scripts\verify_counts.py`
- Create: `D:\1\codex\jcc-new\jcc-db-service\scripts\verify_integrity.py`
- Test: `D:\1\codex\jcc-new\jcc-db-service\tests\test_migration_scripts.py`

- [ ] **Step 1: Write failing migration script tests**

Create `tests/test_migration_scripts.py`:

```python
from scripts.migrate_sqlite_to_postgres import TABLE_ORDER


def test_table_order_loads_parent_tables_before_children():
    assert TABLE_ORDER.index('users') < TABLE_ORDER.index('lineups')
    assert TABLE_ORDER.index('lineups') < TABLE_ORDER.index('likes')
    assert TABLE_ORDER.index('lineups') < TABLE_ORDER.index('favorites')
    assert TABLE_ORDER.index('lineups') < TABLE_ORDER.index('reports')


def test_table_order_includes_current_tables():
    assert TABLE_ORDER == [
        'users',
        'lineups',
        'likes',
        'copy_events',
        'copy_action_events',
        'live_comp_global_stats',
        'live_comp_global_daily_stats',
        'cache_state',
        'app_settings',
        'favorites',
        'reports',
        'recent_lineup_views',
        'recent_lineup_copies',
        'login_events',
        'visit_events',
        'audit_logs',
        'rate_limits',
        'growth_events',
        'guestbook_messages',
        'patch_notes',
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\1\codex\jcc-new\jcc-db-service
python -m pytest tests/test_migration_scripts.py -q
```

Expected: FAIL because the migration script does not exist.

- [ ] **Step 3: Implement migration script**

Create `scripts/migrate_sqlite_to_postgres.py` with:

- `TABLE_ORDER` exactly as tested.
- SQLite source connection using `sqlite3.Row`.
- PostgreSQL target connection using `psycopg`.
- `--sqlite-path`, `--database-url`, and `--truncate-target` flags.
- If `--truncate-target` is set, truncate tables in reverse `TABLE_ORDER` with `RESTART IDENTITY CASCADE`.
- For each table, read rows with `SELECT * FROM {table} ORDER BY id` when an `id` column exists, otherwise plain `SELECT *`.
- Insert with explicit column list and `%s` placeholders.
- After inserting identity tables, run `SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE((SELECT MAX(id) FROM table), 1), true)` for tables with `id`.

- [ ] **Step 4: Implement verification scripts**

Create `scripts/verify_counts.py` that prints SQLite and PostgreSQL row counts for every `TABLE_ORDER` table and exits non-zero if any mismatch.

Create `scripts/verify_integrity.py` that checks:

- every `lineups.user_id` exists in `users.id`;
- every `likes.lineup_id`, `copy_events.lineup_id`, `favorites.lineup_id`, `reports.lineup_id`, `recent_lineup_views.lineup_id`, and `recent_lineup_copies.lineup_id` exists in `lineups.id`;
- every `reports.reporter_user_id` exists in `users.id`;
- every `growth_events.ref_lineup_id` either is null or exists in `lineups.id`.

- [ ] **Step 5: Run tests**

Run:

```powershell
cd D:\1\codex\jcc-new\jcc-db-service
python -m pytest tests/test_migration_scripts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git -C D:\1\codex\jcc-new\jcc-db-service add .
git -C D:\1\codex\jcc-new\jcc-db-service commit -m "feat: add sqlite to postgres migration tools"
```

### Task 4: Initialize `jcc-web-service` From Current App

**Files:**
- Copy from `D:\1\codex\jcc\jcc_git` to `D:\1\codex\jcc-new\jcc-web-service`: application `.py` files, `templates/`, `static/`, `tests/`, `docs/`, `scripts/`, `deploy/`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`.
- Do not copy: `.git/`, `.worktrees/`, `instance/`, `__pycache__/`, `.pytest_cache/`, `*.log`.

- [ ] **Step 1: Copy current source tree**

Use a safe copy command that excludes runtime and git data:

```powershell
robocopy D:\1\codex\jcc\jcc_git D:\1\codex\jcc-new\jcc-web-service /E /XD .git .worktrees instance __pycache__ .pytest_cache /XF *.log
```

Robocopy exit codes `0` through `7` are acceptable.

- [ ] **Step 2: Verify source tree copied**

Run:

```powershell
Test-Path D:\1\codex\jcc-new\jcc-web-service\app.py
Test-Path D:\1\codex\jcc-new\jcc-web-service\templates\index.html
Test-Path D:\1\codex\jcc-new\jcc-web-service\static\app.js
Test-Path D:\1\codex\jcc-new\jcc-web-service\tests
```

Expected: all four commands print `True`.

- [ ] **Step 3: Run baseline tests**

Run:

```powershell
cd D:\1\codex\jcc-new\jcc-web-service
python -m pytest tests -q -p no:cacheprovider
```

Expected: PASS before database adapter work begins. If tests fail because optional local dependencies are missing, install `requirements.txt` and rerun.

- [ ] **Step 4: Commit**

```powershell
git -C D:\1\codex\jcc-new\jcc-web-service add .
git -C D:\1\codex\jcc-new\jcc-web-service commit -m "chore: import current web service"
```

### Task 5: Add Database URL Configuration to Web

**Files:**
- Modify: `D:\1\codex\jcc-new\jcc-web-service\config.py`
- Modify: `D:\1\codex\jcc-new\jcc-web-service\.env.example`
- Test: `D:\1\codex\jcc-new\jcc-web-service\tests\test_config.py`

- [ ] **Step 1: Write failing config test**

Create or update `tests/test_config.py`:

```python
from app import create_app


def test_database_url_defaults_to_sqlite_instance_path():
    app = create_app({'TESTING': True})
    assert app.config['DATABASE_URL'].startswith('sqlite:///')
    assert app.config['DATABASE'].endswith('lineups.sqlite3')


def test_database_url_can_be_configured(monkeypatch):
    monkeypatch.setenv('JCC_DATABASE_URL', 'postgresql://user:pass@database.np5.top:5432/jcc')
    app = create_app({'TESTING': True})
    assert app.config['DATABASE_URL'] == 'postgresql://user:pass@database.np5.top:5432/jcc'
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\1\codex\jcc-new\jcc-web-service
python -m pytest tests/test_config.py -q
```

Expected: FAIL because `DATABASE_URL` is not configured yet.

- [ ] **Step 3: Implement config**

In `config.py`, compute:

```python
default_sqlite_path = os.path.join(app.instance_path, 'lineups.sqlite3')
default_database_url = 'sqlite:///' + default_sqlite_path.replace('\\', '/')
database_url = os.environ.get('JCC_DATABASE_URL', default_database_url)
```

Then configure:

```python
DATABASE=default_sqlite_path,
DATABASE_URL=database_url,
```

Update `.env.example` with:

```text
JCC_DATABASE_URL=sqlite:///instance/lineups.sqlite3
# JCC_DATABASE_URL=postgresql://jcc_app:replace-with-password@database.np5.top:5432/jcc
```

- [ ] **Step 4: Run test**

Run:

```powershell
cd D:\1\codex\jcc-new\jcc-web-service
python -m pytest tests/test_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git -C D:\1\codex\jcc-new\jcc-web-service add config.py .env.example tests/test_config.py
git -C D:\1\codex\jcc-new\jcc-web-service commit -m "feat: add database url configuration"
```

### Task 6: Add Web Database Adapter

**Files:**
- Create: `D:\1\codex\jcc-new\jcc-web-service\db_adapter.py`
- Modify: `D:\1\codex\jcc-new\jcc-web-service\db.py`
- Modify: `D:\1\codex\jcc-new\jcc-web-service\requirements.txt`
- Test: `D:\1\codex\jcc-new\jcc-web-service\tests\test_db_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Create `tests/test_db_adapter.py`:

```python
from db_adapter import database_kind, placeholder, qmarks


def test_database_kind_detects_sqlite():
    assert database_kind('sqlite:///instance/lineups.sqlite3') == 'sqlite'


def test_database_kind_detects_postgres():
    assert database_kind('postgresql://u:p@h:5432/db') == 'postgres'
    assert database_kind('postgres://u:p@h:5432/db') == 'postgres'


def test_placeholder_uses_driver_specific_style():
    assert placeholder('sqlite') == '?'
    assert placeholder('postgres') == '%s'


def test_qmarks_returns_repeated_placeholders():
    assert qmarks('sqlite', 3) == '?,?,?'
    assert qmarks('postgres', 3) == '%s,%s,%s'
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\1\codex\jcc-new\jcc-web-service
python -m pytest tests/test_db_adapter.py -q
```

Expected: FAIL because `db_adapter.py` does not exist.

- [ ] **Step 3: Implement adapter foundation**

Create `db_adapter.py`:

```python
from urllib.parse import urlparse


def database_kind(database_url):
    scheme = urlparse(database_url).scheme
    if scheme in {'postgres', 'postgresql'}:
        return 'postgres'
    if scheme == 'sqlite':
        return 'sqlite'
    raise ValueError(f'Unsupported database URL scheme: {scheme}')


def placeholder(kind):
    return '%s' if kind == 'postgres' else '?'


def qmarks(kind, count):
    return ','.join(placeholder(kind) for _ in range(count))
```

Update `requirements.txt`:

```text
Flask>=3.0
pytest>=8.0
psycopg[binary]>=3.2
```

- [ ] **Step 4: Run adapter tests**

Run:

```powershell
cd D:\1\codex\jcc-new\jcc-web-service
python -m pytest tests/test_db_adapter.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git -C D:\1\codex\jcc-new\jcc-web-service add db_adapter.py requirements.txt tests/test_db_adapter.py
git -C D:\1\codex\jcc-new\jcc-web-service commit -m "feat: add database adapter foundation"
```

### Task 7: Make Web DB Layer Dual-Driver

**Files:**
- Modify: `D:\1\codex\jcc-new\jcc-web-service\db.py`
- Modify: SQL call sites that require `lastrowid`, `?` placeholder generation, `INSERT OR IGNORE`, or metadata queries.
- Test: existing full `tests/` suite plus new adapter-specific tests.

- [ ] **Step 1: Extend tests around inserted IDs and conflict handling**

Add tests proving:

- creating a user returns an ID;
- creating a lineup returns an ID;
- favoriting the same lineup twice remains idempotent;
- visit tracking remains idempotent;
- app settings upsert still works.

Use existing test helpers in `tests/conftest.py`.

- [ ] **Step 2: Run targeted tests to verify current behavior**

Run:

```powershell
cd D:\1\codex\jcc-new\jcc-web-service
python -m pytest tests/test_auth.py tests/test_lineup_write_service.py tests/test_interactions.py tests/test_visits.py tests/test_settings.py -q
```

Expected: PASS on SQLite baseline before code changes.

- [ ] **Step 3: Implement dual-driver connection**

In `db.py`:

- If `DATABASE_URL` is SQLite, keep current `sqlite3.connect`.
- If Postgres, connect with `psycopg.connect`.
- Store `g.db_kind`.
- For PostgreSQL, replace SQLite row behavior with dictionary-like rows using `psycopg.rows.dict_row`.
- Only run SQLite PRAGMAs for SQLite.
- Provide helper functions for `last_insert_id(cursor)` and metadata lookups.

- [ ] **Step 4: Replace SQLite-specific DML**

Update call sites:

- `INSERT OR IGNORE` in `lineup_interaction_service.py` and `visits.py` to dialect helper `insert_ignore_sql(...)`.
- `INSERT OR REPLACE` in `notice_service.py` to a dialect-aware upsert.
- dynamic placeholder lists in `lineups_query.py` and `admin_pagination.py` to use `qmarks(kind, count)`.
- `.lastrowid` in `auth.py`, `lineup_write_service.py`, `admin_user_service.py`, `patch_note_service.py`, and `lineup_interaction_service.py` to use `last_insert_id(cursor)`.

- [ ] **Step 5: Split schema initialization**

Keep SQLite initialization for local tests. For PostgreSQL production, `init_db()` should not attempt to execute SQLite schema. It should either:

- verify `schema_migrations` exists and skip schema creation, or
- run PostgreSQL-compatible migrations shipped in the DB service.

For safety, production Web startup should fail fast with a clear error if `JCC_DATABASE_URL` is PostgreSQL and required tables are missing.

- [ ] **Step 6: Run full SQLite test suite**

Run:

```powershell
cd D:\1\codex\jcc-new\jcc-web-service
python -m pytest tests -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git -C D:\1\codex\jcc-new\jcc-web-service add .
git -C D:\1\codex\jcc-new\jcc-web-service commit -m "feat: support postgres database connections"
```

### Task 8: Add Deployment Documentation and Cutover Runbook

**Files:**
- Create: `D:\1\codex\jcc-new\jcc-db-service\docs\deployment.md`
- Create: `D:\1\codex\jcc-new\jcc-db-service\docs\cutover-runbook.md`
- Modify: `D:\1\codex\jcc-new\jcc-web-service\deploy\jcc.service.example`
- Modify: `D:\1\codex\jcc-new\jcc-web-service\deploy\update.sh`

- [ ] **Step 1: Document database production setup**

`docs/deployment.md` must include:

- create `.env` from `.env.example`;
- start PostgreSQL with Docker Compose;
- set DNS `database.np5.top` to the database host;
- restrict TCP 5432 to Web server IPs;
- never expose PostgreSQL broadly to the public internet;
- run `scripts/apply_migrations.py`;
- run `pg_isready`.

- [ ] **Step 2: Document cutover**

`docs/cutover-runbook.md` must include:

1. pre-cutover backup of `instance/lineups.sqlite3`;
2. start Postgres;
3. apply migrations;
4. run initial migration;
5. run count and integrity verification;
6. deploy Web code with PostgreSQL support but keep SQLite active;
7. during low traffic, enable maintenance/write-freeze;
8. final SQLite backup;
9. final migration to Postgres with `--truncate-target`;
10. verification;
11. update `JCC_DATABASE_URL`;
12. restart Web;
13. test `/api/health`, homepage, login, copy, like, admin;
14. rollback by restoring previous service env and SQLite backup.

- [ ] **Step 3: Update service template**

Add:

```text
Environment="JCC_DATABASE_URL=postgresql://jcc_app:replace-password@database.np5.top:5432/jcc"
```

- [ ] **Step 4: Update Web deploy script**

Change backup logic so it backs up SQLite only when using SQLite. Add a safety message that PostgreSQL backups live in `jcc-db-service`.

- [ ] **Step 5: Commit docs**

```powershell
git -C D:\1\codex\jcc-new\jcc-db-service add docs
git -C D:\1\codex\jcc-new\jcc-db-service commit -m "docs: add postgres deployment runbook"
git -C D:\1\codex\jcc-new\jcc-web-service add deploy
git -C D:\1\codex\jcc-new\jcc-web-service commit -m "docs: document postgres web deployment"
```

## Production Cutover Safety Rules

- Do not change DNS to a new database host until the Web service has run successfully against `database.np5.top` on the current server.
- Keep `JCC_SECRET_KEY` identical across all future Web instances.
- Restrict PostgreSQL access to trusted Web server IPs.
- Keep SQLite backup for rollback until Postgres has run stably through at least one full traffic cycle.
- First phase does not make live-comps JSON/assets multi-instance safe. Do not run multiple Web instances until file-backed live-comps data is migrated or moved to shared storage.

## Verification Checklist

- `jcc-db-service` migration tests pass.
- `jcc-db-service` migration script can import a copy of production SQLite locally.
- `verify_counts.py` reports matching counts for all tables.
- `verify_integrity.py` reports no orphan references.
- `jcc-web-service` full test suite passes on SQLite.
- `jcc-web-service` smoke test passes against PostgreSQL.
- Production `/api/health` returns `{"ok": true}` after cutover.
- Manual smoke tests pass: homepage, login, create lineup, copy lineup, like lineup, favorite lineup, admin overview.

