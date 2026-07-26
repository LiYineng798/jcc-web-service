import os

from flask import Response, abort, jsonify, redirect, send_from_directory

from auth import current_user, login_required
from db import get_db
from lineup_account_service import build_author_profile_payload
from lineup_read_service import build_lineup_detail_payload
from notice_service import get_active_notice
from seo import (
    DEFAULT_DESCRIPTION,
    DEFAULT_TITLE,
    absolute_url,
    breadcrumb_json_ld,
    code_preview,
    make_seo,
    robots_txt,
    season_label,
    sitemap_xml,
    truncate_text,
    webpage_json_ld,
    website_json_ld,
)
from scoring import score_map
from season_reference_service import (
    build_champion_detail as build_season_champion_detail,
    catalog_seasons,
    champion_ids as season_champion_ids,
    find_champion_id_by_name,
    normalize_season_id,
    season_page_context,
    strip_scaling_tokens,
)
from settings_service import get_setting
from visits import tracked_template_response


def _sitemap_entries():
    db = get_db()
    entries = [
        {'loc': absolute_url('/'), 'lastmod': None},
        {'loc': absolute_url('/patch-notes'), 'lastmod': None},
        {'loc': absolute_url('/tools/special-mechanics'), 'lastmod': None},
        {'loc': absolute_url('/tools/artifact-guide'), 'lastmod': None},
        {'loc': absolute_url('/tools/returning-equipment'), 'lastmod': None},
    ]
    for season in catalog_seasons():
        season_id = season['season_id']
        entries.append({'loc': absolute_url(f'/tools/seasons/{season_id}'), 'lastmod': None})
        entries.extend({
            'loc': absolute_url(f'/tools/seasons/{season_id}/champions/{champion_id}'),
            'lastmod': None,
        } for champion_id in season_champion_ids(season_id))
    if get_setting(db, 'simulator_enabled', 'true') == 'true':
        entries.append({'loc': absolute_url('/tools/lineup-simulator'), 'lastmod': None})

    lineup_rows = db.execute(
        "SELECT id, updated_at FROM lineups WHERE status = 'normal' ORDER BY updated_at DESC, id DESC"
    ).fetchall()
    entries.extend({'loc': absolute_url(f"/lineup/{row['id']}"), 'lastmod': row['updated_at']} for row in lineup_rows)

    author_rows = db.execute(
        '''
        SELECT users.username, MAX(lineups.updated_at) AS lastmod
        FROM users
        JOIN lineups ON lineups.user_id = users.id
        WHERE users.role != 'admin' AND lineups.status = 'normal'
        GROUP BY users.id, users.username
        ORDER BY users.username
        '''
    ).fetchall()
    entries.extend({'loc': absolute_url(f"/author/{row['username']}"), 'lastmod': row['lastmod']} for row in author_rows)

    note_rows = db.execute(
        "SELECT id, published_at, updated_at FROM patch_notes WHERE status = 'published' ORDER BY published_at DESC, id DESC"
    ).fetchall()
    entries.extend({'loc': absolute_url(f"/patch-notes/{row['id']}"), 'lastmod': row['updated_at'] or row['published_at']} for row in note_rows)
    return entries


