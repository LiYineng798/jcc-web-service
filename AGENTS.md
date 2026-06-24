# Repository Guidelines

This is the Web service repository for the JCC workspace. Make Web/API/UI changes here and commit them in this repository.

The sibling `..\jcc-db-service` repository owns PostgreSQL migrations, database import/export tooling, backups, restores, and database deployment runbooks. Do not edit database-service files from this repository. If a Web change depends on new database schema or seed data, make and deploy the DB-service change first, then commit the Web change here.

The parent `..\` directory is only a local coordination workspace and may also contain delivery artifacts such as `.sqlite3`, `.tar`, `.bundle`, or worktree files. Do not use the parent repository for normal feature commits.

For Web behavior changes, add or update focused tests under `tests/` and run at least the affected test subset with `python -m pytest -q`.

Homepage S8 return-season information is grouped under the `S8回归信息差` navigation menu in `templates/index.html`. The menu keeps the existing S8 icon and links to `/tools/special-mechanics` and `/tools/returning-equipment`.

The `/tools/special-mechanics` page is a static S8 reference page. Each card shows one rank badge for the currently visible category only, and the rank mapping is maintained in `static/special-mechanics.js` alongside the card data.

The `/tools/returning-equipment` page uses `templates/returning_equipment.html`, `static/returning-equipment.js`, `static/returning-equipment.css`, and local images under `static/returning-equipment/`. Keep these assets inside the Web repository so production deployments do not depend on files from the parent `图片/` workspace.

The homepage hero stat card shows all-site public regular lineup collection size from `/api/home-stats`. Current displayed result count is list context, not site context, and belongs near the list heading through `#currentDisplayCount`.

Live comp season configuration is stored in the live comp season manifest and normalized by `live_comps_helpers.py`. Admin season order changes update each season's `order` and compact the list to `1..N`. The public homepage season menu (`/api/live-comps/seasons`) and lineup create/edit season selector (`/api/lineup-seasons`) both follow this same order, while hidden or disabled seasons stay out of public/user-facing selectors.
