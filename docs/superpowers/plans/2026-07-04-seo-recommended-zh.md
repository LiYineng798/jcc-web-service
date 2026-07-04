# SEO Recommended Chinese Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Baidu-oriented recommended-tier SEO for public JCC pages by adding metadata, server-rendered crawlable public detail content, robots.txt, and sitemap.xml.

**Architecture:** Add a small `seo.py` helper module and a shared `templates/seo_head.html` macro, then pass explicit `seo` dictionaries from page routes. Reuse existing read services for lineup, author, and patch note payloads so the first HTML paint and API responses stay aligned.

**Tech Stack:** Python 3, Flask, Jinja, SQLite/PostgreSQL-compatible DB adapter, pytest.

---

## File Structure

- Create `seo.py`: SEO metadata builders, canonical URL helpers, text truncation, code preview masking, season labels, JSON-LD constructors, robots.txt body builder, and sitemap XML builder.
- Create `templates/seo_head.html`: shared Jinja macro for charset, viewport, title, description, canonical, robots, Open Graph, JSON-LD, favicon, fonts, and stylesheet links.
- Modify `app_pages.py`: pass SEO metadata into public and private page templates, fetch crawlable lineup and author payloads, add `/robots.txt` and `/sitemap.xml`.
- Modify `patch_notes.py`: pass SEO metadata into patch note pages and fetch published patch note details for first-load HTML.
- Modify page templates: replace repeated `<head>` blocks with the shared macro and render server-side fallback content for lineup detail, author profile, and patch note detail.
- Modify `tests/test_ui_routes.py`: add focused route/template tests for metadata and server-rendered public content.
- Add `tests/test_seo.py`: helper, robots, sitemap, and crawlability tests.

## Task 1: SEO Helper And Head Macro

**Files:**
- Create: `seo.py`
- Create: `templates/seo_head.html`
- Modify: `tests/test_seo.py`

- [ ] **Step 1: Write failing tests for SEO helper defaults and head output**

Create `tests/test_seo.py` with:

```python
from seo import code_preview, make_seo, season_label, truncate_text


def test_make_seo_builds_canonical_and_social_fields(app):
    with app.test_request_context('/lineup/12?sort=hot', base_url='https://jcc.example'):
        seo = make_seo(
            title='测试阵容 - 金铲铲阵容库',
            description='测试阵容描述',
            path='/lineup/12',
        )

    assert seo['title'] == '测试阵容 - 金铲铲阵容库'
    assert seo['description'] == '测试阵容描述'
    assert seo['canonical_url'] == 'https://jcc.example/lineup/12'
    assert seo['og_type'] == 'website'
    assert seo['robots'] == 'index, follow'
    assert seo['json_ld'] == []


def test_make_seo_supports_noindex(app):
    with app.test_request_context('/admin', base_url='https://jcc.example'):
        seo = make_seo(title='后台', description='后台页面', noindex=True)

    assert seo['canonical_url'] == 'https://jcc.example/admin'
    assert seo['robots'] == 'noindex, nofollow'


def test_truncate_text_is_plain_and_length_limited():
    assert truncate_text('  abc\\ndefghi  ', 8) == 'abc d...'
    assert truncate_text('', 8) == ''


def test_code_preview_masks_long_lineup_codes():
    assert code_preview('#ABC123') == '#ABC123'
    assert code_preview('#1234567890ABCDEFG') == '#1234567890...'


def test_season_label_uses_catalog_name():
    assert season_label('s17-star-god') == 'S17 · 星神'
    assert season_label('unknown-season') == 'unknown-season'
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_seo.py -q
```

Expected: FAIL because `seo.py` does not exist.

- [ ] **Step 3: Implement `seo.py`**

Create `seo.py`:

