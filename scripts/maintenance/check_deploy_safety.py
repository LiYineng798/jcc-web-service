from __future__ import annotations

import subprocess
import sys

FORBIDDEN_SUFFIXES = ('.sqlite3', '.db', '.pem', '.key', '.crt', '.log')
FORBIDDEN_PARTS = {'instance', 'ssl-export', '__pycache__', '.pytest_cache'}


def run_git(args: list[str]) -> list[str]:
    result = subprocess.run(['git', *args], capture_output=True, text=True, check=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_forbidden(path: str) -> bool:
    normalized = path.replace('\\', '/')
    parts = set(normalized.split('/'))
    return normalized.endswith(FORBIDDEN_SUFFIXES) or bool(parts & FORBIDDEN_PARTS)


def main() -> int:
    tracked = run_git(['ls-files'])
    staged = run_git(['diff', '--cached', '--name-only'])
    problems = sorted({path for path in tracked + staged if is_forbidden(path)})
    if problems:
        print('发现禁止提交的文件：', file=sys.stderr)
        for path in problems:
            print(f'- {path}', file=sys.stderr)
        return 1
    print('部署安全检查通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
