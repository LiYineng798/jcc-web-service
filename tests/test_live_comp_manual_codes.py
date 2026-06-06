from live_comp_manual_codes import (
    load_manual_code_overlay,
    merge_manual_codes_into_payload,
    prune_manual_codes_for_payload,
    save_manual_code_overlay,
    set_manual_code_overlay_value,
)


def test_merge_manual_codes_only_fills_blank_codes(tmp_path):
    payload = {
        'meta': {},
        'tiers': {
            'S': [
                {'id': 's-01', 'title': '缺码阵容', 'tier': 'S', 'jccCode': '', 'mainAvatar': 'a', 'heroImages': ['b']},
                {'id': 's-02', 'title': '原始有码阵容', 'tier': 'S', 'jccCode': '#ORIGINAL002', 'mainAvatar': 'a', 'heroImages': ['b']},
            ],
            'A': [],
            'B': [],
            'C': [],
            'D': [],
        },
    }
    overlay_dir = tmp_path / 'manual-codes'
    save_manual_code_overlay(overlay_dir, 's17-star-god', {
        'season': 's17-star-god',
        'updated_at': '2026-05-24T10:00:00',
        'items': {
            's-01': {'jccCode': '#MANUAL001', 'updated_at': '2026-05-24T10:00:00', 'updated_by': 1},
            's-02': {'jccCode': '#MANUAL002', 'updated_at': '2026-05-24T10:00:00', 'updated_by': 1},
        },
    })

    merged = merge_manual_codes_into_payload(payload, load_manual_code_overlay(overlay_dir, 's17-star-god'))

    assert merged['tiers']['S'][0]['originalJccCode'] == ''
    assert merged['tiers']['S'][0]['resolvedJccCode'] == '#MANUAL001'
    assert merged['tiers']['S'][0]['jccCode'] == '#MANUAL001'
    assert merged['tiers']['S'][0]['codeSource'] == 'manual'
    assert merged['tiers']['S'][0]['hasCode'] is True
    assert merged['tiers']['S'][1]['originalJccCode'] == '#ORIGINAL002'
    assert merged['tiers']['S'][1]['resolvedJccCode'] == '#ORIGINAL002'
    assert merged['tiers']['S'][1]['codeSource'] == 'original'


def test_prune_manual_codes_drops_entries_once_upload_has_original_code(tmp_path):
    overlay_dir = tmp_path / 'manual-codes'
    set_manual_code_overlay_value(overlay_dir, 's16-legends', 'comp-1', '【阵容码】##MANUAL001', admin_id=7, now_value='2026-05-24T10:00:00')
    set_manual_code_overlay_value(overlay_dir, 's16-legends', 'comp-2', '【阵容码】##MANUAL002', admin_id=7, now_value='2026-05-24T10:00:00')
    payload = {
        'meta': {},
        'tiers': {
            'S': [{'id': 'comp-1', 'title': '已有新码', 'tier': 'S', 'jccCode': '#NEW001', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'A': [{'id': 'comp-2', 'title': '仍旧缺码', 'tier': 'A', 'jccCode': '', 'mainAvatar': 'a', 'heroImages': ['b']}],
            'B': [],
            'C': [],
            'D': [],
        },
    }

    pruned = prune_manual_codes_for_payload(overlay_dir, 's16-legends', payload)

    assert 'comp-1' not in pruned['items']
    assert pruned['items']['comp-2']['jccCode'] == '#MANUAL002'
