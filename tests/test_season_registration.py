"""Registration CLI must not expose or overwrite an existing season accidentally."""

import pytest

from scripts.season_library import import_from_archive as importer
from season_package_format import dump, read_json


def test_encounters_use_generic_cards_without_charm_semantics(tmp_path):
    dump(tmp_path / 'mechanics/index.json', {'mechanics': [{
        'id': 'encounters', 'kind': 'encounter', 'display_name': '奇遇',
        'file': 'encounters.json', 'has_images': True,
    }]})
    dump(tmp_path / 'mechanics/encounters.json', {'records': [
        {'id': 'adv_2', 'name': '阿狸', 'description': '恢复生命值', 'data': {}},
        {'id': 'adv_3', 'name': '阿狸', 'description': '获得战斗祝福', 'data': {}},
    ]})
    mechanic, = importer.compact_mechanics(tmp_path)
    assert mechanic['presentation'] == 'cards.v1'
    assert mechanic['display_name'] == '奇遇'
    assert [entry['id'] for entry in mechanic['entries']] == ['adv_2', 'adv_3']
    assert all(entry['data'] == {} for entry in mechanic['entries'])


def test_s11_snapshot_keeps_all_encounters_and_starts_hidden():
    root = importer.REPO_ROOT / 'static/season-data'
    season = next(row for row in read_json(root / 'catalog.json')['seasons']
                  if row['season_id'] == 's11')
    assert season['status'] == 'hidden'
    snapshot = read_json(root / 's11/index.json')
    assert snapshot['game_version'] == '12.4.14'
    mechanic, = snapshot['mechanics']
    assert mechanic['kind'] == 'encounter'
    assert mechanic['presentation'] == 'cards.v1'
    assert len(mechanic['entries']) == 108
    assert len({row['id'] for row in mechanic['entries']}) == 108
    assert all(not row['data'] for row in mechanic['entries'])


def test_import_cli_initial_status_registers_hidden_and_preserves_existing(tmp_path, monkeypatch):
    source, target = tmp_path / 'archive', tmp_path / 'prepared'
    dump(
        source / 'data/catalog.json',
        {
            'seasons': [
                {'season_id': 's18', 'status': 'active'},
                {'season_id': 's99', 'status': 'active'},
            ]
        },
    )
    original = {'season_id': 's18', 'status': 'active', 'path': 's18/index.json'}
    dump(target / 'catalog.json', {'seasons': [original]})
    calls = []

    def convert(root, entry, **options):
        calls.append(entry)
        assert root == source and options['official_only']
        return {
            **entry,
            'display_name': '演练',
            'game_version': '99-test',
            'counts': {'champions': 1, 'traits': 1, 'mechanics': 0},
        }

    monkeypatch.setattr(importer, 'import_season', convert)
    argv = [
        '--source',
        str(source),
        '--output-root',
        str(target),
        '--season',
        's99',
        '--official-only',
        '--initial-status',
        'hidden',
    ]
    assert importer.main(argv) == 0
    entries = read_json(target / 'catalog.json')['seasons']
    assert entries[0] == original
    assert entries[1]['status'] == 'hidden'
    assert len(calls) == 1
    before = (target / 'catalog.json').read_bytes()
    with pytest.raises(SystemExit) as error:
        importer.main(argv)
    assert error.value.code == 2
    assert len(calls) == 1
    assert (target / 'catalog.json').read_bytes() == before


def test_initial_status_requires_single_season(tmp_path):
    dump(tmp_path / 'data/catalog.json', {'seasons': []})
    with pytest.raises(SystemExit) as error:
        importer.main(
            [
                '--source',
                str(tmp_path),
                '--output-root',
                str(tmp_path / 'out'),
                '--initial-status',
                'hidden',
            ]
        )
    assert error.value.code == 2
    assert not (tmp_path / 'out').exists()
