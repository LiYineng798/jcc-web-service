// Admin deck library on the isolated loopback preview (tests/serve_deck_review_preview.py).
// Creates one fictional deck, features, hides (inline reason), restores and deletes it.
const { chromium, webkit } = require('playwright-core');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.DECK_REVIEW_URL || 'http://127.0.0.1:5137';
const out = 'instance/deck-review-preview/screenshots';
fs.mkdirSync(out, { recursive: true });

async function openDecks(page) {
  await page.goto(base + '/__preview/login?user=admin', { waitUntil: 'networkidle' });
  // The tab lives in the sidebar on desktop and in the "more" sheet on phones.
  await page.evaluate(() => ([...document.querySelectorAll('[data-admin-tab="orange-decks"]')].find(n => n.offsetParent)
    || document.querySelector('[data-admin-tab="orange-decks"]')).click());
  await page.locator('.admin-deck-row').first().waitFor();
}

(async () => {
  for (const [name, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch();
    try {
      const author = await browser.newContext();
      await author.request.get(base + '/__preview/login?user=author');
      const authorCsrf = (await (await author.request.get(base + '/api/me')).json()).csrf_token;
      const deckName = `后台验收${name}${Date.now().toString(36)}`;
      const created = await author.request.post(base + '/api/orange-decks', { headers: { 'X-CSRF-Token': authorCsrf }, data: {
        action: 'publish', name: deckName, portal: 'stable', cards: ['7230005', '7220015', '7210014'],
        note: '后台列表只显示这一行备注。',
      } });
      assert.equal(created.status(), 201);
      const deck = await created.json();
      try {
        const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('dialog', dialog => { errors.push('unexpected dialog: ' + dialog.message()); dialog.dismiss(); });
        await openDecks(page);
        await page.locator('.admin-deck-search input').fill(deckName);
        const row = page.locator(`.admin-deck-row[data-deck-id="${deck.id}"]`);
        // The search is debounced; wait for the filtered list, not the deck already on page one.
        await page.waitForFunction(() => document.querySelectorAll('.admin-deck-row').length === 1);
        await row.waitFor();
        // Search keeps focus across the debounced reload.
        assert.equal(await page.evaluate(() => document.activeElement?.closest('.admin-deck-search') !== null), true);
        // Only the shared author avatar is shown; no card art or ordinary public-state badge.
        assert.equal(await row.locator('img').count(), 1);
        assert.equal(await row.locator('.admin-deck-author .user-avatar img').count(), 1);
        assert.equal(await row.locator('.admin-deck-state').count(), 0);
        assert.equal(await row.locator('.admin-deck-author-name').innerText(), '卡组验收作者');
        assert.equal(await row.locator('.admin-deck-portal').innerText(), '稳定');
        assert.match(await row.locator('.admin-deck-energy').innerText(), /^\d+\/8$/);
        assert.equal(await row.locator('.admin-deck-note.is-quiet').innerText(), '后台列表只显示这一行备注。');
        assert.deepEqual(await row.locator('.admin-deck-stat').evaluateAll(items => items.map(item => item.getAttribute('aria-label'))),
          ['点赞 0', '收藏 0', '有效复制 0']);
        // Minutes are enough in the list; the full timestamp stays in the tooltip.
        assert.match(await row.locator('.admin-deck-time').innerText(), /^\d{2}-\d{2} \d{2}:\d{2}$/);
        assert((await row.locator('.admin-deck-time').getAttribute('title')).includes(deck.published_at));

        await row.getByRole('button', { name: '设为推荐', exact: true }).click();
        await row.locator('.admin-deck-state.is-featured').waitFor();
        assert.equal(await row.getByRole('button', { name: '取消推荐', exact: true }).getAttribute('aria-pressed'), 'true');
        await page.screenshot({ path: `${out}/${name}-admin-decks-featured.png` });

        // Hide asks inline: the reason must be 2–200 characters, Escape cancels, nothing is sent until confirmed.
        let hideRequests = 0;
        page.on('request', request => { if (request.url().endsWith(`/api/admin/orange-decks/${deck.id}/hide`)) hideRequests += 1; });
        await row.getByRole('button', { name: '隐藏', exact: true }).click();
        const reason = page.getByLabel('隐藏原因');
        await reason.waitFor();
        assert.equal(await page.evaluate(() => document.activeElement?.id), await reason.getAttribute('id'));
        const confirm = page.getByRole('button', { name: '确认隐藏', exact: true });
        await reason.fill('违');
        assert(await confirm.isDisabled());
        await page.keyboard.press('Escape');
        await reason.waitFor({ state: 'detached' });
        await row.getByRole('button', { name: '隐藏', exact: true }).click();
        await page.getByLabel('隐藏原因').fill('名称含不当内容');
        assert(await confirm.isEnabled());
        await page.screenshot({ path: `${out}/${name}-admin-decks-hide-form.png` });
        await page.keyboard.press('Enter');
        await row.locator('.admin-deck-state.is-hidden').waitFor();
        assert.equal(hideRequests, 1);
        assert.equal(await row.locator('.admin-deck-state.is-hidden').innerText(), '已隐藏');
        assert.equal(await row.locator('.admin-deck-note.is-danger').innerText(), '隐藏原因：名称含不当内容');
        assert.equal(await row.getByRole('button', { name: '设为推荐' }).count(), 0);

        await page.getByRole('button', { name: /^已隐藏/ }).click();
        await row.waitFor();
        assert.equal(await page.getByRole('button', { name: /^已隐藏/ }).getAttribute('aria-pressed'), 'true');
        await page.screenshot({ path: `${out}/${name}-admin-decks-hidden.png` });
        await row.getByRole('button', { name: '恢复公开', exact: true }).click();
        await row.waitFor({ state: 'detached' });
        const restored = await (await author.request.get(base + '/api/orange-decks/' + deck.id)).json();
        assert.equal(restored.status, 'published');
        assert.equal(restored.featured, false);

        // Narrow layouts keep every action reachable without horizontal scrolling.
        await page.getByRole('button', { name: /^全部/ }).click();
        await page.locator('.admin-deck-search input').fill(deckName);
        await row.waitFor();
        for (const width of [1024, 390]) {
          await page.setViewportSize({ width, height: 900 });
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
          assert(await row.getByRole('button', { name: '隐藏', exact: true }).isVisible());
        }

        assert.deepEqual(errors, []);
        console.log(name + ': search focus, feature, inline hide validation/escape/enter, hidden filter, restore and narrow layouts passed');
        await context.close();
      } finally {
        // Leave the shared preview as it was, even after a failed assertion.
        assert.equal((await author.request.delete(base + '/api/orange-decks/' + deck.id, { headers: { 'X-CSRF-Token': authorCsrf } })).status(), 204);
        await author.close();
      }
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
