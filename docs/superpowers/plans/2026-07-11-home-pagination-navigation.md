# Homepage Pagination Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace homepage morphing pagination dots with dynamic numbered navigation, ellipses, themed direction controls, responsive compaction, and successful-load scrolling.

**Architecture:** Keep pagination inside the existing Flask/Jinja and vanilla JavaScript frontend. `static/app.js` owns page-token calculation, semantic DOM construction, click state, and scrolling; `static/styles.css` owns the shadcn-inspired visual treatment and responsive labels.

**Tech Stack:** Flask/Jinja, vanilla JavaScript, CSS, pytest, Node syntax checks, browser responsive testing.

---

## File Map

- Modify `static/app.js`: numbered pagination token algorithm, semantic renderer, inline Lucide-style icons, compact breakpoint handling, and post-render scrolling.
- Modify `static/styles.css`: bordered number buttons, active theme state, hard shadow, ellipsis, responsive direction labels, focus states, and reduced motion.
- Modify `templates/index.html`: navigation semantics and list heading scroll target.
- Modify `tests/test_ui_routes.py`: pagination structure, algorithm, style, scrolling, and old-dot removal contracts.
- Modify `AGENTS.md`: document shared dynamic pagination behavior.

### Task 1: Dynamic Page Tokens And Semantic Markup

**Files:**
- Modify: `tests/test_ui_routes.py`
- Modify: `templates/index.html`
- Modify: `static/app.js`

- [ ] **Step 1: Replace the old pagination test with failing numbered-navigation tests**

Replace `test_home_pagination_uses_morphing_dots` in `tests/test_ui_routes.py` with:

```python
def test_home_pagination_uses_numbered_navigation(client):
    html = client.get('/').get_data(as_text=True)
    js = open('static/app.js', encoding='utf-8').read()

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
    js = open('static/app.js', encoding='utf-8').read()

    assert 'const desktopLimit = 7' in js
    assert 'const compactLimit = 5' in js
    assert "globalThis.matchMedia('(max-width: 520px)')" in js
    assert 'currentPage <= 4' in js
    assert 'currentPage >= totalPages - 3' in js
    assert 'currentPage - 1' in js
    assert 'currentPage + 1' in js
```

- [ ] **Step 2: Run the tests and verify they fail for the old dot implementation**

Run: `python -m pytest tests/test_ui_routes.py::test_home_pagination_uses_numbered_navigation tests/test_ui_routes.py::test_home_pagination_has_desktop_and_compact_windows -q`

Expected: FAIL because the template lacks navigation semantics and the JavaScript still builds morphing dots.

- [ ] **Step 3: Add navigation semantics to the template**

Change the pagination mount point in `templates/index.html` to:

```html
<nav class="pagination" id="pagination" aria-label="分页导航"></nav>
```

Add `id="listHeading"` to the existing `.list-heading` element so successful page changes have a stable scroll target.

- [ ] **Step 4: Implement page token generation**

In `static/app.js`, replace `buildPaginationDots()` with:

```javascript
function paginationPage(page) {
  return { type: 'page', page };
}

function paginationEllipsis(key) {
  return { type: 'ellipsis', key };
}

function buildPaginationItems(currentPage, totalPages, compact = false) {
  const desktopLimit = 7;
  const compactLimit = 5;
  const visibleLimit = compact ? compactLimit : desktopLimit;
  if (totalPages <= visibleLimit) {
    return Array.from({ length: totalPages }, (_, index) => paginationPage(index + 1));
  }
  if (compact) {
    if (currentPage <= 3) {
      return [paginationPage(1), paginationPage(2), paginationPage(3), paginationEllipsis('end'), paginationPage(totalPages)];
    }
    if (currentPage >= totalPages - 2) {
      return [paginationPage(1), paginationEllipsis('start'), paginationPage(totalPages - 2), paginationPage(totalPages - 1), paginationPage(totalPages)];
    }
    return [paginationPage(1), paginationEllipsis('start'), paginationPage(currentPage), paginationEllipsis('end'), paginationPage(totalPages)];
  }
  if (currentPage <= 4) {
    return [1, 2, 3, 4, 5].map(paginationPage).concat(paginationEllipsis('end'), paginationPage(totalPages));
  }
  if (currentPage >= totalPages - 3) {
    return [paginationPage(1), paginationEllipsis('start')].concat(
      [totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages].map(paginationPage)
    );
  }
  return [
    paginationPage(1),
    paginationEllipsis('start'),
    paginationPage(currentPage - 1),
    paginationPage(currentPage),
    paginationPage(currentPage + 1),
    paginationEllipsis('end'),
    paginationPage(totalPages),
  ];
}
```

