"""Build an explicitly reviewed source offer without credentials or runtime data."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SUFFIXES = {'.py', '.js', '.cjs', '.mjs', '.ts', '.tsx', '.css', '.html', '.sql', '.md', '.txt', '.json', '.toml', '.yml', '.yaml', '.sh'}


EXTRA_WEB_SOURCE_FILES = {
    'docs/avatar-system.md', 'frontend/avatar.ts', 'frontend/avatar-presets.json',
    'frontend/avatar-presets.NOTICE.txt', 'static/avatar-lab/app.js',
    'static/avatar-lab/THIRD_PARTY_NOTICES.txt', 'static/avatar-source.css',
    'templates/avatar_source.html', 'scripts/maintenance/import_avatar_presets.py',
    'scripts/maintenance/build_avatar_source.py', 'tests/avatar_lab_rendering.py',
    'tests/avatar_lab_performance.py', 'tests/avatar_gallery_rendering.py', 'tests/serve_avatar_preview.py',
    'tests/test_avatar_source.py', 'tests/avatar_compact_rendering.py', 'tests/avatar_feedback_rendering.py',
}


def source_files(root, extras=()):
    names = subprocess.check_output(
        ['git', '-C', str(root), 'ls-files', '-z', '--cached']
    ).decode('utf-8').split('\0')
    # Never sweep untracked files: a developer's private JSON can look like source.
    for name in sorted(set(filter(None, names)) | set(extras)):
        path = Path(name)
        if path.parts[0] in {'instance', '.claude', '.git', '.venv', 'node_modules'}:
            continue
        if any(part in {'node_modules', '__pycache__', '.worktrees'} for part in path.parts):
            continue
        if name.startswith('test-') and path.suffix == '.json':
            continue
        if name.startswith(('static/season-data/', 'static/tools/lineup-simulator/data/', 'scripts/local/')):
            continue
        if path.suffix not in SOURCE_SUFFIXES and path.name not in {'LICENSE', 'AGENTS.md', '.gitignore'}:
            continue
        if (root / path).is_file():
            yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db-source', required=True, type=Path)
    parser.add_argument('--upstream', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'instance/avatar-source/source.zip')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for label, root in [('jcc-web-service', ROOT), ('jcc-db-service', args.db_source)]:
            extras = EXTRA_WEB_SOURCE_FILES if root == ROOT else {'migrations/0018_avatar_config.sql', 'migrations/0019_avatar_preset_expansion.sql', 'migrations/0020_avatar_expression_expansion.sql'}
            for path in source_files(root, extras):
                content = (root / path).read_bytes()
                name = f'{label}/{path.as_posix()}'
                archive.writestr(name, content)
                manifest[name] = hashlib.sha256(content).hexdigest()
        for package in ('avatar-core', 'avatar-web'):
            root = args.upstream / 'packages' / package
            for path in root.rglob('*'):
                if path.is_file() and 'node_modules' not in path.parts and path.suffix != '.map':
                    archive.write(path, f'upstream/packages/{package}/{path.relative_to(root).as_posix()}')
            # Published maps contain the exact preferred-form sources of the pinned npm build.
            installed = ROOT / 'frontend/node_modules/@bible-strong' / package
            sources = {}
            for mapping in (installed / 'dist').glob('*.js.map'):
                data = json.loads(mapping.read_text(encoding='utf-8'))
                for name, content in zip(data['sources'], data['sourcesContent']):
                    if content is None or not name.startswith('../src/'):
                        raise ValueError(f'Unrecognized runtime source map: {name}')
                    sources[name.removeprefix('../')] = content
            if not sources:
                raise ValueError(f'Missing exact runtime sources for {package}; run npm ci first')
            for name, content in sources.items():
                archive.writestr(f'installed-runtime/{package}/{name}', content)
            archive.write(installed / 'package.json', f'installed-runtime/{package}/package.json')
            archive.write(installed / 'LICENSE', f'installed-runtime/{package}/LICENSE')
        for name in ('LICENSE', 'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml'):
            archive.write(args.upstream / name, 'upstream/' + name)
        archive.write(args.upstream / 'src/features/studio/defaultStudioDocument.json', 'upstream/defaultStudioDocument.json')
        archive.writestr('SOURCE_MANIFEST.json', json.dumps(manifest, indent=2))
        archive.writestr('README.txt', 'Local avatar preview corresponding source. JCC integration: AGPL-3.0-only.\n'
                          'See jcc-web-service/docs/avatar-system.md for build and deployment steps.\n'
                          'installed-runtime/ contains the exact 0.1.0 preferred-form sources extracted from published source maps.\n'
                          'upstream/ contains the pinned studio preset source and reference package build configs.\n'
                          'Excluded: credentials, user/runtime data, third-party game artwork and generated season datasets.\n'
                          'The source is provided as a local preview, not a claim of production legal review.\n')
    print(f'{args.output} ({args.output.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
