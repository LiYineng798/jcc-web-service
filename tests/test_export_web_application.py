from scripts.maintenance.export_web_application import ROOT, should_copy


def test_export_includes_maintenance_scripts():
    assert should_copy(ROOT / 'scripts' / 'maintenance' / 'backup_database.py')
    assert should_copy(ROOT / 'scripts' / 'maintenance' / 'check_deploy_safety.py')
    assert should_copy(ROOT / 'scripts' / 'season_library' / 'import_from_archive.py')
    assert should_copy(ROOT / 'season_package_worker.py')
    assert should_copy(ROOT / 'season_package_validation.py')


def test_export_excludes_local_uploader_scripts():
    assert not should_copy(ROOT / 'scripts' / 'local' / 'upload_live_comps.py')
    assert not should_copy(ROOT / 'scripts' / 'local' / 'refresh_live_comps.py')


def test_export_contains_all_local_runtime_imports():
    import ast

    # Follow real module imports instead of repeating the export whitelist.
    for path in ROOT.glob('*.py'):
        if not should_copy(path):
            continue
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                dependency = ROOT / (name.split('.')[0] + '.py')
                if dependency.is_file():
                    assert should_copy(dependency), f'{path.name} needs {dependency.name}'


def test_export_copies_tracked_server_files_without_local_scratch(tmp_path, monkeypatch):
    import subprocess

    from scripts.maintenance import export_web_application as exporter

    source = tmp_path / 'source'
    target = tmp_path / 'delivery'
    source.mkdir()
    target.mkdir()
    (target / 'obsolete.txt').write_text('old delivery', encoding='utf-8')
    files = {
        'app.py': 'import new_service',
        'new_service.py': 'VALUE = 1',
        'static/app.js': 'const value = 1;',
        'docs/operations.md': '# Operations',
        'scripts/local/private_tool.py': '# local only',
        'tests/test_app.py': '# not a server dependency',
        'instance/data.json': '{}',
        'secret.key': 'fixture, not a real key',
        '.env': 'FIXTURE_ONLY=true',
    }
    for name, body in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding='utf-8')
    subprocess.run(['git', 'init', '--quiet', str(source)], check=True)
    subprocess.run(['git', 'add', '.'], cwd=source, check=True)
    # Untracked Python scratch must not be included by the root-module rule.
    (source / 'scratch.py').write_text('# private local scratch', encoding='utf-8')
    (source / 'static/local.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(exporter, 'ROOT', source)
    monkeypatch.setattr(exporter, 'TARGET', target)

    assert exporter.export() == 0
    actual = {path.relative_to(target).as_posix() for path in target.rglob('*') if path.is_file()}
    assert actual == {'app.py', 'new_service.py', 'static/app.js', 'docs/operations.md'}
