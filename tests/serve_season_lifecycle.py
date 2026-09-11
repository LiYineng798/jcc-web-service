"""Serve an isolated offline S99 rehearsal; never reads a production database."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5097)
    parser.add_argument(
        '--stdio-control', action='store_true', help='Stop when parent closes stdin'
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='jcc-season-lifecycle-') as temp:
        # app.py creates a default app on import; isolate even that startup.
        os.environ['JCC_DATABASE_URL'] = 'sqlite:///' + str(
            Path(temp) / 'bootstrap.sqlite3'
        ).replace('\\', '/')
        os.environ['JCC_PROCESS_ROLE'] = 'season-worker'
        os.environ['JCC_ADMIN_USERNAME'] = 'previewadmin'
        os.environ['JCC_ADMIN_PASSWORD'] = 'Preview1234'
        from season_lifecycle_support import rehearsal, live_payload
        from season_package_service import run_one_job
        from live_comp_upload_service import _claim_next_job, _process_job
        from werkzeug.serving import make_server

        with rehearsal(temp) as env:
            env.register()
            stop = threading.Event()
            server = make_server('127.0.0.1', args.port, env.app, threaded=True)

            def work():
                while not stop.is_set():
                    with env.app.app_context():
                        run_one_job()
                        job = _claim_next_job()
                        if job:
                            _process_job(env.app, job)
                    stop.wait(0.25)

            worker = threading.Thread(target=work, daemon=True)
            worker.start()
            if args.stdio_control:

                def control():
                    sys.stdin.read()
                    server.shutdown()

                threading.Thread(target=control, daemon=True).start()
            print(
                'REHEARSAL_READY='
                + json.dumps(
                    {
                        'url': f'http://127.0.0.1:{server.server_port}',
                        'packages': [str(p) for p in env.packages],
                        'live': live_payload(),
                    },
                    ensure_ascii=True,
                ),
                flush=True,
            )
            try:
                server.serve_forever()
            finally:
                stop.set()
                worker.join(timeout=30)
                server.server_close()


if __name__ == '__main__':
    main()