```python
import html
import re
from urllib.parse import urljoin

from flask import request

from seasons import season_catalog

SITE_NAME = '金铲铲阵容库'
DEFAULT_TITLE = '金铲铲阵容库 - 实时阵容排行与阵容码分享'
DEFAULT_DESCRIPTION = '金铲铲阵容库收录金铲铲之战阵容码、实时阵容排行、赛季阵容搜索和玩家分享阵容，支持复制、收藏、点赞和查看更新公告。'
DEFAULT_IMAGE_PATH = '/static/favicon.png'
INDEX_ROBOTS = 'index, follow'
NOINDEX_ROBOTS = 'noindex, nofollow'


def absolute_url(path):
    selected_path = path or request.path or '/'
    if selected_path.startswith('http://') or selected_path.startswith('https://'):
        return selected_path
    return urljoin(request.url_root, selected_path.lstrip('/'))


def truncate_text(value, max_length=155):
    plain = re.sub(r'\\s+', ' ', str(value or '')).strip()
    if len(plain) <= max_length:
        return plain
    return plain[:max(0, max_length - 3)].rstrip() + '...'


def code_preview(code, max_length=11):
    text = str(code or '').strip()
    if len(text) <= max_length:
        return text
    return text[:max_length] + '...'


def season_label(season_id):
    for season in season_catalog():
        if season['id'] == season_id:
            return season['name']
    return str(season_id or '')


def make_seo(title=None, description=None, path=None, noindex=False, og_type='website', image_path=DEFAULT_IMAGE_PATH, json_ld=None):
    selected_title = title or DEFAULT_TITLE
    selected_description = truncate_text(description or DEFAULT_DESCRIPTION)
    canonical_url = absolute_url(path)
    return {
        'title': selected_title,
        'description': selected_description,
        'canonical_url': canonical_url,
        'robots': NOINDEX_ROBOTS if noindex else INDEX_ROBOTS,
        'noindex': bool(noindex),
        'og_type': og_type,
        'og_image': absolute_url(image_path),
        'site_name': SITE_NAME,
        'json_ld': list(json_ld or []),
    }


def website_json_ld():
    return {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': SITE_NAME,
        'url': absolute_url('/'),
        'description': DEFAULT_DESCRIPTION,
    }


def breadcrumb_json_ld(items):
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {
                '@type': 'ListItem',
                'position': index + 1,
                'name': item['name'],
                'item': absolute_url(item['path']),
            }
            for index, item in enumerate(items)
        ],
    }


def webpage_json_ld(name, description, path):
    return {
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        'name': name,
        'description': truncate_text(description),
        'url': absolute_url(path),
    }


def article_json_ld(note, path):
    return {
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': note['title'],
        'description': truncate_text(note.get('summary_markdown') or note['title']),
        'datePublished': note['published_at'],
        'dateModified': note.get('updated_at') or note['published_at'],
        'url': absolute_url(path),
    }


def xml_escape(value):
    return html.escape(str(value or ''), quote=True)
```

- [ ] **Step 4: Implement `templates/seo_head.html`**

Create `templates/seo_head.html`:

```jinja
{% macro seo_head(seo) -%}
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{{ seo.title }}</title>
    <meta name="description" content="{{ seo.description }}" />
    <meta name="robots" content="{{ seo.robots }}" />
    <link rel="canonical" href="{{ seo.canonical_url }}" />
    <meta property="og:site_name" content="{{ seo.site_name }}" />
    <meta property="og:type" content="{{ seo.og_type }}" />
    <meta property="og:title" content="{{ seo.title }}" />
    <meta property="og:description" content="{{ seo.description }}" />
    <meta property="og:url" content="{{ seo.canonical_url }}" />
    <meta property="og:image" content="{{ seo.og_image }}" />
    <meta name="twitter:card" content="summary" />
    <meta name="twitter:title" content="{{ seo.title }}" />
    <meta name="twitter:description" content="{{ seo.description }}" />
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='favicon.png') }}" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}" />
{% for item in seo.json_ld %}
    <script type="application/ld+json">{{ item|tojson }}</script>
{% endfor %}
{%- endmacro %}
```

- [ ] **Step 5: Run helper tests**

Run:

```powershell
python -m pytest tests/test_seo.py -q
```

