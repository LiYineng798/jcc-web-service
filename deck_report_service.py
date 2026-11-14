"""Deck submission and activity metrics for one half-open time window.

Names keep the counting rules apart: copy actions (every successful gesture, per code type),
effective copies (the shared five-minute public count) and unique copiers (distinct actors).
Metrics that depend on collection started by ``deck_analytics_started_at`` are ``None`` (未采集)
for windows that end before collection began; a window that starts before it is marked partial.
Submission workflow figures come from the submission tables, which have no collection gap.
"""
from statistics import median

from datetime import datetime

from deck_analytics_service import started_at

MAX_TOP_DECKS = 10
MAX_CONTRIBUTORS = 10
COLLECTED_KEYS = (
    'deck_published', 'deck_restored', 'deck_hidden', 'deck_deleted', 'deck_reviewed',
    'deck_copy_actions', 'deck_plan_copy_actions', 'deck_lineup_copy_actions',
    'deck_copiers', 'deck_plan_copiers', 'deck_lineup_copiers',
    'deck_likes', 'deck_favorite_adds', 'deck_favorite_removes',
    'deck_library_visitors', 'deck_detail_visitors', 'deck_detail_visits',
)


def coverage(db, start, end):
    began = started_at(db)
    if not began or began >= end:
        return {'status': 'not_collected', 'started_at': began, 'from': None}
    if began > start:
        return {'status': 'partial', 'started_at': began, 'from': began}
    return {'status': 'full', 'started_at': began, 'from': start}


def _hours(start, end):
    try:
        return (datetime.strptime(end[:19], '%Y-%m-%d %H:%M:%S') - datetime.strptime(start[:19], '%Y-%m-%d %H:%M:%S')).total_seconds() / 3600
    except (TypeError, ValueError):
        return None


def submission_metrics(db, start, end):
    one = lambda sql, params: db.execute(sql, params).fetchone()['c'] or 0
    events = {row['action']: row['c'] for row in db.execute(
        '''SELECT action, COUNT(*) AS c FROM orange_deck_submission_events
           WHERE created_at >= ? AND created_at < ? GROUP BY action''', (start, end)).fetchall()}
    submitters = one('''SELECT COUNT(DISTINCT actor_user_id) AS c FROM orange_deck_submission_events
        WHERE action IN ('submit', 'resubmit') AND created_at >= ? AND created_at < ?''', (start, end))
    # Backlog as of the window end: each submission's latest event before that moment.
    backlog = {row['to_status']: row['c'] for row in db.execute(
        '''SELECT e.to_status, COUNT(*) AS c FROM orange_deck_submission_events e
           JOIN (SELECT submission_id, MAX(submission_version) AS v FROM orange_deck_submission_events
                 WHERE created_at < ? GROUP BY submission_id) last
             ON last.submission_id = e.submission_id AND last.v = e.submission_version
           WHERE e.to_status IN ('pending', 'processing', 'needs_info') GROUP BY e.to_status''', (end,)).fetchall()}
    # Decision cohort: submissions an admin decided in this window (published, rejected or duplicate).
    decided = db.execute(
        '''SELECT e.action, e.created_at AS decided_at, s.created_at AS submitted_at
           FROM orange_deck_submission_events e JOIN orange_deck_submissions s ON s.id = e.submission_id
           WHERE e.action IN ('publish', 'reject', 'mark_duplicate') AND e.created_at >= ? AND e.created_at < ?''',
        (start, end)).fetchall()
    durations = [hours for hours in (_hours(row['submitted_at'], row['decided_at']) for row in decided) if hours is not None]
    accepted = sum(1 for row in decided if row['action'] == 'publish')
    return {
        'deck_submissions_new': events.get('submit', 0),
        'deck_submissions_resubmitted': events.get('resubmit', 0),
        'deck_submitters': submitters,
        'deck_submissions_pending': backlog.get('pending', 0),
        'deck_submissions_processing': backlog.get('processing', 0),
        'deck_submissions_needs_info': backlog.get('needs_info', 0),
        'deck_submissions_published': accepted,
        'deck_submissions_rejected': events.get('reject', 0),
        'deck_submissions_duplicate': events.get('mark_duplicate', 0),
        'deck_submissions_info_requested': events.get('request_info', 0),
        'deck_submissions_withdrawn': events.get('withdraw', 0),
        'deck_submissions_decided': len(decided),
        # Same cohort for numerator and denominator: decisions made in this window.
        'deck_adoption_rate': round(accepted / len(decided) * 100, 1) if decided else None,
        'deck_review_hours_avg': round(sum(durations) / len(durations), 1) if durations else None,
        'deck_review_hours_median': round(median(durations), 1) if durations else None,
    }


