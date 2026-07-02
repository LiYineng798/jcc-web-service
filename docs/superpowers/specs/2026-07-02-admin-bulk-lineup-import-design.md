# Admin Bulk Lineup Import Design

## Goal

Allow administrators to paste many regular lineup-code snippets into the admin console, choose a season, and import only new lineups.

## Admin Entry

The feature belongs in the existing admin "阵容" tab because it creates and maintains regular lineup-library content. It should appear above the lineup search controls as a compact import panel, not as a new top-level admin tab.

## Input Format

Each non-empty line may contain one lineup snippet shaped like:

```text
【阵容码】#Suyu-星守岩雀#MjIwMDQ2MDI3MjA4Mzk1NjkxNzgyNzM4MDk2MTQ2
```

The first hash-delimited segment is the display-name source. If it contains a hyphen, the saved lineup name is the text after the last hyphen. If there is no hyphen, the whole segment is used. The second segment is normalized to the existing `#CODE` lineup-code form.

## API

Add `POST /api/admin/lineups/bulk-import`.

Payload:

```json
{
  "season_id": "s17-star-god",
  "raw_text": "【阵容码】#Suyu-星守岩雀#MjIw..."
}
```

The endpoint is admin-only and uses the existing CSRF protection.

## Import Behavior

The current admin user becomes the owner of imported lineups. Imported rows use the selected `season_id` and `normal` status.

Deduplication happens in two places:

- If the same normalized code appears more than once in the pasted text, only the first occurrence is imported.
- If the normalized code already exists in `lineups`, including hidden or soft-deleted rows, the uploaded entry is skipped.

Invalid lines are skipped and returned in the response with a reason. A missing season, hidden/disabled season, or empty paste returns `400`.

## Response

Return a summary with counts and item-level statuses:

```json
{
  "ok": true,
  "season_id": "s17-star-god",
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

Backend tests cover parsing, selected-season writes, existing-code skip, upload-internal duplicate skip, invalid-line reporting, and admin-only permission. UI route tests cover that the admin JS contains the bulk import controls and API call.
