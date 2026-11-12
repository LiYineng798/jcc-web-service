"""Orange Fortune deck library: publish three time cards with an optional formation.

Card rules (tiers, energy, portals) come from orange_fortune_service; the formation editor
and its season boundary come from the creator surface. Decks keep their own tables and are
never counted as ordinary lineups.
"""
import base64
import binascii
import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from audit import write_audit
from avatar_service import avatar_config
from db import db_kind, get_db, now_text
from db_adapter import insert_returning_id_sql, last_insert_id
from lineup_code import LINEUP_CODE_MESSAGE, extract_lineup_code
from lineups_utils import bucket_start, row_value
from orange_creator_service import creator_config
from orange_fortune_service import DECK_SIZE, PORTALS, TIERS, catalog
from rate_limit import hit_limit
from season_data_repository import asset_url, data_directory
from season_visibility import get_season

PORTAL_BY_ID = {portal['id']: portal for portal in PORTALS}
TABS = ('latest', 'hot', 'featured', 'favorites', 'mine')
LIMITS = {'name': 24, 'note': 300, 'key_rounds': 100, 'alternatives': 200, 'plan_code': 512, 'lineup_code': 20000}
BOARD_SLOTS = 28
MAX_ITEMS, MAX_AUGMENTS, MAX_TRAITS = 3, 6, 24
TRAIT_STYLES = {'1', '2', '3', '4', 'unique'}
HOT_RULE = '按真实互动排序：累计点赞数（每个账号每天对同一卡组计 1 次）加收藏账号数，取消收藏即扣除；只列出至少有 1 次互动的公开卡组，同分按发布时间。'
DAILY_LIKE_LIMIT = 5
OWNER_COLUMNS = ('u.username AS owner_username, u.nickname AS owner_nickname, u.role AS owner_role, '
                 'u.avatar_color AS owner_avatar_color, u.avatar_preset AS owner_avatar_preset, '
                 'u.avatar_expression AS owner_avatar_expression')
RANKING_COUNTS = ('LEFT JOIN (SELECT deck_id, COUNT(*) AS c FROM orange_deck_favorites GROUP BY deck_id) fc ON fc.deck_id = d.id '
                  'LEFT JOIN (SELECT deck_id, COUNT(*) AS c FROM orange_deck_likes GROUP BY deck_id) lc ON lc.deck_id = d.id')
INTERACTION_SCORE = '(COALESCE(fc.c, 0) + COALESCE(lc.c, 0))'


def today():
    return datetime.now().strftime('%Y-%m-%d')


def _viewer_columns(user, *, ranked=False):
    """Indexed counts for displayed decks; only hot ranking needs global aggregates."""
    counts = (
        'COALESCE(fc.c, 0) AS favorite_count, COALESCE(lc.c, 0) AS like_count'
        if ranked else
        '(SELECT COUNT(*) FROM orange_deck_favorites f WHERE f.deck_id = d.id) AS favorite_count, '
        '(SELECT COUNT(*) FROM orange_deck_likes l WHERE l.deck_id = d.id) AS like_count'
    )
    counts += ', (SELECT COUNT(*) FROM orange_deck_copies c WHERE c.deck_id = d.id) AS copy_count'
    if not user:
        return f'{counts}, 0 AS is_favorited, 0 AS is_liked_today', []
    return (f'{counts}, CASE WHEN EXISTS (SELECT 1 FROM orange_deck_favorites mf WHERE mf.deck_id = d.id AND mf.user_id = ?) THEN 1 ELSE 0 END AS is_favorited, '
            'CASE WHEN EXISTS (SELECT 1 FROM orange_deck_likes ml WHERE ml.deck_id = d.id AND ml.user_id = ? AND ml.like_date = ?) THEN 1 ELSE 0 END AS is_liked_today',
            [user['id'], user['id'], today()])


class DeckError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- card rules

def card_index():
    return {card['id']: card for card in catalog()['cards']}


def card_version():
    data = catalog()
    return f"{data['version']}@{data['time']}"


def card_season_id():
    return 'orange_' + catalog()['season'].lower()


def deck_season_choices():
    """Only seasons with an actual time-card catalog can receive deck uploads."""
    season_id = card_season_id()
    season = get_season('creator', season_id)
    return {season_id: {'id': season_id, 'name': season['display_name']}} if season else {}


def validate_plan_code(value):
    """Validate the share text envelope, without claiming to decode game content."""
    if not value:
        return ''
    name, separator, encoded = value.rpartition('-大橘大利-')
    if not name.strip() or not separator or re.search(r'[\x00-\x1f\x7f]', value):
        raise DeckError('方案码格式应为「名称-大橘大利-编码」，请从游戏中复制完整方案码')
    try:
        if not base64.b64decode(encoded, validate=True):
            raise ValueError('empty code')
    except (ValueError, binascii.Error):
        raise DeckError('方案码编码无效，请从游戏中重新复制完整方案码')
    return value


def version_label(value):
    version, _, stamp = str(value or '').partition('@')
    return f'{version}（{stamp[:10]}）' if stamp else version or '未知版本'


