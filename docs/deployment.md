# JCC Web Service Deployment

This repository is the source of truth for the production Web/API service.

Do not continue feature work in the old `jcc_git` repository. The old server
directory is kept only as a rollback point.

## Current Production Layout

| Item | Value |
|---|---|
| Public site | `https://jcc.np5.top` |
| Web server | `103.23.148.135` |
| Web service directory | `/opt/jcc/jcc-web-service` |
| Old rollback directory | `/opt/jcc/jcc_git` |
| systemd service | `jcc.service` |
| systemd working directory | `/opt/jcc/jcc-web-service` |
| systemd env file | `/etc/jcc.env` |
| Database server | `103.23.148.85` |
| Database env key | `JCC_DATABASE_URL` |

Sensitive values such as database passwords, admin passwords, upload tokens, and
SSH passwords must not be committed to this repository.

## What This Repository Owns

- Flask routes and business logic.
- Frontend templates, CSS, and JavaScript.
- Static assets under `static/`.
- Runtime handling for local live-comps files under `instance/`.
- Web-side PostgreSQL adapter code.

It does not own PostgreSQL schema migrations. Those live in `jcc-db-service`.

## Runtime Files Still Stored On The Web Server

The database is already separated, but image and runtime files are still local
to the Web server:

```text
/opt/jcc/jcc-web-service/static
/opt/jcc/jcc-web-service/instance/live-comps-assets
/opt/jcc/jcc-web-service/instance/live-comps.json
/opt/jcc/jcc-web-service/instance/live-comps.previous.json
/opt/jcc/jcc-web-service/instance/live-comps-seasons
/opt/jcc/jcc-web-service/instance/live-comps-manual-codes
```

Do not deploy multiple Web servers for production traffic until these runtime
files are moved to shared storage, object storage, CDN, or another synchronization
strategy. Multiple Web servers can share PostgreSQL today, but they will not
share these local image/runtime files yet.

## Local Development Workflow

Use this repository for Web changes:

```powershell
cd D:\1\codex\jcc-new\jcc-web-service
git pull origin main
```

Make changes, then run tests:

```powershell
python -m pytest -q
```

If the full suite has an unrelated legacy UI assertion, run the focused tests for
the area you changed and mention the known gap in the handoff.

Commit and push:

```powershell
git add .
git commit -m "describe the change"
git push origin main
```

## Production Web Update

SSH to the Web server, then run:

```bash
cd /opt/jcc/jcc-web-service
git pull origin main
. .venv/bin/activate
pip install -r requirements.txt
systemctl restart jcc
curl -fsS http://127.0.0.1:5000/api/health
```

`gunicorn` and `psycopg[pool]` are part of `requirements.txt`; the service unit
runs `gunicorn -c deploy/gunicorn.conf.py app:app` (2 gthread workers x 4
threads, sized for the 2C/2G host). When `deploy/nginx.conf.example` or
`deploy/jcc.service.example` change, re-apply them manually:

```bash
# compare and update the live configs
diff /etc/nginx/sites-available/jcc deploy/nginx.conf.example
diff /etc/systemd/system/jcc.service deploy/jcc.service.example
# after updating:
nginx -t && systemctl reload nginx
systemctl daemon-reload && systemctl restart jcc
```

Also verify from the public domain:

```bash
curl -fsS https://jcc.np5.top/api/health
```

Expected health response:

```json
{"ok": true}
```

## Production Smoke Test

After every deployment, check:

```bash
systemctl is-active jcc
systemctl status jcc --no-pager
journalctl -u jcc -n 80 --no-pager
curl -fsS http://127.0.0.1:5000/api/health
curl -fsS 'http://127.0.0.1:5000/api/lineups?page=1&page_size=3'
```

Confirm the process is using PostgreSQL:

```bash
pid=$(systemctl show -p MainPID --value jcc)
tr '\0' '\n' < /proc/$pid/environ | grep '^JCC_DATABASE_URL='
```

Redact the password before sharing output.

## Web Rollback

For a normal code rollback:

```bash
cd /opt/jcc/jcc-web-service
git log --oneline -10
git checkout <previous_commit>
systemctl restart jcc
curl -fsS http://127.0.0.1:5000/api/health
```

To return systemd to the old `jcc_git` directory:

```bash
cp /etc/systemd/system/jcc.service.pre-webdir.20260606-162718 /etc/systemd/system/jcc.service
systemctl daemon-reload
systemctl restart jcc
curl -fsS http://127.0.0.1:5000/api/health
```

Use this only if the new directory itself is broken. The old directory exists at:

```text
/opt/jcc/jcc_git
```

## When A Change Also Needs Database Work

If a Web change depends on new tables, columns, indexes, or seed data:

1. Implement and deploy the migration in `jcc-db-service`.
2. Run the migration on the database server.
3. Verify database integrity.
4. Deploy this Web repository.
5. Restart and smoke-test `jcc.service`.

This order prevents new Web code from starting before the database shape exists.
