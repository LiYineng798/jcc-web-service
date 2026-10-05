const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium, webkit } = require('playwright');

const base = process.env.S11_ARTIFACTS_PREVIEW_URL || 'http://127.0.0.1:5171';
const route = '/tools/s11-artifacts';
const output = path.resolve(__dirname, '../instance/s11-artifacts-preview');
fs.mkdirSync(output, { recursive: true });

(async () => {
  for (const [engine, launcher] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await launcher.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();
    const errors = [];
    const failedRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => { if (response.status() >= 400) failedRequests.push(`${response.status()} ${response.url()}`); });
    for (const theme of ['light', 'dark']) {
      for (const width of [320, 375, 768, 1280, 1440]) {
        await page.setViewportSize({ width, height: 980 });
        await page.goto(base + route);
        await page.evaluate(theme => { localStorage.setItem('theme', theme); }, theme);
        await page.reload();
        assert.equal(await page.locator('.artifact-card:visible').count(), 31);
        assert.equal(await page.locator('.artifact-champion').count(), 124);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${engine} ${theme} ${width}: overflow`);
        assert.equal(await page.evaluate(() => [...document.images].every(image => image.src.startsWith(location.origin + '/static/s11-artifacts/'))), true);
        const colors = await page.evaluate(() => {
          const values = {};
          for (const badge of document.querySelectorAll('.artifact-cost')) values[badge.textContent] = getComputedStyle(badge).backgroundColor;
          return values;
        });
        assert.deepEqual(colors, { '1': 'rgb(131, 130, 134)', '2': 'rgb(84, 157, 82)', '3': 'rgb(90, 132, 214)', '4': 'rgb(229, 86, 188)', '5': 'rgb(234, 138, 56)' });
        const portrait = await page.locator('.artifact-portrait').first().boundingBox();
        const badge = await page.locator('.artifact-cost').first().boundingBox();
        assert.equal(portrait.x, badge.x); assert.equal(portrait.y, badge.y);
        await page.locator('.toolbox-trigger').press('Enter');
        const panel = await page.locator('.toolbox-panel').boundingBox();
        assert(panel.x >= 0 && panel.x + panel.width <= width, `${width}: toolbox outside viewport`);
        assert.equal(await page.locator(`.toolbox-panel a[href="${route}"]`).count(), 1);
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('.toolbox-menu').getAttribute('open'), null);
        await page.locator('#artifactQuery').fill('阿兹尔');
        assert.equal(await page.locator('.artifact-card:visible').count(), 5);
        assert.match(page.url(), /q=/);
        await page.locator('#artifactQuery').fill('沙皇');
        assert.equal(await page.locator('.artifact-card:visible').count(), 5);
        await page.locator('#artifactQuery').fill('飞升');
        await page.locator('button[name="cost"][value="5"]').click();
        assert.equal(await page.locator('.artifact-card:visible').count(), 0);
        assert(await page.locator('#artifactEmpty').isVisible());
        await page.locator('button[name="cost"][value="1"]').click();
        assert.equal(await page.locator('.artifact-card:visible').count(), 1);
        assert.equal(await page.locator('#artifactCost').inputValue(), '1');
        await page.reload();
        assert.equal(await page.locator('.artifact-card:visible').count(), 1);
        await page.locator('#artifactReset').click();
        assert.equal(await page.locator('.artifact-card:visible').count(), 31);
        await page.locator('.artifact-champion[data-champion="洛"]').first().click();
        assert.equal(await page.locator('#artifactQuery').inputValue(), '洛');
        assert.equal(await page.locator('.artifact-card:visible').count(), 2);
        await page.locator('#artifactReset').click();
        await page.locator('#themeToggle').click();
        assert.equal(await page.locator('html').getAttribute('data-theme'), theme === 'light' ? 'dark' : 'light');
        await page.locator('#themeToggle').click();
        await page.evaluate(() => scrollTo(0, 0));
        await page.evaluate(() => Promise.all([...document.images].filter(img => img.loading === 'eager').map(img => img.decode().catch(() => {}))));
        if (engine === 'chromium' && [375, 1440].includes(width)) {
          await page.screenshot({ path: `${output}/${theme}-${width}.png`, animations: 'disabled' });
        }
      }
    }
    await page.goto(base + route);
    await page.evaluate(() => {
      const input = document.querySelector('#artifactQuery');
      input.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
      input.value = '孙悟空';
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    assert.equal(await page.locator('.artifact-card:visible').count(), 31);
    await page.evaluate(() => document.querySelector('#artifactQuery').dispatchEvent(new CompositionEvent('compositionend', { bubbles: true })));
    assert.equal(await page.locator('.artifact-card:visible').count(), 8);
    // Search remains available using regular HTML GET forms without JavaScript.
    const plain = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 375, height: 900 } });
    const nojs = await plain.newPage();
    await nojs.goto(base + route + '?q=飞升&cost=1');
    assert.equal(await nojs.locator('.artifact-card:visible').count(), 1);
    await nojs.locator('#artifactQuery').fill('可酷伯');
    await Promise.all([nojs.waitForNavigation(), nojs.locator('.artifacts-search-submit').click()]);
    assert.equal(await nojs.locator('.artifact-card:visible').count(), 1);
    assert.match(nojs.url(), /cost=1/);
    await Promise.all([nojs.waitForNavigation(), nojs.locator('button[name="cost"][value="5"]').click()]);
    assert.equal(await nojs.locator('.artifact-card:visible').count(), 0);
    await Promise.all([nojs.waitForNavigation(), nojs.locator('.artifacts-empty-reset').click()]);
    assert.equal(await nojs.locator('.artifact-card:visible').count(), 31);
    assert.deepEqual(errors, [], engine + ': page errors');
    assert.deepEqual(failedRequests, [], engine + ': failed assets');
    await browser.close();
    console.log(`PASS ${engine}: 5 widths × 2 themes, local images, costs, search, aliases, IME, toolbox, no-JS forms`);
  }
})().catch(error => { console.error(error); process.exit(1); });
