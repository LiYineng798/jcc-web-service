"""Loopback-only notification preview, using fictional accounts and local SQLite."""
import os
from serve_search_device_preview import create_preview_app

app = create_preview_app()

with app.app_context():
    from db import get_db, now_text
    from feedback_service import create_feedback, update_feedback
    from notification_service import notify_author
    from avatar_service import random_avatar_config
    from werkzeug.security import generate_password_hash

    db = get_db()
    owner = db.execute("SELECT * FROM users WHERE username='previewuser'").fetchone()
    admin = db.execute("SELECT * FROM users WHERE username='previewadmin'").fetchone()
    if not db.execute("SELECT id FROM guestbook_messages WHERE content='希望可以按开局装备筛选阵容。'").fetchone():
        avatar=random_avatar_config()
        db.execute('UPDATE users SET nickname=?,avatar_color=?,avatar_preset=?,avatar_expression=? WHERE id=?',
                   ('晚风与棋盘',avatar['color'],avatar['preset'],avatar['expression'],owner['id']))
        lineups=db.execute('SELECT * FROM lineups ORDER BY id LIMIT 2').fetchall()
        for lineup in lineups:
            db.execute('UPDATE lineups SET user_id=? WHERE id=?',(owner['id'],lineup['id']))
        lineup=dict(lineups[0]);lineup['user_id']=owner['id']
        for index in range(4):
            username=f'notification-reader-{index}'
            cursor=db.execute('''INSERT INTO users(username,email,nickname,password_hash,role,status,created_at,updated_at)
                VALUES (?,?,?,?,'user','active',?,?)''',(username,username+'@preview.invalid',f'热心棋友{index+1}',generate_password_hash('Preview1234'),now_text(),now_text()))
            actor={'id':cursor.lastrowid}
            db.execute('INSERT INTO likes(user_id,lineup_id,like_date,created_at) VALUES (?,?,?,?)',(actor['id'],lineup['id'],now_text()[:10],now_text()))
            db.execute('INSERT INTO favorites(user_id,lineup_id,created_at) VALUES (?,?,?)',(actor['id'],lineup['id'],now_text()))
            db.execute('INSERT INTO copy_events(lineup_id,user_id,copy_key,bucket_start,counted,created_at) VALUES (?,?,?,?,1,?)',(lineup['id'],actor['id'],f"user:{actor['id']}",now_text(),now_text()))
            for kind in ('like','favorite','copy'):
                notify_author(db,lineup,kind,actor)
        cursor=db.execute("INSERT INTO guestbook_messages(user_id,nickname,content,created_at,ip_address) VALUES (?,?,?,?,'127.0.0.1')",
                          (owner['id'],'晚风与棋盘','希望可以按开局装备筛选阵容。',now_text()))
        receipt=create_feedback(db,'guestbook',cursor.lastrowid,owner['id'],'给站长的留言','希望可以按开局装备筛选阵容。')
        update_feedback(db,admin,receipt['feedback_id'],{'revision':1,'status':'in_progress','body':'谢谢建议，我们正在整理装备与阵容的对应关系，会在这里同步进展。'})
        report=db.execute("INSERT INTO reports(reporter_user_id,lineup_id,reason,status,created_at) VALUES (?,?,?,'pending',?)",
                          (owner['id'],lineups[1]['id'],'导入后缺少一名弈子，希望帮忙核实。',now_text()))
        receipt=create_feedback(db,'report',report.lastrowid,owner['id'],lineups[1]['name'],'导入后缺少一名弈子，希望帮忙核实。',lineups[1]['id'])
        update_feedback(db,admin,receipt['feedback_id'],{'revision':1,'status':'resolved','body':'已核对并修正阵容码，请刷新页面后重新复制。感谢你的反馈！'})
        db.execute("INSERT INTO guestbook_messages(nickname,content,created_at,ip_address) VALUES ('游客棋友','游客留言只供站长阅读，不需要站内回复。',?,'127.0.0.1')",(now_text(),))
        db.commit()

if __name__ == '__main__':
    port=int(os.environ.get('NOTIFICATION_PREVIEW_PORT','5160'))
    app.run(host='127.0.0.1',port=port,debug=False,use_reloader=False,threaded=True)
