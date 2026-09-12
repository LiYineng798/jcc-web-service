"""Paginated audit discovery and on-demand, redacted snapshots for administrators."""
import json
import re
from datetime import date, timedelta

from admin_pagination import paginate_rows

ACTION_LABELS = {
    'create_user': '创建用户', 'update_user': '更新用户', 'disable_user': '禁用用户',
    'create_lineup': '创建阵容', 'update_lineup': '更新阵容', 'delete_lineup': '删除阵容',
    'hide_lineup': '隐藏阵容', 'admin_update_lineup': '管理员更新阵容',
    'admin_bulk_import_lineups': '批量导入阵容', 'adjust_score': '调整阵容评分',
    'handle_report': '处理失效反馈', 'create_patch_note': '创建更新公告',
    'update_patch_note': '更新版本公告', 'create_notice': '创建站点通知',
    'update_saved_notice': '编辑站点通知', 'delete_saved_notice': '删除站点通知',
    'activate_notice': '启用站点通知', 'update_notice': '更新首页通知',
    'update_setting': '更新系统设置', 'update_settings': '更新系统设置', 'generate_daily_report': '生成每日报告',
    'admin_add_live_comp_manual_code': '补充实时阵容码',
    'create_live_comps_season': '创建实时阵容赛季',
    'update_live_comps_season': '更新实时阵容赛季',
    'touch_live_comps_season_updated_at': '刷新赛季更新时间',
    'update_season_display': '调整赛季展示',
    'delete_guestbook_message': '删除留言', 'update_guestbook_message': '更新留言状态',
    'queue_live_comp_upload': '提交阵容上传', 'complete_live_comp_upload': '完成阵容上传',
    'fail_live_comp_upload': '阵容上传失败',
    'update_simulator_season_visibility': '调整模拟器赛季展示',
    'update_library_season_visibility': '调整资料库赛季展示',
}
TARGET_LABELS = {
    'user': '用户', 'lineup': '阵容', 'lineup_bulk_import': '批量导入',
    'report': '失效反馈', 'patch_note': '更新公告', 'site_notice': '站点通知',
    'app_setting': '系统设置', 'daily_report': '每日报告', 'live_comp': '实时阵容',
    'live_comp_season': '实时阵容赛季', 'live_comp_upload_job': '阵容上传',
    'season_display': '赛季展示', 'guestbook_message': '留言',
    'season_package': '赛季更新包', 'season': '赛季',
}
KIND_LABELS = {'create': '新增', 'update': '修改', 'remove': '删除 / 停用', 'publish': '发布', 'error': '异常', 'other': '其他'}


def action_kind(action):
    if action.startswith('fail_'):
        return 'error'
    if any(word in action for word in ('delete', 'disable', 'hide', 'cancel')):
        return 'remove'
    if any(word in action for word in ('publish', 'activate', 'rollback')):
        return 'publish'
    if any(word in action for word in ('create', 'import', 'add_', 'upload', 'generate')):
        return 'create'
    if any(word in action for word in ('update', 'adjust', 'handle', 'touch', 'retry')):
        return 'update'
    return 'other'


FROM_SQL = ' FROM audit_logs a LEFT JOIN users u ON u.id = a.actor_user_id'
SELECT_SQL = '''SELECT a.id, a.actor_user_id, a.action, a.target_type, a.target_id,
    a.target_key, a.created_at, u.username AS actor_username, u.nickname AS actor_nickname'''


def serialize_log(row):
    item = dict(row)
    item['action_label'] = ACTION_LABELS.get(item['action'], item['action'])
    item['target_label'] = TARGET_LABELS.get(item['target_type'], item['target_type'])
    item['kind'] = action_kind(item['action'])
    item['kind_label'] = KIND_LABELS[item['kind']]
    item['actor_label'] = item['actor_nickname'] or item['actor_username'] or (
        f"用户 #{item['actor_user_id']}（已不存在）" if item['actor_user_id'] is not None else '系统'
    )
    return item


