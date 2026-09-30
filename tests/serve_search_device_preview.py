"""Loopback-only fictional data preview; never registered in the real app."""
import json
import os
import sys
import shutil
from datetime import datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def create_preview_app():
    os.environ['JCC_PROCESS_ROLE']='season-worker'
    from app import create_app
    from db import get_db,now_text
    from werkzeug.security import generate_password_hash
    directory=ROOT/'instance'/'search-device-preview';directory.mkdir(parents=True,exist_ok=True)
    seasons=[
        {'id':'s11-inkborn-fables','name':'S11 · 画之灵','status':'active','order':1,'data_file':'s11.json'},
        {'id':'s17-star-god','name':'S17 · 星神','status':'active','order':2,'data_file':'s17.json'},
        {'id':'s18-enchanted-wilds','name':'S18 · 魔法乱斗','status':'active','order':3,'data_file':'s18.json'},
    ]
    manifest=directory/'seasons.json';manifest.write_text(json.dumps({'default_season_id':seasons[0]['id'],'seasons':seasons},ensure_ascii=False),encoding='utf-8')
    season_dir=directory/'seasons';season_dir.mkdir(exist_ok=True)
    assets=directory/'assets';assets.mkdir(exist_ok=True)
    portraits=sorted((ROOT/'static/season-data/s11/assets/optimized').glob('*/champions/*.webp'))[:8]
    image_urls=[]
    for index,path in enumerate(portraits):
        filename=f'preview-{index}.webp';shutil.copyfile(path,assets/filename);image_urls.append('/api/live-comps/assets/'+filename)
    image_urls=image_urls or ['/favicon.ico']
    champion_doc=json.loads((ROOT/'static/season-data/s11/champions.json').read_text(encoding='utf-8'))
    # Details use a real mapping for an otherwise fictional formation.
    champion_id=champion_doc['champions'][0]['id']
    live={'meta':{'source':'fictional-local-preview'},'tiers':{'S':[
        {'id':f'preview-{i}','title':f'预览实时阵容 {i+1}','tier':'S','jccCode':f'#PreviewLive{i}',
         'mainAvatar':image_urls[i%len(image_urls)],'heroImages':image_urls[:6],
         'formationDetails':{'version':1,'season_id':'s11','units':[{'champion_id':champion_id,'position':21,'items':[],'star':2}]}}
        for i in range(14)],'A':[],'B':[],'C':[],'D':[]}}
    (season_dir/'s11-inkborn-fables.json').write_text(json.dumps(live,ensure_ascii=False),encoding='utf-8')
    (directory/'visibility.json').write_text(json.dumps({'library':{'s11':{'status':'active','order':1}},'simulator':{'s11':{'status':'active','order':1}}}),encoding='utf-8')
    app=create_app({
        'TESTING':True,'DATABASE':str(directory/'preview.sqlite3'),'DATABASE_URL':'sqlite:///preview',
        'SECRET_KEY':'local-search-device-preview-only','ADMIN_USERNAME':'previewadmin','ADMIN_PASSWORD':'Preview1234',
        'SESSION_COOKIE_SECURE':False,'DAILY_REPORT_WORKER_ENABLED':False,'LIVE_COMPS_UPLOAD_WORKER_ENABLED':False,
        'RESEND_API_KEY':'','LIVE_COMPS_SEASON_MANIFEST_PATH':str(manifest),'LIVE_COMPS_SEASON_DIR':str(season_dir),
        'LIVE_COMPS_DEFAULT_SEASON_ID':seasons[0]['id'],'LIVE_COMPS_DATA_PATH':str(directory/'live.json'),
        'LIVE_COMPS_BACKUP_PATH':str(directory/'previous.json'),'LIVE_COMPS_ASSET_DIR':str(assets),
        'LIVE_COMPS_MANUAL_CODE_DIR':str(directory/'codes'),'LIVE_COMPS_UPLOAD_JOB_DIR':str(directory/'jobs'),
        'SEASON_VISIBILITY_PATH':str(directory/'visibility.json'),'SEASON_PACKAGE_ROOT':str(directory/'packages'),
    })
    with app.app_context():
        db=get_db();now=now_text();admin=db.execute("SELECT id FROM users WHERE username='previewadmin'").fetchone()['id']
        if not db.execute("SELECT id FROM users WHERE username='previewuser'").fetchone():
            db.execute("INSERT INTO users(username,email,nickname,password_hash,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",('previewuser','user@preview.invalid','预览用户',generate_password_hash('Preview1234'),'user','active',now,now))
        if not db.execute('SELECT id FROM lineups LIMIT 1').fetchone():
            for i in range(60):
                season=seasons[0]['id'] if i<48 else seasons[1]['id']
                name=('天龙九五' if i%2==0 else '斗射卡莎')+f' {i+1:02d}'
                db.execute('''INSERT INTO lineups(user_id,name,code,season_id,status,admin_like_adjustment,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?)''',(admin,name,f'#PreviewLineup{i}',season,'normal',100 if i==0 else 0,now,now))
        if not db.execute('SELECT id FROM search_events LIMIT 1').fetchone():
            for i in range(36):
                kind=['mobile','tablet','desktop'][i%3];timestamp=(datetime.now()-timedelta(days=i%6)).strftime('%Y-%m-%d %H:%M:%S')
                query='不存在阵容' if i%4==0 else ('九五' if i%2 else '卡莎')
                db.execute('''INSERT INTO search_events(event_id,visitor_key,query,season_id,sort_key,result_count,device_type,created_at)
                    VALUES(?,?,?,?,?,?,?,?)''',(f'{i:032x}',f'guest:fixture-{kind}-{i%5}',query,seasons[i%2]['id'],'ss' if i%5==0 else 'latest',0 if i%4==0 else 12,kind,timestamp))
                db.execute('''INSERT INTO visit_events(visit_date,visitor_key,visitor_kind,visitor_token,page_key,created_at,device_type)
                    VALUES(?,?,?,?,?,?,?)''',(timestamp[:10],f'guest:fixture-{i}','guest_token',f'fixture-{i}','home',timestamp,kind))
                if i%2==0:
                    db.execute('''INSERT INTO copy_action_events(target_type,target_id,visitor_token,success,counted,created_at,device_type)
                        VALUES(?,?,?,?,?,?,?)''',('live_comp',f'fixture-{i}',f'fixture-{i}',1,0,timestamp,kind))
            db.execute('''INSERT INTO visit_events(visit_date,visitor_key,visitor_kind,page_key,created_at)
                VALUES(?,?,?,?,?)''',(now[:10],'guest:fixture-old','guest_token','home',now))
        db.commit()
    from flask import jsonify,redirect,request,abort
    from auth import start_user_session
    def loopback():
        if request.remote_addr not in ('127.0.0.1','::1'):abort(403)
    @app.get('/__preview__/login/<kind>')
    def preview_login(kind):
        loopback();username='previewadmin' if kind=='admin' else 'previewuser'
        start_user_session(get_db().execute('SELECT * FROM users WHERE username=?',(username,)).fetchone())
        return redirect('/admin' if kind=='admin' else '/')
    @app.get('/__preview__/metrics')
    def metrics():
        loopback();db=get_db();return jsonify(searches=db.execute('SELECT COUNT(*) AS c FROM search_events').fetchone()['c'])
    return app


if __name__=='__main__':
    app=create_preview_app()
    port=int(os.environ.get('SEARCH_DEVICE_PREVIEW_PORT','5128'))
    print(f'Preview http://127.0.0.1:{port}; local accounts previewadmin / previewuser, password Preview1234',flush=True)
    app.run(host='127.0.0.1',port=port,debug=False,use_reloader=False,threaded=True)
