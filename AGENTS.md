# Repository Guidelines

This is the Web service repository for the JCC workspace. Make Web/API/UI changes here and commit them in this repository.

The sibling `..\jcc-db-service` repository owns PostgreSQL migrations, database import/export tooling, backups, restores, and database deployment runbooks. Do not edit database-service files from this repository. If a Web change depends on new database schema or seed data, make and deploy the DB-service change first, then commit the Web change here.

The parent `..\` directory is only a local coordination workspace and may also contain delivery artifacts such as `.sqlite3`, `.tar`, `.bundle`, or worktree files. Do not use the parent repository for normal feature commits.

For Web behavior changes, add or update focused tests under `tests/` and run at least the affected test subset with `python -m pytest -q`.

Homepage S8 return-season information is grouped under the `S8回归信息差` navigation menu in `templates/index.html`. The menu keeps the existing S8 icon and links to `/tools/special-mechanics` and `/tools/returning-equipment`.

The `/tools/returning-equipment` page uses `templates/returning_equipment.html`, `static/returning-equipment.js`, `static/returning-equipment.css`, and local images under `static/returning-equipment/`. Keep these assets inside the Web repository so production deployments do not depend on files from the parent `图片/` workspace.
