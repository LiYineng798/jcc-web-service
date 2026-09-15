// Run against tests/serve_admin_season_picker_preview.py, never production.
const { chromium, webkit } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.ADMIN_SEASON_PICKER_PREVIEW_URL || 'http://127.0.0.1:5115';
const out = 'instance/season-picker-checks';

(async () => {
  fs.mkdirSync(out, { recursive: true });
  for (const [engineName, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch();
    try {
      for (const width of [320, 390, 1440]) {
        const mobile = width < 820;
        const context = await browser.newContext({ viewport: { width, height: 900 }, isMobile: mobile, hasTouch: mobile });
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        await page.addInitScript(() => {
          const bindings = new WeakMap();
          window.duplicatePickerBinding = false;
          window.pickerDocumentSignals = [];
          const add = EventTarget.prototype.addEventListener;
          EventTarget.prototype.addEventListener = function (type, listener, options) {
            if (type === 'click' && /^(liveUpload|lineupBulkImport)SeasonToggle$/.test(this.id || '')) {
              const count = (bindings.get(this) || 0) + 1;
              bindings.set(this, count);
              if (count > 1) window.duplicatePickerBinding = true;
            }
            if (this === document && ['click', 'pointerdown', 'focusin'].includes(type) && options?.signal) {
              window.pickerDocumentSignals.push(options.signal);
            }
            return add.call(this, type, listener, options);
          };
        });
        const act = locator => mobile ? locator.tap() : locator.click();
        async function dismissNotices() {
          // Screenshot preparation only: avoid racing a toast's own expiry animation.
          await page.getByRole('button', { name: '关闭通知', exact: true })
            .evaluateAll(buttons => buttons.forEach(button => button.click()));
        }
        async function navigate(workspace) {
          if (mobile) {
            await act(page.locator('#adminMoreButton'));
            await act(page.locator(`#adminMoreDialog [data-admin-workspace="${workspace}"]`));
          } else {
            const group = workspace === 'import' ? 'lineups' : 'live-comps';
            const target = page.locator(`.admin-sidebar [data-admin-workspace="${workspace}"]`);
            if (!(await target.isVisible())) await act(page.locator(`.admin-sidebar [data-admin-nav-toggle="${group}"]`));
            await act(target);
          }
        }
        const toggle = prefix => page.locator(`#${prefix}SeasonToggle`);
        const menu = prefix => page.locator(`#${prefix}SeasonMenu`);
        async function checkOpen(prefix, target = toggle(prefix)) {
          await act(target);
          assert.equal(await toggle(prefix).getAttribute('aria-expanded'), 'true');
          assert(await menu(prefix).isVisible(), `${engineName}/${width}/${prefix}: menu must stay open`);
        }
        async function choose(prefix, label) {
          await checkOpen(prefix);
          await act(menu(prefix).getByRole('menuitemradio', { name: label, exact: true }));
          assert.equal(await toggle(prefix).getAttribute('aria-expanded'), 'false');
          assert.equal(await page.evaluate(() => document.activeElement.id), `${prefix}SeasonToggle`);
        }
        async function bounds(prefix) {
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'page overflow');
          const box = await menu(prefix).boundingBox();
          assert(box.x >= 0 && box.x + box.width <= width + 1, 'menu overflow');
          if (mobile) {
            assert((await toggle(prefix).boundingBox()).height >= 44, 'touch trigger too small');
            assert((await menu(prefix).getByRole('menuitemradio').first().boundingBox()).height >= 44, 'touch option too small');
          }
        }

        await page.goto(`${base}/__preview/login`);
        await page.waitForFunction(() => document.querySelector('#adminApp')?.children.length > 0
          && !document.querySelector('#adminApp').classList.contains('admin-app-loading'));
        await navigate('upload');
        await page.waitForFunction(() => !document.querySelector('#liveUploadSeasonToggle')?.disabled);
        assert(await page.getByRole('button', { name: '解析并预览', exact: true }).isDisabled());
        await checkOpen('liveUpload'); // Regression: no JSON file selected yet.
        assert(await menu('liveUpload').getByText('验收用隐藏赛季', { exact: true }).isVisible());
        await page.keyboard.press('Escape');
        assert.equal(await toggle('liveUpload').getAttribute('aria-expanded'), 'false');
        await choose('liveUpload', 'S17 · 星神');
        const payload = { meta: { source: 'fictional-browser-check' }, tiers: {
          S: [{ id: 'preview-new', title: '浏览器验收阵容', tier: 'S', jccCode: '#BrowserPreview001',
            mainAvatar: '/api/live-comps/assets/preview.png', heroImages: ['/api/live-comps/assets/preview.png'] }], A: [], B: [], C: [], D: [],
        } };
        await page.locator('.live-upload-file-input').setInputFiles({ name: 'fixture.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(payload)) });
        assert.equal(await page.locator('#liveUploadSeasonInput').inputValue(), 's17-star-god');
        const previewResponse = page.waitForResponse(r => r.url().endsWith('/api/admin/live-comps/uploads/preview'));
        await act(page.getByRole('button', { name: '解析并预览', exact: true }));
        const livePreview = await (await previewResponse).json();
        assert.equal(livePreview.season_id, 's17-star-god', JSON.stringify(livePreview));
        await page.getByRole('button', { name: '确认并发布', exact: true }).waitFor();
        // Success notices and finally blocks used to schedule duplicate bindings too.
        await choose('liveUpload', 'S17 · 星神');
        assert(await page.getByRole('button', { name: '确认并发布', exact: true }).isVisible());
        await choose('liveUpload', 'S18 · 仙灵');
        assert.equal(await page.getByRole('button', { name: '确认并发布', exact: true }).count(), 0);
        assert.equal(await page.locator('.live-upload-file-name').textContent(), 'fixture.json');
        await dismissNotices();
        for (const theme of ['light', 'dark']) {
          await page.evaluate(value => document.documentElement.dataset.theme = value, theme);
          await checkOpen('liveUpload', page.locator('#liveUploadSeasonToggle .account-chevron'));
          await bounds('liveUpload');
          await page.screenshot({ path: `${out}/${engineName}-upload-${theme}-${width}.png` });
          await act(page.getByRole('heading', { name: '数据上传', exact: true }));
          assert.equal(await toggle('liveUpload').getAttribute('aria-expanded'), 'false');
        }

        await navigate('import');
        await page.waitForFunction(() => !document.querySelector('#lineupBulkImportSeasonToggle')?.disabled);
        assert.equal(await toggle('lineupBulkImport').evaluate(el => el.closest('label')), null);
        await checkOpen('lineupBulkImport', page.getByText('导入赛季', { exact: true }));
        assert.equal(await menu('lineupBulkImport').getByText('验收用隐藏赛季', { exact: true }).count(), 0);
        await act(page.getByText('导入赛季', { exact: true }));
        assert.equal(await toggle('lineupBulkImport').getAttribute('aria-expanded'), 'false');
        await checkOpen('lineupBulkImport', page.getByText('导入赛季', { exact: true }));
        await page.keyboard.press('Escape');
        const raw = `【阵容码】#验收-${engineName}${width}#Browser${engineName}${width}${Date.now()}`;
        await page.locator('#lineupBulkImportRawText').fill(raw);
        await choose('lineupBulkImport', 'S17 · 星神');
        assert.equal(await page.locator('#lineupBulkImportRawText').inputValue(), raw);
        const bulkResponse = page.waitForResponse(r => r.url().endsWith('/api/admin/lineups/bulk-import/preview'));
        await act(page.getByRole('button', { name: '解析阵容码', exact: true }));
        const bulkPreview = await (await bulkResponse).json();
        assert.equal(bulkPreview.season_id, 's17-star-god');
        assert.equal(bulkPreview.importable_count, 1);
        await page.getByRole('button', { name: '确认导入', exact: true }).waitFor();
        await choose('lineupBulkImport', 'S18 · 仙灵');
        assert.equal(await page.getByRole('button', { name: '确认导入', exact: true }).count(), 0);
        await act(page.getByRole('button', { name: '解析阵容码', exact: true }));
        await page.getByRole('button', { name: '确认导入', exact: true }).waitFor();
        page.once('dialog', dialog => dialog.accept());
        const importedResponse = page.waitForResponse(r => r.url().endsWith('/api/admin/lineups/bulk-import'));
        await act(page.getByRole('button', { name: '确认导入', exact: true }));
        const imported = await (await importedResponse).json();
        assert.equal(imported.season_id, 's18');
        assert.equal(imported.created_count, 1);
        await page.getByText('已写入普通阵容库', { exact: true }).waitFor();

        for (let i = 0; i < 3; i++) {
          await navigate('upload');
          await checkOpen('liveUpload');
          await navigate('import'); // Cache-hit path: two renders in one event loop.
          await checkOpen('lineupBulkImport');
          await page.keyboard.press('Escape');
        }
        assert.equal(await page.locator('#lineupBulkImportRawText').inputValue(), raw);
        // Keyboard changes, dismissal and next-field navigation.
        await toggle('lineupBulkImport').focus();
        await page.keyboard.press('ArrowDown');
        const lastName = await menu('lineupBulkImport').getByRole('menuitemradio').last().textContent();
        const manifest = await (await context.request.get(`${base}/api/lineup-seasons`)).json();
        const lastId = manifest.seasons.find(season => season.name === lastName).id;
        await page.keyboard.press('End');
        await page.keyboard.press('Enter');
        assert.equal(await page.locator('#lineupBulkImportSeasonInput').inputValue(), lastId);
        await page.keyboard.press('ArrowUp');
        await page.keyboard.press('Tab');
        assert.equal(await toggle('lineupBulkImport').getAttribute('aria-expanded'), 'false');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'lineupBulkImportRawText');
        await dismissNotices();
        for (const theme of ['light', 'dark']) {
          await page.evaluate(value => document.documentElement.dataset.theme = value, theme);
          await checkOpen('lineupBulkImport', page.locator('#lineupBulkImportSeasonToggle span'));
          await bounds('lineupBulkImport');
          await page.screenshot({ path: `${out}/${engineName}-import-${theme}-${width}.png` });
          await page.keyboard.press('Escape');
        }
        assert.equal(await page.evaluate(() => window.duplicatePickerBinding), false);
        assert.equal(await page.evaluate(() => window.pickerDocumentSignals.filter(s => !s.aborted).length), 3, 'old document listeners must be aborted');
        assert.deepEqual(errors, []);
        await context.close();
        console.log(`PASS ${engineName} ${width}: initial/cached navigation, uploads, imports, state, keyboard, themes and listener cleanup`);
      }
      // Boot/navigation can both await the manifest; file selection may precede it.
      const context = await browser.newContext({ viewport: { width: 390, height: 900 }, isMobile: true, hasTouch: true });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      let releaseManifest;
      const gate = new Promise(resolve => { releaseManifest = resolve; });
      await page.route('**/api/admin/live-comps/seasons', async route => { await gate; await route.continue(); });
      await page.goto(`${base}/__preview/login`);
      await page.locator('#adminMoreButton').tap();
      await page.locator('#adminMoreDialog [data-admin-workspace="upload"]').tap();
      assert(await page.locator('#liveUploadSeasonToggle').isDisabled());
      const sample = await (await context.request.get(`${base}/__preview/sample.json`)).body();
      await page.locator('.live-upload-file-input').setInputFiles({ name: 'slow-boot.json', mimeType: 'application/json', buffer: sample });
      releaseManifest();
      await page.waitForFunction(() => !document.querySelector('#liveUploadSeasonToggle').disabled);
      await page.locator('#liveUploadSeasonToggle').tap();
      assert.equal(await page.locator('#liveUploadSeasonToggle').getAttribute('aria-expanded'), 'true');
      await page.locator('#liveUploadSeasonMenu').getByRole('menuitemradio', { name: 'S17 · 星神', exact: true }).tap();
      assert.equal(await page.locator('.live-upload-file-name').textContent(), 'slow-boot.json');
      // An upload failure must leave the form and its dropdown usable for retry.
      await page.route('**/api/admin/live-comps/uploads/preview', route => route.fulfill({
        status: 400, contentType: 'application/json', body: JSON.stringify({ error: '验收用失败，请重试' }),
      }));
      await page.getByRole('button', { name: '解析并预览', exact: true }).tap();
      await page.getByText('验收用失败，请重试', { exact: true }).waitFor();
      await page.locator('#liveUploadSeasonToggle').tap();
      assert.equal(await page.locator('#liveUploadSeasonToggle').getAttribute('aria-expanded'), 'true');
      await page.keyboard.press('Escape');
      await page.unroute('**/api/admin/live-comps/uploads/preview');
      await page.getByRole('button', { name: '解析并预览', exact: true }).tap();
      await page.getByRole('button', { name: '确认并发布', exact: true }).tap();
      await page.getByText('发布完成 · 100%', { exact: true }).waitFor();
      await page.locator('#liveUploadSeasonToggle').tap();
      assert.equal(await page.locator('#liveUploadSeasonToggle').getAttribute('aria-expanded'), 'true');
      await page.keyboard.press('Escape');
      // An empty season list has an explicit disabled state, never a dead button.
      await page.route('**/api/lineup-seasons', route => route.fulfill({
        contentType: 'application/json', body: JSON.stringify({ default_season_id: '', seasons: [] }),
      }));
      await page.locator('#adminMoreButton').tap();
      await page.locator('#adminMoreDialog [data-admin-workspace="import"]').tap();
      await page.getByText('暂无可用赛季', { exact: true }).waitFor();
      assert(await page.locator('#lineupBulkImportSeasonToggle').isDisabled());
      assert(await page.getByRole('button', { name: '解析阵容码', exact: true }).isDisabled());
      assert.deepEqual(errors, []);
      await context.close();
      console.log(`PASS ${engineName}: delayed manifest, file preservation, failed preview retry, real worker publication and empty list`);
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exit(1); });
