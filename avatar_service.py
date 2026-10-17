"""Persisted, bounded system-avatar parameters shared by API serializers."""
import re
import secrets

AVATAR_COLORS = ('#d5a06f', '#7e927d', '#7e96ad', '#9b8ba5', '#b98187', '#b8a48d', '#6f9893', '#66717e')
AVATAR_PRESETS = ('strobi', 'freddy', 'citrus', 'nova', 'sunee', 'cloudee', 'sprout', 'bloom')
AVATAR_EXPRESSIONS = ('neutral', 'happy', 'wink', 'sleepy', 'curious', 'surprised', 'shy', 'determined')
COLOR_RE = re.compile(r'#[0-9a-fA-F]{6}\Z')


def random_avatar_color():
    return secrets.choice(AVATAR_COLORS)


def random_avatar_config():
    return {
        'version': 1,
        'preset': secrets.choice(AVATAR_PRESETS),
        'expression': secrets.choice(AVATAR_EXPRESSIONS),
        'color': random_avatar_color(),
    }


def _fallback_index(values):
    try:
        return int(values.get('id') or 0)
    except (TypeError, ValueError):
        return 0


def avatar_color(user):
    values = dict(user) if user else {}
    color = values.get('avatar_color')
    if isinstance(color, str) and COLOR_RE.fullmatch(color):
        return color.lower()
    return AVATAR_COLORS[_fallback_index(values) % len(AVATAR_COLORS)]


def avatar_config(user):
    """Old or unknown storage has a stable fallback; reads never randomize."""
    values = dict(user) if user else {}
    index = _fallback_index(values)
    preset = values.get('avatar_preset')
    expression = values.get('avatar_expression')
    return {
        'version': 1,
        'preset': preset if preset in AVATAR_PRESETS else AVATAR_PRESETS[index % len(AVATAR_PRESETS)],
        'expression': expression if expression in AVATAR_EXPRESSIONS else AVATAR_EXPRESSIONS[index % len(AVATAR_EXPRESSIONS)],
        'color': avatar_color(values),
    }
