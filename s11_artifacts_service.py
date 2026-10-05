"""Independent S11 artifact snapshot and search, without live season dependencies."""
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

DATA = Path(__file__).resolve().parent / 'static' / 's11-artifacts' / 'data.json'


@lru_cache(maxsize=1)
def artifact_snapshot():
    return json.loads(DATA.read_text(encoding='utf-8'))


def normalized(text):
    return unicodedata.normalize('NFKC', text).lower()


def description_parts(text):
    return [{'text': part, 'number': bool(re.fullmatch(r'\+?\d+(?:\.\d+)?%?', part))}
            for part in re.split(r'(\+?\d+(?:\.\d+)?%?)', text) if part]


def artifact_guide(query='', cost=''):
    data = artifact_snapshot()
    query = query.strip()[:100]
    tokens = normalized(query).split()
    rows = []
    for artifact in data['artifacts']:
        champions = [data['champions'][identity] for identity in artifact['champion_ids']]
        search = normalized(' '.join([artifact['name'], artifact['description']] +
                                     [champion['name'] + ' ' + ' '.join(champion['aliases']) for champion in champions]))
        matches = all(token in search for token in tokens) and (not cost or any(str(c['cost']) == cost for c in champions))
        rows.append({**artifact, 'champions': champions, 'search': search, 'matches': matches,
                     'description_parts': description_parts(artifact['description'])})
    return {'artifacts': rows, 'query': query, 'cost': cost, 'count': sum(row['matches'] for row in rows),
            'total': len(rows), 'champion_count': len(data['champions'])}
