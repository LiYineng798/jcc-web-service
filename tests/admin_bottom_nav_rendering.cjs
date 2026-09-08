// Run against the isolated preview documented in docs/admin-safari-bottom-nav.md.
const { chromium, webkit, request } = require('playwright');
const { PNG } = require('pngjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.PREVIEW_URL || 'http://127.0.0.1:5088';

(async () => {
  fs.mkdirSync('instance/nav-checks', { recursive: true });
  const auth = await request.newContext();
  assert.equal((await auth.post(base + '/api/login', {
    data: { account: 'previewadmin', password: 'Preview1234' },
  })).status(), 200);
  const storageState = await auth.storageState();
  await auth.dispose();
  for (const [name, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch();
    try {
      for (const theme of ['light', 'dark']) {
        const context = await browser.newContext({ storageState, viewport: { width: 390, height: 844 } });
        await context.addInitScript(theme => localStorage.setItem('theme', theme), theme);
        const page = await context.newPage();
        await page.goto(base + '/admin');
        await page.locator('.admin-stat-card').first().waitFor();
        const nav = page.locator('.admin-mobile-nav');
        for (const [width, height] of [[320,640], [390,844], [390,640], [390,920], [768,844], [812,375]]) {
          await page.setViewportSize({ width, height });
          for (const y of [0, 300, 900, 200, 99999, 0]) {
            await page.evaluate(y => scrollTo(0,y), y);
            await page.waitForTimeout(60);
            const rect = await nav.boundingBox();
            assert(Math.abs(rect.y + rect.height - height) < 1, `${name}: bottom drift`);
            assert(Math.abs((await page.locator('.admin-topbar').boundingBox()).y) < 1);
            assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
          }
        }
        await page.setViewportSize({ width: 390, height: 844 });
        for (const tab of ['reports', 'lineups', 'analytics', 'overview']) {
          const button = nav.locator(`[data-admin-tab="${tab}"]`);
          await button.click();
          await page.waitForFunction(tab => document.querySelector(`.admin-mobile-nav [data-admin-tab="${tab}"]`).classList.contains('is-active'), tab);
        }
        await page.locator('#adminMoreButton').click();
        await page.locator('#adminMoreDialog').waitFor({ state: 'visible' });
        await page.locator('#adminMoreDialog [data-admin-tab="daily-reports"]').click();
        await page.locator('#adminMoreDialog').waitFor({ state: 'hidden' });
        await page.locator('#adminMoreButton').click();
        await page.locator('#adminMoreClose').click();
        await nav.locator('[data-admin-tab="overview"]').click();
        await page.locator('.admin-stat-card').first().waitFor();
        await page.evaluate(() => scrollTo(0,500));
        await page.screenshot({ path: `instance/nav-checks/${name}-${theme}.png` });

        // Model an exposed toolbar strip. This tests our paint fallback, not
        // reproduction of the iPhone compositor bug in a desktop engine.
        const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
        await nav.evaluate(node => node.style.bottom = '48px');
        const screenshot = PNG.sync.read(await page.screenshot());
        const expected = theme === 'light' ? [255,253,248] : [33,31,27];
        for (const y of [804,820,840]) for (const x of [10,195,380]) {
          const offset = (y * screenshot.width + x) * 4;
          assert.deepEqual([...screenshot.data.subarray(offset, offset+3)], expected, `${name} ${theme}: content leaked below nav`);
        }
        assert.equal(await page.evaluate(() => document.documentElement.scrollHeight), scrollHeight);
        await nav.evaluate(node => node.style.removeProperty('bottom'));
        // Desktop engines expose zero device insets; inject known inset values
        // to exercise the production rules for a notched landscape device.
        const css = await (await context.request.get(base + '/static/admin.css')).text();
        const safeAreaStyle = await page.addStyleTag({ content: css.replace(
          /env\(safe-area-inset-(top|bottom|left|right)\)/g,
          (_, side) => ({top:'0px',bottom:'34px',left:'44px',right:'44px'}[side]),
        ) });
        assert.equal((await nav.boundingBox()).height, 102);
        for (const button of await nav.locator('button').all()) {
          const box = await button.boundingBox();
          assert(box.x >= 44 && box.x + box.width <= 346);
          assert(box.y + box.height <= 810);
        }
        await safeAreaStyle.evaluate(node => node.remove());
        await page.setViewportSize({ width: 1280, height: 844 });
        await nav.waitFor({ state: 'hidden' });
        assert(await page.locator('.admin-sidebar').isVisible());
        await context.close();
        console.log(`${name} ${theme}: scrolling, resize, landscape, tabs, More, paint coverage and desktop passed`);
      }
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exit(1); });
