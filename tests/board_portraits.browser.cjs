// Run against the isolated preview, never production. Playwright is optional tooling.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium, webkit, devices } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.BOARD_PREVIEW_URL || 'http://127.0.0.1:5069';
const out = process.env.BOARD_SCREENSHOT_DIR;

async function checkPortraits(page, selector, inset) {
  const results = await page.locator(selector).evaluateAll(images => images.map(img => {
    const crop = img.parentElement;
    const outer = crop.parentElement;
    const a = img.getBoundingClientRect(), b = crop.getBoundingClientRect(), c = outer.getBoundingClientRect();
    const style = getComputedStyle(img);
    return { loaded: img.complete && img.naturalWidth > 0,
      dx: a.x - b.x, dy: a.y - b.y, dw: a.width - b.width, dh: a.height - b.height,
      inset: b.y - c.y, clip: style.clipPath, transform: style.transform,
      outerFilter: getComputedStyle(outer).filter, cropClip: getComputedStyle(crop).clipPath };
  }));
  assert.ok(results.length);
  for (const r of results) {
    assert.equal(r.loaded, true);
    for (const key of ['dx', 'dy', 'dw', 'dh']) assert.ok(Math.abs(r[key]) < .1, JSON.stringify(r));
    assert.ok(Math.abs(r.inset - inset) < .1);
    assert.equal(r.clip, 'none'); assert.equal(r.transform, 'none'); assert.equal(r.outerFilter, 'none');
    assert.ok(r.cropClip.startsWith('polygon('));
  }
}

(async () => {
  if (out) fs.mkdirSync(out, { recursive: true });
  for (const [name, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch({ headless: true, ...(name === 'chromium' && process.env.CHROMIUM_CHANNEL ? {channel: process.env.CHROMIUM_CHANNEL} : {}) });
    for (const mobile of [false, true]) {
      const page = await browser.newPage(mobile ? devices['iPhone 13'] : { viewport: {width:1440,height:1000} });
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      await page.goto(`${base}/live-comps/s17-star-god/portrait-preview`);
      await page.locator('.formation-portrait img').first().waitFor();
      await page.locator('.formation-portrait img').evaluateAll(imgs => Promise.all(imgs.map(i => i.decode())));
      await checkPortraits(page, '.formation-portrait img', 3);
      if (out) await page.locator('.formation-board').screenshot({path:path.join(out,`${name}-${mobile}-live.png`)});
      await page.goto(`${base}/tools/lineup-simulator`);
      await page.locator('.hero-button:not(.is-locked)').first().click();
      await page.locator('.unit-portrait-image').first().evaluate(i => i.decode());
      await checkPortraits(page, '.hex-board .unit-portrait-image', 3);
      if (out) await page.locator('.hex-board').screenshot({path:path.join(out,`${name}-${mobile}-sim.png`)});
      if (!mobile) {
        const source = page.locator('.hex-cell.has-unit').first();
        const target = page.locator('.hex-cell:not(.has-unit)').nth(8);
        await source.dragTo(target);
        await checkPortraits(page, '.hex-board .unit-portrait-image', 3);
        await page.locator('#undoButton').click();
        await checkPortraits(page, '.hex-board .unit-portrait-image', 3);
        await page.locator('#exportImageButton').click();
        const wide = page.waitForEvent('download', {timeout:90000});
        await page.locator('#confirmExportImageButton').click();
        const download = await wide;
        assert.equal(await download.failure(), null);
        if (out) await download.saveAs(path.join(out, `${name}-wide.png`));
      }
      await page.locator('#exportPosterButton').click();
      const poster = page.waitForEvent('download', {timeout:90000});
      await page.locator('#confirmExportPosterButton').click();
      const download = await poster;
      assert.equal(await download.failure(), null);
      if (out) await download.saveAs(path.join(out, `${name}-${mobile}-poster.png`));
      assert.deepEqual(errors, []);
      console.log(`${name} mobile=${mobile}: portraits, interactions and exports passed`);
      await page.close();
    }
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