def validate_cards(raw, require_complete):
    """Return three card IDs (None for an empty draft slot) after server-side checks."""
    if raw is None:
        raw = []
    if not isinstance(raw, list) or len(raw) > DECK_SIZE:
        raise DeckError('卡片数据无效')
    index = card_index()
    slots = [None] * DECK_SIZE
    for position, value in enumerate(raw):
        if value in (None, ''):
            continue
        card_id = str(value)
        if card_id not in index:
            raise DeckError(f'第 {position + 1} 张卡片不存在或已下架，请重新选择')
        if card_id in slots:
            raise DeckError('同一张时间卡片不能重复选择')
        slots[position] = card_id
    if require_complete and None in slots:
        raise DeckError('请选择三张时间卡片')
    return slots


def deck_energy(card_ids):
    index = card_index()
    return sum(index[card_id]['energy'] for card_id in card_ids if card_id in index)


def validate_portal(value):
    if not isinstance(value, str) or value not in PORTAL_BY_ID:
        raise DeckError('请选择推荐传送门')
    return value


def check_energy(card_ids, portal_id):
    """Public decks must fit the portal; the poster tool may still export over-limit drafts."""
    energy, portal = deck_energy(card_ids), PORTAL_BY_ID[portal_id]
    if energy > portal['energy_limit']:
        raise DeckError(f"卡组能量 {energy} 超出{portal['name']}上限 {portal['energy_limit']}，请调整卡片或更换传送门后再发布")
    return energy


def _text(data, key, required=False, default=''):
    value = data.get(key, default)
    if value is None:
        value = ''
    if not isinstance(value, str):
        raise DeckError('文字内容格式无效')
    value = value.strip()
    if required and not value:
        raise DeckError('请填写卡组名称')
    if len(value) > LIMITS[key]:
        raise DeckError(f'内容过长：最多 {LIMITS[key]} 字')
    return value


# ------------------------------------------------------------- formation data

@lru_cache(maxsize=8)
def _read_bundle(directory, stamp):
    root = Path(directory)

    def load(name, key):
        path = root / name
        return json.loads(path.read_text(encoding='utf-8')).get(key, []) if path.exists() else []
    champion_file = json.loads((root / 'champions.json').read_text(encoding='utf-8'))
    return {
        'version_id': str(champion_file.get('version_id') or ''),
        'champions': {str(c['id']): c for c in champion_file.get('champions', [])
                      if (c.get('extensions') or {}).get('simulator_visible') is not False},
        'board_units': {str(u['id']): u for u in load('board_units.json', 'board_units')},
        'items': {str(i['id']): i for i in load('items.json', 'items')},
        'traits': {str(t['id']): t for t in load('traits.json', 'traits')},
        'augments': {str(a['id']): a for a in load('augments.json', 'augments')},
    }


def season_bundle(season_id):
    directory = data_directory(season_id)
    champions = directory / 'champions.json'
    if not champions.exists():
        return None
    return _read_bundle(str(directory), champions.stat().st_mtime_ns)


def _unit(bundle, unit_id):
    base, _, choice = unit_id.partition('~choice-')
    hero = bundle['champions'].get(base)
    if hero is None and not choice:
        hero = bundle['board_units'].get(base)
    if hero is None or (choice and choice not in bundle['traits']):
        return None
    name = hero.get('name') or '未知弈子'
    if choice:
        name = f"{name} · {bundle['traits'][choice].get('name', '')}"
    return {'name': name, 'cost': int(hero.get('cost') or 0),
            'image': (hero.get('images') or {}).get('icon') or hero.get('image') or {}}


def _asset(season_id, image):
    path = (image or {}).get('optimized_local_path') or (image or {}).get('local_path')
    return f'{asset_url(season_id)}/{path}' if path else None


def creator_formation_season():
    config = creator_config()
    return config['season_id'] if config['simulator_available'] else None


def validate_formation(raw):
    """Keep the simulator's structured, re-editable payload; reject anything it could not load."""
    if raw is None:
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get('payload'), dict):
        raise DeckError('阵容数据无效')
    payload = raw['payload']
    season_id = creator_formation_season()
    if not season_id:
        raise DeckError('大橘大利阵容资料暂未开放，可先不配置阵容直接发布')
    if payload.get('season') != season_id:
        raise DeckError('阵容所属赛季与当前创作者资料不一致，请重新配置阵容')
    bundle = season_bundle(season_id)
    if bundle is None:
        raise DeckError('阵容资料暂时无法读取', 503)
    board = payload.get('board')
    if not isinstance(board, list) or len(board) > BOARD_SLOTS:
        raise DeckError('阵容数据无效')
    cells = [None] * BOARD_SLOTS
    for index, slot in enumerate(board):
        if slot in (None, {}):
            continue
        if not isinstance(slot, dict):
            raise DeckError('阵容数据无效')
        unit_id = str(slot.get('championId') or '')
        if len(unit_id) > 60 or _unit(bundle, unit_id) is None:
            raise DeckError('阵容包含当前资料中不存在的弈子，请在编辑器中重新配置')
        items = slot.get('items') or []
        if not isinstance(items, list) or len(items) > MAX_ITEMS or any(str(item) not in bundle['items'] for item in items):
            raise DeckError('阵容包含当前资料中不存在的装备，请在编辑器中重新配置')
        star = slot.get('star', 1)
        if star not in (1, 2, 3):
            raise DeckError('弈子星级只能为 1 至 3 星')
        cells[index] = {'championId': unit_id, 'items': [str(item) for item in items], 'star': star}
    if not any(cells):
        return None
    augments = payload.get('augmentIds') or []
    if not isinstance(augments, list) or len(augments) > MAX_AUGMENTS:
        raise DeckError('强化符文数据无效')
    traits = []
    raw_traits = raw.get('traits') or []
    if not isinstance(raw_traits, list) or len(raw_traits) > MAX_TRAITS:
        raise DeckError('羁绊数据无效')
    if any(str(a) not in bundle['augments'] for a in augments):
        raise DeckError('阵容包含当前资料中不存在的强化符文，请重新配置')
    for trait in raw_traits:
        if not isinstance(trait, dict) or len(traits) >= MAX_TRAITS:
            continue
        trait_id, count, style = str(trait.get('id') or ''), trait.get('count'), str(trait.get('style') or '')
        if trait_id in bundle['traits'] and isinstance(count, int) and 0 < count <= 30 and style in TRAIT_STYLES \
                and trait_id not in {t['id'] for t in traits}:
            traits.append({'id': trait_id, 'count': count, 'style': style})
    return {
        'version': 1, 'season': season_id, 'version_id': bundle['version_id'],
        'payload': {'version': 2, 'season': season_id, 'showNames': payload.get('showNames') is not False, 'board': cells,
                    'augmentIds': [str(a) for a in augments if str(a) in bundle['augments']]},
        # Display snapshot computed by the simulator; names and icons are re-read from data.
        'traits': traits,
    }


