import json
from pathlib import Path

from scripts.build_simulator_data import build_simulator_data, load_source_data


def sample_data():
    return {
        'version': {'set': 'test-set', 'version': '1.0', 'updatedAt': '2026-05-20'},
        'heroCostTabs': ['??', '1?', '2?'],
        'equipTabs': ['??'],
        'heroes': [{'key': 'morgana', 'name': '???', 'cost': 4, 'costLabel': '4?'}],
        'equips': [{'id': 'item-1', 'name': '????', 'type': '??'}],
        'traits': [{'name': '????', 'levels': []}],
        'pets': [{'id': 'pet-1', 'name': '?????'}],
    }


def test_build_simulator_data_from_combined_json(tmp_path):
    source = tmp_path / 'simulator-source.json'
    output = tmp_path / 'data'
    source.write_text(json.dumps(sample_data(), ensure_ascii=False), encoding='utf-8')

    written = build_simulator_data(source, output)

    assert sorted(path.name for path in written) == [
        'equips.json',
        'heroes.json',
        'pets.json',
        'tabs.json',
        'traits.json',
        'version.json',
    ]
    assert json.loads((output / 'heroes.json').read_text(encoding='utf-8'))[0]['cost'] == 4
    assert json.loads((output / 'tabs.json').read_text(encoding='utf-8'))['heroCostTabs'] == ['??', '1?', '2?']
    assert json.loads((output / 'version.json').read_text(encoding='utf-8'))['set'] == 'test-set'


def test_load_source_data_from_legacy_local_data_js(tmp_path):
    source = tmp_path / 'local-data.js'
    source.write_text(
        'window.LOCAL_SIMULATOR_DATA = ' + json.dumps(sample_data(), ensure_ascii=False) + ';',
        encoding='utf-8',
    )

    data = load_source_data(source)

    assert data['heroes'][0]['name'] == '???'
    assert data['heroes'][0]['costLabel'] == '4?'


def test_build_simulator_data_rejects_missing_required_sections(tmp_path):
    source = tmp_path / 'bad.json'
    output = tmp_path / 'data'
    source.write_text(json.dumps({'heroes': []}), encoding='utf-8')

    try:
        build_simulator_data(source, output)
    except ValueError as error:
        assert 'heroCostTabs' in str(error)
    else:
        raise AssertionError('expected ValueError')



def test_load_source_data_from_unquoted_legacy_local_data_js(tmp_path):
    source = tmp_path / 'local-data.js'
    source.write_text(
        'window.LOCAL_SIMULATOR_DATA = {heroCostTabs: ["??"], equipTabs: ["??"], heroes: [], equips: [], traits: [], pets: []};',
        encoding='utf-8',
    )

    data = load_source_data(source)

    assert data['heroCostTabs'] == ['??']
    assert data['equipTabs'] == ['??']


def test_build_simulator_data_can_rewrite_image_paths_to_webp(tmp_path):
    source = tmp_path / 'simulator-source.json'
    output = tmp_path / 'data'
    data = sample_data()
    data['heroes'][0]['image'] = 'mode17s18_hero_by_cost_cn/price-4/???.png'
    data['equips'][0]['image'] = 'mode17s18_equip_by_type/??/????.png'
    data['traits'][0]['image'] = 'mode17s18_trait_icons/s17_trait_icon_darklady.png'
    data['pets'][0]['image'] = 'assets/pets/18406.png'
    source.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    build_simulator_data(source, output, image_format='webp')

    assert json.loads((output / 'heroes.json').read_text(encoding='utf-8'))[0]['image'] == 'webp/mode17s18_hero_by_cost_cn/price-4/???.webp'
    assert json.loads((output / 'equips.json').read_text(encoding='utf-8'))[0]['image'] == 'webp/mode17s18_equip_by_type/??/????.webp'
    assert json.loads((output / 'traits.json').read_text(encoding='utf-8'))[0]['image'] == 'webp/mode17s18_trait_icons/s17_trait_icon_darklady.webp'
    assert json.loads((output / 'pets.json').read_text(encoding='utf-8'))[0]['image'] == 'webp/assets/pets/18406.webp'

