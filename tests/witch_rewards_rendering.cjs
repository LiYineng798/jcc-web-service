// NODE_PATH must provide Playwright; run against an isolated preview instance.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.WITCH_PREVIEW_URL || 'http://127.0.0.1:5128';
const route = '/tools/s18-witch-rewards';
const output = 'instance/witch-rewards-checks';
fs.mkdirSync(output, { recursive: true });
(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => { if (response.status() >= 400) errors.push(response.url()); });
    await page.goto(base + route);
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 1100 });
      for (const theme of ['light', 'dark']) {
        if (await page.evaluate(() => document.documentElement.dataset.theme) !== theme) {
          await page.locator('.animated-theme-toggle').click();
        }
        assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), theme);
        for (const stacks of ['40', '85', '130', '185', '250', '365', '500', '650', '800']) {
          await page.locator(`[data-stack="${stacks}"]`).click();
          assert.equal(await page.locator('.witch-result:visible').count(), 1);
          assert(await page.locator(`#rewards-${stacks}`).isVisible());
          assert.equal(new URL(page.url()).searchParams.get('stacks'), stacks);
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width}: overflow`);
          for (const img of await page.locator('.witch-result:visible img').all()) await img.scrollIntoViewIfNeeded();
          await page.waitForFunction(() => [...document.querySelectorAll('.witch-result:not([hidden]) img')].every(img => img.complete && img.naturalWidth > 0));
        }
        await page.locator('[data-stack="365"]').click();
        await page.evaluate(() => scrollTo(0, 0));
        await page.screenshot({ path: `${output}/${width}-${theme}.png`, fullPage: true });
      }
    }
    await page.locator('[data-stack="800"]').click();
    await page.goBack();
    assert(await page.locator('#rewards-365').isVisible());
    await page.locator('[data-stack="40"]').focus();
    await page.keyboard.press('Enter');
    assert(await page.locator('#rewards-40').isVisible());
    await page.locator('.animated-theme-toggle').click();
    assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), 'light');
    await page.goto(base);
    await page.locator('.toolbox-menu summary').click();
    await page.locator(`.toolbox-panel a[href="${route}"]`).click();
    assert(await page.locator('#rewards-365').isVisible());
    assert.deepEqual(errors, []);
    const noJs = await browser.newContext({ javaScriptEnabled: false });
    const plain = await noJs.newPage();
    await plain.goto(base + route);
    await plain.locator('[data-stack="800"]').click();
    assert(await plain.locator('#rewards-800').isVisible());
    await noJs.close();
    console.log('PASS: 9 tiers, 4 widths, 2 themes, local images, history, keyboard, toolbox, no-JS navigation');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
