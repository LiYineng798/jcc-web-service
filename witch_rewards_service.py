"""Read the independently captured S18 activity snapshot (no database writes)."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def reward_tiers():
    path = Path(__file__).resolve().parent / 'static/witch-rewards/rewards.json'
    return json.loads(path.read_text(encoding='utf-8'))['tiers']


def select_reward_tier(label):
    tiers = reward_tiers()
    return next((tier for tier in tiers if tier['label'] == label), None)
