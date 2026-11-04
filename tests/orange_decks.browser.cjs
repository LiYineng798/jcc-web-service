// Run against tests/serve_deck_review_preview.py; all writes use its disposable data.
const { chromium, webkit } = require('playwright-core');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.DECK_REVIEW_URL || 'http://127.0.0.1:5137';
const out = 'instance/deck-review-preview/screenshots';
const code = '德玛时光速9流-大橘大利-MjE5OTY4Mzc0NDMyOTI3OTQxNzkzNzU0NzMyMTczNQ==';
fs.mkdirSync(out, { recursive: true });

(async () => {
  for (const [engineName, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch();
    try {
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 },
        ...(engineName === 'chromium' ? { permissions: ['clipboard-read', 'clipboard-write'] } : {}) });
      const setup = await browser.newContext();
      await setup.request.get(base + '/__preview/login?user=admin');
      const adminMe = await (await setup.request.get(base + '/api/me')).json();
      const accounts = await (await setup.request.get(base + '/api/admin/automation-accounts')).json();
      const bot = accounts.items.find(a => a.username === 'previewbot');
      assert.equal((await setup.request.put(base + '/api/admin/automation-accounts/' + bot.user_id, {
        headers: { 'X-CSRF-Token': adminMe.csrf_token }, data: { can_upload_decks: true, deck_seasons: ['orange_s400001'] }
      })).status(), 200);
      await setup.close();
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.setDefaultTimeout(15000);
      await page.goto(base + '/?library=decks&q=' + encodeURIComponent('德玛时光速9流'), { waitUntil: 'networkidle' });
      const entry = page.locator('.deck-card').filter({ hasText: '德玛时光速9流·验收示例' });
      await entry.waitFor();
      assert.equal(await entry.locator('.deck-card-copy-row').count(), 0);
      assert.equal(await entry.locator('[data-action="copy-plan"] .home-card-action-label').innerText(), '复制');
      assert.equal(await entry.getByRole('button', { name: '分享', exact: true }).count(), 0);
      assert(!(await entry.innerText()).includes('MjE5OTY4'));
      const copyButton = entry.locator('[data-action="copy-plan"]');
      const beforeCopies = Number((await copyButton.locator('.home-card-number').innerText()).replaceAll(',', ''));
      const copyRecorded = page.waitForResponse(r => /\/api\/orange-decks\/\d+\/copy$/.test(r.url()));
      await copyButton.click();
      await page.getByText('方案码已复制', { exact: true }).waitFor();
      const recorded = await (await copyRecorded).json();
      assert.equal(recorded.copy_count, beforeCopies + (recorded.counted ? 1 : 0));
      await page.waitForFunction(({id, count}) => document.querySelector(`[data-deck-id="${id}"] [data-action="copy-plan"] .home-card-number`).textContent === count,
        { id: await entry.getAttribute('data-deck-id'), count: recorded.copy_count.toLocaleString('zh-CN') });
      const repeatedCopy = page.waitForResponse(r => /\/api\/orange-decks\/\d+\/copy$/.test(r.url()));
      await copyButton.click();
      const repeated = await (await repeatedCopy).json();
      assert.equal(repeated.counted, false);
      assert.equal(repeated.copy_count, recorded.copy_count);
      let failedCopyRequests = 0;
      const watchFailedCopy = request => { if (/\/api\/orange-decks\/\d+\/copy$/.test(request.url())) failedCopyRequests++; };
      page.on('request', watchFailedCopy);
      await page.evaluate(() => { window.JccOrangeDeck.copy = async () => false; });
      await copyButton.click();
      await page.getByText('复制失败，请到详情页手动复制', { exact: true }).waitFor();
      assert.equal(failedCopyRequests, 0);
      page.off('request', watchFailedCopy);
      await page.reload({ waitUntil: 'networkidle' });
      await entry.waitFor();
      assert.equal(await copyButton.locator('.home-card-number').innerText(), recorded.copy_count.toLocaleString('zh-CN'));
      if (engineName === 'chromium') assert.equal(await page.evaluate(() => navigator.clipboard.readText()), code);
      await page.screenshot({ path: `${out}/${engineName}-home-light.png`, fullPage: true });
      await entry.screenshot({ path: `${out}/${engineName}-copy-count-card.png` });
      const fresh = page.waitForResponse(r => /\/api\/orange-decks\/\d+$/.test(r.url()));
      await entry.locator('[data-card-index="0"]').click();
      assert.equal((await fresh).status(), 200);
      await page.getByRole('dialog').waitFor();
      await page.keyboard.press('Escape');
      await entry.getByRole('link', { name: '德玛时光速9流·验收示例' }).click();
      const detailCopy = page.waitForResponse(r => /\/api\/orange-decks\/\d+\/copy$/.test(r.url()));
      await page.locator('#copyDeckPlan').click();
      assert.equal((await (await detailCopy).json()).copy_count, recorded.copy_count);
      assert.equal(await page.locator('.deck-plan-code').innerText(), code);
      await page.screenshot({ path: `${out}/${engineName}-detail-light.png`, fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.locator('#themeToggle').click();
      assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), 'dark');
      await page.waitForFunction(() => getComputedStyle(document.body).color === 'rgb(243, 238, 230)');
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: `${out}/${engineName}-detail-mobile-dark.png`, fullPage: true });
      await page.goto(base + '/?library=decks&q=' + encodeURIComponent('德玛时光速9流'), { waitUntil: 'networkidle' });
      await entry.waitFor();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: `${out}/${engineName}-home-mobile-dark.png`, fullPage: true });

      await page.goto(base + '/__preview/login?user=author', { waitUntil: 'networkidle' });
      await page.goto(base + '/lineup/new?type=deck', { waitUntil: 'networkidle' });
      assert.equal(await page.getByText('选择要发布的内容。阵容码适用于所有赛季；大橘大利卡组发布三张时间卡片与推荐传送门。').count(), 0);
      await page.locator('#savePrimary:not([disabled])').waitFor();
      await page.locator('#deckName').fill(`浏览器验收${engineName}`);
      await page.locator('#deckPlanCode').fill(code);
      for (const [index, id] of ['7230005', '7220015', '7210014'].entries()) {
        await page.locator(`[data-slot="${index}"]`).click();
        await page.locator(`[data-card="${id}"]`).click();
      }
      await page.screenshot({ path: `${out}/${engineName}-editor-mobile.png`, fullPage: true });
      await page.locator('#savePrimary').click();
      await page.waitForURL(/\/orange-decks\/\d+$/);
      const createdId = page.url().split('/').at(-1);
      assert.equal(await page.locator('.deck-plan-code').innerText(), code);
      await page.goto(base + '/me#mine/decks', { waitUntil: 'networkidle' });
      const personal = page.locator('.pf-deck-card').filter({ hasText: `浏览器验收${engineName}` });
      const profileCopy = page.waitForResponse(r => /\/api\/orange-decks\/\d+\/copy$/.test(r.url()));
      await personal.getByRole('button', { name: '复制方案码' }).click();
      assert.equal((await (await profileCopy).json()).copy_count, 1);
      await page.getByText('方案码已复制', { exact: true }).waitFor();
      const me = await (await context.request.get(base + '/api/me')).json();
      assert.equal((await context.request.delete(base + '/api/orange-decks/' + createdId,
        { headers: { 'X-CSRF-Token': me.csrf_token } })).status(), 204);

      await page.waitForLoadState('networkidle');
      await page.goto(base + '/__preview/login?user=ai', { waitUntil: 'networkidle' });
      await page.getByRole('link', { name: '打开卡组编辑器' }).click();
      await page.locator('#savePrimary:not([disabled])').waitFor();
      assert(await page.locator('#saveSecondary').isHidden());
      await page.locator('#deckName').fill(`AI上传验收${engineName}`);
      await page.locator('#deckPlanCode').fill(code);
      for (const [index, id] of ['7230005', '7220015', '7210014'].entries()) {
        await page.locator(`[data-slot="${index}"]`).click();
        await page.locator(`[data-card="${id}"]`).click();
      }
      await page.locator('#savePrimary').click();
      await page.waitForURL(/\/orange-decks\/\d+$/);
      assert.equal(await page.locator('.deck-plan-code').innerText(), code);
      assert.equal(await page.getByRole('link', { name: '编辑卡组', exact: true }).count(), 0);

      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.waitForLoadState('networkidle');
      await page.goto(base + '/__preview/login?user=admin', { waitUntil: 'networkidle' });
      await page.locator('.admin-sidebar [data-admin-tab="users"]').click();
      await page.getByRole('button', { name: 'AI 自动化账号', exact: true }).click();
      await page.getByRole('button', { name: '调整权限', exact: true }).click();
      const permission = page.getByRole('checkbox', { name: '允许上传指定赛季的卡组（默认关闭）' });
      assert(await permission.isChecked());
      await page.screenshot({ path: `${out}/${engineName}-admin-permissions.png`, fullPage: true });
      await permission.uncheck();
      await page.getByRole('button', { name: '保存权限', exact: true }).click();
      await page.getByRole('button', { name: '调整权限', exact: true }).waitFor();
      await page.getByRole('button', { name: '调整权限', exact: true }).click();
      await permission.check();
      await page.getByRole('group', { name: '允许上传卡组的赛季', exact: true }).getByRole('checkbox').check();
      await page.getByRole('button', { name: '保存权限', exact: true }).click();
      await page.getByRole('button', { name: '调整权限', exact: true }).waitFor();
      assert.deepEqual(errors, []);
      console.log(`${engineName}: list copy, latest card detail, mobile themes, publish, personal copy, AI upload, admin grant passed`);
      await context.close();
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
