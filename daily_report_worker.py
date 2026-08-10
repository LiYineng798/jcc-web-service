"""Background worker that auto-generates yesterday's admin daily report.

The worker runs inside the Flask process (one daemon thread per process).
It checks every few minutes whether yesterday's report is missing and
generates it shortly after midnight. ``daily_report_service.ensure_daily_report``
claims the report row with an insert-or-ignore, so multiple gunicorn workers
never write duplicate reports; at most a couple of processes compute the same
snapshot around the same time.

Production deployments that prefer a separate scheduler can instead run
``python scripts/maintenance/generate_daily_report.py`` from a cron/systemd
timer — the endpoint is the same idempotent upsert.
"""

from __future__ import annotations

import threading

from daily_report_service import ensure_daily_report, yesterday_date

CHECK_INTERVAL_SECONDS = 15 * 60


def _generate_once(app):
    with app.app_context():
        report = ensure_daily_report(yesterday_date())
        if report is not None:
            app.logger.info(
                'daily report ready: %s (UV=%s PV=%s copies=%s)',
                report['report_date'],
                report['summary']['unique_visitors'],
                report['summary']['page_visits'],
                report['summary']['total_copies'],
            )


def start_daily_report_worker(app):
    """Start the daemon worker unless the app opts out (tests do)."""
    if app.config.get('TESTING'):
        return None
    if app.config.get('DAILY_REPORT_WORKER_ENABLED', True) is False:
        return None
    if getattr(app, '_daily_report_worker_started', False):
        return None

    def _loop():
        import time

        while True:
            try:
                _generate_once(app)
            except Exception:
                app.logger.exception('daily report background generation failed')
            time.sleep(CHECK_INTERVAL_SECONDS)

    thread = threading.Thread(
        target=_loop,
        name='daily-report-worker',
        daemon=True,
    )
    thread.start()
    app._daily_report_worker_started = True
    return thread