def resolve_formation(row):
    stored = row_value(row, 'formation_json')
    if not stored:
        return None
    formation = json.loads(stored)
    season_id = row['formation_season_id']
    season = get_season('creator', season_id)
    bundle = season_bundle(season_id) if season else None
    if bundle is None:
        return {'available': False, 'season_id': season_id,
                'message': '阵容所属赛季资料当前未开放，暂时无法显示站位。'}
    issues, cells = [], []
    for slot in formation['payload']['board']:
        if not slot:
            cells.append(None)
            continue
        unit = _unit(bundle, slot['championId'])
        items = []
        for item_id in slot['items']:
            item = bundle['items'].get(item_id)
            items.append({'name': item['name'], 'icon': _asset(season_id, item.get('image'))} if item
                         else {'name': '已移除的装备', 'icon': None, 'missing': True})
        if unit is None:
            issues.append('部分弈子在当前资料中已不存在，已标为失效，未用其他弈子替换。')
            cells.append({'missing': True, 'name': '失效弈子', 'cost': 0, 'star': slot.get('star', 1), 'items': items, 'icon': None})
            continue
        if any(item.get('missing') for item in items):
            issues.append('部分装备在当前资料中已不存在，已标为失效。')
        cells.append({'name': unit['name'], 'cost': unit['cost'], 'star': slot.get('star', 1),
                      'icon': _asset(season_id, unit['image']), 'items': items})
    traits = []
    for trait in formation.get('traits', []):
        data = bundle['traits'].get(trait['id'])
        if data:
            traits.append({'name': data.get('name', ''), 'count': trait['count'],
                           'icon': _asset(season_id, data.get('image')),
                           'frame': f"/static/tools/lineup-simulator/ui/{trait['style']}.svg"})
    augments = [bundle['augments'][a]['name'] for a in formation['payload'].get('augmentIds', []) if a in bundle['augments']]
    saved, current = row_value(row, 'formation_version_id') or formation.get('version_id'), bundle['version_id']
    if saved and current and saved != current:
        issues.append(f'阵容资料已从 {saved} 更新为 {current}，羁绊为保存时的计算结果。')
    return {
        'available': True, 'season_id': season_id, 'season_name': season.get('display_name') or season_id,
        'cells': cells, 'traits': traits, 'augments': augments, 'unit_count': sum(1 for c in cells if c),
        'issues': list(dict.fromkeys(issues)),
    }


# ---------------------------------------------------------------- serialization

def _card_view(card):
    return {key: card[key] for key in ('id', 'name', 'tier', 'tier_name', 'energy', 'category', 'rounds', 'description', 'layout')} \
        | {'image_url': card['image_url'], 'framed': card.get('framed', False), 'art_style': card.get('art_style', '')}


def resolve_cards(row):
    """Compare saved card snapshots with current data; never silently swap a changed card."""
    # IDs can be reused by a later mode season; a new catalog must not replace old cards.
    index = card_index() if row['season_id'] == card_season_id() else {}
    snapshot = {item['id']: item for item in json.loads(row['card_snapshot_json'] or '[]') if item}
    cards, issues = [], []
    for position in range(DECK_SIZE):
        card_id = row[f'card_id_{position + 1}']
        if not card_id:
            cards.append(None)
            continue
        saved, card = snapshot.get(card_id, {}), index.get(card_id)
        if card is None:
            name = saved.get('name') or card_id
            cards.append({'id': card_id, 'name': name, 'status': 'missing', 'tier': saved.get('tier'),
                          'tier_name': TIERS.get(saved.get('tier'), ''), 'energy': saved.get('tier') or 0,
                          'changes': ['当前卡片资料中已不存在该卡，未自动替换'], 'image_url': None, 'layout': 'missing',
                          'description': '', 'rounds': [], 'category': ''})
            issues.append(f'「{name}」在当前资料中已失效')
            continue
        changes = []
        if saved.get('name') and saved['name'] != card['name']:
            changes.append(f"卡名由「{saved['name']}」更新为「{card['name']}」")
        if saved.get('tier') and saved['tier'] != card['tier']:
            changes.append(f"品阶由{TIERS.get(saved['tier'], saved['tier'])}调整为{card['tier_name']}（能量 {saved['tier']} → {card['energy']}）")
        if changes:
            issues.append(f"「{card['name']}」：{'；'.join(changes)}")
        cards.append(_card_view(card) | {'status': 'changed' if changes else 'ok', 'changes': changes})
    return cards, issues


