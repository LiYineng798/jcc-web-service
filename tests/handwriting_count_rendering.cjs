// PREVIEW_URL must point to an isolated local preview. Playwright is resolved through NODE_PATH.
const { chromium, webkit } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const base = process.env.PREVIEW_URL || 'http://127.0.0.1:5093';
const output = path.join(__dirname, '../instance/handwriting-acceptance');
fs.mkdirSync(output, { recursive: true });

(async () => {
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      for (const width of [320, 390, 768, 1280]) {
        for (const theme of ['light', 'dark']) {
          const page = await browser.newPage({ viewport: { width, height: 900 } });
          const errors = [];
          page.on('pageerror', error => errors.push(error.message));
          await page.addInitScript(theme => localStorage.setItem('theme', theme), theme);
          await page.route('**/api/home-stats', route => route.fulfill({ json: { total_public_lineups: 2689 } }));
          await page.goto(base);
          await page.waitForFunction(() => document.querySelector('#lineupCount').dataset.handwritingValue === '2689');
          await page.evaluate(async () => {
            await Promise.all(document.querySelector('#lineupCount').getAnimations({ subtree: true }).map(a => a.finished));
          });
          const result = await page.locator('#lineupCount').evaluate(el => {
            const svg = el.querySelector('svg');
            const box = svg.getBoundingClientRect();
            const card = el.closest('.stat-card').getBoundingClientRect();
            return { text: el.textContent, hidden: svg.getAttribute('aria-hidden'), opacity: getComputedStyle(el.querySelector('.handwriting-count-fill')).opacity,
              fits: box.left >= card.left && box.right <= card.right + 1, overflow: document.documentElement.scrollWidth > innerWidth };
          });
          assert.equal(result.text, '2689');
          assert.equal(result.hidden, 'true');
          assert.equal(result.opacity, '1');
          assert(result.fits && !result.overflow, JSON.stringify({ width, theme, result }));
          assert.deepEqual(errors, []);
          if ([390, 1280].includes(width)) await page.screenshot({ path: path.join(output, `${engine.name()}-${width}-${theme}.png`) });
          await page.evaluate(() => {
            const el = document.querySelector('#lineupCount');
            const original = el.querySelector('svg');
            window.jccHandwritingCount.render(el, 2689);
            if (original !== el.querySelector('svg')) throw Error('Unchanged number restarted animation');
            window.jccHandwritingCount.render(el, 1234567890);
            if (el.querySelectorAll('svg > g').length !== 10) throw Error('Missing digit glyph');
          });
          await page.emulateMedia({ reducedMotion: 'reduce' });
          await page.evaluate(() => {
            const el = document.querySelector('#lineupCount');
            window.jccHandwritingCount.render(el, 0);
            if (el.textContent !== '0' || el.getAnimations({ subtree: true }).length) throw Error('Reduced motion/zero failed');
            window.jccHandwritingCount.render(el, '—');
            if (el.textContent !== '—' || el.querySelector('svg')) throw Error('Non-numeric fallback failed');
            delete window.jccHandwritingDigits;
            window.jccHandwritingCount.render(el, 12);
            if (el.textContent !== '12' || el.querySelector('svg')) throw Error('Missing glyph data fallback failed');
          });
          await page.close();
        }
      }
      const page = await browser.newPage();
      await page.route('**/handwriting-count.js*', route => route.abort());
      await page.route('**/api/home-stats', route => route.fulfill({ json: { total_public_lineups: 42 } }));
      await page.goto(base);
      await page.waitForFunction(() => document.querySelector('#lineupCount').textContent === '42');
      assert.equal(await page.locator('#lineupCount svg').count(), 0);
      await page.close();
      console.log(`${engine.name()}: 8 viewport/theme combinations, updates, all digits, reduced motion and fallbacks passed`);
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
