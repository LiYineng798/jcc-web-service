// Run only against tests/serve_live_versions_preview.py.
const { chromium, webkit } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.LIVE_VERSIONS_PREVIEW_URL || 'http://127.0.0.1:5127';
const out = 'instance/live-versions-checks';
fs.mkdirSync(out, { recursive: true });

(async () => {
  for (const [engineName, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch();
    try {
      for (const width of [1440, 390, 320]) {
        const context = await browser.newContext({ viewport: { width, height: 1000 } });
        const page = await context.newPage(); const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(base + '/__preview/login');
        await page.waitForFunction(() => document.querySelector('#adminIdentityName') || document.querySelector('.admin-identity-copy strong')?.textContent);
        async function navigate() {
          if (width < 820) {
            await page.locator('#adminMoreButton').click();
            await page.locator('#adminMoreDialog [data-admin-workspace="upload"]').click();
          } else {
            await page.locator('.admin-sidebar [data-admin-nav-toggle="live-comps"]').click();
            await page.locator('.admin-sidebar [data-admin-workspace="upload"]').click();
          }
          await page.locator('#liveVersionPreviewTitle').waitFor();
        }
        await navigate();
        const original = await page.locator('#liveVersionPreviewTitle').innerText();
        const marker = `${engineName}-${width}-${Date.now()}.json`;
        const sample = await (await context.request.get(base + '/__preview/sample.json')).json();
        await page.locator('input[type=file]').setInputFiles({ name: marker, mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(sample)) });
        await page.getByRole('button', { name: '解析并预览', exact: true }).click();
        await page.getByRole('button', { name: '保存为预上线版本', exact: true }).click();
        await page.locator('#liveVersionPreviewTitle').filter({ hasText: marker }).waitFor({ timeout: 30000 });
        assert.match(await page.locator('.live-version-preview .live-version-badge').innerText(), /预上线/);
        const before = await (await context.request.get(base + '/api/live-comps')).json();
        await page.getByLabel('只看缺码', { exact: true }).check();
        assert.equal(await page.locator('.live-version-comp').count(), 3);
        await page.getByRole('button', { name: '补充阵容码', exact: true }).first().click();
        await page.getByRole('dialog').getByLabel('金铲铲阵容码').fill('#BROWSERDEMO');
        await page.getByRole('button', { name: '保存补码', exact: true }).click();
        await page.getByRole('dialog').waitFor({ state: 'detached' });
        assert.equal(await page.locator('.live-version-comp').count(), 2);
        const stillLive = await (await context.request.get(base + '/api/live-comps')).json();
        assert.deepEqual(stillLive.items, before.items);
        await page.getByRole('button', { name: '上线此版本', exact: true }).click();
        assert(await page.getByRole('button', { name: '确认切换线上版本', exact: true }).isDisabled());
        await page.getByRole('dialog').locator('input[type=checkbox]').check();
        await page.getByRole('button', { name: '确认切换线上版本', exact: true }).click();
        await page.getByRole('dialog').waitFor({ state: 'detached' });
        assert.equal(await page.locator('.live-version-preview .live-version-badge').innerText(), '当前线上');
        assert.equal(await page.getByRole('button', { name: '删除版本', exact: true }).count(), 0);
        await page.locator('.live-version-row').filter({ hasText: original }).click();
        await page.getByRole('button', { name: '回滚到此版本', exact: true }).click();
        await page.getByRole('button', { name: '确认切换线上版本', exact: true }).click();
        await page.getByRole('dialog').waitFor({ state: 'detached' });
        const rolledBack = await (await context.request.get(base + '/api/live-comps')).json();
        assert.deepEqual(rolledBack.items, before.items);
        await page.locator('.live-version-row').filter({ hasText: marker }).click();
        await page.getByRole('button', { name: '删除版本', exact: true }).click();
        await page.getByRole('button', { name: '确认删除', exact: true }).click();
        await page.getByRole('dialog').waitFor({ state: 'detached' });
        assert.equal(await page.locator('.live-version-row').filter({ hasText: marker }).count(), 0);
        await page.locator('.live-version-row').filter({ hasText: '10-15_待补码榜单_演示.json' }).click();
        await page.getByLabel('只看缺码', { exact: true }).uncheck();
        await page.locator('#liveVersionPreviewTitle').waitFor();
        await page.getByRole('button', { name: '关闭通知', exact: true }).evaluateAll(nodes => nodes.forEach(node => node.click()));
        for (const theme of ['light', 'dark']) {
          await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
          await page.locator('.live-version-library').scrollIntoViewIfNeeded();
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${engineName}/${width} overflow`);
          await page.screenshot({ path: `${out}/${engineName}-${width}-${theme}.png` });
        }
        await page.getByRole('button', { name: '补充阵容码', exact: true }).first().click();
        await page.keyboard.press('Escape');
        await page.getByRole('dialog').waitFor({ state: 'detached' });
        assert.equal(await page.getByRole('dialog').count(), 0);
        assert.deepEqual(errors, []);
        console.log(`${engineName} ${width}: upload, staged code, publish, rollback, delete, themes, keyboard passed`);
        await context.close();
      }
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exit(1); });