def card_snapshot(card_ids):
    index = card_index()
    return json.dumps([{'id': c, 'name': index[c]['name'], 'tier': index[c]['tier']} if c else None for c in card_ids],
                      ensure_ascii=False)


def is_owner(row, user):
    return bool(user and row['user_id'] == user['id'])


def is_admin(user):
    return bool(user and user['role'] == 'admin')


def visible_to(row, user):
    """One rule for detail, formation, search and derived entries: deleted is gone, drafts are private."""
    if row is None or row['status'] == 'deleted':
        return False
    if row['status'] == 'published':
        return True
    if row['status'] == 'hidden':
        return is_owner(row, user) or is_admin(user)
    return is_owner(row, user)


def can_derive(row, user):
    """Fork and poster export: public decks, or the owner's own draft; never hidden content."""
    return row['status'] == 'published' or (row['status'] == 'draft' and is_owner(row, user))


def serialize(row, user, detail=False, share_base=None):
    cards, issues = resolve_cards(row)
    portal = PORTAL_BY_ID[row['portal_id']]
    energy = sum(card['energy'] for card in cards if card and card['status'] != 'missing')
    saved_version, current_version = row['card_version'], card_version()
    if saved_version != current_version and not issues:
        issues.append(f'卡片资料已从 {version_label(saved_version)}更新为 {version_label(current_version)}，卡名与品阶未变；效果说明以当前资料为准。')
    elif saved_version != current_version:
        issues.insert(0, f'卡片资料已从 {version_label(saved_version)}更新为 {version_label(current_version)}：')
    # A card that vanished from current data cannot count towards a valid deck.
    complete = all(card and card['status'] != 'missing' for card in cards)
    if complete and energy > portal['energy_limit']:
        issues.append(f"按当前资料计算能量为 {energy}，已超出{portal['name']}上限 {portal['energy_limit']}。")
    role, nickname = row_value(row, 'owner_role'), row_value(row, 'owner_nickname')
    username = row_value(row, 'owner_username')
    owner, admin = is_owner(row, user), is_admin(user)
    editable = owner and user['role'] != 'automation'
    note = row['note'] if detail else row['note'][:120]
    data = {
        'id': row['id'], 'name': row['name'], 'status': row['status'],
        'plan_code': row['plan_code'], 'lineup_code': row['lineup_code'], 'season_id': row['season_id'],
        'portal': dict(portal), 'energy': energy, 'energy_limit': portal['energy_limit'],
        'fits': complete and energy <= portal['energy_limit'],
        'cards': cards, 'note': note, 'note_truncated': len(row['note']) > len(note),
        'author': {
            'nickname': '系统' if role == 'admin' else (nickname or '未知用户'),
            'profile_url': f'/author/{username}' if username and role != 'admin' else None,
            'avatar_config': avatar_config({'id': row['user_id'], 'avatar_color': row_value(row, 'owner_avatar_color'),
                                            'avatar_preset': row_value(row, 'owner_avatar_preset'),
                                            'avatar_expression': row_value(row, 'owner_avatar_expression')}),
        },
        'favorite_count': int(row_value(row, 'favorite_count') or 0),
        'is_favorited': bool(row_value(row, 'is_favorited')),
        'like_count': int(row_value(row, 'like_count') or 0),
        'copy_count': int(row_value(row, 'copy_count') or 0),
        'is_liked_today': bool(row_value(row, 'is_liked_today')),
        'featured': bool(row['featured']),
        'has_formation': bool(row['formation_json']),
        'created_at': row['created_at'], 'updated_at': row['updated_at'], 'published_at': row['published_at'],
        'version': row['version'],
        'detail_url': f"/orange-decks/{row['id']}",
        'compat': {'saved_version': version_label(saved_version), 'current_version': version_label(current_version),
                   'issues': issues,
                   'missing_cards': sum(1 for card in cards if card and card['status'] == 'missing')},
        'can_edit': editable, 'can_delete': editable,
        'can_fork': can_derive(row, user), 'can_export': can_derive(row, user),
        'can_share': row['status'] == 'published',
        'can_moderate': admin,
    }
    if owner or admin:
        data['hidden_reason'] = row['hidden_reason']
    if detail:
        data['key_rounds'] = row['key_rounds']
        data['alternatives'] = row['alternatives']
        data['forked_from_id'] = row['forked_from_id']
    if share_base and row['status'] == 'published':
        data['share_url'] = share_base + data['detail_url']
        data['share_text'] = share_text(data, data['share_url'])
    if detail and owner and row['formation_json']:
        stored = json.loads(row['formation_json'])
        data['formation_edit'] = {'season': row['formation_season_id'], 'payload': stored['payload'], 'traits': stored.get('traits', [])}
    return data


