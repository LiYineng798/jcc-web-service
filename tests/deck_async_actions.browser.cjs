// Delayed responses reproduce races that immediate successful requests cannot cover.
const { chromium, webkit } = require('playwright-core');
const assert = require('node:assert/strict');
const base = process.env.DECK_REVIEW_URL || 'http://127.0.0.1:5137';

function heldRequest(page, pattern) {
  let ready;
  const request = new Promise(resolve => { ready = resolve; });
  const handler = route => { ready(route); };
  return page.route(pattern, handler).then(() => ({
    request,
    release: async data => {
      const route = await request;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
      await page.unroute(pattern, handler);
    },
  }));
}

(async () => {
  for (const [name, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch();
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    let id, headers;
    try {
      await context.request.get(base + '/__preview/login?user=author');
      const me = await (await context.request.get(base + '/api/me')).json();
      headers = { 'X-CSRF-Token': me.csrf_token };
      const title = '异步操作验收' + name;
      const created = await context.request.post(base + '/api/orange-decks', { headers, data: {
        action: 'publish', name: title, portal: 'stable', cards: ['7230005', '7220015', '7210014'],
        plan_code: '演示-大橘大利-MQ==', lineup_code: '#ASYNC123',
      } });
      assert.equal(created.status(), 201);
      id = (await created.json()).id;
      const page = await context.newPage();
      page.setDefaultTimeout(10000);
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.goto(base + '/?library=decks&q=' + encodeURIComponent(title), { waitUntil: 'networkidle' });
      const card = page.locator('[data-deck-id="' + id + '"]');
      await card.waitFor();
      const planPattern = '**/api/orange-decks/' + id + '/copy?code_type=plan';
      const lineupPattern = '**/api/orange-decks/' + id + '/copy?code_type=lineup';
      const plan = await heldRequest(page, planPattern);
      const lineup = await heldRequest(page, lineupPattern);
      await card.locator('[data-action="copy-plan"]').click();
      await plan.request;
      assert(await card.locator('[data-action="copy-lineup"]').isEnabled());
      await card.locator('[data-action="copy-lineup"]').click();
      await lineup.request;
      await lineup.release({ counted: true, copy_count: 12 });
      await page.waitForFunction(id => document.querySelector('[data-deck-id="' + id + '"] [data-copy-count]').textContent === '12', id);
      await plan.release({ counted: true, copy_count: 11 });
      await card.locator('[data-action="copy-plan"]:not([disabled])').waitFor();
      assert.equal(await card.locator('[data-copy-count]').innerText(), '12');

      const delayed = await heldRequest(page, lineupPattern);
      await card.locator('[data-action="copy-lineup"]').click();
      await delayed.request;
      const loaded = page.waitForResponse(r => r.url().includes('/api/orange-decks?') && r.url().includes('tab=mine'));
      await page.locator('[data-deck-tab="mine"]').click();
      await loaded;
      await card.locator('[data-action="copy-lineup"]:not([disabled])').waitFor();
      await delayed.release({ counted: true, copy_count: 13 });
      await page.waitForFunction(id => document.querySelector('[data-deck-id="' + id + '"] [data-copy-count]').textContent === '13', id);

      // A pending social mutation cannot be submitted again through the other action.
      const favorite = await heldRequest(page, '**/api/orange-decks/' + id + '/favorite');
      await card.locator('[data-action="favorite"]').click();
      await favorite.request;
      assert(await card.locator('[data-action="like"]').isDisabled());
      await page.locator('#deckSearch').fill('没有这套卡组的查询');
      await page.locator('#deckSearch').press('Enter');
      await card.waitFor({ state: 'detached' });
      await favorite.release({ favorited: true, favorite_count: 1 });
      // Wait for the response handler, not a timer, before checking for erroneous DOM failures.
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await page.getByText(/Cannot read properties|卡组操作失败/).count(), 0);
      assert.equal(await page.locator('#deckSearch').inputValue(), '没有这套卡组的查询');

      await page.goto(base + '/me#mine/decks', { waitUntil: 'networkidle' });
      const personal = page.locator('.pf-deck-card[data-deck-id="' + id + '"]');
      await personal.waitFor();
      const accountPlan = await heldRequest(page, planPattern);
      const accountLineup = await heldRequest(page, lineupPattern);
      await personal.getByRole('button', { name: '复制方案码', exact: true }).click();
      await accountPlan.request;
      assert(await personal.getByRole('button', { name: '复制阵容码', exact: true }).isEnabled());
      await personal.getByRole('button', { name: '复制阵容码', exact: true }).click();
      await accountLineup.request;
      await accountLineup.release({ counted: true, copy_count: 22 });
      await personal.getByRole('button', { name: '复制阵容码', exact: true }).and(page.locator(':not([disabled])')).waitFor();
      await accountPlan.release({ counted: true, copy_count: 21 });
      await personal.getByRole('button', { name: '复制方案码', exact: true }).and(page.locator(':not([disabled])')).waitFor();
      assert.equal(await personal.locator('[title="卡组有效复制次数"]').innerText(), '22');
      assert.deepEqual(errors, []);
      console.log(name + ': out-of-order copy counts, copy during list reload, social pending guard/navigation, independent personal copy passed');
    } finally {
      if (id) await context.request.delete(base + '/api/orange-decks/' + id, { headers });
      await browser.close();
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
