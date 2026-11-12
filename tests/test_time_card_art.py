"""Geometry is asset-derived so old releases and preview packages remain isolated."""
from pathlib import Path
from PIL import Image, ImageDraw
from time_card_art import presentation
from orange_fortune_service import catalog, _read_time_cards
import json
import pytest


@pytest.mark.parametrize('bounds', [(112,36,399,494), (113,32,400,497), (111,27,400,498), (113,31,399,497), (113,33,400,497)])
def test_all_tiers_fit_the_same_stage_without_stretching(tmp_path, bounds):
    path = tmp_path / 'card.png'
    im = Image.new('RGBA', (512,512))
    ImageDraw.Draw(im).rectangle((bounds[0], bounds[1], bounds[2]-1, bounds[3]-1), fill='white')
    im.save(path)
    art = presentation(path)
    assert art['framed']
    values = {k:float(v.rstrip('%')) for k,v in (pair.split(':') for pair in art['art_style'].split(';'))}
    scale = values['--art-width'] / 512
    left = values['--art-left'] + bounds[0] * scale
    right = values['--art-left'] + bounds[2] * scale
    top = values['--art-top'] + bounds[1] * scale / 1.6
    bottom = values['--art-top'] + bounds[3] * scale / 1.6
    assert 0 <= left < right <= 100
    assert 0 <= top < 1 and 99 < bottom <= 100
    assert abs(left - (100-right)) < .001


def test_portrait_missing_and_opaque_images_keep_legacy_rendering(tmp_path):
    for size, mode in [((326,430),'RGBA'), ((326,524),'RGBA'), ((512,512),'RGB'), ((512,512),'RGBA')]:
        path = tmp_path / 'legacy.png'
        Image.new(mode,size,'white').save(path)
        assert presentation(path) == {'framed':False, 'art_style':''}
    assert presentation(tmp_path/'absent.png')['framed'] is False


def test_release_uses_its_own_art_not_the_new_baseline(tmp_path):
    original = catalog()['cards'][0]
    Image.new('RGBA',(326,430),'white').save(tmp_path/'old.png')
    row = {**original, 'image':'old.png', 'layout':'icon'}
    doc = {'version':'18.18.1','season':'S400001','setId':'16','time':'fixture','time_cards':[row]}
    path = tmp_path/'time_cards.json'
    path.write_text(json.dumps(doc),encoding='utf8')
    result = _read_time_cards(str(path),path.stat().st_mtime_ns,path.stat().st_size)
    assert result['cards'][0]['framed'] is False
    assert result['cards'][0]['image'] == 'old.png'


def test_complete_official_baseline_and_public_adapters(client):
    cards = catalog()['cards']
    assert len(cards) == 201 and all(c['framed'] for c in cards)
    assert all(c['image'] and c['art_style'] for c in cards)
    config = client.get('/api/tools/orange-fortune-creator').get_json()
    assert all(c['framed'] and c['art_style'] for c in config['cards'])


def test_higher_resolution_official_cards_keep_the_same_geometry(tmp_path):
    im = Image.new('RGBA',(512,512))
    ImageDraw.Draw(im).rectangle((113,33,399,496),fill='white')
    im.save(tmp_path/'original.png')
    im.resize((1024,1024),Image.Resampling.NEAREST).save(tmp_path/'large.png')
    assert presentation(tmp_path/'original.png') == presentation(tmp_path/'large.png')
