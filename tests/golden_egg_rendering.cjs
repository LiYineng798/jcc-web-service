const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.GOLDEN_EGG_PREVIEW_URL || 'http://127.0.0.1:5138';
const output = 'instance/golden-egg-checks';
fs.mkdirSync(output, { recursive: true });
(async () => {
  const browser = await chromium.launch({ channel: process.env.GOLDEN_EGG_BROWSER_CHANNEL || undefined });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('response', r => { if (r.status() >= 400) errors.push(r.url()); });
    await page.goto(base + '/tools/golden-egg');
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const theme of ['light', 'dark']) {
        await page.evaluate(t => { document.documentElement.dataset.theme = t; }, theme);
        await page.locator('.egg-notes').scrollIntoViewIfNeeded();
        await page.waitForFunction(() => [...document.images].every(i => i.complete && i.naturalWidth > 0));
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width} overflow`);
        assert.equal(await page.locator('.egg-outcome').count(), 8);
        await page.evaluate(() => scrollTo(0, 0));
        await page.screenshot({ path: `${output}/${width}-${theme}.png`, fullPage: true, animations: 'disabled' });
      }
      await page.locator('.toolbox-trigger').press('Enter');
      const box = await page.locator('.toolbox-panel').boundingBox();
      assert(box.x >= 0 && box.x + box.width <= width);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('.toolbox-menu').getAttribute('open'), null);
    }
    await page.locator('.animated-theme-toggle').click();
    assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), 'light');
    const noJS = await browser.newContext({ javaScriptEnabled: false });
    const plain = await noJS.newPage();
    await plain.goto(base + '/tools/golden-egg');
    assert.equal(await plain.locator('.egg-outcome').count(), 8);
    await noJS.close();
    assert.deepEqual(errors, []);
    console.log('PASS: 8 outcomes, local assets, 4 widths, 2 themes, keyboard, no-JS rendering');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
