"""Fixed system avatar: only its ink color is user configurable."""
import re
import secrets

AVATAR_COLORS = ('#0021ed', '#059669', '#7c3aed', '#ea580c', '#e11d48', '#334155', '#0284c7', '#4f46e5')
COLOR_RE = re.compile(r'#[0-9a-fA-F]{6}\Z')


def random_avatar_color():
    return secrets.choice(AVATAR_COLORS)


def avatar_color(user):
    color = dict(user).get('avatar_color') if user else None
    if isinstance(color, str) and COLOR_RE.fullmatch(color):
        return color.lower()
    return AVATAR_COLORS[int(user['id']) % len(AVATAR_COLORS)] if user else AVATAR_COLORS[0]
