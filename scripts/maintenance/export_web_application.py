from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT.parent / 'webApplication'

INCLUDE_FILES = {
    '.gitignore', 'README.md', 'admin.py', 'admin_audit_service.py', 'admin_dashboard_service.py', 'admin_live_comp_service.py', 'admin_lineup_service.py', 'admin_pagination.py', 'admin_report_service.py', 'admin_user_service.py', 'analytics.py', 'app.py', 'app_pages.py', 'audit.py',
    'auth.py', 'captcha.py', 'captcha_manifest.json', 'config.py', 'db.py', 'db_migrations.py', 'db_schema.py',
    'history.py', 'lineup_account_service.py', 'lineup_bridge_service.py', 'lineup_interaction_service.py', 'lineup_read_service.py', 'lineup_write_service.py', 'lineups.py', 'lineups_query.py', 'lineups_serialization.py', 'lineups_utils.py', 'lineup_code.py', 'live_comps.py', 'live_comps_helpers.py', 'migrate.py',
    'rate_limit.py', 'recommendation.py', 'requirements.txt', 'route_response.py', 'run_server.py',
    'scoring.py', 'visits.py', '.env.example',
}
INCLUDE_DIRS = {'static', 'templates', 'tests', 'docs', 'deploy'}
INCLUDE_PARTS = {'scripts/maintenance'}
EXCLUDE_PARTS = {'instance', '__pycache__', '.pytest_cache', '.git', 'scripts/local'}
EXCLUDE_SUFFIXES = {'.pyc', '.pyo', '.sqlite3', '.db', '.log', '.pem', '.key', '.crt'}
EXCLUDE_FILES = {'tests/test_refresh_live_comps.py', 'tests/test_upload_live_comps.py'}


def should_copy(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    rel_text = rel.as_posix()
    if rel_text in EXCLUDE_FILES:
        return False
    if set(rel.parts) & EXCLUDE_PARTS:
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    if rel_text in INCLUDE_FILES:
        return True
    if rel.parts[0] in INCLUDE_DIRS:
        return True
    return rel_text.startswith('scripts/maintenance/')


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
