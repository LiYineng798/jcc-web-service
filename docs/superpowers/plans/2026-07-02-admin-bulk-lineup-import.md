# Admin Bulk Lineup Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an admin-only two-step bulk import flow for regular lineup codes with season selection, parsing preview, confirmation, and duplicate skipping.

**Architecture:** Add shared preview/import service functions to `admin_lineup_service.py`, expose them through `admin.py`, and render a compact import panel inside the existing admin lineups workspace in `static/admin.js`. No database migration is required because imported rows use existing `lineups` columns.

**Tech Stack:** Flask, SQLite/PostgreSQL-compatible SQL through the existing adapter, vanilla admin JavaScript, pytest.

---

### Task 1: Backend Service And API

**Files:**
- Modify: `admin_lineup_service.py`
- Modify: `admin.py`
- Test: `tests/test_admin.py`

- [ ] **Step 1: Write failing backend tests**

Add tests that call `POST /api/admin/lineups/bulk-import/preview` and `POST /api/admin/lineups/bulk-import` as an admin and assert: preview parses without writing rows, selected season is saved after final confirmation, name is taken after the final hyphen, existing codes are skipped, repeated pasted codes are skipped, invalid lines are reported, and non-admin users cannot import.

- [ ] **Step 2: Run focused backend tests and confirm failure**

Run: `python -m pytest tests/test_admin.py::test_admin_can_bulk_import_lineups_with_selected_season_and_deduplication tests/test_admin.py::test_non_admin_cannot_bulk_import_lineups -q`

Expected: fail because the preview endpoint and final import endpoint do not exist.

- [ ] **Step 3: Implement service parsing and import**

Add `parse_bulk_lineup_entries()`, `preview_bulk_import_lineups()`, and `bulk_import_lineups()` in `admin_lineup_service.py`. Use `season_choice_map()` to validate the selected season, `qmarks()` to query existing codes, `insert_returning_id_sql()` and `last_insert_id()` for driver-compatible inserts, and `write_audit()` for one summary audit row.

- [ ] **Step 4: Add Flask route**

Import `preview_bulk_import_lineups` and `bulk_import_lineups` in `admin.py`, then add `@admin_bp.post('/api/admin/lineups/bulk-import/preview')` and `@admin_bp.post('/api/admin/lineups/bulk-import')` guarded by `admin_required()`.

- [ ] **Step 5: Run focused backend tests and confirm pass**

Run: `python -m pytest tests/test_admin.py::test_admin_can_bulk_import_lineups_with_selected_season_and_deduplication tests/test_admin.py::test_non_admin_cannot_bulk_import_lineups -q`

Expected: both tests pass.

### Task 2: Admin UI

**Files:**
- Modify: `static/admin.js`
- Test: `tests/test_ui_routes.py`

- [ ] **Step 1: Write failing UI route test**

Add a static test asserting `static/admin.js` contains the bulk import panel copy, the internal season dropdown, `/api/admin/lineups/bulk-import/preview`, `/api/admin/lineups/bulk-import`, and the confirmation action.

- [ ] **Step 2: Run focused UI test and confirm failure**

Run: `python -m pytest tests/test_ui_routes.py::test_admin_js_contains_lineup_bulk_import_workspace -q`

Expected: fail because the UI strings are absent.

- [ ] **Step 3: Implement admin JS controls**

Extend admin state with `lineupBulkImport`, render a compact import form at the top of `renderLineupsWorkspace()`, load seasons from `/api/lineup-seasons`, use the site's internal dropdown classes for season selection, submit preview requests to `/api/admin/lineups/bulk-import/preview`, render row-level parsing results, and show a separate `确认导入` action that posts to `/api/admin/lineups/bulk-import`.

- [ ] **Step 4: Run focused UI test and confirm pass**

Run: `python -m pytest tests/test_ui_routes.py::test_admin_js_contains_lineup_bulk_import_workspace -q`

Expected: test passes.

### Task 3: Documentation And Verification

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Update repository guide**

Add a short note that the admin "阵容" tab includes bulk import of regular lineup codes with season selection and duplicate skipping.

- [ ] **Step 2: Run focused feature tests**

Run: `python -m pytest tests/test_admin.py::test_admin_can_bulk_import_lineups_with_selected_season_and_deduplication tests/test_admin.py::test_non_admin_cannot_bulk_import_lineups tests/test_ui_routes.py::test_admin_js_contains_lineup_bulk_import_workspace -q`

Expected: all selected tests pass.

- [ ] **Step 3: Run full Web test suite**

Run: `python -m pytest -q`

Expected: all tests pass.
