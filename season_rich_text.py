"""Shared rich-text parsing for season descriptions.

Season sources use bracket markers such as ``【AP】`` or ``【法术加成】``.
The importer stores normalized tokens next to the original text so every
consumer can render the same accessible stat marker without trusting HTML from
upstream data.
"""

from __future__ import annotations

import re
import unicodedata

from markupsafe import Markup, escape


STAT_PRESENTATION = {
    'attack_damage': {'kind': 'ad', 'label': '物理加成', 'icon': 'ad', 'fallback': 'AD'},
    'ability_power': {'kind': 'ap', 'label': '法术加成', 'icon': 'ap', 'fallback': 'AP'},
    'attack_speed': {'kind': 'attack-speed', 'label': '攻击速度', 'icon': 'as', 'fallback': 'AS'},
    'attack_range': {'kind': 'range', 'label': '攻击范围', 'icon': 'range', 'fallback': 'RNG'},
    'armor': {'kind': 'armor', 'label': '护甲', 'icon': 'armor', 'fallback': 'AR'},
    'magic_resist': {'kind': 'magic-resist', 'label': '魔法抗性', 'icon': 'mr', 'fallback': 'MR'},
    'health': {'kind': 'health', 'label': '生命值', 'icon': 'hp', 'fallback': 'HP'},
    'critical_strike_chance': {'kind': 'crit', 'label': '暴击率', 'icon': 'crit', 'fallback': 'CRIT'},
    'critical_strike_damage': {'kind': 'crit-multiplier', 'label': '暴击伤害', 'icon': 'critmult', 'fallback': 'CRIT'},
    'mana': {'kind': 'mana', 'label': '法力值', 'icon': 'mana', 'fallback': 'MP'},
    'mana_regeneration': {'kind': 'mana-regen', 'label': '法力回复', 'icon': 'manaregen', 'fallback': 'MP'},
    'omnivamp': {'kind': 'omnivamp', 'label': '全能吸血', 'icon': 'sv', 'fallback': '吸'},
    'damage_amplification': {'kind': 'damage-amplification', 'label': '伤害增幅', 'icon': 'da', 'fallback': '增伤'},
    'damage_reduction': {'kind': 'damage-reduction', 'label': '伤害减免', 'icon': 'dr', 'fallback': '减伤'},
    'skill_critical_strike': {'kind': 'skill-crit', 'label': '技能暴击', 'icon': 'crit', 'fallback': 'CRIT'},
    'wood_spirit_bonus': {'kind': 'amp', 'label': '木灵加成', 'icon': 'amp', 'fallback': '木灵'},
    'soul': {'kind': 'soul', 'label': '灵魂', 'icon': 'soul', 'fallback': '魂'},
    'serpent': {'kind': 'serpent', 'label': '银蛇币', 'icon': 'serpent', 'fallback': '币'},
    'ixtal': {'kind': 'ixtal', 'label': '太阳碎片', 'icon': 'ixtal.svg', 'fallback': '碎片'},
}

STAT_ALIASES = {
    'attack_damage': ('AD', '物理加成', '攻击力'),
    'ability_power': ('AP', '法术加成', '法强'),
    'attack_speed': ('AS', '攻击速度', '攻速'),
    'attack_range': ('RANGE', '攻击范围', '射程'),
    'armor': ('AR', 'ARMOR', '护甲'),
    'magic_resist': ('MR', '魔法抗性', '魔抗'),
    'health': ('HP', '生命上限', '最大生命值', '生命值'),
    'critical_strike_chance': ('CRIT', '暴击率', '暴击几率'),
    'critical_strike_damage': ('暴击伤害', '暴击倍率'),
    'mana': ('MANA', 'MP', '法力值', '最大法力值'),
    'mana_regeneration': ('法力回复', '法力回复速度'),
    'omnivamp': ('OMNIVAMP', '全能吸血', '全能汲取'),
    'damage_amplification': ('AMP', 'DA', '伤害加成', '伤害增幅'),
    'damage_reduction': ('DR', '伤害减免'),
    'skill_critical_strike': ('技能暴击',),
    'soul': ('SOUL', '灵魂'),
    'serpent': ('SERPENT', '银蛇币'),
    'ixtal': ('IXTAL', '太阳碎片'),
}

