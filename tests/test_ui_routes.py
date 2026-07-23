def test_index_uses_top_right_auth_link(client):
    html = client.get('/').get_data(as_text=True)
    assert 'href="/auth"' in html
    assert 'id="loginForm"' not in html
    assert 'id="registerForm"' not in html
    assert 'id="lineupForm"' not in html
    assert 'id="createLineupLink"' in html
    assert 'id="toast"' in html


def test_public_pages_include_seo_metadata(client):
    html = client.get('/').get_data(as_text=True)

    assert '<title>金铲铲阵容库 - 实时阵容排行与阵容码分享</title>' in html
    assert '<meta name="description"' in html
    assert '<link rel="canonical" href="http://localhost/"' in html
    assert '<meta name="robots" content="index, follow"' in html
    assert '<meta property="og:title"' in html
    assert 'application/ld+json' in html


def test_private_pages_are_noindex(client):
    auth_html = client.get('/auth').get_data(as_text=True)
    register_html = client.get('/auth/register').get_data(as_text=True)
    create_html = client.get('/lineup/new').get_data(as_text=True)

    assert '<meta name="robots" content="noindex, nofollow"' in auth_html
    assert '<meta name="robots" content="noindex, nofollow"' in register_html
    assert '<meta name="robots" content="noindex, nofollow"' in create_html


def test_admin_page_is_noindex(client):
    from test_admin import login_admin

    login_admin(client)
    html = client.get('/admin').get_data(as_text=True)

    assert '<meta name="robots" content="noindex, nofollow"' in html
    assert '<link rel="canonical" href="http://localhost/admin"' in html


def test_auth_page_contains_login_and_register_forms(client):
    response = client.get('/auth')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="loginForm"' in html
    assert 'id="registerForm"' not in html
    assert 'href="/auth/register"' in html

    register_response = client.get('/auth/register')
    register_html = register_response.get_data(as_text=True)
    assert register_response.status_code == 200
    assert 'id="loginForm"' not in register_html
    assert 'id="registerForm"' in register_html
    assert 'id="captchaImage"' in register_html


def test_auth_page_uses_card_redesign_shell(client):
    html = client.get('/auth').get_data(as_text=True)
    register_html = client.get('/auth/register').get_data(as_text=True)

    assert 'class="auth-redesign-shell"' in html
    assert 'class="auth-brand-panel"' not in html
    assert 'class="auth-redesign-main auth-centered-main"' in html
    assert 'class="auth-card auth-login-card"' in html
    assert 'class="auth-card auth-register-card"' in register_html
    assert 'class="auth-separator"' in html
    assert 'href="/auth/register"' in html
    assert 'href="/auth"' in register_html


def test_auth_page_password_visibility_controls_are_present(client):
    html = client.get('/auth').get_data(as_text=True)
    register_html = client.get('/auth/register').get_data(as_text=True)

    assert 'id="toggleLoginPassword"' in html
    assert 'aria-controls="loginPassword"' in html
    assert 'id="toggleRegisterPassword"' in register_html
    assert 'aria-controls="registerPassword"' in register_html
    assert 'data-password-toggle' in html
    assert 'class="auth-input-icon"' in html
    assert 'class="auth-eye-icon"' in html


