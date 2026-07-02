# Admin Bulk Lineup Import Design

## Goal

Allow administrators to paste many regular lineup-code snippets into the admin console, choose a season, and import only new lineups.

## Admin Entry

The feature belongs in the existing admin "阵容" tab because it creates and maintains regular lineup-library content. It should appear above the lineup search controls as a compact import panel, not as a new top-level admin tab. The season picker uses the site's existing `account-menu`/`season-toggle` dropdown pattern instead of a native select.

## Input Format

Each non-empty line may contain one lineup snippet shaped like:

```text
【阵容码】#Suyu-星守岩雀#MjIwMDQ2MDI3MjA4Mzk1NjkxNzgyNzM4MDk2MTQ2
```

The first hash-delimited segment is the display-name source. If it contains a hyphen, the saved lineup name is the text after the last hyphen. If there is no hyphen, the whole segment is used. The second segment is normalized to the existing `#CODE` lineup-code form.

## API

Add two admin-only endpoints:

- `POST /api/admin/lineups/bulk-import/preview` parses and validates pasted text without writing rows.
- `POST /api/admin/lineups/bulk-import` re-parses, re-checks duplicates, and writes importable rows after admin confirmation.

Payload:

```json
{
  "season_id": "s17-star-god",
  "raw_text": "【阵容码】#Suyu-星守岩雀#MjIw..."
}
```

Both endpoints are admin-only and use the existing CSRF protection.

## Import Behavior

Admins must preview before importing. The preview shows importable, database-duplicate, upload-duplicate, and invalid rows so admins can review parsed names and codes before confirming. The current admin user becomes the owner of imported lineups. Imported rows use the selected `season_id` and `normal` status.

Deduplication happens in two places:

- If the same normalized code appears more than once in the pasted text, only the first occurrence is imported.
- If the normalized code already exists in `lineups`, including hidden or soft-deleted rows, the uploaded entry is skipped.

Invalid lines are skipped and returned in the response with a reason. A missing season, hidden/disabled season, or empty paste returns `400`.

## Response

Preview returns `importable_count` with item statuses such as `importable`, `duplicate_existing`, `duplicate_in_upload`, and `invalid`. Final import returns the same shape, with successfully written rows changed to `created` and `created_count` populated:

```json
{
  "ok": true,
  "season_id": "s17-star-god",
  "importable_count": 0,
  "created_count": 1,
  "duplicate_existing_count": 1,
  "duplicate_in_upload_count": 1,
  "invalid_count": 1,
  "items": [
    {"line": 1, "name": "星守岩雀", "code": "#MjIw...", "status": "created", "id": 12}
  ]
}
```

## Testing

Backend tests cover preview without writes, parsing, selected-season writes, existing-code skip, upload-internal duplicate skip, invalid-line reporting, and admin-only permission. UI route tests cover that the admin JS contains the internal dropdown controls, preview API call, final import API call, and confirmation action.
