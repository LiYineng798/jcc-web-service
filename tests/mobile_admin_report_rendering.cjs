// Run against serve_mobile_admin_report_preview.py; only fictional local data.
const {chromium, webkit} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.MOBILE_ADMIN_REPORT_PREVIEW_URL || 'http://127.0.0.1:5127';
const out = 'instance/mobile-admin-report-preview/screenshots';
fs.mkdirSync(out, {recursive: true});

(async () => {
  for (const [engineName, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch();
    try {
      for (const [mode, stored] of [['default', null], ['saved-text', 'text'], ['invalid', 'invalid']]) {
        const context = await browser.newContext({viewport: {width: 390, height: 844}});
        if (stored !== null) await context.addInitScript(value => localStorage.setItem('homeImageMode', value), stored);
        const page = await context.newPage();
        const errors = []; page.on('pageerror', e => errors.push(e.message));
        await page.goto(base);
        await page.locator('.live-comp-card').first().waitFor();
        assert.equal(await page.locator('#imageModeText').textContent(), stored === 'text' ? '无图' : '有图');
        assert.equal(await page.locator('.live-comp-card-text-only').count(), stored === 'text' ? 6 : 0);
        if (stored !== 'text') {
          const portrait = page.locator('.live-comp-avatar').first();
          await portrait.scrollIntoViewIfNeeded();
          await page.waitForFunction(() => {
            const image = document.querySelector('.live-comp-avatar');
            return image?.complete && image.naturalWidth > 0;
          });
          await page.locator('.nav-bar').scrollIntoViewIfNeeded();
        }
        if (mode === 'default') {
          await page.locator('#imageModeToggle').click();
          assert.equal(await page.locator('.live-comp-card-text-only').count(), 6);
          await page.reload();
          await page.locator('.live-comp-card-text-only').first().waitFor();
          assert.equal(await page.locator('#imageModeText').textContent(), '无图');
          await page.locator('#imageModeToggle').click();
          await page.locator('#mobileResourceTrigger').click();
          assert.equal(await page.locator('#mobileResourceDialog').evaluate(el => el.open), true);
          await page.keyboard.press('Escape');
          await page.locator('#mobileResourceDialog').waitFor({state: 'hidden'});
          await page.waitForFunction(() => document.querySelector('#mobileResourceTrigger').getAttribute('aria-expanded') === 'false');
          await page.locator('#imageModeToggle').press('Enter');
          await page.waitForFunction(() => document.querySelector('#imageModeText').textContent === '无图');
          assert.equal(await page.locator('#imageModeText').textContent(), '无图');
          await page.locator('#imageModeToggle').press('Enter');
          await page.waitForFunction(() => document.querySelector('#imageModeText').textContent === '有图');
          for (const width of [320, 390, 520]) {
            await page.setViewportSize({width, height: 844});
            for (const theme of ['light', 'dark']) {
              await page.evaluate(value => document.documentElement.dataset.theme = value, theme);
              const box = await page.locator('#imageModeToggle').boundingBox();
              assert.equal(Math.round(box.width), 72);
              assert.ok(Math.round(box.height) >= 44);
              assert.ok(box.x + box.width <= width);
              const resource = await page.locator('#mobileResourceTrigger').boundingBox();
              assert.ok(resource.x + resource.width <= box.x, `overlapping navigation at ${width}`);
              assert.ok(Math.abs(box.x - resource.x - resource.width - 8) <= 1, `button group gap at ${width}`);
              assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
              if (width === 390) await page.screenshot({path: `${out}/${engineName}-mobile-${theme}.png`, animations: 'disabled'});
            }
          }
        }
        assert.deepEqual(errors, []);
        await context.close();
      }

      const restricted = await browser.newContext({viewport: {width: 390, height: 844}});
      await restricted.addInitScript(() => {
        Storage.prototype.getItem = function () {throw new DOMException('Blocked', 'SecurityError');};
        Storage.prototype.setItem = function () {throw new DOMException('Blocked', 'SecurityError');};
      });
      const restrictedPage = await restricted.newPage();
      const restrictedErrors = []; restrictedPage.on('pageerror', e => restrictedErrors.push(e.message));
      await restrictedPage.goto(base);
      await restrictedPage.locator('.live-comp-card').first().waitFor();
      assert.equal(await restrictedPage.locator('#imageModeText').textContent(), '有图');
      await restrictedPage.locator('#imageModeToggle').click();
      assert.equal(await restrictedPage.locator('#imageModeText').textContent(), '无图');
      assert.deepEqual(restrictedErrors, []);
      await restricted.close();

      const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
      assert.equal((await context.request.post(base + '/api/login', {
        headers: {'X-Forwarded-For': `192.0.2.${(process.pid % 200) + (engineName === 'webkit' ? 2 : 1)}`},
        data: {account: 'previewadmin', password: 'Preview1234'},
      })).status(), 200);
      const page = await context.newPage();
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      await page.goto(base);
      await page.locator('#lineupNotificationRoot:not([hidden])').waitFor();
      for (const width of [320, 390, 520]) {
        await page.setViewportSize({width, height: 844});
        const controls = await Promise.all(['#imageModeToggle', '#mobileResourceTrigger', '#accountToggle', '#lineupNotificationToggle', '.nav-actions > .animated-theme-toggle'].map(selector => page.locator(selector).boundingBox()));
        for (const box of controls) assert.ok(box.width > 0 && box.x >= 0 && box.x + box.width <= width);
        for (let i = 0; i < controls.length; i++) for (let j = i + 1; j < controls.length; j++) {
          const a = controls[i], b = controls[j];
          assert.ok(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y, `controls overlap at ${width}`);
        }
        if (width === 390) {
          await page.screenshot({path: `${out}/${engineName}-mobile-admin.png`, animations: 'disabled'});
          await page.locator('.nav-bar').screenshot({path: `${out}/${engineName}-mobile-nav.png`, animations: 'disabled'});
        }
      }
      await page.setViewportSize({width: 1440, height: 1000});
      await page.goto(base + '/admin');
      // Hold the initial request until the user chooses score sorting. This
      // reproduces a canceled navigation load on a slow connection.
      let releaseInitial, markInitialHeld;
      const initialHeld = new Promise(resolve => {markInitialHeld = resolve;});
      const release = new Promise(resolve => {releaseInitial = resolve;});
      let held = false;
      await page.route('**/api/admin/lineups?**', async route => {
        if (!held && new URL(route.request().url()).searchParams.get('order') === 'newest') {
          held = true;
          const response = await context.request.get(route.request().url());
          markInitialHeld();
          await release;
          try { await route.fulfill({response}); } catch (_) { /* Request was canceled by the new filter. */ }
        } else await route.continue();
      });
      await page.locator('.admin-sidebar [data-admin-nav-toggle="lineups"]').click();
      await page.locator('.admin-sidebar [data-admin-tab="lineups"][data-admin-workspace="list"]').click();
      await initialHeld;
      await Promise.all([
        page.waitForResponse(r => r.url().includes('/api/admin/lineups?') && r.url().includes('score_desc') && r.status() === 200),
        page.locator('select[aria-label="阵容排序"]').selectOption('score_desc'),
      ]);
      releaseInitial();
      await page.locator('.lm-stats strong').first().waitFor();
      await page.unroute('**/api/admin/lineups?**');
      await Promise.all([
        page.waitForResponse(r => r.url().includes('/api/admin/lineups?') && r.url().includes('season=s11-inkborn-fables') && r.status() === 200),
        page.locator('select[aria-label="筛选赛季"]').selectOption('s11-inkborn-fables'),
      ]);
      const scores = await page.locator('.lm-stats strong').allTextContents();
      const values = scores.map(text => Number(text.replace('分 ', '')));
      assert.equal(await page.locator('select[aria-label="阵容排序"]').inputValue(), 'score_desc');
      assert.deepEqual(values, [...values].sort((a,b) => b-a));
      await page.screenshot({path: `${out}/${engineName}-admin-score.png`, animations: 'disabled'});
      await page.locator('.admin-sidebar [data-admin-tab="daily-reports"]').click();
      await page.locator('.admin-ip-row').first().waitFor();
      await page.locator('.daily-report-detail-grid > :first-child').screenshot({path: `${out}/${engineName}-daily-pages.png`, animations: 'disabled'});
      assert.equal(await page.locator('.admin-ip-row').count(), 3);
      assert.ok((await page.locator('.daily-ip-page').allTextContents()).some(text => text.includes('实时阵容站位详情')));
      assert.ok(!(await page.locator('.admin-daily-reports').textContent()).includes('live_comp_detail'));
      const detail = page.locator('.daily-ip-details').first();
      await detail.locator('summary').click();
      assert.equal(await detail.evaluate(el => el.open), true);
      assert.equal(await detail.locator('li').count(), 10);
      await page.locator('.admin-ip-row').first().scrollIntoViewIfNeeded();
      await page.screenshot({path: `${out}/${engineName}-daily-ip.png`, animations: 'disabled'});
      await page.evaluate(() => document.documentElement.dataset.theme = 'dark');
      await page.waitForFunction(() => getComputedStyle(document.body).color === 'rgb(243, 238, 230)');
      await page.screenshot({path: `${out}/${engineName}-daily-ip-dark.png`, animations: 'disabled'});
      await page.setViewportSize({width: 390, height: 844});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.locator('.admin-ip-row').first().scrollIntoViewIfNeeded();
      await page.screenshot({path: `${out}/${engineName}-daily-ip-mobile.png`, animations: 'disabled'});
      assert.deepEqual(errors, []);
      await context.close();
      console.log(`${engineName}: mobile image preferences/layout, score sorting, daily IP details passed`);
    } finally { await browser.close(); }
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
