"""Read the captured golden egg snapshot; independent of the season database."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def golden_egg_rewards():
    return json.loads((Path(__file__).resolve().parent / 'static/golden-egg/rewards.json').read_text(encoding='utf-8'))
