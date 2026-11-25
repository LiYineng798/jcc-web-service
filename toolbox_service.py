"""Shared navigation catalog and runtime lifecycle overrides for the public toolbox.

Built-in tool metadata lives in TOOLBOX_TOOLS as the baseline; rows in
`toolbox_items` override status (visible / unlisted / disabled), ordering,
grouping, and display copy at runtime without code deployments.
"""
from audit import write_audit
from db import get_db, now_text
from settings_service import get_setting

VALID_STATUSES = ('visible', 'unlisted', 'disabled')
MAX_TITLE_LEN = 80
MAX_DESCRIPTION_LEN = 160
MAX_GROUP_LEN = 40

TOOLBOX_TOOLS = (
    dict(id='lineup-simulator', title='阵容模拟器', description='搭配弈子、装备与羁绊 · 通用工具', group='', setting='simulator_enabled'),
    dict(id='orange-fortune', title='时间卡片图鉴', description='五大品阶 · 传送门规则 · 完整效果', group='英雄联盟传奇大橘大利'),
    dict(id='orange-fortune-creator', title='大橘大利创作者工具', description='三卡构筑 · 传送门校验 · 3:4 海报', group='英雄联盟传奇大橘大利'),
    dict(id='s18-trait-ladder', title='羁绊天梯计算器', description='多羁绊阵容搜索 · 转职与阶段奖励', group='S18 · 当季工具'),
    dict(id='s18-witch-rewards', title='魔女层数奖励查询', description='9 档层数 · 概率、星级与预计价值', group='S18 · 当季工具'),
    dict(id='golden-egg', title='金蛋奖励', description='海克斯奖励一览 · 概率与物品数量', group='S18 · 当季工具'),
    dict(id='s16-5-lucky-openings', title='S16.5 恭喜发财开局推荐', description='九位五费弈子 · 专属效果与阵容码', group='S16.5 · 恭喜发财', aria_label='S16.5恭喜发财开局阵容码推荐'),
    dict(id='s11-artifacts', title='全神器装备推荐', description='31 件神器 · 装备效果与推荐弈子', group='S11 · 画之灵'),
    dict(id='s11-items', title='全弈子推荐出装', description='60 位弈子 · 推荐、备选与装备合成', group='S11 · 画之灵'),
    dict(id='special-mechanics', title='S8 特殊机制', description='怪兽入侵战力与经济形态说明', group='S8 · 怪兽入侵', default_status='unlisted'),
    dict(id='artifact-guide', title='S8 神器搭配指南', description='英雄与神器实战搭配推荐', group='S8 · 怪兽入侵', default_status='unlisted'),
    dict(id='returning-equipment', title='S8 回归装备', description='回归装备属性、组件与效果说明', group='S8 · 怪兽入侵', default_status='unlisted'),
)

_UPSERT_SQL = '''
INSERT INTO toolbox_items (tool_id, title, description, group_name, status, sort_order, updated_at, updated_by)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (tool_id) DO UPDATE SET
    title = excluded.title,
    description = excluded.description,
    group_name = excluded.group_name,
    status = excluded.status,
    sort_order = excluded.sort_order,
    updated_at = excluded.updated_at,
    updated_by = excluded.updated_by
'''


def _default_status(tool):
    if not tool.get('visible', True):
        return 'disabled'
    status = tool.get('default_status', 'visible')
    return status if status in VALID_STATUSES else 'visible'


def _load_overrides(db):
    rows = db.execute(
        '''
        SELECT tool_id, title, description, group_name, status, sort_order, updated_at, updated_by
        FROM toolbox_items
        '''
    ).fetchall()
    return {row['tool_id']: dict(row) for row in rows}


def _merge_tool(base, default_order, override, db):
    setting_key = base.get('setting') or ''
    setting_enabled = True if not setting_key else get_setting(db, setting_key, 'true') == 'true'
    default_status = _default_status(base)
    status = override['status'] if override and override['status'] in VALID_STATUSES else default_status
    sort_order = int(override['sort_order']) if override else default_order
    title = override['title'] if override else base['title']
    description = override['description'] if override else base.get('description', '')
    group = override['group_name'] if override else base.get('group', '')
    item = {
        **base,
        'title': title,
        'description': description,
        'group': group,
        'url': '/tools/' + base['id'],
        'status': status,
        'sort_order': sort_order,
        'setting': setting_key,
        'setting_enabled': setting_enabled,
        'effective_status': status if setting_enabled else 'disabled',
        'customized': bool(override),
        'updated_at': override['updated_at'] if override else None,
        'defaults': {
            'title': base['title'],
            'description': base.get('description', ''),
            'group': base.get('group', ''),
            'status': default_status,
            'sort_order': default_order,
        },
    }
    return item


def list_all_toolbox_tools(db=None):
    db = db if db is not None else get_db()
    overrides = _load_overrides(db)
    merged = [
        (_merge_tool(tool, index, overrides.get(tool['id']), db), index)
        for index, tool in enumerate(TOOLBOX_TOOLS, start=1)
    ]
    merged.sort(key=lambda pair: (pair[0]['sort_order'], pair[1]))
    return [item for item, _ in merged]


def list_toolbox_tools(db=None):
    return [
        tool for tool in list_all_toolbox_tools(db)
        if tool['effective_status'] == 'visible'
    ]


def get_toolbox_tool(tool_id, db=None):
    return next((tool for tool in list_all_toolbox_tools(db) if tool['id'] == tool_id), None)


