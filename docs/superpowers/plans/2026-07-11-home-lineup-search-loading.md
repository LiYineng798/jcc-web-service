# Homepage Lineup Search And Loading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dissolve-style clear interaction to homepage lineup search and layout-stable skeleton/reveal loading for uncached regular-lineup requests.

**Architecture:** A new `static/home-transitions.js` module owns visual transition state and exposes a small `window.JccHomeTransitions` API. Existing `static/app.js` keeps request, cache, and lineup business state, invoking the module for search synchronization and loading lifecycle changes.

**Tech Stack:** Flask/Jinja, vanilla JavaScript, CSS, pytest, browser responsive testing.

---

## File Map

- Create `static/home-transitions.js`: search mirror/clear animation and lineup skeleton/reveal helpers.
- Modify `templates/index.html`: search transition layers and transition script loading.
- Modify `static/app.js`: initialize transitions, clear search immediately, expose cache-hit information, and coordinate skeleton lifecycle.
- Modify `static/styles.css`: clear animation resting states, skeleton geometry, reveal transitions, dark mode, mobile, and reduced motion.
- Modify `tests/test_ui_routes.py`: focused structural and integration contract tests.
- Modify `AGENTS.md`: document homepage search and regular-lineup loading behavior.

### Task 1: Homepage Transition Markup And Script Contract

**Files:**
- Modify: `tests/test_ui_routes.py`
- Modify: `templates/index.html`
- Create: `static/home-transitions.js`

- [ ] **Step 1: Write the failing homepage markup test**

Add to `tests/test_ui_routes.py`:

```python
def test_homepage_search_has_dissolve_clear_layers(client):
    html = client.get('/').get_data(as_text=True)

    assert 'class="search-field t-clear"' in html
    assert 'id="searchInput"' in html
    assert 'class="t-clear-mirror"' in html
    assert 'class="t-clear-placeholder"' in html
    assert 'class="t-clear-glow"' in html
    assert 'id="searchClearButton"' in html
    assert 'aria-label="清除搜索"' in html
    assert "filename='home-transitions.js'" in html
    assert html.index("filename='home-transitions.js'") < html.index("filename='app.js'")
```

- [ ] **Step 2: Run the test and verify it fails for missing markup**

Run: `python -m pytest tests/test_ui_routes.py::test_homepage_search_has_dissolve_clear_layers -q`

Expected: FAIL because the `.t-clear` layers and script are absent.

- [ ] **Step 3: Add the transition-ready search structure**

Replace the existing search label in `templates/index.html` with:

```html
<label class="search-field t-clear" id="searchClear" data-placeholder="搜索阵容名称，例如：九五、卡莎、斗士">
  <span class="sr-only">搜索阵容名称</span>
  <input id="searchInput" type="search" autocomplete="off" placeholder="" />
  <span class="t-clear-mirror" id="searchClearMirror" aria-hidden="true"></span>
  <span class="t-clear-placeholder" id="searchClearPlaceholder" aria-hidden="true">搜索阵容名称，例如：九五、卡莎、斗士</span>
  <span class="t-clear-glow" id="searchClearGlow" aria-hidden="true"></span>
  <button class="t-clear-btn" id="searchClearButton" type="button" aria-label="清除搜索" title="清除搜索">
    <span aria-hidden="true">&times;</span>
  </button>
</label>
```

Load `home-transitions.js` immediately before `app.js` with `defer`.

Create `static/home-transitions.js` with the module shell:

```javascript
(function initHomeTransitions(global) {
  'use strict';

  global.JccHomeTransitions = {
    createSearchClear() {},
    createLineupLoader() {},
  };
})(window);
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `python -m pytest tests/test_ui_routes.py::test_homepage_search_has_dissolve_clear_layers -q`

Expected: PASS.

- [ ] **Step 5: Commit the markup contract**

```powershell
git add tests/test_ui_routes.py templates/index.html static/home-transitions.js
git commit -m "feat: add homepage transition markup"
```

### Task 2: Search Clear Dissolve Module

**Files:**
- Modify: `tests/test_ui_routes.py`
- Modify: `static/home-transitions.js`
- Modify: `static/app.js`

- [ ] **Step 1: Write failing search integration tests**

Add to `tests/test_ui_routes.py`:

```python
def test_home_transition_module_supports_search_clear_animation():
    js = open('static/home-transitions.js', encoding='utf-8').read()

    assert 'function createSearchClear(' in js
    assert 'requestAnimationFrame' in js
    assert 'radial-gradient(' in js
    assert "classList.toggle('has-value'" in js
    assert "classList.add('is-clearing')" in js
    assert 'prefers-reduced-motion: reduce' in js
    assert 'cancelAnimationFrame' in js