Expected: PASS for the helper tests.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add seo.py templates/seo_head.html tests/test_seo.py
git commit -m "feat: add seo metadata helpers"
```

## Task 2: Template Metadata Integration And Noindex Policy

**Files:**
- Modify: `app_pages.py`
- Modify: `admin.py`
- Modify: `patch_notes.py`
- Modify: `templates/index.html`
- Modify: `templates/auth.html`
- Modify: `templates/account.html`
- Modify: `templates/admin.html`
- Modify: `templates/lineup_form.html`
- Modify: `templates/lineup_simulator.html`
- Modify: `templates/patch_notes.html`
- Modify: `templates/special_mechanics.html`
- Modify: `templates/artifact_guide.html`
- Modify: `templates/returning_equipment.html`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: Add failing metadata tests for public and private pages**

Append to `tests/test_ui_routes.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_public_pages_include_seo_metadata tests/test_ui_routes.py::test_private_pages_are_noindex tests/test_ui_routes.py::test_admin_page_is_noindex -q
```

Expected: FAIL because templates do not use the shared SEO macro yet.

- [ ] **Step 3: Pass SEO dictionaries from routes**

Modify `app_pages.py` imports:

```python
from seo import DEFAULT_DESCRIPTION, DEFAULT_TITLE, make_seo, website_json_ld
```

Update route contexts:

```python
seo = make_seo(
    title=DEFAULT_TITLE,
    description=DEFAULT_DESCRIPTION,
    path='/',
    json_ld=[website_json_ld()],
)
return tracked_template_response('index.html', 'home', simulator_enabled=simulator_enabled, notice=notice, seo=seo)
```

For private routes use `noindex=True`:

```python
return tracked_template_response(
    'auth.html',
    'auth',
    page_mode='login',
    seo=make_seo(title='登录 - 金铲铲阵容库', description='登录金铲铲阵容库账号。', path='/auth', noindex=True),
)
```

Use equivalent explicit metadata for `/auth/register`, `/lineup/new`, `/lineup/<id>/edit`, `/me`, and public tool pages.

Modify `admin.py`:

```python
from seo import make_seo
```

Then:

```python
return tracked_template_response(
    'admin.html',
    'admin',
    seo=make_seo(title='金铲铲阵容库后台', description='金铲铲阵容库后台管理页面。', path='/admin', noindex=True),
)
```

Modify `patch_notes.py` list page:

```python
from seo import make_seo
```

Then:

```python
return tracked_template_response(
    'patch_notes.html',
    'patch_notes',
    seo=make_seo(title='金铲铲更新公告 - 金铲铲阵容库', description='查看金铲铲之战版本更新重点、公告摘要和官方原文归档。', path='/patch-notes'),
)
```

- [ ] **Step 4: Replace repeated `<head>` blocks**

In each modified template, add:

```jinja
{% from "seo_head.html" import seo_head %}
```

Then replace the current head contents with:

```jinja
  <head>
{{ seo_head(seo) }}
  </head>
```

Keep any page-specific stylesheet or script tags outside the macro if the template has them. For `lineup_simulator.html`, preserve the existing simulator stylesheet link after `seo_head(seo)`:

```jinja
    <link rel="stylesheet" href="{{ url_for('static', filename='tools/lineup-simulator/style.css') }}" />
```

- [ ] **Step 5: Run metadata tests and existing UI route tests**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_public_pages_include_seo_metadata tests/test_ui_routes.py::test_private_pages_are_noindex tests/test_ui_routes.py::test_admin_page_is_noindex tests/test_pages_include_favicon_and_favicon_route_exists -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add app_pages.py admin.py patch_notes.py templates tests/test_ui_routes.py
git commit -m "feat: add seo metadata to page templates"
```

## Task 3: Crawlable Lineup Detail Page

**Files:**
- Modify: `app_pages.py`
- Modify: `templates/lineup_detail.html`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: Add failing tests for server-rendered lineup detail content**

