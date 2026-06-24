# Artifact Guide Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new S8 homepage menu entry and a dedicated artifact pairing guide page that shows hero-and-artifact cards with local images and mobile-friendly layout.

**Architecture:** Keep the feature static and page-local, following the existing S8 reference pages. Add one new route and template, one page-specific JS file for card data/rendering, one page-specific CSS file for layout, and copy the required source images into the Web repo so production only serves repository-local assets.

**Tech Stack:** Flask, Jinja2, vanilla JavaScript, CSS Grid/Flexbox, pytest

---

### Task 1: Add the failing route and asset tests

**Files:**
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: Write the failing test**

```python
def test_artifact_guide_page_exists_and_index_links_to_it(client):
    index_html = client.get('/').get_data(as_text=True)
    assert 'href="/tools/artifact-guide"' in index_html
    assert '神器搭配指南' in index_html

    response = client.get('/tools/artifact-guide')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'S8·怪兽入侵 神器搭配指南' in html
    assert 'artifacts-guide.js' in html
    assert 'artifacts-guide.css' in html


def test_artifact_guide_assets_define_cards_and_images():
    with open('static/artifacts-guide.js', 'r', encoding='utf-8') as file:
        js = file.read()
    with open('static/artifacts-guide.css', 'r', encoding='utf-8') as file:
        css = file.read()

    assert 'const ARTIFACT_GUIDE_CARDS = [' in js
    assert '英雄图片' in js
    assert '神器图片' in js
    assert '搭配评价' in js
    assert 'artifact-guide-card' in js
    assert 'artifact-guide-hero-image' in js
    assert 'artifact-guide-artifact-image' in js
    assert '.artifact-guide-card {' in css
    assert '.artifact-guide-image-grid {' in css
    assert '.artifact-guide-hero-image {' in css
    assert '.artifact-guide-artifact-image {' in css
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest -q tests/test_ui_routes.py -k "artifact_guide"`
Expected: FAIL because the new route and assets do not exist yet.

- [ ] **Step 3: Stop here**

Do not implement production code until the test fails for the expected missing feature.

### Task 2: Add the homepage entry and page route/template

**Files:**
- Modify: `templates/index.html`
- Modify: `app_pages.py`
- Create: `templates/artifact_guide.html`

- [ ] **Step 1: Write the minimal implementation**

```html
<!-- templates/index.html -->
<a class="returning-info-menu-item" href="/tools/artifact-guide" role="menuitem">
  <span>神器搭配指南</span>
  <small>英雄与神器的实战搭配</small>
</a>
```

```python
# app_pages.py
@app.get('/tools/artifact-guide')
def artifact_guide_page():
    return tracked_template_response('artifact_guide.html', 'artifact_guide')
```

```html
<!-- templates/artifact_guide.html -->
<!doctype html>
{% from "theme_toggle.html" import theme_toggle %}
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>S8·怪兽入侵 神器搭配指南</title>
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='favicon.png') }}" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;700;800&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}" />
    <link rel="stylesheet" href="{{ url_for('static', filename='artifacts-guide.css') }}" />
  </head>
  <body>
    <div class="page-shell artifacts-guide-page">
      <nav class="nav-bar artifacts-guide-nav" aria-label="页面工具">
        <a class="brand-mark brand-link" href="/" aria-label="返回首页">阵</a>
        <div class="nav-actions">
          <a class="ghost-link nav-tool-link" href="/">返回首页</a>
          {{ theme_toggle("nav-icon-button") }}
        </div>
      </nav>
      <header class="artifacts-guide-hero">
        <div class="artifacts-guide-hero-panel">
          <p class="eyebrow">S8 Artifact Guide</p>
          <h1>S8·怪兽入侵 神器搭配指南</h1>
        </div>
      </header>
      <main class="artifact-guide-grid" id="artifactGuideGrid" aria-live="polite"></main>
    </div>
    <script src="{{ url_for('static', filename='theme-toggle.js') }}" defer></script>
    <script src="{{ url_for('static', filename='artifacts-guide.js') }}" defer></script>
  </body>
</html>
```

- [ ] **Step 2: Run the targeted test and confirm it still fails on missing assets**

Run: `python -m pytest -q tests/test_ui_routes.py -k "artifact_guide_page_exists_and_index_links_to_it"`
Expected: FAIL until Task 3 and Task 4 are complete.

- [ ] **Step 3: Keep the page structure static and page-local**

Do not add API routes or shared data loaders. This page should remain a self-contained static reference page like returning equipment.

### Task 3: Add the artifact guide data/rendering JS

**Files:**
- Create: `static/artifacts-guide.js`

- [ ] **Step 1: Implement the card data and rendering**

