# Homepage Border Glow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a native BorderGlow-inspired effect to the homepage statistic card and realtime lineup ranking cards.

**Architecture:** Implement a dependency-free helper in `static/app.js` that initializes selected card elements with CSS variables driven by pointer position. Add scoped CSS in `static/styles.css` so the effect is reusable but only visible on elements explicitly marked with `border-glow-card`.

**Tech Stack:** Flask/Jinja templates, plain JavaScript, CSS custom properties, pytest-based static route/UI tests.

---

### Task 1: Add Static Tests For Scoped Integration

**Files:**
- Modify: `tests/test_ui_routes.py`

- [ ] **Step 1: Add tests that describe the intended integration**

Append these tests near the existing static asset checks in `tests/test_ui_routes.py`:

```python
def test_homepage_stat_card_has_border_glow_hook():
    with open('templates/index.html', 'r', encoding='utf-8') as file:
        html = file.read()

    assert 'class="stat-card border-glow-card"' in html
    assert 'data-border-glow="stat"' in html


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
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_homepage_stat_card_has_border_glow_hook tests/test_ui_routes.py::test_border_glow_is_scoped_to_homepage_realtime_cards tests/test_ui_routes.py::test_border_glow_styles_are_present -v
```

Expected: all three tests fail because the hooks, helper, and styles do not exist yet.

- [ ] **Step 3: Commit the failing tests**

```powershell
git add tests/test_ui_routes.py
git commit -m "test: describe homepage border glow integration"
```

### Task 2: Add Homepage Stat Card Hook

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: Add the stat card classes and data hook**

Change the stat card opening tag from:

```html
<section class="stat-card" aria-label="阵容统计">
```

to:

```html
<section class="stat-card border-glow-card" data-border-glow="stat" aria-label="阵容统计">
```

- [ ] **Step 2: Run the stat card test**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_homepage_stat_card_has_border_glow_hook -v
```

Expected: PASS.

- [ ] **Step 3: Commit the template hook**

```powershell
git add templates/index.html
git commit -m "feat: add border glow hook to homepage stat card"
```

### Task 3: Add Border Glow CSS

**Files:**
- Modify: `static/styles.css`

- [ ] **Step 1: Add scoped reusable CSS**

Add this block after the existing `.stat-card, .panel, .lineup-card` base card styles:

```css
.border-glow-card {
  --edge-proximity: 0;
  --cursor-angle: 45deg;
  --edge-sensitivity: 34;
  --color-sensitivity: calc(var(--edge-sensitivity) + 18);
  --border-glow-radius: var(--radius-lg);
  --border-glow-padding: 32px;
  --cone-spread: 22;
  --fill-opacity: 0.18;
  --card-bg: var(--surface-solid);
  --gradient-one: radial-gradient(at 80% 55%, rgba(201, 100, 66, 0.95) 0, transparent 52%);
  --gradient-two: radial-gradient(at 24% 16%, rgba(245, 185, 92, 0.82) 0, transparent 54%);
  --gradient-three: radial-gradient(at 52% 94%, rgba(66, 176, 184, 0.58) 0, transparent 50%);
  --gradient-base: linear-gradient(rgba(201, 100, 66, 0.36) 0 100%);
  position: relative;
  isolation: isolate;
  overflow: visible;
  transform: translate3d(0, 0, 0.01px);
}

.border-glow-card::before,
.border-glow-card::after,
.border-glow-card > .edge-light {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  opacity: 0;
  pointer-events: none;
  transition: opacity 220ms ease-out;
}

.border-glow-card::before {
  z-index: -1;
  border: 1px solid transparent;
  background:
    linear-gradient(var(--card-bg) 0 100%) padding-box,
    linear-gradient(rgb(255 255 255 / 0%) 0 100%) border-box,
    var(--gradient-one) border-box,
    var(--gradient-two) border-box,
    var(--gradient-three) border-box,
    var(--gradient-base) border-box;
  opacity: max(0, calc((var(--edge-proximity) - var(--color-sensitivity)) / (100 - var(--color-sensitivity))));
  mask-image:
    conic-gradient(
      from var(--cursor-angle) at center,
      black calc(var(--cone-spread) * 1%),
      transparent calc((var(--cone-spread) + 14) * 1%),
      transparent calc((100 - var(--cone-spread) - 14) * 1%),
      black calc((100 - var(--cone-spread)) * 1%)
    );
}

