"""Manually prune old event rows (visit/growth/login/copy-action/rate-limit).

These tables grow without bound; the analytics that read them only look at
recent windows. This script is NOT scheduled anywhere — run it by hand when
you choose to, and it deletes nothing unless you pass ``--yes``.

    # 预览：只统计将要删除的行数，不做任何修改
    python scripts/maintenance/prune_events.py --days 180

    # 实际删除 180 天前的事件（建议先备份数据库）
    python scripts/maintenance/prune_events.py --days 180 --yes

    # 单独清理过期的限流窗口（默认 2 天前）
    python scripts/maintenance/prune_events.py --days 180 --yes --rate-limit-days 2

audit_logs 不在默认清理范围内（审计追踪按需保留）；如确需清理，显式加
``--include-audit-logs``。默认通过 JCC_DATABASE_URL 连接，与 Web 服务一致。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EVENT_TABLES = (
    ('visit_events', 'created_at'),
    ('growth_events', 'created_at'),
    ('login_events', 'created_at'),
    ('copy_action_events', 'created_at'),
)
MIN_RETENTION_DAYS = 30


def open_connection():
    from app import create_app
    app = create_app()
    context = app.app_context()
    context.push()
    from db import get_db
    return get_db(), context


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--days', type=int, required=True, help='保留最近 N 天，删除更早的事件行')
    parser.add_argument('--rate-limit-days', type=int, default=2, help='rate_limits 窗口保留天数（默认 2）')
    parser.add_argument('--include-audit-logs', action='store_true', help='连同 audit_logs 一起清理（默认不动）')
    parser.add_argument('--yes', action='store_true', help='确认执行删除；缺省为 dry-run 预览')
    args = parser.parse_args(argv)

    if args.days < MIN_RETENTION_DAYS:
        raise SystemExit(f'--days 不得小于 {MIN_RETENTION_DAYS}，避免误删近期分析数据')

    cutoff = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d %H:%M:%S')
    rate_cutoff = (datetime.now() - timedelta(days=args.rate_limit_days)).strftime('%Y-%m-%d %H:%M:%S')

    tables = list(EVENT_TABLES)
    if args.include_audit_logs:
        tables.append(('audit_logs', 'created_at'))

    db, context = open_connection()
    try:
        print(f"{'执行删除' if args.yes else '[dry-run 预览]'} 截止时间 < {cutoff}")
        for table, column in tables:
            count = db.execute(
                f'SELECT COUNT(*) AS c FROM {table} WHERE {column} < ?', (cutoff,)
            ).fetchone()['c']
            print(f'  {table}: {count} 行')
            if args.yes and count:
                db.execute(f'DELETE FROM {table} WHERE {column} < ?', (cutoff,))

        rate_count = db.execute(
            'SELECT COUNT(*) AS c FROM rate_limits WHERE window_start < ?', (rate_cutoff,)
        ).fetchone()['c']
        print(f'  rate_limits (< {rate_cutoff}): {rate_count} 行')
        if args.yes and rate_count:
            db.execute('DELETE FROM rate_limits WHERE window_start < ?', (rate_cutoff,))

        if args.yes:
            db.commit()
            print('删除完成。建议随后在低峰期执行 VACUUM（SQLite）或依赖自动 vacuum（PostgreSQL）。')
        else:
            print('未做任何修改。确认无误后加 --yes 执行。')
    finally:
        context.pop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
