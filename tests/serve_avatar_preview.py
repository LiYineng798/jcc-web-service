"""Loopback-only avatar preview with fictional users and lineups."""
import os
from serve_home_cards_preview import app
from avatar_service import AVATAR_COLORS, AVATAR_EXPRESSIONS
from db import get_db
from werkzeug.security import generate_password_hash

with app.app_context():
    db = get_db()
    rows = db.execute("SELECT id FROM lineups WHERE season_id='s11-inkborn-fables' ORDER BY id LIMIT 8").fetchall()
    presets = ('sunee', 'cloudee', 'sprout', 'bloom', 'strobi', 'freddy', 'citrus', 'nova')
    names = ('暖阳上分笔记', '浮云的棋盘', '新芽慢慢来', '花语研究所', '团团上分笔记', '小熊的棋盘', '柚子慢慢来', '新星研究所')
    for index, row in enumerate(rows):
        username = 'avatar-demo-' + str(index)
        db.execute('''INSERT INTO users
            (username,email,nickname,password_hash,role,status,created_at,updated_at,avatar_color,avatar_preset,avatar_expression)
            VALUES (?,?,?,?,'user','active','2026-10-17','2026-10-17',?,?,?)
            ON CONFLICT(username) DO UPDATE SET nickname=excluded.nickname, avatar_color=excluded.avatar_color,
                avatar_preset=excluded.avatar_preset, avatar_expression=excluded.avatar_expression''',
                   (username, username + '@preview.invalid', names[index], generate_password_hash('Preview1234'),
                    AVATAR_COLORS[index], presets[index], AVATAR_EXPRESSIONS[index % len(AVATAR_EXPRESSIONS)]))
        owner = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()['id']
        db.execute('UPDATE lineups SET user_id=?, updated_at=? WHERE id=?',
                   (owner, f'2026-10-17 {19-index:02d}:00:00', row['id']))
    db.commit()

if __name__ == '__main__':
    port = int(os.environ.get('AVATAR_PREVIEW_PORT', '5148'))
    print(f'Avatar preview: http://127.0.0.1:{port}; fictional data only', flush=True)
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False, threaded=True)