.border-glow-card::after {
  z-index: -1;
  background:
    var(--gradient-one) padding-box,
    var(--gradient-two) padding-box,
    var(--gradient-three) padding-box,
    var(--gradient-base) padding-box;
  opacity: max(0, calc(var(--fill-opacity) * (var(--edge-proximity) - var(--color-sensitivity)) / (100 - var(--color-sensitivity))));
  mix-blend-mode: soft-light;
  mask-image:
    radial-gradient(ellipse at 50% 50%, black 38%, transparent 66%),
    conic-gradient(from var(--cursor-angle) at center, transparent 5%, black 16%, black 84%, transparent 95%);
  mask-composite: intersect;
}

.border-glow-card > .edge-light {
  inset: calc(var(--border-glow-padding) * -1);
  z-index: 1;
  opacity: max(0, calc((var(--edge-proximity) - var(--edge-sensitivity)) / (100 - var(--edge-sensitivity))));
  mix-blend-mode: plus-lighter;
  mask-image:
    conic-gradient(
      from var(--cursor-angle) at center,
      black 2.5%,
      transparent 10%,
      transparent 90%,
      black 97.5%
    );
}

.border-glow-card > .edge-light::before {
  content: "";
  position: absolute;
  inset: var(--border-glow-padding);
  border-radius: inherit;
  box-shadow:
    inset 0 0 0 1px var(--glow-color, rgba(245, 185, 92, 0.92)),
    inset 0 0 10px 1px var(--glow-color-soft, rgba(201, 100, 66, 0.28)),
    inset 0 0 28px 2px var(--glow-color-faint, rgba(245, 185, 92, 0.16)),
    0 0 8px 0 var(--glow-color-soft, rgba(201, 100, 66, 0.28)),
    0 0 28px 2px var(--glow-color-faint, rgba(245, 185, 92, 0.16));
}

.border-glow-card.border-glow-sweep {
  --edge-proximity: 100;
}