def share_text(deck, url):
    names = '／'.join(f"{card['name']}（{card.get('tier_name') or '失效'}·{card['energy']}）" for card in deck['cards'] if card)
    return '\n'.join([
        f"【大橘大利卡组】{deck['name']}",
        f'卡片：{names}',
        f"推荐传送门：{deck['portal']['name']}（能量 {deck['energy']} / {deck['energy_limit']}）",
        f'详情：{url}',
    ])


# ---------------------------------------------------------------- reads

def deck_row(deck_id, user=None):
    columns, params = _viewer_columns(user)
    return get_db().execute(
        f'''SELECT d.*, {OWNER_COLUMNS}, {columns}
            FROM orange_decks d JOIN users u ON u.id = d.user_id WHERE d.id = ?''',
        (*params, deck_id),
    ).fetchone()


def get_visible(deck_id, user):
    row = deck_row(deck_id, user)
    if not visible_to(row, user):
        raise DeckError('卡组不存在', 404)
    return row


def matching_card_ids(query):
    terms = query.casefold()
    return [card['id'] for card in catalog()['cards'] if terms in card['name'].casefold()]


def list_decks(user, tab='latest', query='', portal='', page=1, page_size=10, share_base=None):
    if tab not in TABS:
        raise DeckError('列表类型无效')
    if tab in ('favorites', 'mine') and not user:
        raise DeckError('请先登录', 401)
    if portal and portal not in PORTAL_BY_ID:
        raise DeckError('传送门筛选无效')
    query = str(query or '').strip()[:40]
    page_size = max(1, min(int(page_size), 30))
    page = max(1, int(page))
    joins, clauses, params = [], [], []
    if tab == 'mine':
        clauses += ["d.status IN ('draft', 'published', 'hidden')", 'd.user_id = ?']
        params.append(user['id'])
    else:
        clauses.append("d.status = 'published'")
    if tab == 'favorites':
        joins.append('JOIN orange_deck_favorites mine ON mine.deck_id = d.id AND mine.user_id = ?')
        params.insert(0, user['id'])
    if tab == 'featured':
        clauses.append('d.featured = 1')
    if tab == 'hot':
        clauses.append(f'{INTERACTION_SCORE} > 0')
    if portal:
        clauses.append('d.portal_id = ?')
        params.append(portal)
    if query:
        escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        search = ["LOWER(d.name) LIKE ? ESCAPE '\\'"]
        params.append(f'%{escaped.lower()}%')
        card_ids = matching_card_ids(query)
        if card_ids:
            marks = ', '.join('?' for _ in card_ids)
            search += [f'd.card_id_{n} IN ({marks})' for n in range(1, DECK_SIZE + 1)]
            params += card_ids * DECK_SIZE
        clauses.append('(' + ' OR '.join(search) + ')')
    order = {
        'latest': 'd.published_at DESC, d.id DESC',
        'hot': f'{INTERACTION_SCORE} DESC, d.published_at DESC, d.id DESC',
        'featured': 'd.featured_at DESC, d.id DESC',
        'favorites': 'mine.created_at DESC, d.id DESC',
        'mine': 'd.updated_at DESC, d.id DESC',
    }[tab]
    ranking_joins = RANKING_COUNTS if tab == 'hot' else ''
    base = f"FROM orange_decks d JOIN users u ON u.id = d.user_id {ranking_joins} {' '.join(joins)} WHERE {' AND '.join(clauses)}"
    db = get_db()
    total = db.execute(f'SELECT COUNT(*) AS total {base}', params).fetchone()['total']
    columns, viewer_params = _viewer_columns(user, ranked=tab == 'hot')
    rows = db.execute(
        f'SELECT d.*, {OWNER_COLUMNS}, {columns} {base} ORDER BY {order} LIMIT ? OFFSET ?',
        viewer_params + params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return {
        'items': [serialize(row, user, share_base=share_base) for row in rows], 'total': total, 'page': page,
        'page_size': page_size, 'total_pages': max(1, -(-total // page_size)), 'tab': tab, 'q': query, 'portal': portal,
        'ranking_rule': HOT_RULE if tab == 'hot' else None,
    }


def export_payload(deck_id, user):
    """Creator-ready data for the poster tool; the tool decides how to keep local drafts."""
    row = get_visible(deck_id, user)
    if not can_derive(row, user):
        raise DeckError('该卡组当前不可导出', 404)
    deck = serialize(row, user, detail=True)
    formation = None
    if row['formation_json'] and row['formation_season_id'] == creator_formation_season():
        formation = json.loads(row['formation_json'])['payload']
    return {
        'id': row['id'], 'title': row['name'], 'author': deck['author']['nickname'][:16], 'portal': row['portal_id'],
        'cards': [card['id'] if card and card['status'] != 'missing' else None for card in deck['cards']],
        'note': row['note'][:100], 'tempo': row['key_rounds'][:24],
        'layout': 'guide' if formation else 'cards', 'formation': formation,
        'formation_dropped': bool(row['formation_json']) and formation is None,
    }


# ---------------------------------------------------------------- writes

def _status_for(action, current):
    if action not in ('draft', 'publish', 'save'):
        raise DeckError('保存操作无效')
    if current == 'hidden':
        if action != 'save':
            raise DeckError('该卡组已被管理员隐藏，可修改内容，但需管理员恢复后才会重新公开', 409)
        return 'hidden'
    if action == 'save':
        return current or 'draft'
    return 'published' if action == 'publish' else 'draft'


def _fields(data, status, existing=None):
    public = status in ('published', 'hidden')
    name = _text(data, 'name', required=public) or '未命名卡组'
    cards = validate_cards(data.get('cards'), require_complete=public)
    portal = validate_portal(data.get('portal'))
    energy = check_energy(cards, portal) if public else deck_energy(cards)
    season_id = data.get('season_id', existing['season_id'] if existing is not None else card_season_id())
    if season_id != card_season_id():
        raise DeckError('卡组所属赛季与当前时间卡片资料不一致')
    if existing is not None and season_id != existing['season_id']:
        raise DeckError('不能更改已保存卡组的所属赛季')
    plan_code = validate_plan_code(_text(data, 'plan_code', default=existing['plan_code'] if existing is not None else ''))
    raw_lineup_code = _text(data, 'lineup_code', default=existing['lineup_code'] if existing is not None else '')
    lineup_code = extract_lineup_code(raw_lineup_code) if raw_lineup_code else ''
    if raw_lineup_code and not lineup_code:
        raise DeckError(LINEUP_CODE_MESSAGE)
    fields = {'name': name, 'card_id_1': cards[0], 'card_id_2': cards[1], 'card_id_3': cards[2], 'portal_id': portal,
              'plan_code': plan_code, 'lineup_code': lineup_code, 'season_id': season_id,
              'energy': energy, 'note': _text(data, 'note'), 'key_rounds': _text(data, 'key_rounds'),
              'alternatives': _text(data, 'alternatives'), 'card_version': card_version(), 'card_snapshot_json': card_snapshot(cards)}
    # An absent key keeps the saved formation (it may belong to an earlier creator season); null removes it.
    if 'formation' in data:
        formation = validate_formation(data['formation'])
        if formation and formation['season'] != season_id:
            raise DeckError('阵容所属赛季必须与时间卡片所属赛季一致')
        fields.update(formation_json=json.dumps(formation, ensure_ascii=False) if formation else None,
                      formation_season_id=formation['season'] if formation else None,
                      formation_version_id=formation['version_id'] if formation else None)
    elif existing is None:
        fields.update(formation_json=None, formation_season_id=None, formation_version_id=None)
    return fields


def _limit(user, scope, limit):
    if hit_limit(scope, str(user['id']), limit, 60):
        raise DeckError('操作过于频繁，请稍后再试', 429)


def create_deck(user, data, *, commit=True):
    data = data if isinstance(data, dict) else {}
    status = _status_for(data.get('action', 'draft'), None)
    fields = _fields(data, status)
    # Scoped uploads already consume the automation quota before locking permissions.
    if commit:
        _limit(user, 'orange_deck_create', 30)
    now = now_text()
    fields.update(user_id=user['id'], status=status, created_at=now, updated_at=now,
                  published_at=now if status == 'published' else None, forked_from_id=None)
    columns = list(fields)
    db = get_db()
    cursor = db.execute(insert_returning_id_sql(
        f"INSERT INTO orange_decks ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})", db_kind()),
        [fields[c] for c in columns])
    deck_id = last_insert_id(cursor, db_kind())
    if commit:
        db.commit()
    return serialize(deck_row(deck_id, user), user, detail=True)


def update_deck(user, deck_id, data):
    data = data if isinstance(data, dict) else {}
    row = get_visible(deck_id, user)
    if not is_owner(row, user):
        raise DeckError('只能编辑自己的卡组', 403)
    if data.get('version') != row['version']:
        raise DeckError('卡组已在其他页面更新，请刷新后再编辑', 409)
    status = _status_for(data.get('action', 'save'), row['status'])
    fields = _fields(data, status, existing=row)
    now = now_text()
    fields.update(status=status, updated_at=now, version=row['version'] + 1)
    if status == 'published' and not row['published_at']:
        fields['published_at'] = now
    if status != 'published':
        fields.update(featured=0, featured_at=None)
    assignments = ', '.join(f'{column} = ?' for column in fields)
    db = get_db()
    cursor = db.execute(f'UPDATE orange_decks SET {assignments} WHERE id = ? AND version = ?',
                        [*fields.values(), deck_id, row['version']])
    if not cursor.rowcount:
        db.rollback()
        raise DeckError('卡组已在其他页面更新，请刷新后再编辑', 409)
    db.commit()
    return serialize(deck_row(deck_id, user), user, detail=True)


def delete_deck(user, deck_id):
    row = get_visible(deck_id, user)
    if not is_owner(row, user):
        raise DeckError('只能删除自己的卡组', 403)
    db = get_db()
    db.execute("UPDATE orange_decks SET status = 'deleted', featured = 0, featured_at = NULL, updated_at = ?, version = version + 1 WHERE id = ?",
               (now_text(), deck_id))
    db.commit()


def favorite(user, deck_id, on):
    db = get_db()
    if on:
        row = get_visible(deck_id, user)
        if row['status'] != 'published':
            raise DeckError('只能收藏公开的卡组', 409)
        db.execute('INSERT INTO orange_deck_favorites (user_id, deck_id, created_at) VALUES (?, ?, ?) '
                   'ON CONFLICT (user_id, deck_id) DO NOTHING', (user['id'], deck_id, now_text()))
    else:
        # Removing is always allowed so a hidden deck can still leave a user's list.
        db.execute('DELETE FROM orange_deck_favorites WHERE user_id = ? AND deck_id = ?', (user['id'], deck_id))
    db.commit()
    count = db.execute('SELECT COUNT(*) AS c FROM orange_deck_favorites WHERE deck_id = ?', (deck_id,)).fetchone()['c']
    return {'favorited': on, 'favorite_count': count}


def like(user, deck_id):
    """Mirror lineup likes: once per deck per day, five deck likes per account per day."""
    db, day = get_db(), today()
    # Serialize this account's quota checks on both SQLite and PostgreSQL.
    db.execute('UPDATE users SET id=id WHERE id=?', (user['id'],))
    row = get_visible(deck_id, user)
    if row['status'] != 'published':
        raise DeckError('只能点赞公开的卡组', 409)
    used = db.execute('SELECT COUNT(*) AS c FROM orange_deck_likes WHERE user_id = ? AND like_date = ?', (user['id'], day)).fetchone()['c']
    if used >= DAILY_LIKE_LIMIT:
        raise DeckError('今天的卡组点赞次数已用完', 429)
    cursor = db.execute('INSERT INTO orange_deck_likes (user_id, deck_id, like_date, created_at) VALUES (?, ?, ?, ?) '
                        'ON CONFLICT (user_id, deck_id, like_date) DO NOTHING', (user['id'], deck_id, day, now_text()))
    if not cursor.rowcount:
        db.rollback()
        raise DeckError('今天已经点赞过该卡组', 409)
    db.commit()
    count = db.execute('SELECT COUNT(*) AS c FROM orange_deck_likes WHERE deck_id = ?', (deck_id,)).fetchone()['c']
    return {'liked_today': True, 'like_count': count}


def record_copy(user, deck_id, ip, code_type='plan'):
    """Count either code; keep the existing per-deck five-minute deduplication."""
    if code_type not in ('plan', 'lineup'):
        raise DeckError('复制类型无效')
    column = 'plan_code' if code_type == 'plan' else 'lineup_code'
    label = '方案码' if code_type == 'plan' else '阵容码'
    db = get_db()
    # Copy recording needs visibility and the chosen code, not author metadata or social counts.
    row = db.execute('SELECT user_id, status, plan_code, lineup_code FROM orange_decks WHERE id = ?', (deck_id,)).fetchone()
    if not visible_to(row, user):
        raise DeckError('卡组不存在', 404)
    if row['status'] != 'published':
        raise DeckError('只能统计公开卡组的复制次数', 409)
    if not row[column]:
        raise DeckError(f'此卡组暂未提供{label}', 400)
    key = f'user:{user["id"]}' if user else f'ip:{ip}'
    cursor = db.execute(
        f'''INSERT INTO orange_deck_copies (deck_id, copy_key, bucket_start, created_at)
           SELECT id, ?, ?, ? FROM orange_decks WHERE id = ? AND status = 'published' AND {column} <> ''
           ON CONFLICT (deck_id, copy_key, bucket_start) DO NOTHING''',
        (key, bucket_start(), now_text(), deck_id),
    )
    counted = bool(cursor.rowcount)
    count = db.execute('SELECT COUNT(*) AS c FROM orange_deck_copies WHERE deck_id = ?', (deck_id,)).fetchone()['c']
    db.commit()
    return {'counted': counted, 'copy_count': count}


def received_summary(user_id):
    """Personal-centre figures for the user's own decks, kept apart from lineup totals."""
    db = get_db()
    one = lambda sql: db.execute(sql, (user_id,)).fetchone()['c']
    return {
        'decks': one("SELECT COUNT(*) AS c FROM orange_decks WHERE user_id = ? AND status != 'deleted'"),
        'published_decks': one("SELECT COUNT(*) AS c FROM orange_decks WHERE user_id = ? AND status = 'published'"),
        'draft_decks': one("SELECT COUNT(*) AS c FROM orange_decks WHERE user_id = ? AND status = 'draft'"),
        'hidden_decks': one("SELECT COUNT(*) AS c FROM orange_decks WHERE user_id = ? AND status = 'hidden'"),
        'received_likes': one('SELECT COUNT(*) AS c FROM orange_deck_likes l JOIN orange_decks d ON d.id = l.deck_id WHERE d.user_id = ?'),
        'received_favorites': one('SELECT COUNT(*) AS c FROM orange_deck_favorites f JOIN orange_decks d ON d.id = f.deck_id WHERE d.user_id = ?'),
    }


def fork_deck(user, deck_id):
    """Create a new draft for the current user; the source deck and existing drafts stay untouched."""
    row = get_visible(deck_id, user)
    if not can_derive(row, user):
        raise DeckError('该卡组当前不可作为基础创建', 404)
    _limit(user, 'orange_deck_create', 30)
    index, notes = (card_index() if row['season_id'] == card_season_id() else {}), []
    cards = [row[f'card_id_{n}'] if row[f'card_id_{n}'] in index else None for n in range(1, DECK_SIZE + 1)]
    if None in cards and all(row[f'card_id_{n}'] for n in range(1, DECK_SIZE + 1)):
        notes.append('原卡组中有卡片已在当前资料中失效，对应卡槽已留空，请重新选择。')
    formation = row['formation_json']
    if formation and row['formation_season_id'] != creator_formation_season():
        formation = None
        notes.append('原卡组的阵容属于当前未开放的赛季资料，未复制阵容。')
    now = now_text()
    fields = {
        'user_id': user['id'], 'name': row['name'], 'card_id_1': cards[0], 'card_id_2': cards[1], 'card_id_3': cards[2],
        'season_id': card_season_id(), 'plan_code': '', 'lineup_code': '',
        'portal_id': row['portal_id'], 'energy': deck_energy(cards), 'note': row['note'], 'key_rounds': row['key_rounds'],
        'alternatives': row['alternatives'], 'formation_json': formation,
        'formation_season_id': row['formation_season_id'] if formation else None,
        'formation_version_id': row['formation_version_id'] if formation else None,
        'card_version': card_version(), 'card_snapshot_json': card_snapshot(cards), 'status': 'draft',
        'forked_from_id': row['id'], 'created_at': now, 'updated_at': now,
    }
    db = get_db()
    cursor = db.execute(insert_returning_id_sql(
        f"INSERT INTO orange_decks ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})", db_kind()),
        list(fields.values()))
    new_id = last_insert_id(cursor, db_kind())
    db.commit()
    return {'id': new_id, 'edit_url': f'/orange-decks/{new_id}/edit', 'notes': notes}


# ---------------------------------------------------------------- admin

ADMIN_FILTERS = {
    'all': "d.status IN ('published', 'hidden')",
    'published': "d.status = 'published'",
    'featured': "d.status = 'published' AND d.featured = 1",
    'hidden': "d.status = 'hidden'",
}


def admin_list(admin, status='all', query='', page=1, page_size=20):
    if status not in ADMIN_FILTERS:
        raise DeckError('筛选条件无效')
    clauses, params = [ADMIN_FILTERS[status]], []
    query = str(query or '').strip()[:40]
    if query:
        escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_').lower()
        clauses.append("(LOWER(d.name) LIKE ? ESCAPE '\\' OR LOWER(u.nickname) LIKE ? ESCAPE '\\' OR LOWER(u.username) LIKE ? ESCAPE '\\')")
        params += [f'%{escaped}%'] * 3
    page_size, page = max(1, min(int(page_size), 50)), max(1, int(page))
    base = f"FROM orange_decks d JOIN users u ON u.id = d.user_id WHERE {' AND '.join(clauses)}"
    db = get_db()
    total = db.execute(f'SELECT COUNT(*) AS total {base}', params).fetchone()['total']
    rows = db.execute(f'SELECT d.*, {OWNER_COLUMNS}, {_viewer_columns(None)[0]} {base} '
                      'ORDER BY d.updated_at DESC, d.id DESC LIMIT ? OFFSET ?', params + [page_size, (page - 1) * page_size]).fetchall()
    counts = {row['status']: row['c'] for row in db.execute(
        "SELECT status, COUNT(*) AS c FROM orange_decks WHERE status IN ('published', 'hidden') GROUP BY status").fetchall()}
    counts['featured'] = db.execute("SELECT COUNT(*) AS c FROM orange_decks WHERE status = 'published' AND featured = 1").fetchone()['c']
    return {'items': [serialize(row, admin) for row in rows], 'total': total, 'page': page, 'page_size': page_size,
            'total_pages': max(1, -(-total // page_size)), 'counts': counts}


def admin_moderate(admin, deck_id, action, data):
    data = data if isinstance(data, dict) else {}
    row = deck_row(deck_id)
    if row is None or row['status'] not in ('published', 'hidden'):
        raise DeckError('卡组不存在', 404)
    if data.get('version') != row['version']:
        raise DeckError('卡组已被更新，请刷新列表后再操作', 409)
    now = now_text()
    if action in ('feature', 'unfeature'):
        if row['status'] != 'published':
            raise DeckError('只能推荐公开中的卡组', 409)
        changes = {'featured': 1 if action == 'feature' else 0, 'featured_at': now if action == 'feature' else None}
    elif action == 'hide':
        reason = str(data.get('reason') or '').strip()
        if not 2 <= len(reason) <= 200:
            raise DeckError('请填写 2–200 字隐藏原因')
        if row['status'] != 'published':
            raise DeckError('该卡组已隐藏', 409)
        changes = {'status': 'hidden', 'hidden_reason': reason, 'featured': 0, 'featured_at': None}
    elif action == 'restore':
        if row['status'] != 'hidden':
            raise DeckError('该卡组未被隐藏', 409)
        changes = {'status': 'published', 'hidden_reason': ''}
    else:
        raise DeckError('操作无效', 404)
    changes.update(updated_at=now, version=row['version'] + 1)
    db = get_db()
    try:
        cursor = db.execute(f"UPDATE orange_decks SET {', '.join(f'{k} = ?' for k in changes)} WHERE id = ? AND version = ?",
                   [*changes.values(), deck_id, row['version']])
        if not cursor.rowcount:
            raise DeckError('卡组已被更新，请刷新列表后再操作', 409)
        before = {'status': row['status'], 'featured': bool(row['featured'])}
        after = {'status': changes.get('status', row['status']), 'featured': bool(changes.get('featured', row['featured']))}
        if action == 'hide':
            after['reason'] = changes['hidden_reason']
        write_audit(admin['id'], f'orange_deck.{action}', 'orange_deck', target_id=deck_id, before=before, after=after)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return serialize(deck_row(deck_id, admin), admin)


def published_deck_entries():
    return get_db().execute(
        "SELECT id, updated_at FROM orange_decks WHERE status = 'published' ORDER BY updated_at DESC, id DESC").fetchall()