def test_app_js_clears_search_state_before_reloading_lineups():
    js = open('static/app.js', encoding='utf-8').read()

    assert 'JccHomeTransitions.createSearchClear' in js
    assert 'function clearLineupSearch()' in js
    function_body = js.split('function clearLineupSearch()', 1)[1].split('\n}', 1)[0]
    assert function_body.index("state.query = ''") < function_body.index('loadLineups()')
    assert function_body.index('state.page = 1') < function_body.index('loadLineups()')
```

- [ ] **Step 2: Run the tests and verify the module contract fails**

Run: `python -m pytest tests/test_ui_routes.py::test_home_transition_module_supports_search_clear_animation tests/test_ui_routes.py::test_app_js_clears_search_state_before_reloading_lineups -q`

Expected: FAIL because the module and application integration do not exist.

- [ ] **Step 3: Implement the search controller**

In `static/home-transitions.js`, implement `createSearchClear({ root, input, mirror, placeholder, glow, button, onClear })` returning `{ sync, setDisabled, cancel, destroy }`.

The implementation must:

```javascript
const reducedMotion = global.matchMedia('(prefers-reduced-motion: reduce)');
let frameId = 0;

function sync(value = input.value) {
  const hasValue = Boolean(value);
  if (!root.classList.contains('is-clearing')) mirror.textContent = value;
  root.classList.toggle('has-value', hasValue);
  button.disabled = !hasValue || input.disabled;
}

function cancel() {
  if (frameId) global.cancelAnimationFrame(frameId);
  frameId = 0;
  root.classList.remove('is-clearing');
  mirror.removeAttribute('style');
  placeholder.removeAttribute('style');
  glow.removeAttribute('style');
  sync();
}
```

On clear, capture the old mirror text, call `onClear()` synchronously, then either finish immediately for reduced motion or animate over CSS variable `--clear-dur`. Measure text runs with a hidden canvas or `Range` rectangles, build per-run `radial-gradient(...)` layers, and update mirror/placeholder transform, opacity, blur, and glow opacity each frame. Clean all temporary styles at completion.

In `static/app.js`, initialize the controller after `elements`, replace direct search presentation writes with `searchClear.sync()` / `searchClear.setDisabled()`, and add:

```javascript
function clearLineupSearch() {
  state.query = '';
  state.page = 1;
  loadLineups();
}
```

- [ ] **Step 4: Run focused tests and verify they pass**

Run: `python -m pytest tests/test_ui_routes.py::test_homepage_search_has_dissolve_clear_layers tests/test_ui_routes.py::test_home_transition_module_supports_search_clear_animation tests/test_ui_routes.py::test_app_js_clears_search_state_before_reloading_lineups -q`

Expected: PASS.

- [ ] **Step 5: Commit the search behavior**

```powershell
git add tests/test_ui_routes.py static/home-transitions.js static/app.js
git commit -m "feat: animate homepage search clearing"
```

### Task 3: Regular Lineup Skeleton And Reveal Lifecycle

**Files:**
- Modify: `tests/test_ui_routes.py`
- Modify: `static/home-transitions.js`
- Modify: `static/app.js`

- [ ] **Step 1: Write failing skeleton lifecycle tests**

Add to `tests/test_ui_routes.py`:

```python
def test_home_transition_module_builds_lineup_skeletons_and_reveals():
    js = open('static/home-transitions.js', encoding='utf-8').read()

    assert 'function createLineupLoader(' in js
    assert "wrapper.className = 't-skel'" in js
    assert "skeleton.className = 't-skel-skeleton is-pulsing'" in js
    assert "content.className = 't-skel-content'" in js
    assert "classList.add('is-revealed')" in js
    assert "classList.add('is-resetting')" in js


def test_app_js_uses_skeletons_only_for_uncached_regular_lineup_navigation():
    js = open('static/app.js', encoding='utf-8').read()

    assert 'const cachedResponse = readHomeCache(' in js
    assert 'lineupLoader.showLoading()' in js
    assert 'lineupLoader.reveal(' in js
    assert 'lineupLoader.fail()' in js
    assert 'async function loadLineups(options = {})' in js
    assert 'options.preserveContent' in js
    assert 'loadLineups({ preserveContent: true })' in js
