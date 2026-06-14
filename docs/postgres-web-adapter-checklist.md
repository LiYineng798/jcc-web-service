# PostgreSQL Web Adapter Checklist

This checklist tracks the remaining work required before the Web service can run real requests against PostgreSQL.

## Current State

- `JCC_DATABASE_URL` is configurable.
- SQLite remains the default local/development database.
- PostgreSQL mode fails fast unless schema readiness is explicitly confirmed.
- Runtime PostgreSQL queries are not enabled yet.

## Required Adapter Work

1. Add real PostgreSQL connections in `db.py`.
   - Use `psycopg.connect`.
   - Use dict-like row factory.
   - Set `g.db_kind`.
   - Implement real `postgres_schema_ready()`.

2. Add SQL helper functions in `db_adapter.py`.
   - Parameter conversion from SQLite `?` to PostgreSQL `%s`.
   - `last_insert_id(cursor)` helper.
   - conflict helpers for insert-ignore and upsert.
   - metadata helpers for table names and columns.

3. Replace insert ID access.
   - `auth.py`
   - `lineup_write_service.py`
   - `lineup_interaction_service.py`
   - `admin_user_service.py`
   - `patch_note_service.py`

4. Replace SQLite-only conflict syntax.
   - `lineup_interaction_service.py`: `INSERT OR IGNORE`.
   - `visits.py`: `INSERT OR IGNORE`.
   - `notice_service.py`: `INSERT OR REPLACE`.
   - `settings_service.py`: `INSERT OR REPLACE`.

5. Replace metadata queries.
   - `db_schema.py`: `PRAGMA table_info`.
   - `db_schema.py`: `sqlite_master`.
   - `db_migrations.py`: avoid SQLite-specific exception handling in PostgreSQL mode.

6. Replace dynamic placeholder generation.
   - `lineups_query.py`: `IN (?, ?, ...)`.
   - `admin_pagination.py`: `LIMIT ? OFFSET ?`.
   - `guestbook_service.py`: `LIMIT ? OFFSET ?`.

7. Audit date SQL.
   - Current date values are stored as text.
   - Keep text format for first migration to reduce risk.
   - Existing `substr(created_at, 1, 10)` can continue working in PostgreSQL text columns.

8. Add PostgreSQL integration smoke tests.
   - Apply DB service migrations to a test database.
   - Import a sample SQLite database.
   - Start Flask with PostgreSQL URL.
   - Exercise `/api/health`, `/api/me`, `/api/lineups`, create lineup, copy, like, favorite.

## Cutover Guardrails

- Do not set production `JCC_DATABASE_URL` until PostgreSQL runtime queries pass smoke tests.
- Do not run multiple Web instances until file-backed live-comps state is moved to PostgreSQL or shared storage.
- Keep SQLite backup and rollback path intact until PostgreSQL has served production traffic through one full traffic cycle.