def test_auth_js_wires_password_visibility_and_card_links():
    with open('static/auth.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'passwordToggles' in js
    assert 'setupPasswordVisibilityToggles' in js
    assert 'aria-pressed' in js
    assert "input.type = input.type === 'password' ? 'text' : 'password';" in js
    assert 'setupAuthJumpLinks' not in js
    assert 'scrollIntoView' not in js


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
    assert 'data-admin-tab="guestbook"' in admin_html
    assert 'class="admin-sidebar"' in admin_html
    assert 'class="admin-mobile-nav"' in admin_html
    assert 'id="adminMoreDialog"' in admin_html
    assert '/static/admin.css' in admin_html
    assert '/static/vendor/lucide/lucide.min.js' in admin_html
    assert 'class="hero"' not in admin_html
    assert 'id="adminTabBar"' not in admin_html

    favicon_response = client.get('/favicon.ico')
    assert favicon_response.status_code == 200
    assert favicon_response.mimetype == 'image/vnd.microsoft.icon'


def test_admin_mobile_styles_do_not_force_fixed_height_on_wide_traffic_module():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.admin-module:not(.admin-module-wide)' in css


def test_admin_responsive_shell_uses_sidebar_and_mobile_bottom_navigation():
    with open('static/admin.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.admin-sidebar {' in css
    assert '.admin-mobile-nav {' in css
    assert '.admin-more-dialog {' in css
    assert '@media (max-width: 820px)' in css
    assert 'grid-template-columns: repeat(5, 1fr);' in css
    assert 'padding-bottom: calc(var(--admin-mobile-nav-height) + env(safe-area-inset-bottom));' in css


def test_admin_vendors_lucide_icons_locally():
    with open('static/vendor/lucide/lucide.min.js', 'r', encoding='utf-8') as file:
        lucide_js = file.read()
    with open('static/vendor/lucide/LICENSE', 'r', encoding='utf-8') as file:
        license_text = file.read()

    assert 'createIcons' in lucide_js
    assert 'ISC License' in license_text


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


def test_admin_js_contains_lineup_bulk_import_workspace():
    with open('static/admin.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'lineupBulkImport' in js
    assert '批量导入阵容码' in js
    assert '导入赛季' in js
    assert 'lineupBulkImportSeasonToggle' in js
    assert 'setupLineupBulkImportSeasonDropdown' in js
    assert '/api/admin/lineups/bulk-import/preview' in js
    assert '/api/admin/lineups/bulk-import' in js
    assert '确认导入' in js


def test_index_page_contains_account_value_copy_and_favorites_tab(client):
    html = client.get('/').get_data(as_text=True)
    assert 'id="favoritesTab"' in html
    assert '登录后可收藏阵容并跨设备同步' in html
    assert '登录后可查看我的收藏和我的阵容' in html


def test_index_page_contains_home_image_mode_toggle(client):
    html = client.get('/').get_data(as_text=True)
    assert 'id="imageModeToggle"' in html
    assert 'id="imageModeText"' in html


def test_index_page_uses_animated_theme_toggler_shell(client):
    html = client.get('/').get_data(as_text=True)

    assert 'class="theme-toggle nav-icon-button animated-theme-toggle"' in html
    assert 'class="theme-toggle-svg"' in html
    assert 'id="themeMoonMaskCircle"' in html
    assert 'class="theme-toggle-rays"' in html
    assert 'aria-hidden="true"' in html


def test_homepage_theme_toggler_styles_and_state_are_present():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()
    with open('static/theme-toggle.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert '.animated-theme-toggle' in css
    assert '.theme-toggle-svg' in css
    assert '.theme-toggle-rays' in css
    assert '.animated-theme-toggle.is-dark' in css
    assert '.theme-toggle-svg,\n  .theme-toggle-body,\n  .theme-toggle-mask-circle,\n  .theme-toggle-rays,' in css
    assert "themeToggle.classList.toggle('is-dark', theme === 'dark');" in js
    assert "themeToggle.setAttribute('aria-label', theme === 'dark' ? '切换为白天模式' : '切换为夜间模式');" in js


def test_all_theme_toggles_use_animated_svg_shell():
    template_names = [
        'account.html',
        'admin.html',
        'auth.html',
        'author.html',
        'index.html',
        'lineup_detail.html',
        'lineup_form.html',
        'patch_note_detail.html',
        'patch_notes.html',
    ]

    for template_name in template_names:
        with open(f'templates/{template_name}', 'r', encoding='utf-8') as file:
            html = file.read()
        assert 'theme_toggle.html' in html or 'theme_toggle(' in html, template_name
        assert 'theme-toggle.js' in html, template_name

    with open('templates/theme_toggle.html', 'r', encoding='utf-8') as file:
        macro = file.read()
    assert 'animated-theme-toggle' in macro
    assert 'class="theme-toggle-svg"' in macro
    assert 'class="theme-toggle-rays"' in macro
    assert 'id="themeIcon" class="theme-toggle-icon" aria-hidden="true"' in macro


def test_all_theme_scripts_preserve_animated_svg_icon():
    script_names = [
        'account.js',
        'admin.js',
        'auth.js',
        'author.js',
        'lineup-detail.js',
        'lineup-editor.js',
        'patch-notes.js',
    ]

    for script_name in script_names:
        with open(f'static/{script_name}', 'r', encoding='utf-8') as file:
            js = file.read()
        assert 'jccApplyThemeToggleState' in js, script_name
        assert ".textContent = theme === 'dark' ? '☼' : '☾'" not in js, script_name
        assert ".textContent = theme === 'dark' ? '☀' : '☾'" not in js, script_name


def test_homepage_stat_card_has_border_glow_hook():
    with open('templates/index.html', 'r', encoding='utf-8') as file:
        html = file.read()

    assert 'class="stat-card border-glow-card"' in html
    assert 'data-border-glow="stat"' in html


def test_homepage_separates_site_total_from_current_display_count(client):
    html = client.get('/').get_data(as_text=True)

    assert '<span class="stat-label">全站收录</span>' in html
    assert '<span class="stat-caption">套阵容</span>' in html
    assert 'id="currentDisplayCount"' in html
    assert '当前展示' in html
    assert '<span class="stat-label">已展示</span>' not in html


def test_app_js_loads_home_stats_and_updates_current_display_count():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert "fetch('/api/home-stats')" in js
    assert 'homeStats' in js
    assert 'currentDisplayCount' in js
    assert 'renderCurrentDisplayCount(' in js
    assert 'elements.lineupCount.textContent = state.homeStats.total_public_lineups' in js
    assert 'elements.lineupCount.textContent = state.total' not in js


def test_homepage_search_has_dissolve_clear_layers(client):
    html = client.get('/').get_data(as_text=True)

    assert '<div class="search-field t-clear"' in html
    assert '<label class="sr-only" for="searchInput">搜索阵容名称</label>' in html
    assert 'id="searchInput"' in html
    assert 'class="t-clear-mirror"' in html
    assert 'class="t-clear-placeholder"' in html
    assert 'class="t-clear-glow"' in html
    assert 'id="searchClearButton"' in html
    assert 'aria-label="清除搜索"' in html
    assert 'src="/static/home-transitions.js"' in html
    assert html.index('src="/static/home-transitions.js"') < html.index('src="/static/app.js"')


def test_home_transition_module_supports_search_clear_animation():
    with open('static/home-transitions.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'function createSearchClear(' in js
    assert 'requestAnimationFrame' in js
    assert 'radial-gradient(' in js
    assert "classList.toggle('has-value'" in js
    assert "classList.add('is-clearing')" in js
    assert 'prefers-reduced-motion: reduce' in js
    assert 'cancelAnimationFrame' in js


def test_app_js_clears_search_state_before_reloading_lineups():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'JccHomeTransitions.createSearchClear' in js
    assert 'function clearLineupSearch()' in js
    function_body = js.split('function clearLineupSearch()', 1)[1].split('\n}', 1)[0]
    assert function_body.index("state.query = ''") < function_body.index('loadLineups()')
    assert function_body.index('state.page = 1') < function_body.index('loadLineups()')


def test_home_transition_module_builds_lineup_skeletons_and_reveals():
    with open('static/home-transitions.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'function createLineupLoader(' in js
    assert "wrapper.className = 't-skel'" in js
    assert "skeleton.className = 't-skel-skeleton is-pulsing'" in js
    assert "content.className = 't-skel-content'" in js
    assert "classList.add('is-revealed')" in js
    assert "classList.add('is-resetting')" in js


def test_app_js_uses_skeletons_only_for_uncached_regular_lineup_navigation():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'const cachedResponse = readHomeCache(' in js
    assert 'lineupLoader.showLoading()' in js
    assert 'lineupLoader.reveal(' in js
    assert 'lineupLoader.fail()' in js
    assert 'async function loadLineups(options = {})' in js
    assert 'options.preserveContent' in js
    assert 'loadLineups({ preserveContent: true })' in js


def test_homepage_clear_and_skeleton_transition_styles_are_present():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    for selector in (
        '.t-clear {',
        '.t-clear-mirror,',
        '.t-clear-glow {',
        '.t-clear:focus-within {',
        '.t-clear-btn {',
        '.t-skel {',
        '.t-skel-skeleton,',
        '.t-skel.is-revealed .t-skel-content',
        '.t-skel.is-resetting .t-skel-skeleton',
        '@keyframes t-skel-pulse',
    ):
        assert selector in css
    assert ':root[data-theme="dark"] .t-clear-glow' in css
    assert '@media (prefers-reduced-motion: reduce)' in css


def test_border_glow_is_scoped_to_homepage_realtime_cards():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'function initBorderGlowCard(' in js
    assert 'function applyBorderGlowToStaticCards(' in js
    assert "card.dataset.borderGlow = 'live-comp'" in js
    assert 'initBorderGlowCard(card, {' in js


def test_border_glow_styles_are_present():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert '.border-glow-card {' in css
    assert '.border-glow-card::before' in css
    assert '.border-glow-card::after' in css
    assert '.border-glow-card > .edge-light' in css
    assert '@media (prefers-reduced-motion: reduce)' in css


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
    assert '登录后可收藏阵容并跨设备同步' not in html
    assert '登录后可发布和管理自己的阵容' not in html
    assert '登录后可查看我的收藏、我的阵容和个人记录' not in html


def test_index_and_auth_pages_include_auth_intent_script(client):
    index_html = client.get('/').get_data(as_text=True)
    auth_html = client.get('/auth').get_data(as_text=True)

    assert 'auth-intent.js' in index_html
    assert 'auth-intent.js' in auth_html


def test_patch_note_pages_exist_and_homepage_links_to_patch_notes(client):
    from test_admin import login_admin

    index_html = client.get('/').get_data(as_text=True)
    assert 'href="/patch-notes"' in index_html
    assert '更新公告' in index_html

    headers = login_admin(client)
    created = client.post('/api/admin/patch-notes', json={
        'title': '页面存在性公告',
        'version': 'UI',
        'source_url': '',
        'summary_markdown': '页面存在性公告内容',
        'original_text': '',
        'status': 'published',
        'published_at': '2026-07-04',
    }, headers=headers).get_json()
    client.post('/api/logout')

    list_response = client.get('/patch-notes')
    detail_response = client.get(f"/patch-notes/{created['id']}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert 'id="patchNotesApp"' in list_response.get_data(as_text=True)
    assert 'id="patchNoteDetailApp"' in detail_response.get_data(as_text=True)


def test_patch_note_detail_page_renders_crawlable_published_content(client):
    from test_admin import login_admin

    headers = login_admin(client)
    created = client.post('/api/admin/patch-notes', json={
        'title': 'S17 平衡调整',
        'version': 'S17.1',
        'source_url': 'https://example.com/source',
        'summary_markdown': '## 英雄调整\n- [buff] 卡莎 攻速 0.8 => 0.85',
        'original_text': '官方原文',
        'status': 'published',
        'published_at': '2026-07-04',
    }, headers=headers).get_json()
    client.post('/api/logout')

    response = client.get(f"/patch-notes/{created['id']}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<h1>S17 平衡调整</h1>' in html
    assert 'S17.1' in html
    assert '英雄调整' in html
    assert '卡莎 攻速 0.8 =&gt; 0.85' in html
    assert '<script type="application/ld+json">' in html
    assert f'<link rel="canonical" href="http://localhost/patch-notes/{created["id"]}"' in html


def test_patch_note_detail_page_returns_404_for_draft(client):
    from test_admin import login_admin

    headers = login_admin(client)
    created = client.post('/api/admin/patch-notes', json={
        'title': '草稿公告',
        'version': 'D1',
        'source_url': '',
        'summary_markdown': '草稿内容',
        'original_text': '',
        'status': 'draft',
        'published_at': '2026-07-04',
    }, headers=headers).get_json()
    client.post('/api/logout')

    assert client.get(f"/patch-notes/{created['id']}").status_code == 404


def test_index_page_contains_rising_recommended_and_author_link_shell(client):
    html = client.get('/').get_data(as_text=True)
    assert 'data-sort="rising"' in html
    assert 'data-sort="recommended"' in html
    assert 'author-link' in html


def test_index_page_contains_guest_action_prompt_shell(client):
    html = client.get('/').get_data(as_text=True)
    assert 'id="authPromptRoot"' in html


def test_home_pagination_uses_numbered_navigation(client):
    html = client.get('/').get_data(as_text=True)
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'id="pagination"' in html
    assert 'aria-label="分页导航"' in html
    assert 'function buildPaginationItems(' in js
    assert "type: 'ellipsis'" in js
    assert 'pagination-page' in js
    assert 'pagination-ellipsis' in js
    assert '前往第 ${pageNumber} 页' in js
    assert "setAttribute('aria-current', 'page')" in js
    assert 'pagination-dot' not in js
    assert 'pagination-ripple' not in js


def test_home_pagination_has_desktop_and_compact_windows():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'const desktopLimit = 7' in js
    assert 'const compactLimit = 5' in js
    assert "globalThis.matchMedia('(max-width: 520px)')" in js
    assert 'currentPage <= 4' in js
    assert 'currentPage >= totalPages - 3' in js
    assert 'currentPage - 1' in js
    assert 'currentPage + 1' in js


def test_home_pagination_scrolls_after_successful_page_load():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'pendingPaginationScroll' in js
    assert 'function scrollToLineupList()' in js
    assert "behavior: reduceMotion.matches ? 'auto' : 'smooth'" in js
    assert 'elements.listHeading.scrollIntoView(' in js
    assert 'completePaginationNavigation()' in js
    assert 'pendingPaginationScroll = true' in js


def test_home_pagination_reacts_to_mobile_breakpoint_changes():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'paginationCompactQuery' in js
    assert "paginationCompactQuery.addEventListener('change'" in js
    assert 'renderPagination()' in js


def test_home_numbered_pagination_styles_are_present():
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    for selector in (
        '.pagination-content {',
        '.pagination-direction,',
        '.pagination-page {',
        '.pagination-page.is-active {',
        '.pagination-ellipsis {',
        '.pagination-icon {',
        '.pagination-direction-label {',
    ):
        assert selector in css
    assert 'box-shadow: 3px 3px 0' in css
    assert '@media (max-width: 520px)' in css
    assert '.pagination-direction-label' in css
    assert '.pagination-dot' not in css
    assert '@keyframes pagination-ripple' not in css


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


def test_lineup_detail_page_renders_crawlable_lineup_content(client):
    from test_auth import register_user
    from test_lineup_permissions import create_lineup

    register_user(client, username='seoowner', email='seoowner@example.com', nickname='阵容作者')
    lineup = create_lineup(client, name='SEO阵容', code='#SEOCODE123456789').get_json()
    client.post('/api/logout')

    response = client.get(f"/lineup/{lineup['id']}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<h1 class="detail-title">SEO阵容</h1>' in html
    assert '阵容作者' in html
    assert 'S17 · 星神' in html
    assert '#SEOCODE123...' in html
    assert f'<link rel="canonical" href="http://localhost/lineup/{lineup["id"]}"' in html
    assert 'Lineup Detail' in html


def test_lineup_detail_page_returns_404_for_hidden_lineup_to_public(client):
    from test_auth import register_user
    from test_lineup_permissions import create_lineup

    register_user(client, username='hiddenowner', email='hiddenowner@example.com')
    lineup = create_lineup(client, name='隐藏SEO阵容', code='#HIDDENSEO', status='hidden').get_json()
    client.post('/api/logout')

    assert client.get(f"/lineup/{lineup['id']}").status_code == 404


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


def test_author_page_renders_crawlable_public_profile(client):
    from test_auth import register_user
    from test_lineup_permissions import create_lineup

    register_user(client, username='seoauthor', email='seoauthor@example.com', nickname='SEO作者')
    create_lineup(client, name='作者公开阵容', code='#AUTHORSEO123')
    client.post('/api/logout')

    response = client.get('/author/seoauthor')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<h1>SEO作者的金铲铲阵容</h1>' in html
    assert '作者公开阵容' in html
    assert '<meta name="robots" content="index, follow"' in html
    assert '<link rel="canonical" href="http://localhost/author/seoauthor"' in html


def test_author_page_with_no_public_lineups_is_noindex(client):
    from test_auth import register_user

    register_user(client, username='emptyauthor', email='emptyauthor@example.com', nickname='空作者')
    client.post('/api/logout')

    html = client.get('/author/emptyauthor').get_data(as_text=True)

    assert '空作者' in html
    assert '<meta name="robots" content="noindex, nofollow"' in html


def test_author_page_returns_404_for_missing_author(client):
    assert client.get('/author/missing-author').status_code == 404


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
    assert '普通阵容 ${stats.today_lineup_copy_count || 0}' in js
    assert '实时阵容 ${stats.today_live_comp_copy_count || 0}' in js
    assert 'today_total_copy_count' in js


def test_shared_head_restores_saved_theme_before_stylesheet():
    with open('templates/seo_head.html', 'r', encoding='utf-8') as file:
        head = file.read()

    theme_position = head.index("localStorage.getItem('theme')")
    stylesheet_position = head.index("filename='styles.css'")
    assert theme_position < stylesheet_position
    assert "document.documentElement.dataset.theme = savedTheme" in head


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


def test_index_tabs_use_underline_indicator_shell(client):
    html = client.get('/').get_data(as_text=True)

    assert 'class="tabs-shell"' in html
    assert 'class="tabs" id="tabs" role="tablist"' in html
    assert 'class="tab-indicator" id="tabIndicator" aria-hidden="true"' in html


def test_app_js_updates_home_tab_indicator():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'tabIndicator: $(\'#tabIndicator\')' in js
    assert 'function updateTabIndicator()' in js
    assert "elements.tabs.style.setProperty('--active-tab-width'" in js
    assert "window.addEventListener('resize', updateTabIndicator)" in js


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


def test_special_mechanics_page_exists_and_index_links_to_it(client):
    index_html = client.get('/').get_data(as_text=True)
    assert 'href="/tools/special-mechanics"' in index_html
    assert '<img class="nav-tool-icon special-mechanics-nav-icon"' in index_html
    assert 'src="/static/special-mechanics/s8-icon.png"' in index_html
    assert 'S8回归信息差' in index_html
    assert 'class="returning-info-menu desktop-resource-entry"' in index_html
    assert 'href="/tools/returning-equipment"' in index_html
    assert '回归装备' in index_html
    assert '12 件返场装备说明' in index_html
    assert '5 件返场装备说明' not in index_html
    assert '特殊机制' in index_html

    response = client.get('/tools/special-mechanics')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'S8·怪兽入侵 特殊机制' in html
    assert '查看返场赛季的战力形态与经济形态' not in html
    assert 'href="/tools/lineup-simulator"' not in html
    assert 'data-filter="all"' in html
    assert 'data-filter="power"' in html
    assert 'data-filter="economy"' in html
    assert 'class="special-mechanics-hero-panel"' in html
    assert 'special-mechanics-hero-mark' not in html
    assert 'class="special-mechanics-filter special-mechanics-filter-sticky"' in html
    assert 'special-mechanics.js' in html
    assert 'special-mechanics.css' in html
    assert client.get('/static/special-mechanics/s8-icon.png').status_code == 200
    assert client.get('/static/special-mechanics/avatars/8357.png').status_code == 200


def test_home_mobile_resource_dialog_groups_content_entries(client):
    index_html = client.get('/').get_data(as_text=True)
    css = client.get('/static/styles.css').get_data(as_text=True)
    javascript = client.get('/static/app.js').get_data(as_text=True)

    assert 'id="mobileResourceTrigger"' in index_html
    assert 'aria-controls="mobileResourceDialog"' in index_html
    assert '<dialog class="mobile-resource-dialog" id="mobileResourceDialog"' in index_html
    assert 'id="mobileS8ResourceTitle"' in index_html
    assert 'class="mobile-resource-item" href="/tools/lineup-simulator"' in index_html
    assert 'class="mobile-resource-item mobile-resource-item-featured" href="/tools/s18-preview"' in index_html
    assert 'class="mobile-resource-item" href="/patch-notes"' in index_html
    assert 'class="mobile-resource-subitem" href="/tools/special-mechanics"' in index_html
    assert 'class="mobile-resource-subitem" href="/tools/artifact-guide"' in index_html
    assert 'class="mobile-resource-subitem" href="/tools/returning-equipment"' in index_html
    assert index_html.count('desktop-resource-entry') == 4

    mobile_css = css[css.index('@media (max-width: 520px)'):]
    assert '.nav-actions > .desktop-resource-entry {' in mobile_css
    assert '.nav-actions > .mobile-resource-trigger {' in mobile_css
    assert '.mobile-resource-dialog[open] {' in css
    assert '.mobile-resource-dialog::backdrop {' in css
    assert 'openMobileResourceDialog' in javascript
    assert 'handleMobileResourceDialogClosed' in javascript
    assert "event.key !== 'Escape' || !elements.mobileResourceDialog?.open" in javascript
    assert "if (!event.matches) closeMobileResourceDialog({ restoreFocus: false });" in javascript


def test_returning_equipment_page_exists_and_index_links_to_it(client):
    index_html = client.get('/').get_data(as_text=True)
    assert 'S8回归信息差' in index_html
    assert 'href="/tools/returning-equipment"' in index_html

    response = client.get('/tools/returning-equipment')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'S8·怪兽入侵 回归装备' in html
    assert '鬼索的狂暴之刃' in html
    assert '卢安娜的飓风' in html
    assert '灵风' in html
    assert '基克的先驱' in html
    assert '静止法衣' in html
    assert '兹若特传送门' in html
    assert '疾射火炮' in html
    assert '钢铁烈阳之匣' in html
    assert '能量圣杯' in html
    assert '狂徒铠甲' in html
    assert '斯塔缇克电刃' in html
    assert '蓝霸符' in html
    assert '基克的聚合' not in html
    assert '每次攻击提供5%额外攻击速度' in html
    assert '攻击距离+1' in html
    assert 'returning-equipment-component-image' in html
    assert 'returning-equipment.css' in html
    assert 'returning-equipment.js' in html
    assert 'href="/tools/special-mechanics"' not in html

    for filename in (
        'guinsoos-rageblade.png',
        'runaans-hurricane.png',
        'zephyr.png',
        'zekes-herald.png',
        'shroud-of-stillness.png',
        'zzrot-portal.png',
        'rapid-firecannon.png',
        'locket-of-the-iron-solari.png',
        'chalice-of-power.png',
        'warmogs-armor.png',
        'statikk-shiv.png',
        'blue-buff.png',
        'component-recurve-bow.jpg',
        'component-needlessly-large-rod.jpg',
        'component-negatron-cloak.jpg',
        'component-giants-belt.jpg',
        'component-bf-sword.jpg',
        'component-chain-vest.jpg',
        'component-sparring-gloves.jpg',
        'component-tear-of-the-goddess.jpg',
    ):
        assert client.get(f'/static/returning-equipment/{filename}').status_code == 200


def test_artifact_guide_page_exists_and_index_links_to_it(client):
    index_html = client.get('/').get_data(as_text=True)
    assert 'href="/tools/artifact-guide"' in index_html
    assert '神器搭配指南' in index_html

    response = client.get('/tools/artifact-guide')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'S8·怪兽入侵 神器搭配指南' in html
    assert 'artifact-guide-grid' in html
    assert 'artifacts-guide.js' in html
    assert 'artifacts-guide.css' in html
    assert '查看返场赛季的英雄与神器搭配' not in html
    assert client.get('/static/artifacts-guide/heroes/5127_厄加特_s8_urgot.png').status_code == 200
    assert client.get('/static/artifacts-guide/artifacts/6072_密银黎明_silvermere_dawn.jpg').status_code == 200


def test_artifact_guide_assets_define_cards_and_images():
    with open('static/artifacts-guide.js', 'r', encoding='utf-8') as file:
        js = file.read()
    with open('static/artifacts-guide.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert 'const ARTIFACT_GUIDE_CARDS = [' in js
    assert 'artifact-guide-card' in js
    assert 'artifact-guide-hero-image' in js
    assert 'artifact-guide-artifact-image' in js
    assert 'artifact-guide-evaluation' in js
    assert '厄加特' in js
    assert '秘银' in js
    assert '努努' in js
    assert '探索者护臂' in js
    assert '薇恩' in js
    assert '斯塔缇克电刃' in js
    assert '.artifact-guide-card {' in css
    assert '.artifact-guide-image-grid {' in css
    assert '.artifact-guide-hero-image {' in css
    assert '.artifact-guide-artifact-image {' in css
    assert '.artifact-guide-image-wrap {' in css
    assert 'width: 68px;' in css
    assert 'height: 68px;' in css
    assert 'width: 60px;' in css
    assert 'height: 60px;' in css
    assert 'object-fit: contain;' in css


def test_special_mechanics_assets_define_filter_groups():
    with open('static/special-mechanics.js', 'r', encoding='utf-8') as file:
        js = file.read()
    with open('static/special-mechanics.css', 'r', encoding='utf-8') as file:
        css = file.read()
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        global_css = file.read()

    assert "filter: 'power'" in js
    assert "filter: 'economy'" in js
    assert '卑鄙茧房' in js
    assert 'skillDesc' in js
    assert 'summary:' not in js
    assert '受到攻击后会逃跑的胆小单位，每生存1秒获得1成长层数' in js
    assert "image: '/static/special-mechanics/avatars/8357.png'" in js
    assert 'setSpecialMechanicsTheme' in js
    assert "themeToggle?.addEventListener('click'" in js
    assert '.nav-tool-icon {' in global_css
    assert 'object-fit: contain;' in global_css
    assert '.special-mechanics-nav-icon {' in global_css
    assert 'background: rgb(201, 100, 66);' in global_css
    assert 'grid-template-columns: 72px minmax(0, 1fr);' in css
    assert '.special-mechanic-image-wrap {' in css
    assert 'border-radius: 0;' in css
    assert 'overflow-wrap: anywhere;' in css
    assert 'word-break: break-word;' in css
    assert 'special-mechanic-list' in css
    assert 'mechanic-filter-button' in css
    assert '.special-mechanics-filter-sticky' in css
    assert 'position: sticky;' in css
    assert '.special-mechanic-type-badge' in css
    assert '.special-mechanic-description-label' in css
    assert '@media (max-width: 640px)' in css
    assert 'grid-template-columns: 1fr;' in css
    assert 'special-mechanics-hero-mark' not in css
    assert 'SPECIAL_MECHANIC_FILTER_LABELS' in js
    assert "summary.textContent = item.skillDesc;" in js
    assert 'special-mechanic-meta-row' in js
    assert 'special-mechanic-rank-badge' in js


def test_special_mechanics_assets_define_rank_badges():
    with open('static/special-mechanics.js', 'r', encoding='utf-8') as file:
        js = file.read()
    with open('static/special-mechanics.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert 'const SPECIAL_MECHANIC_RANKS = {' in js
    assert 'power: {' in js
    assert 'economy: {' in js
    assert "'迅捷蟹（战力）': 'A'" in js
    assert "'迅捷蟹（经济）': 'C'" in js
    assert "'胖胖龙（战力）': 'S'" in js
    assert "'阿木木（经济）': 'S'" in js
    assert "'防御塔（战力）': 'C'" in js
    assert "'卑鄙茧房': 'S'" in js
    assert 'special-mechanic-meta-row' in js
    assert 'special-mechanic-rank-badge' in js
    assert "rankBadge.textContent = rank;" in js
    assert '.special-mechanic-meta-row {' in css
    assert '.special-mechanic-rank-badge {' in css
    assert '[data-rank="S"]' in css
    assert '[data-rank="A"]' in css
    assert '[data-rank="B"]' in css
    assert '[data-rank="C"]' in css


def test_returning_equipment_assets_define_cards_and_mobile_layout():
    with open('static/returning-equipment.js', 'r', encoding='utf-8') as file:
        js = file.read()
    with open('static/returning-equipment.css', 'r', encoding='utf-8') as file:
        css = file.read()
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        global_css = file.read()

    assert 'RETURNING_EQUIPMENT' in js
    assert "image: '/static/returning-equipment/guinsoos-rageblade.png'" in js
    assert '鬼索的狂暴之刃' in js
    assert '卢安娜的飓风' in js
    assert '灵风' in js
    assert '基克的先驱' in js
    assert '静止法衣' in js
    assert '兹若特传送门' in js
    assert '疾射火炮' in js
    assert '钢铁烈阳之匣' in js
    assert '能量圣杯' in js
    assert '狂徒铠甲' in js
    assert '斯塔缇克电刃' in js
    assert '蓝霸符' in js
    assert '基克的聚合' not in js
    assert 'basicDesc' in js
    assert 'components' in js
    assert 'component-recurve-bow.jpg' in js
    assert 'returning-equipment-grid' in css
    assert 'returning-equipment-card' in css
    assert 'returning-equipment-components' in css
    assert 'returning-equipment-component-image' in css
    assert '@media (max-width: 640px)' in css
    assert 'grid-template-columns: 1fr;' in css
    assert '.returning-info-menu' in global_css
    assert '.returning-info-menu::after' in global_css
    assert '.returning-info-menu-panel' in global_css


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


def test_lineup_simulator_does_not_load_global_stylesheet(client):
    html = client.get('/tools/lineup-simulator').get_data(as_text=True)

    assert '<meta name="description" content="在线搭配金铲铲阵容棋盘、弈子、装备和羁绊。"' in html
    assert '<link rel="canonical" href="http://localhost/tools/lineup-simulator"' in html
    assert 'href="/static/styles.css"' not in html
    assert 'href="./style.css"' in html


def test_home_live_comps_uses_live_comps_seasons_without_changing_lineup_editor():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        home_js = file.read()
    with open('static/lineup-editor.js', 'r', encoding='utf-8') as file:
        editor_js = file.read()

    assert "fetch('/api/live-comps/seasons')" in home_js
    assert "fetch('/api/lineup-seasons')" in editor_js


def test_home_tab_switch_refreshes_season_filter_for_current_view():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    start = js.index('function setActiveTab(sort, view)')
    end = js.index('function syncActiveTab()', start)
    body = js[start:end]

    assert 'syncSeasonSelectionForViewChange(previousView, view);' in body
    assert 'renderLineupSeasonFilter();' in body


def test_home_tab_switch_keeps_selected_season_across_live_and_lineup_views():
    with open('static/app.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert 'function syncSeasonSelectionForViewChange(previousView, nextView)' in js
    assert "previousView === 'live-comps' && nextView !== 'live-comps'" in js
    assert 'state.selectedLineupSeasonId = state.selectedLiveCompSeasonId;' in js
    assert "previousView !== 'live-comps' && nextView === 'live-comps'" in js
    assert 'state.selectedLiveCompSeasonId = state.selectedLineupSeasonId;' in js


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


def test_admin_dashboard_renders_uv_trend_as_line_chart():
    with open('static/admin.js', 'r', encoding='utf-8') as file:
        js = file.read()
    with open('static/styles.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert 'function renderTrafficLineChart(' in js
    assert 'traffic-line-chart' in js
    assert 'traffic-line-path' in js
    assert 'traffic-line-point' in js
    assert 'traffic-line-point-wrap' in js
    assert 'traffic-line-hit-area' in js
    assert 'traffic-line-guide' in js
    assert 'traffic-line-tooltip' in js
    assert 'traffic-line-tooltip-date' in js
    assert 'traffic-line-tooltip-value' in js
    assert "pointGroup.setAttribute('role', 'list')" in js
    assert "pointWrap.setAttribute('tabindex', '0')" in js
    assert 'traffic-trend-row' not in js
    assert 'traffic-trend-fill' not in js
    assert '.traffic-line-chart' in css
    assert '.traffic-line-path' in css
    assert '.traffic-line-point' in css
    assert '.traffic-line-point-wrap:hover .traffic-line-tooltip' in css
    assert '.traffic-line-point-wrap:focus-visible .traffic-line-tooltip' in css


def test_admin_live_comps_season_manager_supports_order_controls():
    with open('static/admin.js', 'r', encoding='utf-8') as file:
        js = file.read()

    assert "button('上移'" in js
    assert "button('下移'" in js
    assert 'moveLiveCompSeason(season, -1)' in js
    assert 'moveLiveCompSeason(season, 1)' in js
    assert 'body: JSON.stringify({ order: nextOrder })' in js