```

- [ ] **Step 2: Run the skeleton tests and verify they fail**

Run: `python -m pytest tests/test_ui_routes.py::test_home_transition_module_builds_lineup_skeletons_and_reveals tests/test_ui_routes.py::test_app_js_uses_skeletons_only_for_uncached_regular_lineup_navigation -q`

Expected: FAIL because skeleton helpers and lifecycle calls are missing.

- [ ] **Step 3: Implement the lineup loader helper**

In `static/home-transitions.js`, implement `createLineupLoader({ container, count = 3 })` returning `{ showLoading, reveal, fail, reset }`.

`showLoading()` must mount `count` `.t-skel` wrappers, each containing a `.t-skel-skeleton.is-pulsing` card and empty `.t-skel-content`. `reveal(nodes)` places each real card into a content layer, removes unused skeleton wrappers, forces a reflow after `.is-resetting`, and adds `.is-revealed` on the next animation frame. Empty results clear the container.

- [ ] **Step 4: Integrate cache-aware loading in `app.js`**

Change the signature to `async function loadLineups(options = {})`. Read the cache before starting the request:

```javascript
const cachedResponse = readHomeCache('lineups', requestKey);
const shouldShowLoading = !cachedResponse && !options.preserveContent;
if (shouldShowLoading) lineupLoader.showLoading();
```

Use cached data directly or fetch and write it. After confirming the request controller is still current, update state, build lineup card nodes without immediately replacing the container, and call `lineupLoader.reveal(cards)`. On a non-abort failure owned by the current request, call `lineupLoader.fail()` before rethrowing.

Call `loadLineups({ preserveContent: true })` after copy, like, and favorite. Keep deletion and navigation loads on the default behavior because they can change pagination or list membership materially.

- [ ] **Step 5: Run focused UI and API tests**

Run: `python -m pytest tests/test_ui_routes.py tests/test_lineup_permissions.py::test_lineups_pagination_applies_after_search_filter -q`

Expected: PASS.

- [ ] **Step 6: Commit the loading lifecycle**

```powershell
git add tests/test_ui_routes.py static/home-transitions.js static/app.js
git commit -m "feat: reveal lineup cards from skeletons"
```

### Task 4: Transition Styling, Documentation, And Verification

**Files:**
- Modify: `tests/test_ui_routes.py`
- Modify: `static/styles.css`
- Modify: `AGENTS.md`

- [ ] **Step 1: Write failing style contract tests**

Add to `tests/test_ui_routes.py`:

```python
def test_homepage_clear_and_skeleton_transition_styles_are_present():
    css = open('static/styles.css', encoding='utf-8').read()

    for selector in (
        '.t-clear {',
        '.t-clear-mirror,',
        '.t-clear-glow {',
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
```

- [ ] **Step 2: Run the style test and verify it fails**

Run: `python -m pytest tests/test_ui_routes.py::test_homepage_clear_and_skeleton_transition_styles_are_present -q`

Expected: FAIL because the transition CSS is absent.

- [ ] **Step 3: Add adapted Transitions.dev styles**

Add clear variables (`--clear-dur`, fly distances, blur, glow timing) and skeleton variables (`--pulse-dur`, `--reveal-dur`, blur, easing) to `:root`. Implement the approved selectors using existing `--surface-solid`, `--surface-soft`, `--line`, `--muted`, `--accent`, and radius tokens.

Reserve at least 44 px on the input/mirror/placeholder right edge for the clear button. Use `mix-blend-mode: multiply` by default and `screen` in dark mode. Give skeleton code and action blocks fixed responsive dimensions matching real cards. At `max-width: 520px`, keep skeleton action blocks in two columns. Disable clear and reveal animation in the existing reduced-motion media block.

- [ ] **Step 4: Update repository guidance**

Add to the homepage section in `AGENTS.md`:

```markdown
Homepage regular-lineup search uses the `.t-clear` structure in `templates/index.html` and `static/home-transitions.js`. Clearing resets query results immediately while the previous text dissolves. Uncached regular-lineup navigation requests use layout-stable skeleton cards; cache hits and copy/like/favorite refreshes must not flash the skeleton state. Live comp rankings retain their separate loading behavior.
```

- [ ] **Step 5: Run focused tests and the complete suite**

Run: `python -m pytest tests/test_ui_routes.py -q`

Expected: PASS.

Run: `python -m pytest -q`

Expected: all tests pass, with at least the 410-test baseline plus the new tests.

- [ ] **Step 6: Start the local server and verify in a browser**

Run: `python run_server.py` on an available local port.

Verify desktop and mobile widths:

- Search typing and clear-button visibility.
- Immediate result reset while dissolve continues.
- Rapid type/clear cancellation.
- Disabled search in live comps and restored query when returning.
- Slow uncached search, sort, season, and pagination skeleton reveal.
- No skeleton flash on cache hits or copy/like/favorite refreshes.
- Empty results and request-error cleanup.
- Light mode, dark mode, and reduced motion.
- No button, placeholder, card, or action overlap.

- [ ] **Step 7: Check the final diff and commit**

Run: `git diff --check`

Expected: no output.

```powershell
git add tests/test_ui_routes.py static/styles.css AGENTS.md
git commit -m "feat: polish homepage lineup loading states"
```
