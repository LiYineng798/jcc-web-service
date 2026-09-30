"""Settled public-lineup searches and coarse device statistics."""
from datetime import date, datetime, timedelta
import re

from flask import current_app, request
from itsdangerous import URLSafeTimedSerializer, BadSignature

from db import db_kind, get_db, now_text
from db_adapter import insert_ignore_sql
from device_type import DEVICE_LABELS, request_device_type
from lineup_cache import TimedCache
from lineups_utils import lineup_season_manifest
from visits import VISITOR_COOKIE_NAME, is_bot_request, resolve_visitor_identity

SORT_LABELS = {'latest': '最新', 'hot': '最热', 'rising': '上升', 'recommended': '推荐', 'ss': 'SS'}
_cache = TimedCache(30, 32)


def _signer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='public-search-result-v1')


def _actor(user):
    token = request.cookies.get(VISITOR_COOKIE_NAME, '').strip()
    return resolve_visitor_identity(user, token, request.remote_addr)[1] if user or token else None


def issue_search_receipt(user, view, sort, query, season_id, total):
    """Sign the actual result count, without recording requests/type-ahead."""
    if view != 'all' or sort not in SORT_LABELS or not query or len(query) > 80:
        return None
    if is_bot_request() or (user and user['role'] == 'admin'):
        return None
    actor = _actor(user)
    if not actor:
        return None
    manifest = lineup_season_manifest()
    season_id = season_id or manifest['default_season_id']
    if season_id not in {item['id'] for item in manifest['seasons']}:
        return None
    return _signer().dumps({'actor': actor, 'query': query, 'season': season_id, 'sort': sort, 'total': int(total)})


def record_search_result(data, user):
    if is_bot_request() or (user and user['role'] == 'admin'):
        return None
    if not isinstance(data, dict) or not re.fullmatch(r'[a-f0-9]{32}', str(data.get('event_id', ''))):
        raise ValueError('搜索事件标识无效')
    receipt = data.get('receipt')
    if not isinstance(receipt, str) or len(receipt) > 3000:
        raise ValueError('搜索结果凭据无效')
    try:
        payload = _signer().loads(receipt, max_age=600)
    except BadSignature:
        raise ValueError('搜索结果凭据已过期或无效') from None
    actor = _actor(user)
    if not actor or payload.get('actor') != actor:
        raise ValueError('搜索结果凭据与当前访客不匹配')
    db = get_db()
    event_id = data['event_id']
    if db.execute('SELECT id FROM search_events WHERE visitor_key=? AND event_id=?', (actor, event_id)).fetchone():
        return None
    from rate_limit import hit_limit
    from auth import get_client_ip
    if hit_limit('search_analytics', get_client_ip(), 120, 5):
        return 'limited'
    # Normalization only affects analytics; search matching itself is unchanged.
    query = ' '.join(payload['query'].split()).casefold()
    db.execute(insert_ignore_sql('search_events',
        ['event_id','visitor_key','user_id','query','season_id','sort_key','result_count','device_type','created_at'],
        ['visitor_key','event_id'], db_kind()),
        (event_id, actor, user['id'] if user else None, query, payload['season'], payload['sort'], payload['total'], request_device_type(), now_text()))
    db.commit()
    return None


def normalize_range(start, end):
    today = date.today()
    try:
        end_date = date.fromisoformat(end) if end else today
        start_date = date.fromisoformat(start) if start else end_date - timedelta(days=6)
    except (ValueError, TypeError):
        raise ValueError('日期格式无效') from None
    if start_date > end_date or end_date > today or (end_date-start_date).days >= 90:
        raise ValueError('请选择不超过 90 天、且不包含未来日期的范围')
    return start_date.isoformat(), end_date.isoformat(), (end_date+timedelta(days=1)).isoformat()