@media (hover: none), (pointer: coarse) {
  .border-glow-card::before,
  .border-glow-card::after,
  .border-glow-card > .edge-light {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .border-glow-card::before,
  .border-glow-card::after,
  .border-glow-card > .edge-light {
    transition: none;
  }
}
```

- [ ] **Step 2: Run the CSS presence test**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_border_glow_styles_are_present -v
```

Expected: PASS.

- [ ] **Step 3: Commit the CSS**

```powershell
git add static/styles.css
git commit -m "feat: add homepage border glow styles"
```

### Task 4: Add Native JavaScript Helper And Wire Realtime Cards

**Files:**
- Modify: `static/app.js`

- [ ] **Step 1: Add helper functions**

Add these functions after `renderHomeImageModeToggle()`:

```javascript
function initBorderGlowCard(card, options = {}) {
  if (!card || card.dataset.borderGlowReady === 'true') return;
  if (window.matchMedia?.('(hover: none), (pointer: coarse)').matches) return;
  card.dataset.borderGlowReady = 'true';
  card.classList.add('border-glow-card');

  const {
    glowColor = 'rgba(245, 185, 92, 0.92)',
    glowColorSoft = 'rgba(201, 100, 66, 0.28)',
    glowColorFaint = 'rgba(245, 185, 92, 0.16)',
    fillOpacity = '0.18',
    edgeSensitivity = '34',
    coneSpread = '22',
    initialSweep = false,
  } = options;

  card.style.setProperty('--glow-color', glowColor);
  card.style.setProperty('--glow-color-soft', glowColorSoft);
  card.style.setProperty('--glow-color-faint', glowColorFaint);
  card.style.setProperty('--fill-opacity', fillOpacity);
  card.style.setProperty('--edge-sensitivity', edgeSensitivity);
  card.style.setProperty('--cone-spread', coneSpread);

  if (!card.querySelector(':scope > .edge-light')) {
    const edgeLight = document.createElement('span');
    edgeLight.className = 'edge-light';
    edgeLight.setAttribute('aria-hidden', 'true');
    card.prepend(edgeLight);
  }

  card.addEventListener('pointermove', handleBorderGlowPointerMove);
  card.addEventListener('pointerleave', handleBorderGlowPointerLeave);

  if (initialSweep && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    runBorderGlowSweep(card);
  }
}

function handleBorderGlowPointerMove(event) {
  const card = event.currentTarget;
  const rect = card.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const cx = rect.width / 2;
  const cy = rect.height / 2;
  const dx = x - cx;
  const dy = y - cy;
  const kx = dx === 0 ? Infinity : cx / Math.abs(dx);
  const ky = dy === 0 ? Infinity : cy / Math.abs(dy);
  const edge = Math.min(Math.max(1 / Math.min(kx, ky), 0), 1);
  let angle = Math.atan2(dy, dx) * (180 / Math.PI) + 90;
  if (angle < 0) angle += 360;
  card.style.setProperty('--edge-proximity', `${(edge * 100).toFixed(3)}`);
  card.style.setProperty('--cursor-angle', `${angle.toFixed(3)}deg`);
}

function handleBorderGlowPointerLeave(event) {
  event.currentTarget.style.setProperty('--edge-proximity', '0');
}

function runBorderGlowSweep(card) {
  card.classList.add('border-glow-sweep');
  card.style.setProperty('--cursor-angle', '115deg');
  window.setTimeout(() => {
    card.style.setProperty('--cursor-angle', '430deg');
  }, 80);
  window.setTimeout(() => {
    card.classList.remove('border-glow-sweep');
    card.style.setProperty('--edge-proximity', '0');
  }, 1200);
}

function applyBorderGlowToStaticCards() {
  const statCard = document.querySelector('[data-border-glow="stat"]');
  initBorderGlowCard(statCard, {
    fillOpacity: '0.14',
    edgeSensitivity: '38',
    coneSpread: '20',
    initialSweep: true,
  });
}
```

- [ ] **Step 2: Initialize the stat card during startup**

Add this call after `renderHomeImageModeToggle();`:

```javascript
applyBorderGlowToStaticCards();
```

- [ ] **Step 3: Wire realtime cards**

In `renderLiveCompCard(item)`, after the card class is assigned, add:

```javascript
  card.dataset.borderGlow = 'live-comp';
  initBorderGlowCard(card, {
    fillOpacity: state.imageMode === 'image' ? '0.16' : '0.1',
    edgeSensitivity: '36',
    coneSpread: '21',
  });
```

- [ ] **Step 4: Run the JS integration test**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_border_glow_is_scoped_to_homepage_realtime_cards -v
```

Expected: PASS.

- [ ] **Step 5: Commit the JavaScript**

```powershell
git add static/app.js
git commit -m "feat: initialize homepage border glow cards"
```

### Task 5: Verify And Document Result

**Files:**
- No planned file changes.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_ui_routes.py::test_homepage_stat_card_has_border_glow_hook tests/test_ui_routes.py::test_border_glow_is_scoped_to_homepage_realtime_cards tests/test_ui_routes.py::test_border_glow_styles_are_present -v
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
python -m pytest
```

Expected: all tests pass except the existing baseline failure if it remains:

```text
tests/test_ui_routes.py::test_app_js_defaults_home_image_mode_to_text_only
```

- [ ] **Step 3: Start local server for visual check**

Run:

```powershell
$env:JCC_SECRET_KEY='dev-secret-change-me'
$env:JCC_ADMIN_USERNAME='adminxlx'
$env:JCC_ADMIN_PASSWORD='Admin1234'
python run_server.py
```

Open `http://127.0.0.1:5000/`, move the pointer near the stat card edge, and verify the glow appears. If realtime data is available, verify realtime cards glow; if data is not available, verify the page remains clean in the empty state.

- [ ] **Step 4: Commit any verification-only fixes**

If visual verification requires small tuning, commit it:

```powershell
git add static/styles.css static/app.js templates/index.html tests/test_ui_routes.py
git commit -m "fix: tune homepage border glow"
```