def list_admin_audit_logs(db, page, page_size, *, query='', targets=(), kinds=(), start='', end=''):
    # Facets cover the entire history, not just the current page. Never load snapshot blobs here.
    facets = db.execute('SELECT action, target_type, COUNT(*) AS c FROM audit_logs GROUP BY action, target_type').fetchall()
    target_counts, kind_counts = {}, {}
    for row in facets:
        target_counts[row['target_type']] = target_counts.get(row['target_type'], 0) + row['c']
        kind = action_kind(row['action'])
        kind_counts[kind] = kind_counts.get(kind, 0) + row['c']
    conditions, params = [], []
    query = query.strip()[:200]
    if query:
        # Escape LIKE metacharacters so pasted IDs and underscores are literal.
        needle = '%' + query.lower().replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
        fields = ['a.action', 'a.target_type', 'a.target_key', 'CAST(a.target_id AS TEXT)',
                  'CAST(a.actor_user_id AS TEXT)', 'u.username', 'u.nickname']
        matches = [f"LOWER(COALESCE({field}, '')) LIKE ? ESCAPE '!'" for field in fields]
        params.extend([needle] * len(fields))
        for field, labels in [('a.action', ACTION_LABELS), ('a.target_type', TARGET_LABELS)]:
            values = [key for key, label in labels.items() if query.lower() in label.lower()]
            if values:
                matches.append(f"{field} IN ({','.join('?' for _ in values)})")
                params.extend(values)
        conditions.append('(' + ' OR '.join(matches) + ')')
    if targets:
        targets = list(dict.fromkeys(targets))[:50]
        conditions.append(f"a.target_type IN ({','.join('?' for _ in targets)})")
        params.extend(targets)
    if kinds:
        actions = sorted({row['action'] for row in facets if action_kind(row['action']) in kinds})
        conditions.append(f"a.action IN ({','.join('?' for _ in actions)})" if actions else '1 = 0')
        params.extend(actions)
    try:
        first = date.fromisoformat(start) if start else None
        last = date.fromisoformat(end) if end else None
        if first and last and first > last:
            raise ValueError
        if first:
            conditions.append('a.created_at >= ?')
            params.append(first.isoformat() + ' 00:00:00')
        if last:
            conditions.append('a.created_at < ?')
            params.append((last + timedelta(days=1)).isoformat() + ' 00:00:00')
    except (ValueError, OverflowError):
        raise ValueError('请选择有效的日期范围，开始日期不能晚于结束日期') from None
    where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
    payload = paginate_rows(db, SELECT_SQL + FROM_SQL + where + ' ORDER BY a.id DESC',
                            'SELECT COUNT(*) AS c' + FROM_SQL + where, params, page, page_size,
                            serializer=serialize_log)
    payload['total_all'] = sum(target_counts.values())
    payload['filters'] = {
        'targets': [{'value': key, 'label': TARGET_LABELS.get(key, key), 'count': count}
                    for key, count in sorted(target_counts.items())],
        'kinds': [{'value': key, 'label': label, 'count': kind_counts.get(key, 0)}
                  for key, label in KIND_LABELS.items() if kind_counts.get(key)],
    }
    return payload


def redact_snapshot(value):
    if isinstance(value, dict):
        if re.search(r'password|secret|token|api.?key|credential|database.?url',
                     str(value.get('setting_key', '')), re.I):
            value = {**value, 'setting_value': '[已隐藏敏感字段]'}
        return {key: '[已隐藏敏感字段]' if re.search(
            r'password|passwd|pwd|secret|token|api.?key|authorization|cookie|credential|private.?key|database.?url',
            str(key), re.I) else redact_snapshot(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_snapshot(item) for item in value]
    return value


def parse_snapshot(raw):
    if raw is None:
        return None
    try:
        return redact_snapshot(json.loads(raw))
    except (ValueError, TypeError, RecursionError):
        # Do not return unparsed historical blobs: they could contain credentials.
        return '[历史记录无法解析]'


def get_admin_audit_log(db, log_id):
    row = db.execute(SELECT_SQL + ', a.before_json, a.after_json' + FROM_SQL + ' WHERE a.id = ?', (log_id,)).fetchone()
    if row is None:
        return None
    item = serialize_log(row)
    item['before'] = parse_snapshot(item.pop('before_json'))
    item['after'] = parse_snapshot(item.pop('after_json'))
    return item
