def test_index_uses_top_right_auth_link(client):
    html = client.get('/').get_data(as_text=True)
    assert 'href="/auth"' in html
    assert 'id="loginForm"' not in html
    assert 'id="registerForm"' not in html
    assert 'id="lineupForm"' not in html
    assert 'id="createLineupLink"' in html
    assert 'id="toast"' in html


def test_auth_page_contains_login_and_register_forms(client):
    response = client.get('/auth')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="loginForm"' in html
    assert 'id="registerForm"' in html
    assert 'id="captchaImage"' in html


def test_lineup_editor_pages_exist(client):
    create_response = client.get('/lineup/new')
    edit_response = client.get('/lineup/1/edit')
    assert create_response.status_code == 200
    assert edit_response.status_code == 200
    assert 'id="editorForm"' in create_response.get_data(as_text=True)
    assert 'id="editorForm"' in edit_response.get_data(as_text=True)
    assert 'id="statusToggle"' in create_response.get_data(as_text=True)
    assert '直接展示' in create_response.get_data(as_text=True)
    assert '直接隐藏' in create_response.get_data(as_text=True)
    assert '默认直接展示；开启后会直接隐藏，仅你自己可见' in create_response.get_data(as_text=True)


def test_pages_include_favicon_and_favicon_route_exists(client):
    for path in ['/', '/auth', '/lineup/new', '/lineup/1/edit']:
        response = client.get(path)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'rel="icon"' in html
        assert 'href="/static/favicon.png"' in html

    login_response = client.post('/api/login', json={'account': 'adminxlx', 'password': 'Admin1234'})
    assert login_response.status_code == 200
    admin_response = client.get('/admin')
    assert admin_response.status_code == 200
    admin_html = admin_response.get_data(as_text=True)
    assert 'rel="icon"' in admin_html
    assert 'href="/static/favicon.png"' in admin_html
    assert 'id="adminDialogRoot"' in admin_html
    assert 'data-admin-tab="overview"' in admin_html
    assert 'data-admin-tab="reports"' in admin_html
    assert 'data-admin-tab="lineups"' in admin_html
    assert 'data-admin-tab="live-comps"' in admin_html
    assert 'data-admin-tab="users"' in admin_html
    assert 'data-admin-tab="analytics"' in admin_html
    assert 'data-admin-tab="audit"' in admin_html
    assert 'data-admin-tab="settings"' in admin_html
    assert 'data-admin-tab="patch-notes"' in admin_html

    favicon_response = client.get('/favicon.ico')
    assert favicon_response.status_code == 200
    assert favicon_response.mimetype == 'image/vnd.microsoft.icon'


def test_admin_mobile_styles_do_not_force_fixed_height_on_wide_traffic_module():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.admin-module:not(.admin-module-wide)' in css


def test_admin_mobile_tab_bar_uses_readable_grid_layout():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.admin-tab-bar {' in css
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr));' in css
    assert 'white-space: nowrap;' in css
    assert 'overflow-x: auto;' not in css[css.index('@media (max-width: 560px)'):]


def test_patch_note_styles_exist():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.patch-note-list' in css
    assert '.change-tag-buff' in css
    assert '.change-tag-nerf' in css
    assert '.patch-note-original' in css
    assert '.patch-note-card-action' in css
    assert '.patch-note-change-body span' in css
    assert '.patch-note-mobile-meta' in css


