"""Local-only card preview using fictional data; never serves production data."""
import os
from pathlib import Path

from serve_search_device_preview import create_preview_app

app = create_preview_app()

with app.app_context():
    from db import get_db

    db = get_db()
    owner = db.execute("SELECT id FROM users WHERE username='previewuser'").fetchone()['id']
    samples = [
        ('天龙九五 · 稳稳走向后期', '2026-10-16 19:42:00', 128, 2048),
        ('斗射卡莎', '2026-10-16 18:16:00', 36, 512),
        ('森林秘术 · 给慢节奏一点耐心', '2026-10-16 17:08:00', 9, 76),
        ('一份适合周末慢慢研究的阵容笔记：从连胜过渡到后期成型', '2026-10-16 16:04:00', 2, 15),
    ]
    db.execute("UPDATE users SET nickname='晚风与棋盘', avatar_color='#7c8969' WHERE id=?", (owner,))
    ids = db.execute("SELECT id FROM lineups WHERE season_id='s11-inkborn-fables' ORDER BY id LIMIT 4").fetchall()
    for row, (name, timestamp, likes, copies) in zip(ids, samples):
        code = '#仅供本地样式预览#' + 'a1b2c3d4e5f6' * (12 if row['id'] == ids[-1]['id'] else 4)
        db.execute('UPDATE lineups SET user_id=?,name=?,code=?,updated_at=?,admin_like_adjustment=?,admin_copy_adjustment=? WHERE id=?',
                   (owner, name, code, timestamp, likes, copies, row['id']))
    db.execute("UPDATE lineups SET updated_at='2026-10-15 12:00:00' WHERE id NOT IN (?,?,?,?)", tuple(row['id'] for row in ids))
    db.commit()

if __name__ == '__main__':
    port = int(os.environ.get('HOME_CARD_PREVIEW_PORT', '5136'))
    print(f'Card preview: http://127.0.0.1:{port} (fictional data)', flush=True)
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False, threaded=True)
