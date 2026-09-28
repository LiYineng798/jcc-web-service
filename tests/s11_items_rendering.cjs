// Run against the isolated preview, with Playwright available through NODE_PATH.
const { chromium, webkit } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.S11_PREVIEW_URL || 'http://127.0.0.1:5111';
const route = '/tools/s11-items';
const output = 'instance/s11-checks';
fs.mkdirSync(output, { recursive: true });

(async () => {
  for (const [name, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch();
    try {
      const page = await browser.newPage({ viewport: { width: 1440, height: 1080 } });
      const errors = [], failures = [], requests = [];
      page.on('pageerror', e => errors.push(e.message));
      page.on('response', r => { if (r.status() >= 400) failures.push(r.url()); });
      page.on('request', r => requests.push(r.url()));
      await page.goto(base + route);
      assert.equal(await page.locator('.ink-card:visible').count(), 60);
      for (const [cost, count] of [[5, 9], [4, 12], [3, 13], [2, 13], [1, 13]]) {
        await page.locator(`[data-cost="${cost}"]`).click();
        assert.equal(await page.locator('.ink-card:visible').count(), count);
      }
      await page.locator('[data-cost="all"]').click();
      await page.locator('#ink-search').fill('孙悟空');
      assert.equal(await page.locator('.ink-card:visible').count(), 1);
      await page.locator('[data-cost="1"]').click();
      assert(await page.locator('.ink-empty').isVisible());
      await page.locator('.ink-empty .ink-reset').click();
      assert.equal(await page.locator('.ink-card:visible').count(), 60);
      assert(await page.locator('#ink-search').evaluate(e => e === document.activeElement));
      for (const term of ['珠光护手', '无用大棒', '天龙之子', '孙悟空 汲取剑']) {
        await page.locator('#ink-search').fill(term);
        assert(await page.locator('.ink-card:visible').count() > 0, term);
        for (const card of await page.locator('.ink-card:visible').all()) {
          const search = await card.getAttribute('data-search');
          assert(term.split(' ').every(t => search.includes(t)));
        }
      }
      await page.locator('#ink-search').fill('<script>');
      assert(await page.locator('.ink-empty').isVisible());
      await page.locator('.ink-empty .ink-reset').click();
      for (const img of await page.locator('.ink-page img').all()) {
        await img.evaluate(e => { e.loading = 'eager'; });
      }
      await page.waitForFunction(() => [...document.querySelectorAll('.ink-page img')].every(i => i.complete && i.naturalWidth > 0));
      for (const width of [320, 390, 520, 768, 1440]) {
        await page.setViewportSize({ width, height: 1080 });
        await page.locator('.toolbox-menu summary').click();
        const panel = await page.locator('.toolbox-panel').boundingBox();
        assert(panel.x >= 0 && panel.x + panel.width <= width, `${width} toolbox bounds`);
        await page.keyboard.press('Escape');
        for (const theme of ['light', 'dark']) {
          if (await page.evaluate(() => document.documentElement.dataset.theme || 'light') !== theme) {
            await page.locator('.animated-theme-toggle').click();
          }
          assert.equal(await page.evaluate(() => document.documentElement.dataset.theme || 'light'), theme);
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name} ${width} ${theme} overflow`);
          const collisions = await page.locator('.ink-item').evaluateAll(items => items.filter(item => {
            const box = item.getBoundingClientRect();
            return [...item.querySelectorAll('img, h4, .ink-component')].some(e => {
              const r = e.getBoundingClientRect(); return r.left < box.left - 1 || r.right > box.right + 1;
            });
          }).length);
          assert.equal(collisions, 0, `${width} equipment overflow`);
          await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
          await page.screenshot({ animations: 'disabled', path: `${output}/${name}-${width}-${theme}.png` });
        }
      }
      assert(requests.filter(url => url.includes('/assets/')).every(url => url.startsWith(base + '/static/tools/s11-items/assets/')));
      await page.goto(base);
      await page.locator('.toolbox-menu summary').click();
      assert.equal(await page.locator(`.toolbox-panel a[href="${route}"]`).count(), 1);
      for (const old of ['special-mechanics', 'artifact-guide', 'returning-equipment']) {
        assert.equal(await page.locator(`a[href="/tools/${old}"]`).count(), 0);
      }
      await page.keyboard.press('Escape');
      await page.setViewportSize({ width: 390, height: 844 });
      await page.locator('#mobileResourceTrigger').click();
      await page.locator(`#mobileResourceDialog a[href="${route}"]`).click();
      await page.waitForURL(base + route);
      assert.equal(await page.locator('.ink-card:visible').count(), 60);
      assert.deepEqual(errors, []);
      assert.deepEqual(failures, []);
      const nojs = await browser.newPage({ javaScriptEnabled: false });
      await nojs.goto(base + route);
      assert.equal(await nojs.locator('.ink-card:visible').count(), 60);
      assert.equal(await nojs.locator('.ink-controls:visible').count(), 0);
      console.log(`${name}: search, costs, recipes, assets, themes, 320–1440px, navigation, no-JS passed`);
    } finally { await browser.close(); }
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