def test_patch_notes_js_uses_small_card_action_class():
    with open('static/patch-notes.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'patch-note-card-action' in js


def test_admin_js_contains_patch_notes_workbench():
    with open('static/admin.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'patchNotes' in js
    assert 'loadPatchNotes' in js
    assert 'renderPatchNotesWorkspace' in js
    assert 'PATCH_NOTE_TEMPLATE' in js


def test_index_page_contains_account_value_copy_and_favorites_tab(client):
    html = client.get('/').get_data(as_text=True)
    assert 'id="favoritesTab"' in html
    assert '登录后可收藏阵容并跨设备同步' in html
    assert '登录后可查看我的收藏和我的阵容' in html


def test_index_page_contains_home_image_mode_toggle(client):
    html = client.get('/').get_data(as_text=True)
    assert 'id="imageModeToggle"' in html
    assert 'id="imageModeText"' in html


def test_app_js_defaults_home_image_mode_to_text_only():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert "imageMode: localStorage.getItem('homeImageMode') || 'text'" in js
    assert 'live-comp-card-text-only' in js
    assert 'toggleHomeImageMode' in js


def test_app_js_uses_home_view_cache_and_abortable_fetches():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'const HOME_VIEW_CACHE_TTL = 60000;' in js
    assert 'state.requestControllers' in js
    assert 'AbortController' in js
    assert 'fetchCachedJson(' in js
    assert 'state.user?.id || \'guest\'' in js
    assert 'invalidateHomeViewCache(' in js
    assert 'Promise.all([' in js


def test_auth_page_contains_account_benefits_copy(client):
    html = client.get('/auth').get_data(as_text=True)
    assert '登录后可收藏阵容并跨设备同步' in html
    assert '登录后可发布和管理自己的阵容' in html
    assert '登录后可查看我的收藏、我的阵容和个人记录' in html


def test_index_and_auth_pages_include_auth_intent_script(client):
    index_html = client.get('/').get_data(as_text=True)
    auth_html = client.get('/auth').get_data(as_text=True)

    assert 'auth-intent.js' in index_html
    assert 'auth-intent.js' in auth_html


def test_patch_note_pages_exist_and_homepage_links_to_patch_notes(client):
    index_html = client.get('/').get_data(as_text=True)
    assert 'href="/patch-notes"' in index_html
    assert '更新公告' in index_html

    list_response = client.get('/patch-notes')
    detail_response = client.get('/patch-notes/1')

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert 'id="patchNotesApp"' in list_response.get_data(as_text=True)
    assert 'id="patchNoteDetailApp"' in detail_response.get_data(as_text=True)


def test_index_page_contains_rising_recommended_and_author_link_shell(client):
    html = client.get('/').get_data(as_text=True)
    assert 'data-sort="rising"' in html
    assert 'data-sort="recommended"' in html
    assert 'author-link' in html


def test_index_page_contains_guest_action_prompt_shell(client):
    html = client.get('/').get_data(as_text=True)
    assert 'id="authPromptRoot"' in html


def test_index_page_contains_favorites_empty_state_copy(client):
    html = client.get('/').get_data(as_text=True)
    assert '登录后可收藏阵容并随时找回' in html


def test_app_js_supports_favorite_toggle():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert '取消收藏' in js
    assert "await api(`/api/lineups/${lineup.id}/favorite`, { method: 'DELETE' });" in js
    assert 'trackGrowth' in js
    assert 'guest_click_like' in js
    assert 'guest_click_favorite' in js


def test_app_js_auth_prompt_copy_is_trimmed():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert '登录后可收藏阵容、查看我的收藏。' in js
    assert '并自动续上刚才的操作' not in js


def test_lineup_detail_page_exists(client):
    from test_auth import register_user
    from test_lineup_permissions import create_lineup

    register_user(client, username='owner', email='owner@example.com')
    lineup = create_lineup(client, name='详情页阵容', code='#DETAIL001').get_json()
    response = client.get(f"/lineup/{lineup['id']}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="lineupDetailApp"' in html
    assert 'lineup-detail.js' in html


def test_account_page_requires_login_and_contains_shell(client):
    from test_auth import register_user

    assert client.get('/me').status_code == 401
    register_user(client, username='alice', email='alice@example.com')
    response = client.get('/me')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="accountApp"' in html
    assert 'account.js' in html
    assert '我的数据' in html


def test_account_js_contains_dashboard_and_history_sections():
    with open('static/account.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert '最近浏览' in js
    assert '最近复制' in js
    assert '我的举报' in js
    assert '我的阵容' in js


def test_account_js_contains_report_and_lineup_status_mappings():
    with open('static/account.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert "pending: '待处理'" in js
    assert "resolved: '已处理'" in js
    assert "dismissed: '已驳回'" in js
    assert "hidden: '已隐藏'" in js


def test_account_js_contains_copy_action_for_recent_history():
    with open('static/account.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert '复制阵容码' in js
    assert 'copyLineupCode' in js
    assert "recordLineupCopy(item.id, 'account')" in js
    assert 'account-list is-scrollable-history' in js


def test_app_js_contains_hide_action_for_admin_lineups():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'lineup.can_hide' in js
    assert '隐藏阵容' in js
    assert js.index("actions.append(button('复制阵容码'") < js.index("actions.append(button('查看'")
    assert 'showReportDialog' in js
    assert 'prompt(' not in js


def test_lineup_editor_js_submits_status_field():
    with open('static/lineup-editor.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'statusToggle' in js
    assert "status: elements.statusToggle.checked ? 'hidden' : 'normal'" in js


def test_auth_js_tracks_auth_page_open_growth_event():
    with open('static/auth.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'open_auth_page' in js
    assert '/api/growth-events' in js


def test_author_js_contains_copy_view_like_favorite_and_report_actions():
    with open('static/author.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert '复制阵容码' in js
    assert '查看' in js
    assert '点赞' in js
    assert '收藏' in js
    assert '举报' in js
    assert 'showAuthPrompt' in js
    assert 'showReportDialog' in js


def test_admin_js_supports_daily_growth_filter_and_clear_labels():
    with open('static/admin.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert '/api/admin/overview' in js
    assert '/api/admin/live-comps' in js
    assert '今日复制' in js
    assert '累计复制' in js
    assert '按实时阵容专区整体统计' in js
    assert 'activeTab' in js
    assert 'AbortController' in js
    assert 'debounce' in js
    assert 'growthDate' in js
    assert '/api/admin/growth?date=' in js
    assert '首页 UV' in js
    assert '点击登录入口人数' in js
    assert '登录后 10 分钟内完成点赞人数' in js
    assert '搜索用户名、邮箱或昵称后开始查找' in js
    assert '输入阵容名、阵容码、作者后开始查找' in js
    assert 'pending_reports_count' in js


def test_admin_js_renders_today_total_copy_metric():
    with open('static/admin.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert '今日总复制' in js
    assert '实时阵容 + 普通阵容有效复制' in js
    assert 'today_total_copy_count' in js


def test_styles_support_history_scroll_and_visibility_toggle():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.account-list.is-scrollable-history' in css
    assert '.visibility-toggle' in css


def test_admin_js_renders_lineup_code_in_lineup_management():
    with open('static/admin.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'lineup.code' in js


def test_index_contains_live_comps_tab_before_latest(client):
    html = client.get('/').get_data(as_text=True)
    assert '实时阵容排行' in html
    assert html.index('实时阵容排行') < html.index('最新')
    assert 'class="tab active" data-sort="live" data-view="live-comps"' in html


def test_index_contains_live_comps_mount_points(client):
    html = client.get('/').get_data(as_text=True)
    assert 'id="lineupList"' in html
    assert 'id="pagination"' in html
    assert 'data-view="live-comps"' in html


def test_app_js_contains_live_comps_mode_and_copy_only_actions():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'live-comps' in js
    assert '/api/live-comps/${encodeURIComponent(item.id)}/copy' in js
    assert '/api/live-comps/summary' in js
    assert '/api/live-comps?page=' in js
    assert '实时阵容排行' in js
    assert 'renderLiveComps' in js
    assert "sort: 'live'" in js
    assert "view: 'live-comps'" in js
    assert '由 DataTFT 支持' in js
    assert '暂无阵容码' in js
    assert 'item.jccCode' in js
    assert "button('暂无阵容码'" in js
    assert 'code.textContent = item.jccCode' not in js


def test_styles_include_live_comps_sections_and_cards():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.live-comps-summary-source' in css

    assert '.live-comps-shell' in css
    assert '.live-comps-grid' in css
    assert '.live-comp-card' in css
    assert '.live-comp-avatar-badge' in css
    assert '.live-comp-pagination' in css
    assert '.tier-s' in css
    assert '.tier-a' in css
    assert '.tier-b' in css
    assert '.tier-c' in css
    assert '.tier-d' in css



def test_lineup_simulator_page_exists_and_index_links_to_it(client):
    index_html = client.get('/').get_data(as_text=True)
    assert 'href="/tools/lineup-simulator"' in index_html
    assert '\u9635\u5bb9\u6a21\u62df\u5668' in index_html

    response = client.get('/tools/lineup-simulator')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<title>\u9635\u5bb9\u6a21\u62df\u5668</title>' in html
    assert 'simulator-root' in html
    assert 'tools/lineup-simulator/' in html
    assert 'local-data.js' not in html
    assert 'app.js' in html
    assert '\u8fd4\u56de\u9635\u5bb9\u5e93' in html
    assert 'background-upload-button' not in html
    assert 'background-upload-input' not in html
    assert 'custom-background-list' not in html
    assert 'panel-tab-backgrounds' not in html
    assert 'backgrounds-panel' not in html
    assert 'preset-background-list' not in html

    assert client.get('/static/tools/lineup-simulator/style.css').status_code == 200
    assert client.get('/static/tools/lineup-simulator/data/heroes.json').status_code == 200
    assert client.get('/static/tools/lineup-simulator/app.js').status_code == 200


def test_lineup_simulator_hidden_when_disabled(client):
    from test_admin import login_admin

    headers = login_admin(client)

    resp = client.put('/api/admin/settings', json={'simulator_enabled': 'false'}, headers=headers)
    assert resp.status_code == 200

    index_html = client.get('/').get_data(as_text=True)
    assert 'href="/tools/lineup-simulator"' not in index_html

    assert client.get('/tools/lineup-simulator').status_code == 404

    config = client.get('/api/site-config').get_json()
    assert config['simulator_enabled'] is False

    client.put('/api/admin/settings', json={'simulator_enabled': 'true'}, headers=headers)


def test_lineup_simulator_uses_jcc_light_theme_and_no_upload_script():
    with open('static/tools/lineup-simulator/style.css', 'r', encoding='utf-8') as file:
        css = file.read()
    with open('static/tools/lineup-simulator/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'JCC integrated light theme overrides' in css
    assert '--jcc-bg: #f8f5ef' in css
    assert '--jcc-accent: #c96442' in css
    assert 'backgroundUploadButton' not in js
    assert 'backgroundUploadInput' not in js
    assert 'customBackgroundList' not in js
    assert 'backgroundTabButton' not in js
    assert 'presetBackgroundList' not in js
    assert 'renderBackgroundPanel(refs, state)' not in js
    assert 'function loadCustomBackgrounds' not in js
    assert 'function renderBackgroundPanel' not in js
    assert 'function applyBattleCardBackground' not in js
    assert 'SELECTED_BACKGROUND_STORAGE_KEY' not in js



def test_lineup_simulator_has_no_background_modification_ui(client):
    html = client.get('/tools/lineup-simulator').get_data(as_text=True)

    assert 'panel-tab-backgrounds' not in html
    assert 'backgrounds-panel' not in html
    assert 'preset-background-list' not in html
    assert 'background-upload-button' not in html
    assert 'background-upload-input' not in html
    assert 'custom-background-list' not in html



def test_lineup_simulator_responsive_ux_structure(client):
    html = client.get('/tools/lineup-simulator').get_data(as_text=True)
    with open('static/tools/lineup-simulator/style.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert 'simulator-topbar' in html
    assert 'simulator-quick-guide' in html
    assert 'simulator-board-actions' in html
    assert 'simulator-tool-panel' in html
    assert '\u9635\u5bb9\u6a21\u62df\u5668' in html
    assert '\u7535\u8111\u7aef\u53ef\u62d6\u62fd' in html
    assert '\u5f08\u5b50' in html
    assert '\u88c5\u5907' in html
    assert 'order: 1' in css
    assert 'order: 2' in css
    assert 'position: sticky' in css
    assert 'max-height: min(58vh, 520px)' in css
    assert '@media (max-width: 760px)' in css
    assert 'max-height: 42vh' in css


def test_lineup_simulator_click_equip_interaction_support():
    with open('static/tools/lineup-simulator/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'selectedEquipId' in js
    assert 'selectEquipForClick' in js
    assert 'applySelectedEquipToBoardSlot' in js
    assert 'clearSelectedEquip' in js
    assert 'is-selected-for-click' in js
    assert 'aria-pressed' in js



def test_lineup_simulator_tool_panel_keeps_actions_visible():
    with open('static/tools/lineup-simulator/style.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.panel-shell {' in css
    assert 'min-height: 0' in css
    assert '.panel-body:not([hidden])' in css
    assert 'flex: 1 1 auto' in css
    assert '.simulator-board-actions {' in css
    assert 'flex: 0 0 auto' in css
    assert 'overscroll-behavior: contain' in css
    assert 'margin-right: 0' in css



def test_lineup_simulator_uses_three_column_workspace(client):
    html = client.get('/tools/lineup-simulator').get_data(as_text=True)
    with open('static/tools/lineup-simulator/style.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert 'simulator-shell--three-column' in html
    assert 'simulator-hero-panel' in html
    assert 'simulator-board-panel' in html
    assert 'simulator-equip-panel' in html
    assert 'simulator-side-title' in html
    assert 'equip-removal-hint' in html
    assert 'grid-template-columns: minmax(250px, 300px) minmax(560px, 1fr) minmax(250px, 300px)' in css
    assert 'grid-template-areas:' in css
    assert '"hero board equip"' in css
    assert '.simulator-hero-panel' in css
    assert '.simulator-equip-panel' in css
    assert '.simulator-board-panel' in css


def test_lineup_simulator_mobile_orders_board_before_side_panels():
    with open('static/tools/lineup-simulator/style.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '@media (max-width: 760px)' in css
    assert '"board"' in css
    assert '"hero"' in css
    assert '"equip"' in css
    assert 'max-height: 46vh' in css


def test_lineup_simulator_supports_direct_delete_and_equip_removal():
    with open('static/tools/lineup-simulator/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'removeEquipFromHero' in js
    assert 'removeEquipFromBoardSlot' in js
    assert 'data-remove-equip-index' in js
    assert 'data-remove-board-slot' in js
    assert 'board-unit-remove' in js



def test_lineup_simulator_enlarges_board_without_enlarging_card():
    with open('static/tools/lineup-simulator/style.css', 'r', encoding='utf-8') as file:
        css = file.read()
    with open('static/tools/lineup-simulator/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'grid-template-columns: minmax(250px, 300px) minmax(560px, 1fr) minmax(250px, 300px)' in css
    assert 'width: min(1380px, calc(100vw - 28px))' in css
    assert 'min-height: 560px' in css
    assert 'max-width: 1120px' not in css
    assert 'const BOARD_SCALE_MAX = 1.32;' in js
    assert '.simulator-shell--three-column .battle-card-board-panel' in css
    assert 'padding: 0.02rem 0 0.04rem' in css



def test_lineup_simulator_board_has_no_scroll_interaction():
    with open('static/tools/lineup-simulator/style.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.battle-card-board-area {' in css
    assert 'touch-action: none' in css
    assert 'overscroll-behavior: none' in css
    assert 'scrollbar-width: none' in css
    assert '.battle-card-board-area::-webkit-scrollbar' in css
    assert 'display: none' in css
    assert '.lineup-list {' in css
    assert 'overflow: visible' in css


def test_lineup_simulator_mobile_uses_board_first_layout_from_repo():
    with open('static/tools/lineup-simulator/style.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '/* JCC mobile simulator board-first UX */' in css
    assert 'min-height: clamp(410px, 128vw, 520px)' in css
    assert 'grid-template-rows: minmax(235px, 1fr) auto' in css
    assert 'width: 5.32rem' in css
    assert 'width: 0.7rem' in css
    assert 'max-height: 118px' in css



def test_lineup_simulator_cost_borders_use_requested_rgb_colors():
    with open('static/tools/lineup-simulator/style.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '--cost-1-border: rgb(175, 175, 175)' in css
    assert '--cost-2-border: rgb(28, 195, 152)' in css
    assert '--cost-3-border: rgb(7, 165, 241)' in css
    assert '--cost-4-border: rgb(213, 105, 230)' in css
    assert '--cost-5-border: rgb(255, 183, 1)' in css
    assert '.cost-1 {' in css
    assert '.cost-5 {' in css
    assert 'border-color: var(--cost-border)' in css
    assert 'box-shadow: 0 0 0 2px color-mix' in css



def test_lineup_simulator_board_units_show_cost_borders():
    with open('static/tools/lineup-simulator/style.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.cost-1.board-unit .board-unit-frame' in css
    assert '.cost-5.board-unit .board-unit-frame' in css
    assert 'padding: 0.028rem' in css
    assert 'filter: none' in css
    assert '.cost-1.board-unit::after' in css
    assert 'background: var(--cost-border)' in css
    assert '-webkit-mask:' in css
    assert 'mask-composite: exclude' in css
    board_section = css.split('/* JCC board unit cost borders */', 1)[1]
    assert 'drop-shadow' not in board_section
    assert 'color-mix' not in board_section



def test_lineup_simulator_loads_versioned_json_data_files(client):
    html = client.get('/tools/lineup-simulator').get_data(as_text=True)
    with open('static/tools/lineup-simulator/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert './local-data.js' not in html
    assert './app.js' in html
    assert 'loadSimulatorData' in js
    assert 'fetchJsonData("data/heroes.json")' in js
    assert 'fetchJsonData("data/equips.json")' in js
    assert 'fetchJsonData("data/traits.json")' in js
    assert 'fetchJsonData("data/pets.json")' in js
    assert 'fetchJsonData("data/tabs.json")' in js
    assert 'fetchJsonData("data/version.json")' in js

    for path in [
        '/static/tools/lineup-simulator/data/version.json',
        '/static/tools/lineup-simulator/data/tabs.json',
        '/static/tools/lineup-simulator/data/heroes.json',
        '/static/tools/lineup-simulator/data/equips.json',
        '/static/tools/lineup-simulator/data/traits.json',
        '/static/tools/lineup-simulator/data/pets.json',
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.mimetype == 'application/json'


def test_lineup_simulator_pool_images_use_lazy_loading():
    with open('static/tools/lineup-simulator/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert '<img class="pool-card-pic ${getProgressiveImageClass(hero.image)}" src="${hero.image}" alt="${hero.name}" loading="lazy" decoding="async" fetchpriority="low" data-progressive-image draggable="false" />' in js
    assert '<img class="pool-card-pic ${getProgressiveImageClass(equip.image)}" src="${equip.image}" alt="${equip.name}" loading="lazy" decoding="async" fetchpriority="low" data-progressive-image draggable="false" />' in js
    assert '<img class="${getProgressiveImageClass(equip.image)}" src="${equip.image}" alt="${equip.name}" loading="lazy" decoding="async" fetchpriority="low" data-progressive-image draggable="false" />' in js


def test_lineup_simulator_uses_blur_placeholders_for_progressive_images():
    with open('static/tools/lineup-simulator/app.js', 'r', encoding='utf-8') as file:
        js = file.read()
    with open('static/tools/lineup-simulator/style.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert 'function getBlurImagePath' in js
    assert 'class="pool-card-pic-box ${getProgressiveShellClass(hero.image)}"' in js
    assert 'getProgressiveImageStyle(hero.image)' in js
    assert 'getProgressiveImageStyle(equip.image)' in js
    assert 'return normalizedPath ? `blur/${normalizedPath}` : "";' in js
    assert 'data-progressive-image' in js
    assert 'markProgressiveImageLoaded' in js
    assert '.progressive-image-shell::before' in css
    assert '.progressive-image.is-loaded' in css


def test_lineup_simulator_remembers_loaded_progressive_images():
    with open('static/tools/lineup-simulator/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'const loadedProgressiveImagePaths = new Set();' in js
    assert 'function isProgressiveImageLoaded' in js
    assert 'function getProgressiveShellClass' in js
    assert 'function getProgressiveImageClass' in js
    assert 'loadedProgressiveImagePaths.add(getProgressiveImageCacheKey(image.getAttribute("src")))' in js
    assert 'class="pool-card-pic-box ${getProgressiveShellClass(hero.image)}"' in js
    assert 'class="pool-card-pic ${getProgressiveImageClass(hero.image)}"' in js


def test_admin_dashboard_clarifies_uv_labels_and_new_returning_visitors():
    with open('static/admin.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert '\u4eca\u65e5\u5168\u7ad9 UV' in js
    assert '\u6628\u65e5\u5168\u7ad9 UV' in js
    assert '7 \u65e5\u7d2f\u8ba1\u5168\u7ad9 UV' in js
    assert '\u9996\u9875 UV' in js
    assert '\u4eca\u65e5\u65b0\u8bbf\u5ba2' in js
    assert '\u4eca\u65e5\u8001\u8bbf\u5ba2' in js
    assert '\u9996\u6b21\u8bbf\u95ee\u65e5\u671f\u4e3a\u4eca\u5929' in js
    assert '\u4eca\u5929\u4e4b\u524d\u5df2\u8bbf\u95ee\u8fc7' in js
