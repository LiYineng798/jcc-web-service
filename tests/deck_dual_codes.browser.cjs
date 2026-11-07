// Uses only the isolated loopback preview, including its fictional dual-code examples.
const { chromium, webkit } = require('playwright-core');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.DECK_REVIEW_URL || 'http://127.0.0.1:5137';
const out = 'instance/deck-review-preview/screenshots';
fs.mkdirSync(out, { recursive: true });

(async () => {
  for (const [name, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch();
    try {
      const context = await browser.newContext({
        viewport: { width: 1440, height: 1100 },
        ...(name === 'chromium' ? { permissions: ['clipboard-read', 'clipboard-write'] } : {}),
      });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.goto(base + '/?library=decks&q=' + encodeURIComponent('双码示例'), { waitUntil: 'networkidle' });
      await page.locator('.deck-card').first().waitFor();
      assert.equal(await page.locator('.deck-card').count(), 4);
      for (const [title, plan, lineup] of [
        ['完整搭配', true, true], ['仅方案码', true, false], ['仅阵容码', false, true], ['暂无代码', false, false],
      ]) {
        const card = page.locator('.deck-card').filter({ hasText: title });
        assert.equal(await card.locator('[data-action="copy-plan"]').isEnabled(), plan);
        assert.equal(await card.locator('[data-action="copy-lineup"]').isEnabled(), lineup);
        assert((await card.innerText()).includes(plan ? '复制方案码' : '未提供方案码'));
        assert((await card.innerText()).includes(lineup ? '复制阵容码' : '未提供阵容码'));
      }
      const full = page.locator('.deck-card').filter({ hasText: '完整搭配' });
      const id = await full.getAttribute('data-deck-id');
      const deck = await (await context.request.get(base + '/api/orange-decks/' + id)).json();
      for (const type of ['plan', 'lineup']) {
        const response = page.waitForResponse(r => r.url().includes('/copy?code_type=' + type));
        await full.locator('[data-action="copy-' + type + '"]').click();
        assert.equal((await response).status(), 200);
        if (name === 'chromium') assert.equal(await page.evaluate(() => navigator.clipboard.readText()), deck[type + '_code']);
      }
      // Keyboard focus and activation keep the two actions distinguishable.
      await full.locator('[data-action="copy-plan"]').focus();
      await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(() => document.activeElement.dataset.action), 'copy-lineup');
      const keyboardCopy = page.waitForResponse(r => r.url().includes('/copy?code_type=lineup'));
      await page.keyboard.press('Enter');
      assert.equal((await keyboardCopy).status(), 200);
      // A stale/unavailable statistics endpoint does not turn a successful copy into failure.
      await page.route('**/api/orange-decks/*/copy?*', route => route.fulfill({
        status: 503, contentType: 'application/json', body: '{"error":"test unavailable"}',
      }));
      await full.locator('[data-action="copy-lineup"]').click();
      await page.getByText('阵容码已复制，但次数未同步，请稍后刷新', { exact: true }).waitFor();
      await page.unroute('**/api/orange-decks/*/copy?*');
      await page.getByRole('button', { name: '关闭通知', exact: true }).evaluateAll(buttons => buttons.forEach(button => button.click()));
      await page.locator('.jcc-notification').first().waitFor({ state: 'detached' });
      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({ width, height: width === 1440 ? 1100 : 844 });
        for (const theme of ['light', 'dark']) {
          await page.evaluate(theme => {
            document.documentElement.dataset.theme = theme;
            localStorage.setItem('theme', theme);
          }, theme);
          await page.locator('#deckList').scrollIntoViewIfNeeded();
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
          assert(await page.locator('.deck-code-action').evaluateAll(buttons => buttons.every(b => b.scrollWidth <= b.clientWidth + 1)));
          // Missing codes keep their slot, so every card has one height and a one-row footer.
          const layout = await page.locator('.deck-card').evaluateAll(cards => cards.map(card => ({
            height: card.offsetHeight,
            footerRows: new Set([...card.querySelectorAll('.home-card-footer > * > *')].map(item => item.offsetTop)).size,
            countInFooter: Boolean(card.querySelector('.home-card-footer [data-copy-count]')),
          })));
          assert.equal(new Set(layout.map(item => item.height)).size, 1);
          assert(layout.every(item => item.footerRows === 1 && item.countInFooter));
          await page.locator('#deckList').screenshot({ path: `${out}/${name}-dual-${width}-${theme}.png` });
        }
      }
      await page.emulateMedia({ reducedMotion: 'reduce' });
      assert.equal(await full.locator('[data-action="copy-lineup"]').evaluate(b => getComputedStyle(b).transitionDuration), '0s');
      await page.goto(base + deck.detail_url, { waitUntil: 'networkidle' });
      await page.locator('#copyDeckLineup').click();
      await page.locator('#deckLineupCopyStatus').getByText('阵容码已复制', { exact: true }).waitFor();
      if (name === 'chromium') assert.equal(await page.evaluate(() => navigator.clipboard.readText()), deck.lineup_code);
      await page.goto(base + '/__preview/login?user=author', { waitUntil: 'networkidle' });
      const me = await (await context.request.get(base + '/api/me')).json();
      const headers = { 'X-CSRF-Token': me.csrf_token };
      const created = await context.request.post(base + '/api/orange-decks', { headers, data: {
        action: 'publish', name: '双码编辑验收', portal: 'stable', cards: ['7230005', '7220015', '7210014'],
        plan_code: deck.plan_code, lineup_code: deck.lineup_code,
      } });
      assert.equal(created.status(), 201);
      const editDeck = await created.json();
      await page.goto(base + '/orange-decks/' + editDeck.id + '/edit', { waitUntil: 'networkidle' });
      assert.equal(await page.locator('#deckLineupCode').inputValue(), deck.lineup_code);
      await page.locator('#deckLineupCode').fill('无效文案');
      await page.locator('#savePrimary').click();
      await page.locator('#deckFormError').getByText('阵容码无法解析，请改成以 # 开头的阵容码后再提交', { exact: true }).waitFor();
      assert.equal(await page.locator('#deckPlanCode').inputValue(), deck.plan_code);
      await page.locator('#deckLineupCode').fill('');
      await page.locator('#savePrimary').click();
      await page.waitForURL(base + '/orange-decks/' + editDeck.id);
      const saved = await (await context.request.get(base + '/api/orange-decks/' + editDeck.id)).json();
      assert.equal(saved.lineup_code, '');
      assert.equal(saved.plan_code, deck.plan_code);
      assert.equal((await context.request.delete(base + '/api/orange-decks/' + editDeck.id, { headers })).status(), 204);
      // Profile deck cards keep the four-row lineup card shape; a missing code stays visible but disabled.
      await page.setViewportSize({ width: 1440, height: 1100 });
      await page.goto(base + '/me#mine/decks', { waitUntil: 'networkidle' });
      await page.locator('.pf-deck-card').first().waitFor();
      assert.equal(new Set(await page.locator('.pf-deck-card').evaluateAll(cards => cards.map(card => card.offsetHeight))).size, 1);
      const onlyPlan = page.locator('.pf-deck-card').filter({ hasText: '双码示例·仅方案码' });
      assert(await onlyPlan.getByRole('button', { name: /^复制方案码：/ }).isEnabled());
      assert(await onlyPlan.getByRole('button', { name: '未提供阵容码', exact: true }).isDisabled());
      assert.deepEqual(errors, []);
      console.log(name + ': four code states, independent clipboard, keyboard, sync failure, 320/390/1440 light/dark, reduced motion, editing validation and independent clearing passed');
      await context.close();
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
