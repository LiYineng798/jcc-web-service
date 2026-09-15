from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT.parent / 'webApplication'

INCLUDE_FILES = {'.gitignore', '.env.example', 'README.md', 'AGENTS.md', 'requirements.txt', 'captcha_manifest.json'}
INCLUDE_DIRS = {'static', 'templates', 'docs', 'deploy'}
INCLUDE_PARTS = {'scripts/maintenance', 'scripts/season_library'}
EXCLUDE_PARTS = {'instance', '__pycache__', '.pytest_cache', '.git', 'scripts/local'}
EXCLUDE_SUFFIXES = {'.pyc', '.pyo', '.sqlite3', '.db', '.log', '.pem', '.key', '.crt'}


def should_copy(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    rel_text = rel.as_posix()
    if set(rel.parts) & EXCLUDE_PARTS:
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    if rel_text in INCLUDE_FILES:
        return True
    if len(rel.parts) == 1 and path.suffix == '.py':
        return True
    if rel.parts[0] in INCLUDE_DIRS:
        return True
    return any(rel_text.startswith(part + '/') for part in INCLUDE_PARTS)


def clean_target() -> None:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.mkdir(parents=True)


def export() -> int:
    # Export only tracked working-tree files. Do not traverse worktrees, local
    # source bundles or ignored scratch files, even when they have a .py suffix.
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    sources = [ROOT / name for name in tracked if name and (ROOT / name).is_file() and should_copy(ROOT / name)]
    clean_target()
    copied = 0
    for path in sources:
        rel = path.relative_to(ROOT)
        target = TARGET / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    print(f'已导出 {copied} 个文件到 {TARGET}')
    return 0


if __name__ == '__main__':
    raise SystemExit(export())