```javascript
const ARTIFACT_GUIDE_CARDS = [
  {
    hero: '厄加特',
    heroImage: '/static/artifacts-guide/heroes/5127_厄加特_s8_urgot.png',
    artifact: '秘银',
    artifactImage: '/static/artifacts-guide/artifacts/6072_密银黎明_silvermere_dawn.jpg',
    evaluation: '普攻持续给对面挂上0.8秒控制，一开大招全员集体被推晕，堪称无限连环眩晕折磨流',
  },
  {
    hero: '努努',
    heroImage: '/static/artifacts-guide/heroes/5121_努努和威朗普_s8_nunu.png',
    artifact: '探索者护臂',
    artifactImage: '/static/artifacts-guide/artifacts/6084_探索者的护臂_seeker_s_armguard.jpg',
    evaluation: '搭配专属强化【当面推球】大幅提升球体游走效率，沿途敌人全被眩晕持续掉血，击杀后靠护臂无限叠双抗法强',
  }
];

const grid = document.querySelector('#artifactGuideGrid');
grid.replaceChildren(...ARTIFACT_GUIDE_CARDS.map(createCard));
```

- [ ] **Step 2: Include all cards from `神器搭配.md`**

Populate the full table in the same order as the source document. Each card must include a hero image, an artifact image, the hero name, the artifact name, and the pairing evaluation text.

- [ ] **Step 3: Keep image paths repository-local**

Use only `/static/artifacts-guide/...` paths in the page. Do not reference the top-level `图片/` workspace from templates or JS.

- [ ] **Step 4: Run the asset test**

Run: `python -m pytest -q tests/test_ui_routes.py -k "artifact_guide_assets"`
Expected: PASS once the card data and image references exist.

### Task 4: Add artifact guide CSS for card layout and image sizing

**Files:**
- Create: `static/artifacts-guide.css`

- [ ] **Step 1: Write the page CSS**

```css
.artifacts-guide-page {
  max-width: 1120px;
}

.artifact-guide-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.artifact-guide-card {
  display: grid;
  gap: 14px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: var(--surface);
  padding: 16px;
  box-shadow: 0 16px 44px rgba(55, 45, 31, 0.08);
}

.artifact-guide-image-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.artifact-guide-image-wrap {
  display: grid;
  aspect-ratio: 1 / 1;
  place-items: center;
  border-radius: 16px;
  overflow: hidden;
  background: color-mix(in srgb, var(--accent-soft) 54%, transparent);
}

.artifact-guide-hero-image,
.artifact-guide-artifact-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
```

- [ ] **Step 2: Add mobile breakpoints**

```css
@media (max-width: 860px) {
  .artifact-guide-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .artifact-guide-card {
    padding: 12px;
  }
  .artifact-guide-image-grid {
    gap: 8px;
  }
}
```

- [ ] **Step 3: Verify the layout strings**

Run: `python -m pytest -q tests/test_ui_routes.py -k "artifact_guide_assets"`
Expected: PASS.

### Task 5: Copy images into the Web repo and wire the paths

**Files:**
- Create: `static/artifacts-guide/heroes/*`
- Create: `static/artifacts-guide/artifacts/*`
- Modify: `static/artifacts-guide.js`
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: Copy the required hero and artifact images**

Copy the source files from the top-level `图片/S8-怪兽入侵-返厂/...` directories into:

```text
static/artifacts-guide/heroes/
static/artifacts-guide/artifacts/
```

Use the original filenames so the mapping stays obvious and test assertions can reference exact paths.

- [ ] **Step 2: Point the JS data at the copied files**

Update each `heroImage` and `artifactImage` path to the new `/static/artifacts-guide/...` location.

- [ ] **Step 3: Add file-serving assertions**

```python
assert client.get('/static/artifacts-guide/heroes/5127_厄加特_s8_urgot.png').status_code == 200
assert client.get('/static/artifacts-guide/artifacts/6072_密银黎明_silvermere_dawn.jpg').status_code == 200
```

- [ ] **Step 4: Run the page test**

Run: `python -m pytest -q tests/test_ui_routes.py -k "artifact_guide"`
Expected: PASS.

### Task 6: Update repository guidance

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Add a short note about the new S8 artifact guide page**

```md
The `/tools/artifact-guide` page is a static S8 reference page. It shows hero-and-artifact pairing cards sourced from `神器搭配.md`, and all images are copied into the Web repo under `static/artifacts-guide/` so production deployments do not depend on the top-level `图片/` workspace.
```

- [ ] **Step 2: Keep the note concise and specific**

Do not expand the Web instructions beyond this page-specific rule.

### Task 7: Final verification and branch cleanup

**Files:**
- None

- [ ] **Step 1: Run the focused test file**

Run: `python -m pytest -q tests/test_ui_routes.py`
Expected: All tests pass.

- [ ] **Step 2: Check git status**

Run: `git status --short`
Expected: Only the intended feature files are modified or added.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md app_pages.py static/artifacts-guide* templates/artifact_guide.html templates/index.html tests/test_ui_routes.py
git commit -m "feat: add artifact guide page"
```

