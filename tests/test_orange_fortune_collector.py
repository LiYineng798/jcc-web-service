import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect_orange_fortune import describe_text_change, inspect_image, parse_arguments, select_branch  # noqa: E402


def test_branch_requires_mode_and_season_and_ignores_newest_flag():
    directory = [
        {'mode': '16', 'season': 'S100024', 'version': '18.18.4', 'version_start_time': '2026-10-14', 'is_newest_version': 1},
        {'mode': '16', 'season': 'S400001', 'version': '18.18.1', 'version_start_time': '2026-10-13 19:49:20', 'is_newest_version': 0},
        {'mode': 16, 'season': 'S400001', 'version': '18.18.2', 'version_start_time': '2026-10-30', 'is_newest_version': 0},
    ]
    selected, candidates = select_branch(directory, '16', 'S400001')
    assert selected['version'] == '18.18.2' and len(candidates) == 2
    assert select_branch(directory, '16', 'S400002') == (None, [])


def test_arguments_keep_case_order_duplicates_and_pipes():
    assert parse_arguments('equipNum=2^equipnum=1^detail=1|2^a=b=c^bare') == [
        ['equipNum', '2'], ['equipnum', '1'], ['detail', '1|2'], ['a', 'b=c'], ['bare', None]]
    assert parse_arguments('') == []


def test_image_checks_reject_error_pages_and_accept_real_png():
    buffer = io.BytesIO()
    Image.new('RGBA', (3, 4)).save(buffer, 'PNG')
    assert inspect_image(buffer.getvalue()) == ({'format': 'PNG', 'width': 3, 'height': 4}, None)
    assert inspect_image(b'') == (None, 'empty')
    assert inspect_image(b'<html>404</html>') == (None, 'not_image')
    assert inspect_image(b'\x89PNG\r\n\x1a\ntruncated')[1].startswith('decode_error')


def test_description_changes_separate_punctuation_numbers_and_wording():
    assert describe_text_change('获得4金币。', '获得4金币') == ['punctuation_or_whitespace_only']
    assert describe_text_change('获得4金币。', '获得6金币。') == ['numbers_changed']
    assert describe_text_change('获得4金币。', '立即获得6金币。') == ['numbers_changed', 'wording_changed']
