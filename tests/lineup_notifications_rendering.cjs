// Run against the isolated moderation preview; never against production.
const { chromium, webkit } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.MODERATION_PREVIEW_URL || 'http://127.0.0.1:5112';
const out = 'instance/notification-checks';
(async () => {
  fs.mkdirSync(out, { recursive: true });
  for (const [name, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch(name === 'chromium' ? { channel: process.env.PLAYWRIGHT_CHROMIUM_CHANNEL || 'msedge' } : {});
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    await page.waitForFunction(() => Boolean(window.JccLineupNotifications));
    assert.equal(await page.locator('#lineupNotificationRoot').isVisible(), false, 'guests have no private notification entry');
    await context.request.post(`${base}/api/login`, { data: { account: 'previewuser', password: 'Preview1234' } });
    await page.reload();
    const bell = page.locator('#lineupNotificationToggle'), panel = page.locator('#lineupNotificationPanel');
    await bell.waitFor();
    const initial = await (await context.request.get(`${base}/api/me/lineup-notifications`)).json();
    await page.waitForFunction(n => document.querySelector('#lineupNotificationCount').textContent === String(n), initial.counts.unread);
    await page.locator('#accountToggle').click();
    await bell.click();
    await panel.locator('.ln-item').first().waitFor();
    assert.equal(await page.locator('#accountMenu').isVisible(), false);
    await page.keyboard.press('Escape');
    assert.equal(await panel.isVisible(), false);
    assert(await bell.evaluate(node => node === document.activeElement), 'Escape restores focus');
    await page.keyboard.press('Enter'); await panel.waitFor();
    await page.getByRole('heading', { name: '金铲铲阵容库', exact: true }).click();
    assert.equal(await panel.isVisible(), false, 'outside click closes');
    await bell.click();
    await panel.getByRole('button', { name: /^未读/ }).click();
    await panel.locator('.ln-list[aria-busy="false"]').waitFor();
    assert.equal(await panel.locator('.ln-item:not(.is-unread)').count(), 0);
    const unread = await (await context.request.get(`${base}/api/me/lineup-notifications?status=unread`)).json();
    const row = panel.locator('.ln-item').first(), id = await row.getAttribute('data-lineup-id');
    await row.getByRole('button', { name: '标记已读', exact: true }).click();
    await panel.locator(`.ln-item[data-lineup-id="${id}"]`).waitFor({ state: 'detached' });
    assert.equal(await page.locator('#lineupNotificationCount').textContent(), String(unread.counts.unread - 1));
    await panel.getByRole('button', { name: /^已读/ }).click();
    await panel.locator('.ln-list[aria-busy="false"]').waitFor();
    assert.equal(await panel.locator('.ln-item.is-unread').count(), 0);
    await panel.locator('.ln-item').first().getByRole('button', { name: '标记未读', exact: true }).click();
    await panel.getByRole('button', { name: /^全部/ }).click();
    await panel.locator('.ln-list[aria-busy="false"]').waitFor();
    const firstId = await panel.locator('.ln-item').first().getAttribute('data-lineup-id');
    await panel.getByRole('button', { name: '下一页', exact: true }).click();
    await panel.locator('.ln-list[aria-busy="false"]').waitFor();
    assert.notEqual(await panel.locator('.ln-item').first().getAttribute('data-lineup-id'), firstId);
    await panel.getByRole('button', { name: '上一页', exact: true }).click();
    await panel.locator('.ln-list[aria-busy="false"]').waitFor();
    for (const theme of ['light', 'dark']) for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 800 });
      await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
      if (!await panel.isVisible()) await bell.click();
      await page.waitForFunction(() => {
        const r = document.querySelector('.ln-panel').getBoundingClientRect();
        return r.x >= 0 && r.right <= innerWidth && r.bottom <= innerHeight;
      });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      for (const selector of ['.ln-bell', '#accountToggle', '#themeToggle']) {
        const r = await page.locator(selector).boundingBox();
        assert(r.x >= 0 && r.x + r.width <= width, `${selector} outside ${width}`);
      }
      await page.screenshot({ path: `${out}/${name}-home-${theme}-${width}.png` });
    }
    await page.setViewportSize({ width: 390, height: 800 });
    await page.evaluate(() => document.documentElement.dataset.theme = 'light');
    const banned = (await (await context.request.get(`${base}/api/me/lineup-notifications?page_size=100`)).json()).items.find(item => item.state === 'banned');
    await page.goto(`${base}/me/lineup-notifications/${banned.lineup_id}`);
    await page.locator('#lineupNotificationDetail[aria-busy="false"]').waitFor();
    await page.getByRole('link', { name: '修改重审', exact: true }).waitFor();
    await page.screenshot({ path: `${out}/${name}-detail-mobile.png` });
    await page.getByRole('link', { name: '返回通知', exact: true }).click();
    await panel.waitFor(); await panel.locator('.ln-list[aria-busy="false"]').waitFor();
    const latest = await (await context.request.get(`${base}/api/me/lineup-notifications`)).json();
    assert.equal(await page.locator('#lineupNotificationCount').textContent(), String(latest.counts.unread || 0));
    await page.goto(`${base}/me`);
    await page.locator('#accountApp .account-section').first().waitFor();
    assert.equal(await page.locator('#lineup-notifications').count(), 0, 'old card section removed');
    await page.setViewportSize({ width: 320, height: 800 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'account navigation fits small screens');
    const accountNoticeLink = await page.getByRole('link', { name: '查看通知', exact: true }).boundingBox();
    assert(accountNoticeLink.x >= 0 && accountNoticeLink.x + accountNoticeLink.width <= 320);
    await page.getByRole('link', { name: '查看通知', exact: true }).click();
    await panel.waitFor(); await panel.locator('.ln-list[aria-busy="false"]').waitFor();
    await page.route('**/api/me/lineup-notifications?*', route => route.fulfill({ status: 503, json: { error: '暂时不可用' } }));
    await panel.getByRole('button', { name: /^未读/ }).click();
    await panel.getByText('通知加载失败', { exact: true }).waitFor();
    await page.unroute('**/api/me/lineup-notifications?*');
    await panel.getByRole('button', { name: '重新加载', exact: true }).click();
    await panel.locator('.ln-item').first().waitFor();

    // Delayed private data must not reappear after the user logs out.
    let release;
    const gate = new Promise(resolve => release = resolve);
    await page.route('**/api/me/lineup-notifications?*', async route => {
      const response = await route.fetch(); await gate; await route.fulfill({ response });
    });
    await panel.getByRole('button', { name: '关闭通知', exact: true }).click();
    await bell.click();
    await page.locator('#accountToggle').click();
    await page.locator('#menuLogoutButton').click();
    await page.locator('#lineupNotificationRoot').waitFor({ state: 'hidden' });
    release(); await page.unrouteAll({ behavior: 'wait' });
    assert.equal(await panel.locator('.ln-item').count(), 0);
    await context.request.post(`${base}/api/login`, { data: { account: 'previewadmin', password: 'Preview1234' } });
    await page.goto(`${base}/?notifications=open`);
    await panel.getByText('暂时没有通知', { exact: true }).waitFor();
    assert.equal(await page.locator('#lineupNotificationCount').isVisible(), false);
    assert.deepEqual(errors, []);
    await browser.close();
    console.log(`${name}: notification entry, filters, counts, navigation, themes, empty/error/retry and logout race passed`);
  }
})().catch(error => { console.error(error); process.exit(1); });
