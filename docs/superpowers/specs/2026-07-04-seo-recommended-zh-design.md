# SEO Recommended Chinese Search Design

## Purpose

Improve organic discovery for the JCC web service, with Baidu and Chinese search engines as the primary target. The first phase should make public pages crawlable, understandable, and shareable without changing the core product workflows.

## Current State

The site already has public pages for the homepage, lineup details, author profiles, tools, and patch notes. Most templates include only a basic `<title>`. Key dynamic pages such as `/lineup/<id>`, `/author/<username>`, and `/patch-notes/<id>` render meaningful page content through JavaScript after load, so their initial HTML is thin. The repository does not currently expose `robots.txt` or `sitemap.xml`, and there is no canonical URL policy for public versus account/admin/API pages.

## Goals

- Add unique SEO metadata for public pages: title, description, canonical URL, and social preview fields.
- Render useful first-load HTML for high-value public pages:
  - lineup detail pages,
  - author profile pages,
  - patch note detail pages.
- Add crawler entry points through `robots.txt` and `sitemap.xml`.
- Keep private, administrative, account, authentication, editor, and API surfaces out of the index.
- Preserve the existing JavaScript interactions for copy, like, favorite, report, filters, pagination, and admin workflows.

## Non-Goals

- Do not create bulk keyword landing pages.
- Do not add new database tables or migrations.
- Do not change ranking, recommendation, scoring, login, account, admin, or live comp behavior.
- Do not remove existing client-side rendering; server-rendered content should be a crawlable fallback and first paint enhancement.
- Do not implement external search engine submission APIs in this phase. Baidu Search Resource Platform submission can be handled operationally after deployment using the generated sitemap.

## SEO Policy

Public indexable pages:

- `/`
- `/lineup/<id>` for visible public lineups only
- `/author/<username>` for public authors with visible content
- `/patch-notes`
- `/patch-notes/<id>` for published patch notes only
- Public tool/reference pages:
  - `/tools/lineup-simulator` when enabled
  - `/tools/special-mechanics`
  - `/tools/artifact-guide`
  - `/tools/returning-equipment`

Noindex or disallowed surfaces:

- `/admin`
- `/api/*`
- `/auth` and `/auth/register`
- `/me`
- `/lineup/new`
- `/lineup/<id>/edit`
- hidden, disabled, draft, unpublished, or permission-protected content
- author pages that exist but have no visible public lineup content

Canonical URLs should use clean path-only public URLs. Query-driven homepage states such as search, sort, view, season, and page should not create separate canonical pages in this phase.

## Architecture

Add a small SEO helper layer in the web service rather than scattering metadata logic across templates. The helper should:

- build absolute canonical URLs from request context,
- provide default site metadata,
- provide page-specific metadata,
- serialize JSON-LD safely where needed,
- keep `noindex` decisions explicit.

Templates should share a common head partial or macro so metadata behavior is consistent. Existing templates can pass a `seo` object into this shared head. Pages that are not yet migrated can use default values.

Page route handlers should fetch enough public data to render first-load HTML for SEO-sensitive pages. Existing API endpoints and page JavaScript should continue to work from the same URLs.

## Page Design

### Homepage

The homepage should describe the site as a Chinese-language Gold Spatula lineup library with lineup codes, real-time lineup rankings, search, favorites, and public lineup sharing. The page should include:

- unique title and description,
- canonical URL `/`,
- `WebSite` JSON-LD with site name and URL,
- a crawlable heading and intro copy already present in the template.

### Lineup Detail

The server should load the requested lineup using existing read service rules. If the lineup is not visible, return the existing 404-style response behavior.

Initial HTML should include:

- lineup name in the title and visible heading,
- season name or season ID,
- author display name and author link when available,
- like count, copy count, rank level,
- a shortened or masked lineup code preview,
- updated time,
- canonical URL `/lineup/<id>`,
- JSON-LD suitable for a content page, such as `WebPage` with breadcrumb data.

The existing `lineup-detail.js` should still hydrate the page and render the full interactive detail view.

### Author Profile

The server should fetch the public author profile and a small list of visible public lineups. Initial HTML should include:

- author display name,
- public interaction summary when available,
- links to recent or popular public lineups,
- canonical URL `/author/<username>`.

If the author does not exist, the route should return a not-found response instead of a thin loading shell.

If the author exists but has no visible public lineup content, the route may render a normal user-facing empty state, but it should be marked noindex and excluded from `sitemap.xml`.

### Patch Note Detail

The server should fetch only published patch notes. Initial HTML should include:

- patch note title,
- version,
- published date,
- parsed summary content,
- source link when valid and public,
- canonical URL `/patch-notes/<id>`,
- `Article` JSON-LD.

Draft and hidden patch notes should not be indexable.

### Patch Note List And Tool Pages

These pages should get static metadata and canonical URLs. Existing content can remain mostly unchanged, but the metadata should be complete and noindex should not be applied to public reference pages.

## Sitemap

Add `GET /sitemap.xml` that returns XML with canonical public URLs:

- static public pages,
- visible public lineup detail pages,
- public author pages with visible lineups,
- published patch notes.

Use `updated_at` for lineups and authors when available, `published_at` or `updated_at` for patch notes, and omit private or hidden content. The response should use `application/xml` or a correct XML mimetype.

## Robots

Add `GET /robots.txt` with:

- `Allow: /`
- `Disallow` rules for admin, API, auth, account, and editor routes,
- a `Sitemap:` line containing the absolute `/sitemap.xml` URL built from the request host.

This file should not block public static assets needed for rendering.

## Error Handling

- If a public detail page references missing or hidden content, return 404 and keep it out of the sitemap.
- If sitemap generation hits malformed optional data, skip only the bad optional field and keep the sitemap valid.
- If a route cannot build page-specific SEO metadata, fall back to site defaults rather than failing the request.

## Testing

Add focused tests under `tests/` for:

- public pages include title, description, canonical, and expected index/noindex directives,
- private/admin/auth/editor/account pages are noindex or disallowed as designed,
- `robots.txt` includes expected disallow rules and sitemap location,
- `sitemap.xml` includes public pages and excludes hidden/draft/private pages,
- lineup detail initial HTML contains crawlable lineup data,
- author initial HTML contains crawlable public author data,
- patch note detail initial HTML contains crawlable published content,
- existing full test suite continues to pass with `python -m pytest -q`.

## Deployment Notes

No database migration is required. Production should deploy the web service only. After deployment, the operator should verify:

- `/robots.txt`
- `/sitemap.xml`
- `/lineup/<public-id>`
- `/author/<public-username>`
- `/patch-notes/<published-id>`

Then submit or refresh the sitemap in Baidu Search Resource Platform and any other search consoles used by the site.