def activity_metrics(db, start, end):
    actions = {row['action']: row['c'] for row in db.execute(
        '''SELECT action, COUNT(*) AS c FROM orange_deck_activity_events
           WHERE created_at >= ? AND created_at < ? GROUP BY action''', (start, end)).fetchall()}
    copies = db.execute(
        '''SELECT COUNT(*) AS actions,
                  SUM(CASE WHEN code_type = 'plan' THEN 1 ELSE 0 END) AS plan_actions,
                  SUM(CASE WHEN code_type = 'lineup' THEN 1 ELSE 0 END) AS lineup_actions,
                  COUNT(DISTINCT actor_key) AS copiers,
                  COUNT(DISTINCT CASE WHEN code_type = 'plan' THEN actor_key END) AS plan_copiers,
                  COUNT(DISTINCT CASE WHEN code_type = 'lineup' THEN actor_key END) AS lineup_copiers
           FROM copy_action_events WHERE target_type = 'orange_deck' AND success = 1 AND created_at >= ? AND created_at < ?''',
        (start, end)).fetchone()
    visits = db.execute(
        '''SELECT COUNT(DISTINCT CASE WHEN surface = 'library' THEN visitor_key END) AS library_visitors,
                  COUNT(DISTINCT CASE WHEN surface = 'detail' THEN visitor_key END) AS detail_visitors,
                  SUM(CASE WHEN surface = 'detail' THEN 1 ELSE 0 END) AS detail_visits
           FROM orange_deck_visit_events WHERE created_at >= ? AND created_at < ?''', (start, end)).fetchone()
    value = lambda row, key: int(row[key] or 0)
    return {
        'deck_published': actions.get('published', 0), 'deck_restored': actions.get('restored', 0),
        'deck_hidden': actions.get('hidden', 0), 'deck_deleted': actions.get('deleted', 0), 'deck_reviewed': actions.get('reviewed', 0),
        'deck_copy_actions': value(copies, 'actions'), 'deck_plan_copy_actions': value(copies, 'plan_actions'),
        'deck_lineup_copy_actions': value(copies, 'lineup_actions'), 'deck_copiers': value(copies, 'copiers'),
        'deck_plan_copiers': value(copies, 'plan_copiers'), 'deck_lineup_copiers': value(copies, 'lineup_copiers'),
        'deck_likes': actions.get('like', 0), 'deck_favorite_adds': actions.get('favorite_add', 0),
        'deck_favorite_removes': actions.get('favorite_remove', 0),
        'deck_library_visitors': value(visits, 'library_visitors'), 'deck_detail_visitors': value(visits, 'detail_visitors'),
        'deck_detail_visits': value(visits, 'detail_visits'),
    }


def _credit_label(row):
    nickname = row['credit_nickname'] or row['credit_username']
    return f"{nickname} (@{row['credit_username']})" if row['credit_username'] else '原账号不可用'


