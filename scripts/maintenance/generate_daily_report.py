"""Generate (or regenerate) one daily admin report snapshot.

The Web process already auto-generates yesterday's report a few minutes after
midnight via the in-process worker. This script is for manual backfills and
for production setups that prefer a separate scheduler (cron / systemd timer).
It is idempotent: a second run without ``--force`` leaves the existing
snapshot untouched.

Usage:

    # 生成昨天的报告（缺省日期）
    python scripts/maintenance/generate_daily_report.py

    # 指定日期
    python scripts/maintenance/generate_daily_report.py --date 2026-08-08

    # 覆盖重新生成（已存在时）
    python scripts/maintenance/generate_daily_report.py --date 2026-08-08 --force

连接方式与 Web 服务一致：默认 SQLite（instance/lineups.sqlite3），或通过
JCC_DATABASE_URL 连接 PostgreSQL。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--date', default='', help='目标日期 YYYY-MM-DD，缺省为昨天')
    parser.add_argument('--force', action='store_true', help='覆盖已存在的报告')
    args = parser.parse_args(argv)

    from app import create_app
    from daily_report_service import ensure_daily_report

    app = create_app()
    with app.app_context():
        report = ensure_daily_report(args.date or None, force=args.force)
        if report is None:
            print('报告已存在或正在生成；如需覆盖请加 --force')
            return 0
        summary = report['summary']
        print(
            f"已生成 {report['report_date']} 每日报告："
            f"UV {summary['unique_visitors']} / PV {summary['page_visits']} / "
            f"复制 {summary['total_copies']} / 新增注册 {summary['new_registrations']}"
        )
    return 0


if __name__ == '__main__':
    sys.exit(main())
