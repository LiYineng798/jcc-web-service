// Touch-device end-to-end checks. OS share sheets and album writes still require a physical phone.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium, webkit, devices} = require('playwright');
const {PNG} = require('pngjs');
const base = process.env.CREATOR_PREVIEW_URL || 'http://127.0.0.1:5146';
const out = 'instance/creator-review';
const material = process.env.CREATOR_MATERIAL || 'editorial';
fs.mkdirSync(out, {recursive:true});
async function fits(page) {
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'page must fit phone width');
  assert.ok(await page.locator('.analytics-chart-plot,.analytics-table-shell,.analytics-rates').evaluateAll(nodes => nodes.every(node => node.scrollWidth <= node.clientWidth + 1)), 'analytics must fit phone width');
}
(async () => {
  for (const [name, engine, device] of [['iphone', webkit, 'iPhone 13'], ['android', chromium, 'Pixel 7']]) {
    const browser = await engine.launch();
    const page = await browser.newPage({...devices[device], reducedMotion:'reduce'});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${base}/__preview__/login/admin`);
    await page.locator('[data-admin-tab="analytics"]:visible').first().tap();
    await page.locator('.analytics-chart').first().waitFor();
    for (const card of await page.locator('.analytics-chart').all()) {
      await card.locator('.analytics-bar-group').first().tap();
      assert.ok(!(await card.locator('.analytics-chart-detail').innerText()).includes('悬停'));
      await card.locator('summary').tap();
      assert.ok(await card.locator('tbody').isVisible());
    }
    await fits(page);
    await page.screenshot({path:`${out}/mobile-${name}-analytics.png`, fullPage:true});
    await page.locator('#themeToggle').tap();
    await fits(page);
    await page.getByRole('button', {name:'搜索与设备', exact:true}).tap();
    await page.locator('.experience-section .analytics-chart').waitFor();
    assert.deepEqual(await page.locator('.experience-section .analytics-legend-item').allTextContents(), ['访问人数','搜索人数']);
    await page.locator('.experience-section .analytics-legend-item').last().tap();
    assert.equal(await page.locator('.experience-section .analytics-legend-item').last().getAttribute('aria-pressed'), 'false');
    await page.locator('.experience-section .analytics-legend-item').last().tap();
    await page.locator('.experience-section .analytics-data summary').tap();
    await fits(page);
    await page.screenshot({path:`${out}/mobile-${name}-devices.png`, fullPage:true});

    await page.goto(`${base}/tools/orange-fortune-creator`);
    await page.waitForFunction(() => document.querySelector('#formation-status').textContent.includes('已连接'));
    await page.locator('#deck-name').fill('时光手札 · 手机端构筑');
    await page.locator('[data-panel="cards"]').tap();
    for (const [slot,id] of ['7250036','7250046','7250034'].entries()) {
      await page.locator(`[data-slot="${slot}"]`).tap();
      await page.locator(`[data-card="${id}"]`).tap();
    }
    await page.locator('#edit-formation').tap();
    const frame = page.frameLocator('#formation-frame');
    await frame.locator('.hero-button:not(.is-locked)').first().tap();
    await page.locator('[data-close="formation-dialog"]').tap();
    await page.locator('[data-panel="materials"]').tap();
    await page.locator(`[data-background="${material}"]`).tap();
    for (const layout of ['guide','showcase']) {
      await page.locator('[data-panel="content"]').tap();
      await page.locator(`[name="poster-layout"][value="${layout}"]`).check();
      await page.locator('#open-preview').tap();
      await fits(page);
      const preview = await page.locator('#poster-preview').boundingBox();
      assert.ok(preview.width > 200 && preview.width < devices[device].viewport.width);
      await page.screenshot({path:`${out}/mobile-${name}-${layout}-preview.png`});
      await page.locator('[data-close="preview-dialog"]').tap();
      await page.locator('#export-poster').tap();
      await page.locator('.creator-save-dialog[open]').waitFor({timeout:90000});
      await page.locator('.poster-save-image').evaluate(image => image.decode());
      assert.ok(await page.locator('.poster-save-image').evaluate(image => image.naturalWidth === 1200 && image.naturalHeight === 1600));
      assert.ok(await page.locator('.creator-save-dialog').evaluate(dialog => /^rgb\(/.test(getComputedStyle(dialog).backgroundColor)), 'save panel must have an opaque background');
      await fits(page);
      await page.screenshot({path:`${out}/mobile-${name}-${layout}-save.png`});
      const pending = page.waitForEvent('download');
      await page.locator('[data-save-download]').tap();
      const download = await pending;
      assert.equal(await download.failure(), null);
      const path = `${out}/mobile-${name}-${material}-${layout}.png`;
      await download.saveAs(path);
      const png = PNG.sync.read(fs.readFileSync(path));
      assert.equal(png.width,1200); assert.equal(png.height,1600);
      await page.locator('[data-save-close]').tap();
      await page.waitForFunction(() => document.activeElement === document.querySelector('#export-poster'));
    }
    await page.reload();
    await page.waitForFunction(() => document.querySelector('.fp-unit'));
    assert.equal(await page.locator('#deck-name').inputValue(), '时光手札 · 手机端构筑');
    assert.ok(await page.locator('.fortune-poster').evaluate((poster,material) => poster.classList.contains(`theme-${material}`),material));
    assert.deepEqual(errors, []);
    await browser.close();
    console.log(`${name}: touch charts/tables/themes, device search metrics, editor, two ${material} PNG exports and draft restore passed`);
  }
})().catch(error => { console.error(error); process.exit(1); });