- [ ] **Step 5: Render numbered buttons and ellipses**

Add helpers for a chevron icon and three-dot icon using DOM-created spans with CSS classes. Rewrite `renderPagination()` to:

- Hide when `state.totalPages <= 1`.
- Render a `.pagination-content` list.
- Render previous and next controls with `.pagination-direction`, icon spans, and `.pagination-direction-label` text.
- Call `buildPaginationItems(state.page, state.totalPages, globalThis.matchMedia('(max-width: 520px)').matches)`.
- Render page tokens as `.pagination-page` buttons with visible page numbers.
- Set `aria-label="前往第 N 页"` on page buttons.
- Set `aria-current="page"` and disable the active page.
- Render ellipses as non-interactive `.pagination-ellipsis` spans with `aria-hidden="true"` and a nested `.sr-only` explanation.

- [ ] **Step 6: Run focused tests and JavaScript syntax checks**

Run: `python -m pytest tests/test_ui_routes.py::test_home_pagination_uses_numbered_navigation tests/test_ui_routes.py::test_home_pagination_has_desktop_and_compact_windows -q`

Expected: PASS.

Run: `node --check static/app.js`

Expected: exit code 0.

- [ ] **Step 7: Commit dynamic pagination**

```powershell
git add tests/test_ui_routes.py templates/index.html static/app.js
git commit -m "feat: add numbered homepage pagination"
```

### Task 2: Successful-Load Scrolling And Responsive Re-rendering

**Files:**
- Modify: `tests/test_ui_routes.py`
- Modify: `static/app.js`

- [ ] **Step 1: Write failing interaction tests**

Add to `tests/test_ui_routes.py`:

```python
def test_home_pagination_scrolls_after_successful_page_load():
    js = open('static/app.js', encoding='utf-8').read()

    assert 'pendingPaginationScroll' in js
    assert 'function scrollToLineupList()' in js
    assert "behavior: reduceMotion.matches ? 'auto' : 'smooth'" in js
    assert 'elements.listHeading.scrollIntoView(' in js
    assert 'completePaginationNavigation()' in js
    assert 'pendingPaginationScroll = true' in js


def test_home_pagination_reacts_to_mobile_breakpoint_changes():
    js = open('static/app.js', encoding='utf-8').read()

    assert 'paginationCompactQuery' in js
    assert "paginationCompactQuery.addEventListener('change'" in js
    assert 'renderPagination()' in js
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/test_ui_routes.py::test_home_pagination_scrolls_after_successful_page_load tests/test_ui_routes.py::test_home_pagination_reacts_to_mobile_breakpoint_changes -q`

Expected: FAIL because scrolling and breakpoint listeners are missing.

- [ ] **Step 3: Track pagination-originated requests**

Add `listHeading` to `elements`, create `const paginationCompactQuery = globalThis.matchMedia('(max-width: 520px)')`, and add `let pendingPaginationScroll = false`.

In the pagination click handler, set `pendingPaginationScroll = true` immediately before `loadCurrentView()`.

Add:

```javascript
function scrollToLineupList() {
  const reduceMotion = globalThis.matchMedia('(prefers-reduced-motion: reduce)');
  elements.listHeading?.scrollIntoView({
    behavior: reduceMotion.matches ? 'auto' : 'smooth',
    block: 'start',
  });
}

function completePaginationNavigation() {
  if (!pendingPaginationScroll) return;
  pendingPaginationScroll = false;
  scrollToLineupList();
}
```

- [ ] **Step 4: Complete scrolling only after successful renders**

