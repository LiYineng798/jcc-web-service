import json
import subprocess
from pathlib import Path

import pytest

from trait_ladder_service import calculator_data, reward_tiers
from scripts.season_library.import_trait_ladder import extract


def test_rewards_and_safe_import():
    tiers = reward_tiers()
    assert [t['threshold'] for t in tiers] == list(range(2, 15))
    for tier in tiers:
        assert sum(float(r['percent'].rstrip('%')) for r in tier['list']) == pytest.approx(100)
    assert [r['percent'] for r in tiers[6]['list']] == ['42.9%', '57.1%']
    for text in ['', '羁绊天梯:[{label:evil()}],幻灵战队jcc:']:
        raw = json.dumps({'log': {'entries': [{'response': {'content': {'text': text}}}]}}).encode()
        with pytest.raises(ValueError):
            extract(raw)


def test_ladder_route_and_hidden_data(client, monkeypatch):
    page = '/tools/s18-trait-ladder'
    response = client.get(page)
    assert response.status_code == 200
    assert 'reward-14' in response.text
    assert page in client.get('/').text
    assert page in client.get('/sitemap.xml').text
    monkeypatch.setattr('trait_ladder_service.get_season', lambda *a: None)
    hidden = client.get(page).text
    assert 'S18 资料暂未开放' in hidden
    assert 'assets/champions' not in hidden
    assert 'reward-14' in hidden


def test_rules_and_search_against_current_release(app, tmp_path):
    with app.test_request_context():
        data = calculator_data()
    assert len([c for c in data['champions'] if c['lux']]) == 1
    assert len(data['luxChoices']) == 9
    dragon = next(c for c in data['champions'] if c['id'] == '5458')
    assert dragon['slots'] == 2 and dragon['traits']['454'] == 2
    path = tmp_path / 'data.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    result = subprocess.run(['node', 'tests/trait_ladder_rules.cjs', str(path)],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
