// Hold list responses and advance only the page clock to exercise the 200 ms threshold.
const { chromium, webkit } = require('playwright-core');
const assert = require('node:assert/strict');
const base = process.env.DECK_REVIEW_URL || 'http://127.0.0.1:5137';

async function checkLoading(browser, width) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  const list = page.locator('#deckList');
  const count = page.locator('#deckCount');
  const click = selector => page.locator(selector).dispatchEvent('click');
  const idle = () => page.locator('#deckList[aria-busy="false"]:not(.is-loading):not(.show-skeletons):not([inert])')
    .waitFor({ state: 'attached' });
  const positions = () => page.locator('#deckPortalToggle, #deckCodeToggle').evaluateAll(
    buttons => buttons.map(button => button.getBoundingClientRect().left));
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let capture;
  await page.route('**/api/orange-decks?*', route => {
    if (!capture) return route.continue();
    capture(route);
    capture = null;
  });
  async function holdList(trigger) {
    const pending = new Promise(resolve => { capture = resolve; });
    await trigger();
    return pending;
  }
  try {
    const first = await holdList(() => page.goto(base + '/?library=decks', { waitUntil: 'domcontentloaded' }));
    assert.equal(await count.textContent(), '正在加载卡组…');
    assert.equal(await list.locator('.deck-skeleton').count(), 2);
    assert.equal(await list.getAttribute('aria-busy'), 'true');
    await first.continue();
    await idle();
    await page.evaluate(() => document.fonts.ready);
    const original = await count.textContent();
    const buttons = await positions();
    const heading = list.locator('.home-card-heading').first();
    await heading.waitFor();
    const height = await list.evaluate(node => node.offsetHeight);
    const now = new Date();
    await page.clock.install({ time: now });
    await page.clock.pauseAt(new Date(now.valueOf() + 1000));

    // Deliver this one response even after cancellation to exercise stale-response handling.
    await page.evaluate(() => {
      const fetch = window.fetch;
      window.fetch = (url, options) => {
        if (String(url).includes('/api/orange-decks?')) {
          window.fetch = fetch;
          return fetch(url, { ...options, signal: null });
        }
        return fetch(url, options);
      };
    });
    const slow = await holdList(() => click('#deckCodeToggle'));
    await page.clock.runFor(199);
    assert.equal(await count.textContent(), original);
    assert.equal(await list.getAttribute('aria-busy'), 'true');
    assert(await heading.isVisible());
    assert.deepEqual(await positions(), buttons);
    await page.clock.runFor(1);
    assert(await heading.isHidden());
    assert.equal(await list.evaluate(node => node.offsetHeight), height);
    assert.equal(await count.textContent(), original);
    assert.deepEqual(await positions(), buttons);

    // A new filter supersedes the slow one. Old cards reappear immediately, and a
    // fast response must cancel its timer even after the previous request settles.
    const fast = await holdList(() => click('[data-deck-tab="hot"]'));
    assert(await heading.isVisible());
    assert.equal(await list.getAttribute('aria-busy'), 'true');
    await fast.continue();
    await idle();
    const filtered = await count.textContent();
    assert.notEqual(filtered, original);
    await slow.fulfill({ json: { items: [], total: 0, total_pages: 1, page: 1 } });
    await (await slow.request().response()).finished();
    await page.clock.runFor(250);
    await idle();
    assert(await heading.isVisible());
    assert.equal(await count.textContent(), filtered);
    assert.deepEqual(await positions(), buttons);

    await click('#deckPortalToggle');
    const failure = await holdList(() => click('#deckPortalMenu button[data-portal="stable"]'));
    await page.clock.runFor(200);
    await failure.fulfill({ status: 503, json: { error: '预览测试' } });
    await idle();
    assert(await list.getByRole('alert').isVisible());
    assert.equal(await count.textContent(), filtered);
    await click('#deckList [data-action="retry"]');
    await idle();
    assert(await heading.isVisible());
    assert.deepEqual(await positions(), buttons);

    await page.locator('#deckSearch').fill('传送门');
    const search = await holdList(() => page.locator('#deckSearch').press('Enter'));
    await click('[data-deck-tab="mine"]');
    await idle();
    await search.abort();
    await page.clock.runFor(250);
    await idle();
    assert(await list.getByRole('heading', { name: '登录后查看我的卡组' }).isVisible());
    assert.deepEqual(errors, []);
  } finally {
    await page.close();
  }
}

(async () => {
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      for (const width of [1280, 390]) await checkLoading(browser, width);
      console.log(engine.name() + ': desktop and mobile filter loading passed');
    } finally {
      await browser.close();
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
