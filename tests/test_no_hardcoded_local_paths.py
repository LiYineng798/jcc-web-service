import re
from pathlib import Path


FORBIDDEN_TEST_PATH_PATTERNS = (
    re.compile(r'[A-Za-z]:[\\/]{1,2}1[\\/]{1,2}codex', re.IGNORECASE),
    re.compile(r'claude' + r'_project', re.IGNORECASE),
    re.compile(r'jcc_git[\\/]{1,2}\.worktrees', re.IGNORECASE),
)


def test_tests_do_not_reference_local_absolute_project_paths():
    offenders = []
    for path in Path('tests').glob('test_*.py'):
        text = path.read_text(encoding='utf-8')
        for pattern in FORBIDDEN_TEST_PATH_PATTERNS:
            if pattern.search(text):
                offenders.append(f'{path}: {pattern.pattern}')

    assert not offenders, 'hardcoded local paths found:\n' + '\n'.join(offenders)