def experience_summary(start=None, end=None, refresh=False):
    start, end, after_end = normalize_range(start, end)
    key = (current_app.config['DATABASE_URL'], current_app.config['DATABASE'], start, end)
    if not refresh and not current_app.testing:
        cached = _cache.get(key)
        if cached is not None:
            return cached
    db = get_db()
    def rows(sql):
        return db.execute(sql, (start, after_end)).fetchall()
    scope = "(e.user_id IS NULL OR COALESCE(u.role,'user') != 'admin')"
    visits = rows(f'''SELECT e.device_type, COUNT(*) AS pv, COUNT(DISTINCT e.visitor_key) AS uv
        FROM visit_events e LEFT JOIN users u ON u.id=e.user_id
        WHERE e.created_at>=? AND e.created_at<? AND {scope} GROUP BY e.device_type''')
    copies = rows(f'''SELECT e.device_type, COUNT(*) AS copies,
        COUNT(DISTINCT CASE WHEN e.user_id IS NOT NULL THEN 'user:' || e.user_id
          WHEN COALESCE(e.visitor_token,'') != '' THEN 'guest:' || e.visitor_token
          ELSE 'ip:' || COALESCE(e.ip_address,'') END) AS copy_visitors
        FROM copy_action_events e LEFT JOIN users u ON u.id=e.user_id
        WHERE e.created_at>=? AND e.created_at<? AND e.success=1 AND {scope} GROUP BY e.device_type''')
    searches = rows(f'''SELECT e.device_type, COUNT(*) AS searches, COUNT(DISTINCT e.visitor_key) AS search_visitors,
        SUM(CASE WHEN e.result_count=0 THEN 1 ELSE 0 END) AS zero_results
        FROM search_events e LEFT JOIN users u ON u.id=e.user_id
        WHERE e.created_at>=? AND e.created_at<? AND {scope} GROUP BY e.device_type''')
    devices = {kind: {'device_type':kind,'label':label,'pv':0,'uv':0,'copies':0,'copy_visitors':0,'searches':0,'search_visitors':0,'zero_results':0} for kind,label in DEVICE_LABELS.items()}
    for groups in (visits,copies,searches):
        for row in groups:
            devices[row['device_type']].update({k:int(v or 0) for k,v in dict(row).items() if k!='device_type'})
    summary = dict(rows(f'''SELECT COUNT(*) AS searches, COUNT(DISTINCT e.visitor_key) AS search_visitors,
        COALESCE(SUM(CASE WHEN e.result_count=0 THEN 1 ELSE 0 END),0) AS zero_results,
        MIN(e.created_at) AS first_search_at
        FROM search_events e LEFT JOIN users u ON u.id=e.user_id
        WHERE e.created_at>=? AND e.created_at<? AND {scope}''')[0])
    summary['zero_result_pct'] = round(100*summary['zero_results']/summary['searches'],2) if summary['searches'] else 0
    for item in devices.values():
        item['zero_result_pct'] = round(100*item['zero_results']/item['searches'],2) if item['searches'] else 0
    def keywords(zero_only=False):
        grouped = rows(f'''SELECT e.query,e.season_id,e.sort_key,COUNT(*) AS searches,
            COUNT(DISTINCT e.visitor_key) AS visitors,
            SUM(CASE WHEN e.result_count=0 THEN 1 ELSE 0 END) AS zero_results,
            MIN(e.result_count) AS min_results,MAX(e.result_count) AS max_results
            FROM search_events e LEFT JOIN users u ON u.id=e.user_id
            WHERE e.created_at>=? AND e.created_at<? AND {scope}
            {'AND e.result_count=0' if zero_only else ''}
            GROUP BY e.query,e.season_id,e.sort_key
            ORDER BY searches DESC,e.query,e.season_id,e.sort_key LIMIT 20''')
        seasons = {item['id']:item.get('name',item['id']) for item in lineup_season_manifest()['seasons']}
        return [{**dict(r),'season_label':seasons.get(r['season_id'],r['season_id']), 'sort_label':SORT_LABELS.get(r['sort_key'],r['sort_key'])} for r in grouped]
    result = {'start':start,'end':end,'summary':summary,'devices':list(devices.values()),'top_queries':keywords(),'zero_queries':keywords(True),'generated_at':now_text()}
    if not current_app.testing:
        _cache.set(key,result)
    return result