def register_page_routes(app):
    @app.get('/robots.txt')
    def robots():
        return Response(robots_txt(), mimetype='text/plain')

    @app.get('/sitemap.xml')
    def sitemap():
        return Response(sitemap_xml(_sitemap_entries()), mimetype='application/xml')

    @app.get('/')
    def index():
        db = get_db()
        simulator_enabled = get_setting(db, 'simulator_enabled', 'true') == 'true'
        notice = get_active_notice(db)
        seo = make_seo(
            title=DEFAULT_TITLE,
            description=DEFAULT_DESCRIPTION,
            path='/',
            json_ld=[website_json_ld()],
        )
        return tracked_template_response(
            'index.html',
            'home',
            simulator_enabled=simulator_enabled,
            notice=notice,
            reference_seasons=catalog_seasons(),
            seo=seo,
        )

    @app.get('/auth')
    def auth_page():
        return tracked_template_response(
            'auth.html',
            'auth',
            page_mode='login',
            seo=make_seo(title='登录 - 金铲铲阵容库', description='登录金铲铲阵容库账号。', path='/auth', noindex=True),
        )

    @app.get('/auth/register')
    def register_page():
        return tracked_template_response(
            'auth.html',
            'auth',
            page_mode='register',
            seo=make_seo(title='注册 - 金铲铲阵容库', description='注册金铲铲阵容库账号。', path='/auth/register', noindex=True),
        )

    @app.get('/favicon.ico')
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon',
        )

    @app.get('/lineup/new')
    def lineup_create_page():
        return tracked_template_response(
            'lineup_form.html',
            'lineup_editor',
            lineup_id='',
            page_mode='create',
            seo=make_seo(title='新增阵容 - 金铲铲阵容库', description='新增金铲铲阵容。', path='/lineup/new', noindex=True),
        )

    @app.get('/lineup/<int:lineup_id>/edit')
    def lineup_edit_page(lineup_id):
        return tracked_template_response(
            'lineup_form.html',
            'lineup_editor',
            lineup_id=lineup_id,
            page_mode='edit',
            seo=make_seo(title='编辑阵容 - 金铲铲阵容库', description='编辑金铲铲阵容。', path=f'/lineup/{lineup_id}/edit', noindex=True),
        )

    @app.get('/lineup/<int:lineup_id>')
    def lineup_detail_page(lineup_id):
        payload, service_error, status_code = build_lineup_detail_payload(lineup_id, current_user())
        if service_error:
            abort(status_code)
        title = f"{payload['name']} - 金铲铲阵容码 - 金铲铲阵容库"
        description = truncate_text(
            f"{payload['name']}，{season_label(payload['season_id'])}阵容，作者{payload['owner_nickname']}，"
            f"评级{payload['rank_level']}，累计点赞{payload['like_count']}，累计复制{payload['copy_count']}。"
        )
        path = f'/lineup/{lineup_id}'
        seo = make_seo(
            title=title,
            description=description,
            path=path,
            json_ld=[
                webpage_json_ld(payload['name'], description, path),
                breadcrumb_json_ld([
                    {'name': '首页', 'path': '/'},
                    {'name': payload['name'], 'path': path},
                ]),
            ],
        )
        return tracked_template_response(
            'lineup_detail.html',
            'lineup_detail',
            lineup_id=lineup_id,
            lineup=payload,
            lineup_season_label=season_label(payload['season_id']),
            lineup_code_preview=code_preview(payload['code']),
            seo=seo,
        )

    @app.get('/author/<username>')
    def author_page(username):
        payload, service_error, status_code = build_author_profile_payload(username, current_user(), score_map())
        if service_error:
            abort(status_code)
        profile = payload['profile']
        summary = payload['summary']
        noindex = summary['published_lineups'] == 0
        title = f"{profile['nickname']}的金铲铲阵容 - 金铲铲阵容库"
        description = truncate_text(
            f"{profile['nickname']}在金铲铲阵容库发布了{summary['published_lineups']}套公开阵容，"
            f"累计点赞{summary['total_likes']}，累计复制{summary['total_copies']}。"
        )
        return tracked_template_response(
            'author.html',
            'author',
            username=username,
            author_payload=payload,
            author_public_lineups=payload['lineups'][:6],
            seo=make_seo(title=title, description=description, path=f'/author/{username}', noindex=noindex),
        )

    @app.get('/tools/lineup-simulator')
    def lineup_simulator_page():
        if get_setting(get_db(), 'simulator_enabled', 'true') != 'true':
            abort(404)
        return tracked_template_response(
            'lineup_simulator.html',
            'lineup_simulator',
            seo=make_seo(title='阵容模拟器', description='在线搭配金铲铲阵容棋盘、弈子、装备和羁绊。', path='/tools/lineup-simulator'),
        )

    @app.get('/tools/special-mechanics')
    def special_mechanics_page():
        return tracked_template_response(
            'special_mechanics.html',
            'special_mechanics',
            seo=make_seo(title='S8·怪兽入侵 特殊机制', description='查看S8怪兽入侵回归赛季特殊机制、战力形态和经济形态。', path='/tools/special-mechanics'),
        )

    @app.get('/tools/artifact-guide')
    def artifact_guide_page():
        return tracked_template_response(
            'artifact_guide.html',
            'artifact_guide',
            seo=make_seo(title='S8·怪兽入侵 神器搭配指南', description='查看S8怪兽入侵英雄与神器的实战搭配推荐。', path='/tools/artifact-guide'),
        )

    @app.get('/tools/returning-equipment')
    def returning_equipment_page():
        return tracked_template_response(
            'returning_equipment.html',
            'returning_equipment',
            seo=make_seo(title='S8·怪兽入侵 回归装备', description='查看S8怪兽入侵回归装备属性、组件和效果说明。', path='/tools/returning-equipment'),
        )

    @app.get('/tools/seasons/<season_id>')
    def season_reference_page(season_id):
        normalized = normalize_season_id(season_id)
        context = season_page_context(normalized)
        if context is None:
            abort(404)
        if season_id != normalized:
            return redirect(f'/tools/seasons/{normalized}', 301)
        season = context['season']
        mechanic_names = '、'.join(item['display_name'] for item in context['mechanics'] if item.get('display_name'))
        section_text = f"弈子、羁绊{'与' + mechanic_names if mechanic_names else ''}"
        return tracked_template_response(
            'season_reference.html',
            'season_reference',
            seo=make_seo(
                title=f"{season['display_name']}资料 - {section_text} - 金铲铲阵容库",
                description=f"查看金铲铲{season['display_name']}赛季的{section_text}资料。",
                path=f'/tools/seasons/{normalized}',
            ),
            **context,
        )

    @app.get('/tools/seasons/<season_id>/champions/<champion_id>')
    def season_champion_detail_page(season_id, champion_id):
        normalized = normalize_season_id(season_id)
        detail = build_season_champion_detail(normalized, champion_id)
        if detail is None:
            abort(404)
        if season_id != normalized:
            return redirect(f'/tools/seasons/{normalized}/champions/{champion_id}', 301)
        season = detail['season']
        champion = detail['champion']
        path = f'/tools/seasons/{normalized}/champions/{champion["id"]}'
        trait_names = '、'.join(trait['name'] for trait in detail['traits'])
        description = truncate_text(
            f"{season['display_name']} {champion['name']}，{champion['cost']}费弈子"
            f"{'，羁绊为' + trait_names if trait_names else ''}。"
            f"技能：{champion['skill']['name'] or ''}，{strip_scaling_tokens(champion['skill']['description'])}"
        )
        splash = champion['splash'] or champion['icon']
        return tracked_template_response(
            'season_champion_detail.html',
            'season_champion_detail',
            detail=detail,
            asset_root=f"/static/season-data/{season['season_id']}",
            seo=make_seo(
                title=f"{champion['name']} - {season['display_name']}弈子详情 - 金铲铲阵容库",
                description=description,
                path=path,
                image_path=f"/static/season-data/{season['season_id']}/{splash}" if splash else None,
                json_ld=[
                    webpage_json_ld(champion['name'], description, path),
                    breadcrumb_json_ld([
                        {'name': '首页', 'path': '/'},
                        {'name': f"{season['display_name']}资料", 'path': f'/tools/seasons/{normalized}'},
                        {'name': champion['name'], 'path': path},
                    ]),
                ],
            ),
        )

    @app.get('/tools/s18-preview')
    def legacy_s18_preview_page():
        return redirect('/tools/seasons/s18', 301)

    @app.get('/tools/s16-5-preview')
    def legacy_s16_5_preview_page():
        return redirect('/tools/seasons/s16_5', 301)

    @app.get('/tools/s18-preview/champions/<champion_name>')
    def legacy_s18_champion_detail_page(champion_name):
        champion_id = find_champion_id_by_name('s18', champion_name)
        if champion_id is None:
            abort(404)
        return redirect(f'/tools/seasons/s18/champions/{champion_id}', 301)

    @app.get('/me')
    def account_page():
        user, error = login_required()
        if error:
            return error
        return tracked_template_response(
            'account.html',
            'account',
            seo=make_seo(title='个人中心 - 金铲铲阵容库', description='金铲铲阵容库个人中心。', path='/me', noindex=True),
        )

    @app.get('/api/site-config')
    def site_config():
        db = get_db()
        return jsonify({
            'simulator_enabled': get_setting(db, 'simulator_enabled', 'true') == 'true',
            'notice': get_active_notice(db),
        })

    @app.get('/api/health')
    def health():
        return jsonify({'ok': True})


def register_test_helpers(app, get_table_names_func, lookup_captcha_answer_func):
    app.get_table_names = get_table_names_func
    app.lookup_captcha_answer_for_tests = lookup_captcha_answer_func
