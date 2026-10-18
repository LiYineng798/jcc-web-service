"""Check publication candidates without printing matched secrets (stdlib only)."""
from __future__ import annotations

import argparse
import ipaddress
import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {
    'instance', 'private', 'backups', 'deploy-backups', 'postgres-backups',
    'ssl-export', 'season-library', '.worktrees', 'worktrees', '__pycache__',
    '.pytest_cache', '.venv', 'node_modules', 'webApplication', '.ssh', '.aws', '.kube',
}
FORBIDDEN_SUFFIXES = (
    '.sqlite', '.sqlite-wal', '.sqlite-shm', '.sqlite3', '.sqlite3-wal', '.sqlite3-shm', '.db', '.db-wal',
    '.db-shm', '.dump', '.sql.gz', '.log', '.pem', '.key', '.crt', '.p12',
    '.pfx', '.p8', '.bak', '.zip', '.tar', '.tar.gz', '.tgz', '.7z', '.rar',
    '.local.json', '.local.yml', '.local.yaml',
)
PRIVATE_KEY = re.compile(r'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----')
TOKEN = re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16}|sk_live_[A-Za-z0-9]{20,})\b')
CREDENTIAL_URL = re.compile(r'\b[a-z][a-z0-9+.-]*://([^\s:/\'"<>]+):([^\s@/\'"<>]+)@([^\s/\'"<>]+)', re.I)
IPV4 = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')
DOCUMENTATION_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    '192.0.2.0/24', '198.51.100.0/24', '203.0.113.0/24',
))
HOST_IPV4 = re.compile(r'(?:[a-z][a-z0-9+.-]*://(?:[^\s/@]+@)?|\bHostName\s+|ssh\s+(?:[^\s@]+@)?)(\d{1,3}(?:\.\d{1,3}){3})\b', re.I)
WORKSTATION_PATH = re.compile(r'\b[A-Za-z]:[/\\](?:Users[/\\]|1[/\\]codex[/\\])', re.I)
CONFIG_SUFFIXES = {'.md', '.sh', '.example', '.yml', '.yaml', '.toml', '.ini', '.conf', '.service'}


def forbidden_path(name: str) -> bool:
    path = PurePosixPath(name.replace('\\', '/'))
    base = path.name.lower()
    environment = base == '.env' or base.startswith('.env.') or base.endswith('.env')
    example = base == '.env.example' or (base.startswith('.env.') and base.endswith('.example'))
    return (
        bool(set(path.parts) & FORBIDDEN_PARTS)
        or (environment and not example)
        or base.endswith(FORBIDDEN_SUFFIXES)
        or base in {'id_rsa', 'id_ed25519', 'deployment-history.md'}
        or base.endswith('-production-deployment.md')
        or ('deploy' in path.parts and path.suffix in {'.conf', '.service'})
    )


def placeholder_password(password: str, host: str) -> bool:
    if password.startswith(('replace-with-', '${', '%24%7B')):
        return True
    hostname = host.split(':', 1)[0].lower()
    example_host = hostname in {'localhost', '127.0.0.1', 'example.com', 'example.test'} or hostname.endswith(('.example.com', '.example.test', '.invalid'))
    return example_host and password in {'pass', 'password', 'test', 'test-password'}


def scan_content(name: str, data: bytes) -> list[tuple[int, str]]:
    if b'\0' in data:
        return []
    text = data.decode('utf-8-sig', errors='replace')
    findings = []
    config_file = PurePosixPath(name).suffix in CONFIG_SUFFIXES
    for number, line in enumerate(text.splitlines(), 1):
        if PRIVATE_KEY.search(line):
            findings.append((number, 'private-key'))
        if TOKEN.search(line):
            findings.append((number, 'access-token'))
        for match in CREDENTIAL_URL.finditer(line):
            if not placeholder_password(match[2], match[3]):
                findings.append((number, 'credential-url'))
        if WORKSTATION_PATH.search(line):
            findings.append((number, 'personal-workstation-path'))
        addresses = [match[0] for match in IPV4.finditer(line)] if config_file else [match[1] for match in HOST_IPV4.finditer(line)]
        for candidate in addresses:
            try:
                address = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if address.is_loopback or address.is_unspecified or any(address in net for net in DOCUMENTATION_NETWORKS):
                continue
            findings.append((number, 'non-example-ipv4'))
    return sorted(set(findings))


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


def candidates(root: Path, worktree: bool):
    if worktree:
        names = git(root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').decode('utf-8').split('\0')
        for name in sorted(set(names) - {''}):
            path = root / name
            if path.is_symlink():
                yield name, b'', 'symlink'
            elif path.is_file():
                yield name, path.read_bytes(), ''
        return

    entries = []
    for entry in git(root, 'ls-files', '--stage', '-z').split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        mode, oid, stage = metadata.decode('ascii').split()
        entries.append((name.decode('utf-8'), mode, oid, stage))
    # Read the actual index blobs, not worktree files that may differ after git add.
    with subprocess.Popen(['git', '-C', str(root), 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as proc:
        try:
            for name, mode, oid, stage in entries:
                if stage != '0' or mode not in {'100644', '100755'}:
                    yield name, b'', 'unmerged-or-nonregular-entry'
                    continue
                proc.stdin.write((oid + '\n').encode('ascii'))
                proc.stdin.flush()
                header = proc.stdout.readline().split()
                if len(header) != 3 or header[1] != b'blob':
                    raise ValueError('Cannot read index blob')
                size = int(header[2])
                data = proc.stdout.read(size)
                if len(data) != size or proc.stdout.read(1) != b'\n':
                    raise ValueError('Incomplete index blob')
                yield name, data, ''
        finally:
            proc.stdin.close()
        if proc.wait() != 0:
            raise ValueError('Git blob reader failed')


def check(root: Path, worktree: bool = False) -> list[tuple[str, int, str]]:
    findings = []
    for name, data, error in candidates(root, worktree):
        if forbidden_path(name):
            findings.append((name, 0, 'private-or-generated-file'))
        if error:
            findings.append((name, 0, error))
        findings.extend((name, line, rule) for line, rule in scan_content(name, data))
    return sorted(set(findings))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worktree', action='store_true', help='Check tracked and non-ignored untracked working files instead of the complete Git index')
    args = parser.parse_args(argv)
    try:
        findings = check(ROOT, worktree=args.worktree)
    except (OSError, ValueError, subprocess.SubprocessError):
        print('Repository safety check could not complete; publication blocked.')
        return 2
    for name, line, rule in findings:
        print(f'{name}:{line}: {rule}')
    if findings:
        print(f'Publication blocked: {len(findings)} finding(s). Matched values are never printed.')
        return 1
    print('Repository safety checks passed (' + ('worktree' if args.worktree else 'Git index') + '). This is not a complete secret/history audit.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