Call `completePaginationNavigation()` after `renderPagination()` in successful `loadLineups()` and `loadLiveComps()` paths. Do not call it from catch or abort paths. Reset `pendingPaginationScroll = false` when tabs, seasons, or search reset the page for reasons other than pagination.

- [ ] **Step 5: Re-render at the compact breakpoint**

Use:

```javascript
paginationCompactQuery.addEventListener('change', () => renderPagination());
```

Pass `paginationCompactQuery.matches` to `buildPaginationItems()` instead of creating a new media query in every render.

- [ ] **Step 6: Run focused tests and syntax checks**

Run: `python -m pytest tests/test_ui_routes.py::test_home_pagination_scrolls_after_successful_page_load tests/test_ui_routes.py::test_home_pagination_reacts_to_mobile_breakpoint_changes -q`

Expected: PASS.

Run: `node --check static/app.js`

Expected: exit code 0.

- [ ] **Step 7: Commit interaction behavior**

```powershell
git add tests/test_ui_routes.py static/app.js
git commit -m "feat: scroll after homepage pagination"
```

### Task 3: Theme Styling, Documentation, And Verification

**Files:**
- Modify: `tests/test_ui_routes.py`
- Modify: `static/styles.css`
- Modify: `AGENTS.md`

- [ ] **Step 1: Write failing style tests**

Add to `tests/test_ui_routes.py`:

```python
def test_home_numbered_pagination_styles_are_present():
    css = open('static/styles.css', encoding='utf-8').read()

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
```

- [ ] **Step 2: Run the style test and verify it fails**

Run: `python -m pytest tests/test_ui_routes.py::test_home_numbered_pagination_styles_are_present -q`

Expected: FAIL because numbered pagination styles are absent and old dot styles remain.

- [ ] **Step 3: Replace pagination CSS**

Remove `.pagination-dots`, `.pagination-dot`, `.pagination-ripple`, and `@keyframes pagination-ripple` rules. Implement:

- `.pagination-content` as a centered flex row with a stable gap.
- `.pagination-direction` and `.pagination-page` as 40-pixel minimum controls with existing radius tokens.
- Default background `var(--surface-solid)`, text `var(--text)`, border `var(--line)`.
- A `3px 3px 0` hard shadow tinted through the existing line/accent palette.
- Hover translation and shadow removal.
- `.pagination-page.is-active` using `var(--accent)` and light text.
- Disabled, focus-visible, ellipsis, and inline icon rules.
- A `max-width: 520px` rule that hides `.pagination-direction-label`, preserves icon-only 40-pixel controls, and reduces gaps.
- Reduced-motion overrides for transforms and scrolling-related transitions.

- [ ] **Step 4: Update repository guidance**

Add to `AGENTS.md`:

```markdown
Homepage regular lineups and live comps share numbered pagination rendered by `static/app.js`. Page counts come from each API's dynamic `total_pages`; long ranges keep the first and last page with responsive ellipses. Successful pagination requests scroll to `#listHeading`, while failed or aborted requests do not. Keep mobile pagination on one row with icon-only direction controls.
```

- [ ] **Step 5: Run focused and complete verification**

Run: `python -m pytest tests/test_ui_routes.py -q`

Expected: PASS.

Run: `node --check static/app.js`

Expected: exit code 0.

Run: `python -m pytest -q`

Expected: all tests pass, with at least the 416-test baseline plus the new tests.

- [ ] **Step 6: Browser verification**

Start `python run_server.py` on an available local port and verify:

- One-page results hide pagination.
- Small totals show all page numbers.
- First, middle, and final pages produce correct ellipses.
- Regular lineups and live comps both navigate correctly.
- Desktop direction labels and mobile icon-only controls.
- Light and dark theme contrast.
- Focus-visible and disabled states.
- Successful loading scrolls to the list heading.
- Failed or aborted requests do not scroll.
- Reduced motion uses immediate scrolling and no movement-based hover transitions.
- No overlap or horizontal overflow at 375, 520, 860, and 1440 pixel widths.

- [ ] **Step 7: Check the final diff and commit**

Run: `git diff --check`

Expected: no output.

```powershell
git add tests/test_ui_routes.py static/styles.css AGENTS.md
git commit -m "feat: style homepage numbered pagination"
```
