"""Offline rehearsal fixtures. S99 is a labeled copy of S18, never real S19 data."""

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import shutil

from season_package_format import dump, read_json, MODULES
from scripts.season_library.build_upload_package import build_package
from scripts.season_library.import_from_archive import compact_champion

ROOT = Path(__file__).resolve().parents[1]
SID = 's99'
TITLE = 'S99 本地演练（复制 S18）'


def snapshot(source, version, variant):
    index = read_json(source / 'index.json')
    index.update(
        season_id=SID,
        display_name=TITLE,
        set_number='99',
        theme='本地演练',
        game_version=version,
        version_id=f'{SID}__{version}',
        status='hidden',
    )
    docs = {name: read_json(source / f'{name}.json') for name in MODULES}
    if variant:
        hero = docs['champions']['champions'][0]
        hero['stats_by_star']['1']['health'] += variant * 10
        hero['name'] = f'演练弈子补丁{variant}'
        bonus = deepcopy(hero)
        bonus.update(id='rehearsalbonus', name='演练新增弈子', source_ids={})
        docs['champions']['champions'].append(bonus)
    index['champions'] = [compact_champion(row) for row in docs['champions']['champions']]
    # Exercise absent -> multiple mechanics -> one removed, with provenance.
    index['mechanics'] = []
    if variant:
        index['mechanics'].append(
            {
                'id': 'rehearsal-reward',
                'kind': 'generic',
                'display_name': '演练阶段奖励',
                'presentation': 'stages.v1',
                'entries': [
                    {
                        'id': 'reward',
                        'name': '演练奖励',
                        'description': '仅验证上传流程',
                        'data': {
                            'rounds': ['2-1'],
                            'requires': ['完成演练条件'],
                            'stages': [
                                {'label': '演练阶段', 'effect': f'修订 {variant}', 'cost': 1}
                            ],
                        },
                        'extensions': {
                            'provenance': {
                                'source_type': 'local_rehearsal',
                                'verified_for_current_patch': False,
                                'note': '虚构测试条件，不代表真实玩法',
                            }
                        },
                    }
                ],
            }
        )
    if variant == 1:
        index['mechanics'].append(
            {
                'id': 'rehearsal-table',
                'kind': 'generic',
                'display_name': '演练规则表',
                'presentation': 'table.v1',
                'entries': [
                    {
                        'id': 'rule',
                        'name': '待移除规则',
                        'description': '验证补丁移除玩法',
                        'data': {'columns': ['条件', '结果'], 'rows': [['演练', '通过']]},
                    }
                ],
            }
        )
    for name, doc in docs.items():
        doc['version_id'] = index['version_id']
        dump(source / f'{name}.json', doc)
    counts = {name: len(doc[name]) for name, doc in docs.items()}
    counts['mechanics'] = sum(len(m['entries']) for m in index['mechanics'])
    dump(source / 'index.json', index)
    entry = {
        k: index[k]
        for k in (
            'season_id',
            'display_name',
            'set_number',
            'theme',
            'game_version',
            'version_id',
            'status',
            'effective_at',
        )
    }
    entry.update(path=f'{SID}/index.json', counts=counts)
    dump(source / 'season.json', entry)
    return entry