RICH_TEXT_FIELDS = frozenset({'description', 'effect'})
RICH_TOKEN_RE = re.compile(r'【([^】]+)】|(\(\))')


def _normalize_alias(value):
    normalized = unicodedata.normalize('NFKC', str(value or '')).strip().upper()
    return re.sub(r'[\s_-]+', '', normalized)


ALIAS_TO_STAT = {
    _normalize_alias(alias): stat
    for stat, aliases in STAT_ALIASES.items()
    for alias in aliases
}


def parse_rich_text(text):
    """Return safe text/stat tokens while preserving the original wording."""
    value = str(text or '')
    tokens = []
    cursor = 0
    for match in RICH_TOKEN_RE.finditer(value):
        wood_spirit_placeholder = bool(
            match.group(2)
            and '木灵加成' in value
            and match.start() > 0
            and value[match.start() - 1] in '0123456789%'
        )
        if match.group(2) and not wood_spirit_placeholder:
            continue
        source_label = '木灵加成' if wood_spirit_placeholder else match.group(1)
        stat = 'wood_spirit_bonus' if wood_spirit_placeholder else ALIAS_TO_STAT.get(_normalize_alias(source_label))
        if not stat:
            continue
        start = match.start()
        end = match.end()
        if wood_spirit_placeholder:
            start += 1
            end -= 1
        elif start > cursor and value[start - 1] == '(' and end < len(value) and value[end] == ')':
            start -= 1
            end += 1
        if start > cursor:
            tokens.append({'type': 'text', 'value': value[cursor:start]})
        presentation = STAT_PRESENTATION[stat]
        tokens.append({
            'type': 'stat',
            'stat': stat,
            'kind': presentation['kind'],
            'label': presentation['label'],
            'source_label': source_label,
            'icon': presentation['icon'],
            'fallback': presentation['fallback'],
        })
        cursor = end
    if cursor < len(value):
        tokens.append({'type': 'text', 'value': value[cursor:]})
    return tokens


def has_stat_tokens(tokens):
    return any(token.get('type') == 'stat' for token in tokens or [])


def enrich_rich_text_fields(value):
    """Recursively add ``*_tokens`` fields where recognized markers exist."""
    if isinstance(value, list):
        for item in value:
            enrich_rich_text_fields(item)
        return value
    if not isinstance(value, dict):
        return value
    for key, item in list(value.items()):
        enrich_rich_text_fields(item)
        if key not in RICH_TEXT_FIELDS or not isinstance(item, str):
            continue
        tokens = parse_rich_text(item)
        if has_stat_tokens(tokens):
            value[f'{key}_tokens'] = tokens
    return value


def render_rich_text(text, tokens=None):
    """Render normalized tokens as escaped, accessible stat markers."""
    parsed = tokens if has_stat_tokens(tokens) else parse_rich_text(text)
    if not has_stat_tokens(parsed):
        return Markup(escape(text or ''))
    rendered = []
    for token in parsed:
        if token.get('type') == 'text':
            rendered.append(str(escape(token.get('value') or '')))
            continue
        stat = token.get('stat') or 'unknown'
        presentation = STAT_PRESENTATION.get(stat) or {}
        kind = presentation.get('kind') or token.get('kind') or stat.replace('_', '-')
        label = presentation.get('label') or token.get('label') or token.get('source_label') or stat
        icon = presentation.get('icon', token.get('icon'))
        if icon:
            filename = icon if re.search(r'\.[a-z0-9]+$', icon, flags=re.IGNORECASE) else f'{icon}.png'
            content = (
                f'<img src="/static/season-stats/{escape(filename)}" alt="" '
                'aria-hidden="true" />'
            )
        else:
            content = f'<span aria-hidden="true">{escape(token.get("fallback") or label)}</span>'
        rendered.append(
            f'<span class="scale-chip scale-chip-{escape(kind)}" '
            f'role="img" aria-label="{escape(label)}" title="{escape(label)}">{content}</span>'
        )
    return Markup(''.join(rendered))


def strip_rich_text_markers(text):
    """Return description text without recognized stat markers for SEO copy."""
    return ''.join(
        token.get('value') or ''
        for token in parse_rich_text(text)
        if token.get('type') == 'text'
    )
