"""Run with python season_package_worker.py [--once]; never hosted inside Gunicorn."""

import argparse
import os
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
    from app import app
    from season_package_service import run_one_job, recover_publications

    while True:
        with app.app_context():
            recover_publications()
            worked = run_one_job()
        if args.once:
            break
        if not worked:
            time.sleep(2)


if __name__ == '__main__':
    main()