Append to `tests/test_ui_routes.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_lineup_detail_page_renders_crawlable_lineup_content tests/test_ui_routes.py::test_lineup_detail_page_returns_404_for_hidden_lineup_to_public -q
```

Expected: first test FAIL because the template only renders loading text; second test FAIL because the page route currently returns the shell.

- [ ] **Step 3: Fetch lineup payload and SEO metadata in `app_pages.py`**

Add imports:

```python
from flask import abort
from auth import current_user
from lineup_read_service import build_lineup_detail_payload
from seo import breadcrumb_json_ld, code_preview, make_seo, season_label, truncate_text, webpage_json_ld
```

Update `lineup_detail_page`:

```python
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
```

- [ ] **Step 4: Render crawlable fallback in `templates/lineup_detail.html`**

Replace the loading-only root with:

```jinja
        <div id="lineupDetailApp" data-lineup-id="{{ lineup_id }}">
          <div class="detail-stack">
            <p class="section-kicker">Lineup Detail</p>
            <h1 class="detail-title">{{ lineup.name }}</h1>
            <p class="hero-description">由 {{ lineup.owner_nickname }} 上传 · {{ lineup_season_label }} · 评级 {{ lineup.rank_level }}</p>
            <p class="card-time">赞 {{ lineup.like_count }} · 复制 {{ lineup.copy_count }} · 更新于 {{ lineup.updated_at }}</p>
{% if lineup.owner_username %}
            <p class="card-time">作者主页：<a class="author-link" href="/author/{{ lineup.owner_username }}">{{ lineup.owner_nickname }}</a></p>
{% endif %}
            <pre class="code-preview">{{ lineup_code_preview }}</pre>
          </div>
        </div>
```

- [ ] **Step 5: Run lineup detail tests**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_lineup_detail_page_exists tests/test_ui_routes.py::test_lineup_detail_page_renders_crawlable_lineup_content tests/test_ui_routes.py::test_lineup_detail_page_returns_404_for_hidden_lineup_to_public -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add app_pages.py templates/lineup_detail.html tests/test_ui_routes.py
git commit -m "feat: render crawlable lineup detail pages"
```

## Task 4: Crawlable Author Profile Page

**Files:**
- Modify: `app_pages.py`
- Modify: `templates/author.html`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: Add failing tests for server-rendered author content**

Append to `tests/test_ui_routes.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_author_page_renders_crawlable_public_profile tests/test_ui_routes.py::test_author_page_with_no_public_lineups_is_noindex tests/test_ui_routes.py::test_author_page_returns_404_for_missing_author -q
```

Expected: FAIL because the author page currently renders only a loading shell and missing authors still get a shell.

- [ ] **Step 3: Fetch author payload and SEO metadata in `app_pages.py`**

Add imports:

```python
from lineup_account_service import build_author_profile_payload
from scoring import score_map
```

Update `author_page`:

```python
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
    seo = make_seo(title=title, description=description, path=f'/author/{username}', noindex=noindex)
    return tracked_template_response('author.html', 'author', username=username, author_payload=payload, seo=seo)
```

- [ ] **Step 4: Render crawlable author fallback in `templates/author.html`**

Change the header:

```jinja
        <h1>{{ author_payload.profile.nickname }}的金铲铲阵容</h1>
        <p class="hero-description">@{{ author_payload.profile.username }} · 公开阵容 {{ author_payload.summary.published_lineups }} 套 · 累计点赞 {{ author_payload.summary.total_likes }} · 累计复制 {{ author_payload.summary.total_copies }}</p>
