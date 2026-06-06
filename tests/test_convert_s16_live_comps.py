import importlib.util
from pathlib import Path


SCRIPT_PATH = Path('scripts/convert_s16_datatft_raw_to_live_comps.py')


def load_module():
    spec = importlib.util.spec_from_file_location('convert_s16_live_comps', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_convert_payload_keeps_items_without_jcc_code():
    module = load_module()
    raw_payload = {
        'data': {
            'list': [{
                'id': 16001,
                'title': '暗影岛佛爷',
                'tier': 'B',
                'heroId': '916234',
                'score': 266.0,
                'strategyId': 16001,
                'tags': ['速升8级'],
                'heros': [{'id': '916234'}, {'id': '916083'}],
            }],
        },
    }

    payload = module.convert_payload(raw_payload, 's16-legends', module.DEFAULT_IMAGE_BASE)

    assert payload['meta']['season_id'] == 's16-legends'
    assert payload['meta']['supports_copy'] is False
    assert payload['tiers']['B'][0]['id'] == '16001'
    assert payload['tiers']['B'][0]['jccCode'] == ''
    assert payload['tiers']['B'][0]['mainAvatar'].endswith('/916234.jpg')
    assert len(payload['tiers']['B'][0]['heroImages']) == 2