@contextmanager
def rehearsal(directory):
    """Only redirect filesystem roots; use real DB, APIs, validators and workers."""
    from app import create_app
    import season_data_repository
    import season_visibility

    directory = Path(directory)
    library = directory / 'season-data'
    original = ROOT / 'static/season-data/s18'
    shutil.copytree(original, library / 's18')
    original_entry = next(
        s
        for s in read_json(ROOT / 'static/season-data/catalog.json')['seasons']
        if s['season_id'] == 's18'
    )
    catalog = {'format_version': '1.0.0', 'seasons': [original_entry]}
    dump(library / 'catalog.json', catalog)
    packages = []
    sources = []
    entry = None
    for label, version, revision, variant in (
        ('initial', '99.1-rehearsal', 1, 0),
        ('update', '99.2-rehearsal', 1, 1),
        ('hotfix', '99.2-rehearsal', 2, 2),
    ):
        source = library / SID if not variant else directory / label
        shutil.copytree(original, source)
        metadata = snapshot(source, version, variant)
        entry = entry or metadata
        package = directory / f'{label}.zip'
        build_package(
            source,
            package,
            revision,
            {
                'title': f'{TITLE} {label}',
                'summary': '本地离线演练，不是真实赛季或可用游戏码',
                'sections': [{'title': '演练', 'items': [f'阶段 {label}']}],
            },
        )
        packages.append(package)
        sources.append(source)

    def register():
        dump(library / 'catalog.json', {**catalog, 'seasons': [original_entry, entry]})

    config = {
        'TESTING': True,
        'DATABASE': str(directory / 'app.sqlite3'),
        'DATABASE_URL': 'sqlite:///' + str(directory / 'app.sqlite3').replace('\\', '/'),
        'SECRET_KEY': 'isolated-season-lifecycle-test-only',
        'SESSION_COOKIE_SECURE': False,
        'ADMIN_USERNAME': 'previewadmin',
        'ADMIN_PASSWORD': 'Preview1234',
        'SEASON_PACKAGE_ROOT': str(directory / 'packages'),
        'SEASON_VISIBILITY_PATH': str(directory / 'visibility.json'),
        'DAILY_REPORT_WORKER_ENABLED': False,
        'LIVE_COMPS_UPLOAD_WORKER_ENABLED': False,
        'LIVE_COMPS_DEFAULT_SEASON_ID': 's18',
        'LIVE_COMPS_UPLOAD_TOKEN': '',
    }
    for key, relative in {
        'LIVE_COMPS_DATA_PATH': 'live.json',
        'LIVE_COMPS_BACKUP_PATH': 'live.previous.json',
        'LIVE_COMPS_BACKUP_DIR': 'live-backups',
        'LIVE_COMPS_ASSET_DIR': 'live-assets',
        'LIVE_COMPS_SEASON_MANIFEST_PATH': 'live-seasons.json',
        'LIVE_COMPS_SEASON_DIR': 'live-seasons',
        'LIVE_COMPS_MANUAL_CODE_DIR': 'manual-codes',
        'LIVE_COMPS_UPLOAD_JOB_DIR': 'live-jobs',
    }.items():
        config[key] = str(directory / relative)
    dump(
        Path(config['LIVE_COMPS_SEASON_MANIFEST_PATH']),
        {
            'default_season_id': 's18',
            'seasons': [
                {
                    'id': 's18',
                    'name': 'S18',
                    'status': 'active',
                    'order': 1,
                    'data_file': 's18.json',
                }
            ],
        },
    )
    icon = read_json(original / 'index.json')['champions'][0]['icon']
    live_assets = Path(config['LIVE_COMPS_ASSET_DIR'])
    live_assets.mkdir()
    shutil.copy2(original / icon, live_assets / 'rehearsal.webp')
    with patch.object(season_data_repository, 'BASE_ROOT', library), patch.object(
        season_visibility, 'DATA_ROOT', library
    ):
        app = create_app(config)

        # Serve this fixture's baseline at the ordinary static URL. Authentication
        # and the application's hidden-season gate still run before this hook.
        @app.before_request
        def fixture_assets():
            from flask import request, send_from_directory

            prefix = '/static/season-data/'
            if request.path.startswith(prefix):
                return send_from_directory(library, request.path[len(prefix) :])

        yield SimpleNamespace(
            app=app,
            register=register,
            packages=packages,
            sources=sources,
            library=library,
            entry=entry,
            directory=directory,
        )


def live_payload():
    return {
        'meta': {'source': 'offline-rehearsal-only'},
        'tiers': {
            'S': [
                {
                    'id': 'rehearsal',
                    'title': 'S99 演练阵容（非游戏码）',
                    'tier': 'S',
                    'jccCode': '#REHEARSALONLY1',
                    'mainAvatar': '/api/live-comps/assets/rehearsal.webp',
                    'heroImages': ['/api/live-comps/assets/rehearsal.webp'],
                    'formationDetails': {
                        'version': 1,
                        'season_id': SID,
                        'units': [
                            {'champion_id': '1500', 'position': 21, 'items': [], 'star': 2},
                        ],
                    },
                }
            ],
            'A': [],
            'B': [],
            'C': [],
            'D': [],
        },
    }
