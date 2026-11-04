/* Exercise a ready, local-only time-card package. Always restore the previous live release. */
const { chromium, webkit } = require('playwright-core');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const base = process.env.DECK_REVIEW_URL || 'http://127.0.0.1:5137';
const rid = JSON.parse(fs.readFileSync('instance/deck-review-preview/time-card-package.json', 'utf8')).id;
const shots = 'instance/deck-review-preview/screenshots';

(async () => {
  for (const [name, engine] of Object.entries({ chromium, webkit })) {
    const browser = await engine.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const guest = await browser.newContext();
    let published = null, original = null, headers = null;
    try {
      await context.request.get(base + '/__preview/login?user=admin');
      headers = { 'X-CSRF-Token': (await (await context.request.get(base + '/api/me')).json()).csrf_token };
      const detail = await (await context.request.get(base + '/api/admin/season-packages/' + rid)).json();
      const pkg = detail.package || detail;
      original = pkg.active;
      const page = await context.newPage();
      page.setDefaultTimeout(20000);
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.goto(base + '/admin#season-packages', { waitUntil: 'networkidle' });
      await page.locator('[data-admin-tab="season-packages"]:visible').first().click();
      await page.locator('.sp-season').filter({ hasText: '大橘大利' }).click();
      if (pkg.published_at && original.release_id !== rid) await page.locator('.sp-group-toggle').filter({ hasText: '历史版本' }).click();
      await page.locator('.sp-package').filter({ hasText: '18.18.1' }).first().click();
      await page.getByRole('link', { name: '预览时间卡片', exact: true }).waitFor();
      for (const label of ['预览时间卡片', '预览海报选卡', '预览卡组发布']) {
        assert((await page.getByRole('link', { name: label, exact: true }).getAttribute('href')).includes(rid));
      }
      await page.screenshot({ path: `${shots}/${name}-time-card-admin.png`, fullPage: true });
      await page.goto(base + '/tools/orange-fortune?preview_release=' + rid, { waitUntil: 'networkidle' });
      assert.equal(await page.locator('.fortune-card').count(), 201);
      const firstImage = page.locator('.fortune-card-image').first();
      await firstImage.evaluate(img => img.decode());
      assert((await firstImage.getAttribute('src')).startsWith('/season-assets/' + rid));
      await page.screenshot({ path: `${shots}/${name}-time-card-gallery.png` });
      await page.goto(base + '/tools/orange-fortune-creator?preview_release=' + rid, { waitUntil: 'networkidle' });
      if (await page.locator('[data-panel="cards"]').isVisible()) await page.locator('[data-panel="cards"]').click();
      await page.locator('#card-slots [data-slot="0"]').click();
      const posterCard = page.locator('#picker-results [data-card="7230005"]');
      await posterCard.scrollIntoViewIfNeeded();
      await posterCard.locator('img').evaluate(img => img.decode());
      assert((await posterCard.locator('img').getAttribute('src')).startsWith('/season-assets/' + rid));
      await posterCard.click();
      assert((await page.locator('#formation-frame').getAttribute('src')).includes(rid));
      await page.screenshot({ path: `${shots}/${name}-time-card-poster.png` });
      await page.goto(base + '/lineup/new?type=deck&preview_release=' + rid, { waitUntil: 'networkidle' });
      await page.locator('#savePrimary').filter({ hasText: '预览中不可发布' }).waitFor();
      assert(await page.locator('#savePrimary').isDisabled());
      assert(await page.locator('#submitButton').isDisabled());
      await page.locator('#deckSlots [data-slot="0"]').click();
      const editorCard = page.locator('#cardPicker [data-card="7230005"]');
      await editorCard.scrollIntoViewIfNeeded();
      await editorCard.locator('img').evaluate(img => img.decode());
      assert((await editorCard.locator('img').getAttribute('src')).startsWith('/season-assets/' + rid));
      await page.screenshot({ path: `${shots}/${name}-time-card-picker.png` });
      assert.deepEqual(errors, []);
      // A new request sees the new release immediately, with no server restart.
      assert.equal((await context.request.post(base + '/api/admin/season-packages/' + rid + '/compare', { headers, data: {} })).status(), 200);
      const response = await context.request.post(base + '/api/admin/season-packages/' + rid + '/publish', {
        headers, data: { expected_revision: original.revision, acknowledge_warnings: true }
      });
      assert.equal(response.status(), 200, await response.text());
      published = (await response.json()).active;
      const live = await (await guest.request.get(base + '/api/tools/orange-fortune-creator')).json();
      assert.equal(live.cards.length, 201);
      const image = live.cards.find(card => card.image_url)?.image_url;
      assert(image.startsWith('/season-assets/' + rid));
      assert.equal((await guest.request.get(base + image)).status(), 200);
      console.log(`${name}: admin previews, gallery, poster, readonly picker, published images passed`);
    } finally {
      if (published) {
        const response = await context.request.post(base + '/api/admin/seasons/orange_s400001/rollback', {
          headers, data: { expected_revision: published.revision, release_id: original.release_id }
        });
        assert.equal(response.status(), 200, await response.text());
        const restored = await (await guest.request.get(base + '/api/tools/orange-fortune-creator')).json();
        assert(restored.cards.find(c => c.image_url).image_url.startsWith(original.release_id ? '/season-assets/' + original.release_id : '/static/'));
      }
      await context.close(); await guest.close(); await browser.close();
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
