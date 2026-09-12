// Run against tests/serve_lucky_openings_preview.py; NODE_PATH provides Playwright.
const { chromium, webkit } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.OPENINGS_PREVIEW_URL || 'http://127.0.0.1:5105';
const route = '/tools/s16-5-lucky-openings';
const output = 'instance/lucky-openings-checks';
fs.mkdirSync(output, { recursive: true });

(async () => {
  for (const [name, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch();
    try {
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
      const page = await context.newPage();
      const errors = [], failures = [], requests = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('response', response => { if (response.status() >= 400) failures.push(response.url()); });
      page.on('request', request => requests.push(request.url()));
      await page.goto(base);
      await page.locator('.toolbox-menu summary').click();
      assert(await page.locator('.toolbox-panel').isVisible());
      await page.screenshot({ animations: 'disabled', path: `${output}/${name}-home-toolbox.png` });
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('.toolbox-menu').getAttribute('open'), null);
      await page.locator('.toolbox-menu summary').press('Enter');
      await page.locator('.toolbox-panel a').first().click();
      await page.waitForURL(base + route);
      assert.equal(await page.locator('.opening-card').count(), 9);
      for (const img of await page.locator('.opening-portrait img').all()) await img.scrollIntoViewIfNeeded();
      await page.waitForFunction(() => [...document.querySelectorAll('.opening-portrait img')].every(i => i.complete && i.naturalWidth > 0));
      for (const width of [320, 390, 520, 768, 1440]) {
        await page.setViewportSize({ width, height: 900 });
        await page.locator('.toolbox-menu summary').click();
        const panelBounds = await page.locator('.toolbox-panel').boundingBox();
        assert(panelBounds.x >= 0 && panelBounds.x + panelBounds.width <= width, `${name} ${width}: toolbox bounds`);
        await page.keyboard.press('Escape');
        for (const theme of ['light', 'dark']) {
          if (await page.evaluate(() => document.documentElement.dataset.theme || 'light') !== theme) await page.locator('.animated-theme-toggle').click();
          assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), theme, 'theme button switches the actual page theme');
          assert(await page.locator('.theme-toggle-body').evaluate(e => e.getBBox().width > 0), 'theme icon has visible SVG geometry');
          const metrics = await page.evaluate(() => ({
            width: innerWidth, scroll: document.documentElement.scrollWidth,
            columns: getComputedStyle(document.querySelector('.openings-grid')).gridTemplateColumns.split(' ').length,
            buttons: [...document.querySelectorAll('.opening-copy')].map(b => { const r = b.getBoundingClientRect(); return { left: r.left, right: r.right, height: r.height, overflow: b.scrollWidth > b.clientWidth }; }),
          }));
          assert(metrics.scroll <= metrics.width, `${name} ${width} ${theme}: horizontal overflow`);
          assert.equal(metrics.columns, width <= 760 ? 2 : 3);
          assert(metrics.buttons.every(b => b.left >= 0 && b.right <= width && b.height >= 44 && !b.overflow));
          if ([390, 1440].includes(width)) await page.screenshot({ animations: 'disabled', path: `${output}/${name}-${width}-${theme}.png`, fullPage: true });
        }
      }
      // Every guest copy matches the data normalized by the server. Chromium uses its real clipboard.
      if (name === 'chromium') {
        await context.grantPermissions(['clipboard-read', 'clipboard-write']);
        for (const button of await page.locator('.opening-copy').all()) {
          const expected = await button.getAttribute('data-code');
          await button.click();
          await page.waitForFunction(expected => navigator.clipboard.readText().then(text => text === expected), expected);
          assert(expected.startsWith('#MjIw'));
        }
      }
      // Insecure-context/denied-clipboard fallback, followed by complete clipboard failure.
      await page.evaluate(() => {
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async () => { throw new Error('denied'); } } });
        document.execCommand = command => {
          window.fallbackText = document.activeElement.value;
          return command === 'copy';
        };
      });
      await page.locator('.opening-copy').first().click();
      assert.equal(await page.evaluate(() => window.fallbackText), await page.locator('.opening-copy').first().getAttribute('data-code'));
      await page.evaluate(() => { document.execCommand = () => false; });
      await page.locator('.opening-copy').first().click();
      assert(await page.locator('.opening-manual').first().getAttribute('open') !== null);
      assert.equal(await page.locator('.opening-manual textarea').first().inputValue(), await page.locator('.opening-copy').first().getAttribute('data-code'));
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(base);
      await page.locator('#mobileResourceTrigger').click();
      await page.locator('#mobileToolsResourceTitle').scrollIntoViewIfNeeded();
      await page.screenshot({ animations: 'disabled', path: `${output}/${name}-mobile-toolbox.png` });
      await page.locator('#mobileResourceDialog a[href="' + route + '"]').click();
      await page.waitForURL(base + route);
      const previousTheme = await page.evaluate(() => document.documentElement.dataset.theme);
      await page.locator('.animated-theme-toggle').click();
      const chosen = await page.evaluate(() => document.documentElement.dataset.theme);
      assert.notEqual(chosen, previousTheme);
      await page.reload();
      assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), chosen);
      assert.deepEqual(errors, []);
      assert.deepEqual(failures, []);
      assert(!requests.some(url => /\/api\/.*copy/.test(url)), 'fixed recommendations do not alter lineup copy rankings');
      await context.close();
      const noJS = await browser.newContext({ javaScriptEnabled: false });
      const staticPage = await noJS.newPage();
      await staticPage.goto(base + route);
      assert.equal(await staticPage.locator('.opening-card').count(), 9);
      await staticPage.locator('.opening-manual summary').first().click();
      assert(await staticPage.locator('.opening-manual textarea').first().isVisible());
      await noJS.close();
      console.log(`${name}: layouts, art, navigation, copy fallbacks, themes and no-JS passed`);
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