def top_decks(db, start, end, limit=MAX_TOP_DECKS):
    """Most copied decks: actions, effective copies and unique copiers side by side, never summed."""
    rows = db.execute(
        f'''SELECT a.deck_id, a.actions, a.copiers, a.plan_actions, a.lineup_actions,
                   (SELECT COUNT(*) FROM orange_deck_copies c WHERE c.deck_id = a.deck_id AND c.created_at >= ? AND c.created_at < ?) AS effective,
                   d.name, d.status, d.origin_type, cu.username AS credit_username, cu.nickname AS credit_nickname
            FROM (SELECT deck_id, COUNT(*) AS actions, COUNT(DISTINCT actor_key) AS copiers,
                         SUM(CASE WHEN code_type = 'plan' THEN 1 ELSE 0 END) AS plan_actions,
                         SUM(CASE WHEN code_type = 'lineup' THEN 1 ELSE 0 END) AS lineup_actions
                  FROM copy_action_events WHERE target_type = 'orange_deck' AND success = 1 AND created_at >= ? AND created_at < ?
                  GROUP BY deck_id) a
            JOIN orange_decks d ON d.id = a.deck_id
            LEFT JOIN users cu ON cu.id = COALESCE(d.provided_by_user_id, d.user_id)
            ORDER BY a.copiers DESC, a.actions DESC, a.deck_id LIMIT ?''', (start, end, start, end, limit)).fetchall()
    return [{'rank': index, 'deck_id': row['deck_id'], 'title': row['name'], 'status': row['status'],
             'credit': 'provided' if row['origin_type'] == 'submission' else 'author', 'uploader': _credit_label(row),
             'copy_actions': int(row['actions'] or 0), 'plan_copy_actions': int(row['plan_actions'] or 0),
             'lineup_copy_actions': int(row['lineup_actions'] or 0), 'effective_copies': int(row['effective'] or 0),
             'copiers': int(row['copiers'] or 0)} for index, row in enumerate(rows, start=1)]


def top_contributors(db, start, end, limit=MAX_CONTRIBUTORS):
    rows = db.execute(
        '''SELECT s.submitter_user_id AS user_id, u.username AS credit_username, u.nickname AS credit_nickname,
                  SUM(CASE WHEN e.action IN ('submit', 'resubmit') THEN 1 ELSE 0 END) AS submitted,
                  SUM(CASE WHEN e.action = 'publish' THEN 1 ELSE 0 END) AS published
           FROM orange_deck_submission_events e JOIN orange_deck_submissions s ON s.id = e.submission_id
           LEFT JOIN users u ON u.id = s.submitter_user_id
           WHERE e.created_at >= ? AND e.created_at < ? AND e.action IN ('submit', 'resubmit', 'publish')
           GROUP BY s.submitter_user_id, u.username, u.nickname
           ORDER BY published DESC, submitted DESC, s.submitter_user_id LIMIT ?''', (start, end, limit)).fetchall()
    return [{'user': _credit_label(row), 'submitted': int(row['submitted'] or 0), 'published': int(row['published'] or 0)} for row in rows]


def deck_metrics(db, start, end):
    """All deck figures for one window, plus current snapshot totals labelled as such."""
    cover = coverage(db, start, end)
    metrics = submission_metrics(db, start, end)
    if cover['status'] == 'not_collected':
        metrics.update({key: None for key in COLLECTED_KEYS})
        top = None
    else:
        metrics.update(activity_metrics(db, start, end))
        top = top_decks(db, start, end)
    # Effective copies predate event collection (five-minute table), so they are always available.
    metrics['deck_effective_copies'] = db.execute(
        'SELECT COUNT(*) AS c FROM orange_deck_copies WHERE created_at >= ? AND created_at < ?', (start, end)).fetchone()['c']
    return {'summary': metrics, 'coverage': cover, 'top_decks': top, 'contributors': top_contributors(db, start, end)}


def deck_snapshot(db):
    """Current totals at generation time (not reconstructed for past days)."""
    row = db.execute("""SELECT
        (SELECT COUNT(*) FROM orange_decks WHERE status = 'published') AS public_decks,
        (SELECT COUNT(*) FROM orange_decks WHERE status = 'published' AND origin_type = 'submission') AS public_submitted_decks,
        (SELECT COUNT(*) FROM orange_deck_submissions WHERE status = 'pending') AS pending,
        (SELECT COUNT(*) FROM orange_deck_submissions WHERE status = 'processing') AS processing,
        (SELECT COUNT(*) FROM orange_deck_submissions WHERE status = 'needs_info') AS needs_info""").fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}
