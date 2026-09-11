"""Isolated loopback-only server for season_packages.browser.cjs; all data is temporary."""

import json
import os
import runpy
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['JCC_PROCESS_ROLE'] = 'season-worker'

if __name__ == '__main__':
    from app import create_app
    from scripts.season_library.build_upload_package import build_package
    from season_package_format import dump
    from season_package_service import run_one_job

    with tempfile.TemporaryDirectory(prefix='jcc-package-browser-') as temp:
        directory = Path(temp)
        fixture = runpy.run_path(str(ROOT / 'tests/test_season_packages.py'))['prepared']
        source = fixture.__wrapped__(directory)
        index = json.loads((source / 'index.json').read_text('utf8'))
        index['mechanics'] = [
            {
                'id': 'season-rewards',
                'kind': 'future',
                'display_name': '赛季奖励',
                'presentation': 'stages.v1',
                'entries': [
                    {
                        'id': 'reward1',
                        'name': '阶段奖励',
                        'image': 'assets/icon.png',
                        'description': '可配置的新玩法',
                        'data': {
                            'rounds': ['2-1'],
                            'requires': ['拥有测试弈子'],
                            'stages': [
                                {
                                    'label': '阶段一',
                                    'effect': '获得奖励',
                                    'cost': 2,
                                    'requirements': ['条件完成'],
                                }
                            ],
                        },
                    }
                ],
            }
        ]
        dump(source / 'index.json', index)
        package_path = directory / 'preview-season.zip'
        build_package(
            source,
            package_path,
            1,
            {
                'title': '测试版本说明',
                'summary': '验证完整的上传、预览和发布流程',
                'sections': [{'title': '玩法调整', 'items': ['增加阶段奖励展示']}],
            },
        )
        app = create_app(
            {
                'TESTING': True,
                'DATABASE': str(directory / 'app.sqlite3'),
                'SECRET_KEY': 'local-browser-test-only',
                'ADMIN_USERNAME': 'previewadmin',
                'ADMIN_PASSWORD': 'Preview1234',
                'SEASON_PACKAGE_ROOT': str(directory / 'packages'),
                'SEASON_VISIBILITY_PATH': str(directory / 'visibility.json'),
                'DAILY_REPORT_WORKER_ENABLED': False,
                'LIVE_COMPS_UPLOAD_WORKER_ENABLED': False,
            }
        )
        stop = threading.Event()

        def worker():
            while not stop.is_set():
                with app.app_context():
                    run_one_job()
                stop.wait(0.25)

        task = threading.Thread(target=worker, daemon=True)
        task.start()
        print('PACKAGE_PATH=' + str(package_path), flush=True)
        try:
            app.run(
                host='127.0.0.1',
                port=int(os.environ.get('SEASON_PREVIEW_PORT', '5096')),
                use_reloader=False,
            )
        finally:
            stop.set()
            task.join(timeout=5)