def tool_for_url(url, db=None):
    return next((tool for tool in list_toolbox_tools(db) if tool['url'] == url), None)


def toolbox_state_version(db=None):
    return tuple(
        (tool['id'], tool['effective_status'], tool['sort_order'])
        for tool in list_all_toolbox_tools(db)
    )


def check_tool_access(tool_id, user=None, preview=False, db=None):
    """Return (state, noindex) for a public /tools/<id> route.

    state is one of 'ok', 'preview', or 'not_found'.
    """
    tool = get_toolbox_tool(tool_id, db=db)
    if tool is None:
        return 'not_found', True
    effective = tool['effective_status']
    if effective == 'visible':
        return 'ok', False
    if effective == 'unlisted':
        return 'ok', True
    if preview and user and user['role'] == 'admin':
        return 'preview', True
    return 'not_found', True


def _audit_snapshot(tool):
    return {
        'id': tool['id'],
        'title': tool['title'],
        'description': tool['description'],
        'group': tool['group'],
        'status': tool['status'],
        'sort_order': tool['sort_order'],
    }


def update_toolbox_tool(db, actor_user_id, tool_id, data):
    current = get_toolbox_tool(tool_id, db=db)
    if current is None:
        return None, '工具不存在', 404
    if not isinstance(data, dict):
        return None, '请求参数无效', 400

    title = current['title']
    if 'title' in data:
        title = str(data.get('title') or '').strip()
        if not title or len(title) > MAX_TITLE_LEN:
            return None, f'标题长度需在 1-{MAX_TITLE_LEN} 字之间', 400

    description = current['description']
    if 'description' in data:
        description = str(data.get('description') or '').strip()
        if len(description) > MAX_DESCRIPTION_LEN:
            return None, f'简介不能超过 {MAX_DESCRIPTION_LEN} 字', 400

    group_name = current['group']
    if 'group' in data:
        group_name = str(data.get('group') or '').strip()
        if len(group_name) > MAX_GROUP_LEN:
            return None, f'分组名不能超过 {MAX_GROUP_LEN} 字', 400

    status = current['status']
    if 'status' in data:
        status = str(data.get('status') or '').strip().lower()
        if status not in VALID_STATUSES:
            return None, '状态无效，仅支持 visible / unlisted / disabled', 400

    sort_order = current['sort_order']
    if 'sort_order' in data:
        try:
            sort_order = int(data['sort_order'])
        except (TypeError, ValueError):
            return None, '排序必须为整数', 400
        if sort_order < 0 or sort_order > 9999:
            return None, '排序范围需在 0-9999 之间', 400

    before = _audit_snapshot(current)
    now = now_text()
    try:
        db.execute(
            _UPSERT_SQL,
            (tool_id, title, description, group_name, status, sort_order, now, actor_user_id),
        )
        updated = get_toolbox_tool(tool_id, db=db)
        write_audit(
            actor_user_id,
            'update_toolbox_item',
            'toolbox_item',
            target_key=tool_id,
            before=before,
            after=_audit_snapshot(updated),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return updated, None, 200


def reorder_toolbox_tools(db, actor_user_id, ordered_entries):
    if not isinstance(ordered_entries, list) or not ordered_entries:
        return None, '请提供有效的工具排序列表', 400
    all_tools = list_all_toolbox_tools(db)
    by_id = {tool['id']: tool for tool in all_tools}
    cleaned = []
    seen = set()
    for entry in ordered_entries:
        if isinstance(entry, dict):
            tool_id = str(entry.get('id') or '').strip()
            group_name = str(entry.get('group') or '').strip() if 'group' in entry else None
        else:
            tool_id = str(entry or '').strip()
            group_name = None
        if tool_id not in by_id or tool_id in seen:
            return None, f'无效或重复的工具 ID: {tool_id}', 400
        if group_name is not None and len(group_name) > MAX_GROUP_LEN:
            return None, f'分组名不能超过 {MAX_GROUP_LEN} 字', 400
        seen.add(tool_id)
        cleaned.append((tool_id, by_id[tool_id]['group'] if group_name is None else group_name))
    for tool in all_tools:
        if tool['id'] not in seen:
            cleaned.append((tool['id'], tool['group']))

    before_order = [{'id': tool['id'], 'group': tool['group']} for tool in all_tools]
    after_order = [{'id': tool_id, 'group': group_name} for tool_id, group_name in cleaned]
    now = now_text()
    try:
        for index, (tool_id, group_name) in enumerate(cleaned, start=1):
            tool = by_id[tool_id]
            db.execute(
                _UPSERT_SQL,
                (tool_id, tool['title'], tool['description'], group_name, tool['status'], index, now, actor_user_id),
            )
        write_audit(
            actor_user_id,
            'reorder_toolbox',
            'toolbox_item',
            target_key='all',
            before={'order': before_order},
            after={'order': after_order},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return list_all_toolbox_tools(db), None, 200


def reset_toolbox_tool(db, actor_user_id, tool_id):
    current = get_toolbox_tool(tool_id, db=db)
    if current is None:
        return None, '工具不存在', 404
    before = _audit_snapshot(current)
    try:
        db.execute('DELETE FROM toolbox_items WHERE tool_id = ?', (tool_id,))
        restored = get_toolbox_tool(tool_id, db=db)
        write_audit(
            actor_user_id,
            'reset_toolbox_item',
            'toolbox_item',
            target_key=tool_id,
            before=before,
            after=_audit_snapshot(restored),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return restored, None, 200
