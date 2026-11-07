// Read-only browser regressions against the isolated deck preview; counts/errors are mocked.
const { chromium, webkit } = require('playwright-core');
const assert = require('node:assert/strict');
const base = process.env.DECK_REVIEW_URL || 'http://127.0.0.1:5137';

(async () => {
  for (const [name, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch();
    try {
      const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      let nextGate = null;
      function holdNext() {
        let ready, release;
        const started = new Promise((resolve, reject) => {
          const timeout = setTimeout(() => reject(new Error('Expected debounced search request did not arrive')), 10000);
          ready = () => { clearTimeout(timeout); resolve(); };
        });
        const gate = new Promise(resolve => { release = resolve; });
        nextGate = { ready, gate };
        return { started, release };
      }
      await page.route('**/api/admin/orange-decks?*', async route => {
        const held = nextGate;
        nextGate = null;
        const response = await route.fetch();
        const data = await response.json();
        data.items.forEach(deck => Object.assign(deck, { like_count: 1234, favorite_count: 1234, copy_count: 12345 }));
        if (held) { held.ready(); await held.gate; }
        await route.fulfill({ response, json: data });
      });
      await page.goto(base + '/__preview/login?user=admin', { waitUntil: 'networkidle' });
      await page.evaluate(() => document.querySelector('[data-admin-tab="orange-decks"]').click());
      await page.locator('.admin-deck-row').first().waitFor();
      // Full numeric values must stay inside their cell, including on phones with little room.
      for (const width of [1440, 1280, 1024, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        const layout = await page.locator('.admin-deck-row').first().evaluate(row => {
          const cell = row.querySelector('.is-stats').getBoundingClientRect();
          return {
            contained: [...row.querySelectorAll('.admin-deck-stat')].every(stat => {
              const rect = stat.getBoundingClientRect();
              return rect.left >= cell.left && rect.right <= cell.right + 1 && stat.scrollWidth <= stat.clientWidth + 1;
            }),
            authorWidth: row.querySelector('.admin-deck-author').getBoundingClientRect().width,
            overflow: document.documentElement.scrollWidth > innerWidth,
          };
        });
        assert(layout.contained, `${name} ${width}: statistics overflow their cell`);
        assert(layout.authorWidth > 20, `${name} ${width}: statistics squeeze out the author`);
        assert.equal(layout.overflow, false);
      }
      assert.deepEqual(await page.locator('.admin-deck-row').first().locator('.admin-deck-stat > span').allTextContents(),
        ['1,234', '1,234', '12,345']);
      await page.setViewportSize({ width: 1440, height: 1000 });
      const search = page.getByRole('searchbox', { name: '搜索卡组名或作者' });
      const originalInput = await search.elementHandle();
      const first = holdNext();
      await search.fill('双码');
      await first.started;
      assert(await search.evaluate(input => input === document.activeElement), 'loading loses search focus');
      // Continue typing without clicking the replacement input. Both requests remain in flight.
      const second = holdNext();
      await page.keyboard.insertText('示例');
      await second.started;
      assert.equal(await search.inputValue(), '双码示例');
      await search.evaluate(input => input.setSelectionRange(1, 3));
      const stale = page.waitForResponse(response => new URL(response.url()).searchParams.get('q') === '双码');
      first.release();
      await (await stale).finished();
      assert.equal(await search.inputValue(), '双码示例');
      assert.deepEqual(await search.evaluate(input => [input.selectionStart, input.selectionEnd]), [1, 3]);
      const latest = page.waitForResponse(response => new URL(response.url()).searchParams.get('q') === '双码示例');
      second.release();
      await (await latest).finished();
      await page.waitForFunction(() => document.querySelector('.admin-deck-table')?.getAttribute('aria-busy') === 'false');
      assert(await search.evaluate(input => input === document.activeElement));
      assert(await originalInput.evaluate(input => input.isConnected), 'search input was replaced during loading');
      assert.deepEqual(await search.evaluate(input => [input.selectionStart, input.selectionEnd]), [1, 3]);

      // An older result arriving during Chinese composition must not replace the live input or its draft.
      const composing = holdNext();
      await search.fill('双码示');
      await composing.started;
      await search.evaluate(input => {
        input.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
        input.value = '双码示例';
        input.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: true }));
      });
      composing.release();
      await page.waitForFunction(() => document.querySelector('.admin-deck-table')?.getAttribute('aria-busy') === 'false');
      assert(await originalInput.evaluate(input => input.isConnected && input === document.activeElement));
      assert.equal(await search.inputValue(), '双码示例');
      const composed = page.waitForResponse(response => new URL(response.url()).searchParams.get('q') === '双码示例');
      await search.evaluate(input => input.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true })));
      await (await composed).finished();
      await page.waitForFunction(() => document.querySelector('.admin-deck-table')?.getAttribute('aria-busy') === 'false');

      const row = page.locator('.admin-deck-row').filter({ hasText: '完整搭配' }).first();
      const fullName = await row.locator('.admin-deck-name').innerText();
      const pending = holdNext();
      await search.fill(fullName);
      await pending.started;
      await row.getByRole('button', { name: '隐藏', exact: true }).click();
      const reason = page.getByLabel('隐藏原因');
      await reason.fill('保留原因');
      pending.release();
      await page.waitForFunction(() => document.querySelector('.admin-deck-table')?.getAttribute('aria-busy') === 'false');
      assert(await reason.evaluate(input => input === document.activeElement), 'search steals reason focus');
      await page.keyboard.insertText('继续输入');
      assert.equal(await reason.inputValue(), '保留原因继续输入');
      assert.equal(await search.inputValue(), fullName);
      // Failed moderation leaves the draft available for correction and retry; no real write is sent.
      await page.route('**/api/admin/orange-decks/*/hide', route => route.fulfill({
        status: 503, contentType: 'application/json', body: JSON.stringify({ error: '模拟隐藏失败' }),
      }));
      await page.getByRole('button', { name: '确认隐藏', exact: true }).click();
      await page.getByText('模拟隐藏失败', { exact: true }).waitFor();
      assert.equal(await reason.inputValue(), '保留原因继续输入');
      assert(await page.getByRole('button', { name: '确认隐藏', exact: true }).isEnabled());
      assert.deepEqual(errors, []);
      console.log(name + ': large counts, slow search typing/caret, stale responses, reason focus and failed moderation passed');
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