```

Replace the loading-only root:

```jinja
        <div id="authorApp" data-username="{{ username }}">
          <section class="author-profile">
            <div>
              <p class="section-kicker">Creator</p>
              <h2>{{ author_payload.profile.nickname }}</h2>
              <p class="account-row-meta">@{{ author_payload.profile.username }} · 入驻时间：{{ author_payload.profile.created_at }}</p>
            </div>
          </section>
          <section class="author-lineups">
            <h3>公开阵容</h3>
{% if author_payload.lineups %}
            <div class="lineup-list">
{% for lineup in author_payload.lineups[:6] %}
              <article class="lineup-card">
                <h3 class="lineup-title"><a href="/lineup/{{ lineup.id }}">{{ lineup.name }} · {{ lineup.rank_level }}</a></h3>
                <p class="card-time">赞 {{ lineup.like_count }} · 复制 {{ lineup.copy_count }} · 更新于 {{ lineup.updated_at }}</p>
                <pre class="code-preview">{{ lineup.code }}</pre>
              </article>
{% endfor %}
            </div>
{% else %}
            <div class="empty-state">这个作者暂时还没有公开阵容。</div>
{% endif %}
          </section>
        </div>
```

- [ ] **Step 5: Run author tests**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_author_page_renders_crawlable_public_profile tests/test_ui_routes.py::test_author_page_with_no_public_lineups_is_noindex tests/test_ui_routes.py::test_author_page_returns_404_for_missing_author tests/test_author_js_contains_copy_view_like_favorite_and_report_actions -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Run:

```powershell
git add app_pages.py templates/author.html tests/test_ui_routes.py
git commit -m "feat: render crawlable author pages"
```

## Task 5: Crawlable Patch Note Detail Page

**Files:**
- Modify: `patch_notes.py`
- Modify: `templates/patch_note_detail.html`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: Add failing tests for server-rendered patch note detail content**

Append to `tests/test_ui_routes.py`:

```python
def test_patch_note_detail_page_renders_crawlable_published_content(client):
    from test_admin import login_admin

    headers = login_admin(client)
    created = client.post('/api/admin/patch-notes', json={
        'title': 'S17 平衡调整',
        'version': 'S17.1',
        'source_url': 'https://example.com/source',
        'summary_markdown': '## 英雄调整\\n- [buff] 卡莎 攻速 0.8 => 0.85',
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_patch_note_detail_page_renders_crawlable_published_content tests/test_ui_routes.py::test_patch_note_detail_page_returns_404_for_draft -q
```

Expected: FAIL because the detail template only renders a loading shell and draft pages still get a shell.

- [ ] **Step 3: Fetch patch note payload and SEO metadata in `patch_notes.py`**

Add imports:

```python
from flask import abort
from seo import article_json_ld, make_seo, truncate_text
```

Update `patch_note_detail_page`:

```python
    payload, service_error, status_code = get_public_patch_note(patch_note_id)
    if service_error:
        abort(status_code)
    title = f"{payload['title']} - 金铲铲更新公告"
    description = truncate_text(payload.get('summary_markdown') or payload['title'])
    path = f'/patch-notes/{patch_note_id}'
    seo = make_seo(
        title=title,
        description=description,
        path=path,
        og_type='article',
        json_ld=[article_json_ld(payload, path)],
    )
    return tracked_template_response(
        'patch_note_detail.html',
        'patch_note_detail',
        patch_note_id=patch_note_id,
        patch_note=payload,
        seo=seo,
    )
```

- [ ] **Step 4: Render crawlable patch note fallback**

Replace the loading-only root in `templates/patch_note_detail.html`:

```jinja
        <div id="patchNoteDetailApp" data-patch-note-id="{{ patch_note_id }}">
          <article class="patch-note-detail">
            <p class="section-kicker">Patch Notes</p>
            <h1>{{ patch_note.title }}</h1>
            <p class="hero-description">{{ patch_note.version or '版本公告' }} · {{ patch_note.published_at }}</p>
            <div class="patch-note-body">
{% for item in patch_note.summary_items %}
{% if item.type == 'section' %}
              <h2>{{ item.title }}</h2>
{% elif item.type == 'change' %}
              <p><span class="change-tag change-tag-{{ item.kind }}">{{ item.label }}</span> {{ item.text }}</p>
{% else %}
              <p>{{ item.text }}</p>
{% endif %}
{% endfor %}
            </div>
{% if patch_note.source_url %}
            <p><a class="primary-link" href="{{ patch_note.source_url }}" target="_blank" rel="noopener">查看官方原文</a></p>
{% endif %}
          </article>
        </div>
```

- [ ] **Step 5: Run patch note tests**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_patch_note_pages_exist_and_homepage_links_to_patch_notes tests/test_ui_routes.py::test_patch_note_detail_page_renders_crawlable_published_content tests/test_ui_routes.py::test_patch_note_detail_page_returns_404_for_draft tests/test_patch_note_styles_exist -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

Run:

```powershell
git add patch_notes.py templates/patch_note_detail.html tests/test_ui_routes.py
git commit -m "feat: render crawlable patch note pages"
```

## Task 6: Robots.txt And Sitemap.xml

**Files:**
- Modify: `seo.py`
- Modify: `app_pages.py`
- Modify: `tests/test_seo.py`

- [ ] **Step 1: Add failing tests for robots and sitemap routes**

Append to `tests/test_seo.py`:

```python
def test_robots_txt_lists_disallowed_private_surfaces_and_sitemap(client):
    response = client.get('/robots.txt')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == 'text/plain'
    assert 'User-agent: *' in body
    assert 'Allow: /' in body
    assert 'Disallow: /api/' in body
    assert 'Disallow: /admin' in body
    assert 'Disallow: /auth' in body
    assert 'Disallow: /me' in body
    assert 'Disallow: /lineup/new' in body
    assert 'Sitemap: http://localhost/sitemap.xml' in body


def test_sitemap_includes_public_urls_and_excludes_hidden_and_draft(client):
    from test_admin import login_admin
    from test_auth import register_user
    from test_lineup_permissions import auth_headers, create_lineup

    register_user(client, username='mapauthor', email='mapauthor@example.com', nickname='地图作者')
    public_lineup = create_lineup(client, name='地图公开阵容', code='#MAPSEO1').get_json()
    hidden_lineup = create_lineup(client, name='地图隐藏阵容', code='#MAPSEO2', status='hidden').get_json()
    client.post('/api/logout')
    headers = login_admin(client)
    published_note = client.post('/api/admin/patch-notes', json={
        'title': '地图公告',
        'version': 'M1',
        'source_url': '',
        'summary_markdown': '地图公告内容',
        'original_text': '',
        'status': 'published',
        'published_at': '2026-07-04',
    }, headers=headers).get_json()
    draft_note = client.post('/api/admin/patch-notes', json={
        'title': '地图草稿',
        'version': 'M2',
        'source_url': '',
        'summary_markdown': '地图草稿内容',
        'original_text': '',
        'status': 'draft',
        'published_at': '2026-07-04',
    }, headers=headers).get_json()

    response = client.get('/sitemap.xml')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype in {'application/xml', 'text/xml'}
    assert '<loc>http://localhost/</loc>' in body
    assert f'<loc>http://localhost/lineup/{public_lineup["id"]}</loc>' in body
    assert f'<loc>http://localhost/lineup/{hidden_lineup["id"]}</loc>' not in body
    assert '<loc>http://localhost/author/mapauthor</loc>' in body
    assert f'<loc>http://localhost/patch-notes/{published_note["id"]}</loc>' in body
    assert f'<loc>http://localhost/patch-notes/{draft_note["id"]}</loc>' not in body
    assert '<loc>http://localhost/admin</loc>' not in body
    assert '<loc>http://localhost/api/' not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_seo.py::test_robots_txt_lists_disallowed_private_surfaces_and_sitemap tests/test_seo.py::test_sitemap_includes_public_urls_and_excludes_hidden_and_draft -q
```

Expected: FAIL because routes do not exist.

- [ ] **Step 3: Add robots and sitemap builders in `seo.py`**

Append to `seo.py`:

```python
def robots_txt():
    return '\\n'.join([
        'User-agent: *',
        'Allow: /',
        'Disallow: /api/',
        'Disallow: /admin',
        'Disallow: /auth',
        'Disallow: /me',
        'Disallow: /lineup/new',
        'Disallow: /lineup/*/edit',
        f'Sitemap: {absolute_url("/sitemap.xml")}',
        '',
    ])


def sitemap_xml(entries):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for entry in entries:
        lines.append('  <url>')
        lines.append(f'    <loc>{xml_escape(entry["loc"])}</loc>')
        if entry.get('lastmod'):
            lines.append(f'    <lastmod>{xml_escape(str(entry["lastmod"])[:10])}</lastmod>')
        lines.append('  </url>')
    lines.append('</urlset>')
    return '\\n'.join(lines) + '\\n'
```

- [ ] **Step 4: Add route-level sitemap query in `app_pages.py`**

Add imports:

```python
from flask import Response
from seo import absolute_url, robots_txt, sitemap_xml
```

Add helpers near `register_page_routes`:

```python
def _sitemap_entries():
    db = get_db()
    entries = [
        {'loc': absolute_url('/'), 'lastmod': None},
        {'loc': absolute_url('/patch-notes'), 'lastmod': None},
        {'loc': absolute_url('/tools/special-mechanics'), 'lastmod': None},
        {'loc': absolute_url('/tools/artifact-guide'), 'lastmod': None},
        {'loc': absolute_url('/tools/returning-equipment'), 'lastmod': None},
    ]
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
```

Add routes inside `register_page_routes(app)`:

```python
    @app.get('/robots.txt')
    def robots():
        return Response(robots_txt(), mimetype='text/plain')

    @app.get('/sitemap.xml')
    def sitemap():
        return Response(sitemap_xml(_sitemap_entries()), mimetype='application/xml')
```

- [ ] **Step 5: Run robots and sitemap tests**

Run:

```powershell
python -m pytest tests/test_seo.py::test_robots_txt_lists_disallowed_private_surfaces_and_sitemap tests/test_seo.py::test_sitemap_includes_public_urls_and_excludes_hidden_and_draft -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 6**

Run:

```powershell
git add seo.py app_pages.py tests/test_seo.py
git commit -m "feat: add robots and sitemap routes"
```

## Task 7: Full Regression And Documentation Check

**Files:**
- Modify: `AGENTS.md` if SEO behavior changes repository guidance
- Modify: `docs/index.md` or `docs/api.md` only if existing docs already cover public routes and need SEO route references

- [ ] **Step 1: Check whether repository guidance needs an SEO note**

Read `AGENTS.md`. If it does not mention SEO metadata and crawlable public pages, add this paragraph under Web UI or route guidance:

```markdown
Public pages should pass explicit SEO metadata through `seo.py` and `templates/seo_head.html`. Keep login, account, admin, editor, API, hidden, and draft surfaces noindex or out of `sitemap.xml`; public detail pages should render useful first-load HTML before JavaScript hydration.
```

- [ ] **Step 2: Run focused SEO/UI tests**

Run:

```powershell
python -m pytest tests/test_seo.py tests/test_ui_routes.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run:

```powershell
python -m pytest -q
```

Expected: PASS with all tests passing.

- [ ] **Step 4: Manually inspect generated HTML from test client**

Run:

```powershell
python - <<'PY'
from app import create_app

app = create_app({'TESTING': True})
client = app.test_client()
for path in ['/', '/robots.txt', '/sitemap.xml']:
    response = client.get(path)
    print(path, response.status_code, response.mimetype)
    print(response.get_data(as_text=True)[:240].replace('\\n', ' '))
PY
```

Expected: `/` returns `200 text/html`, `/robots.txt` returns `200 text/plain`, `/sitemap.xml` returns `200 application/xml`.

- [ ] **Step 5: Commit documentation changes if any were made**

If `AGENTS.md` or docs changed, run:

```powershell
git add AGENTS.md docs
git commit -m "docs: document seo route expectations"
```

If no documentation files changed, record in the final handoff that no docs update was needed beyond the committed design and plan.

- [ ] **Step 6: Final status check**

Run:

```powershell
git status --short --branch
git log --oneline -5
```

Expected: worktree is clean, and the last commits are the SEO implementation commits.
