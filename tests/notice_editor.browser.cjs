// Run against serve_notice_editor_preview.py; NODE_PATH must provide Playwright.
const { chromium, webkit, request } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.NOTICE_PREVIEW_URL || 'http://127.0.0.1:5138';
(async () => {
  fs.mkdirSync('instance/notice-checks', { recursive: true });
  const auth = await request.newContext();
  const login = await auth.post(base + '/api/login', { data: { account: 'previewadmin', password: 'Preview1234' } });
  assert.equal(login.status(), 200);
  const headers = { 'X-CSRF-Token': (await login.json()).csrf_token };
  const storageState = await auth.storageState();
  const seed = await (await auth.get(base + '/api/admin/notice')).json();
  for (const entry of seed.items.filter(entry => entry.title.startsWith('浏览器验证'))) {
    await auth.delete(base + `/api/admin/notices/${entry.id}`, { headers });
  }
  const demo = seed.items.find(entry => entry.title === '时间卡片图鉴已上线');
  await auth.post(base + `/api/admin/notices/${demo.id}/activate`, { headers });
  const initial = await (await auth.get(base + '/api/admin/notice')).json();
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch();
    try {
      const context = await browser.newContext({ storageState, viewport: { width: 1440, height: 1100 } });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(base + '/admin');
      await page.locator('.admin-sidebar [data-admin-tab="settings"]').click();
      const open = page.getByRole('button', { name: '新增通知', exact: true });
      await open.click();
      const dialog = page.locator('dialog.notice-editor');
      await dialog.waitFor();
      await dialog.locator('[name="target_kind"][value="tool"]').check();
      await dialog.locator('[name="tool_id"][value="orange-fortune"]').check();
      await dialog.locator('#noticeTitleInput').fill('浏览器验证 · 时间卡片图鉴');
      await dialog.locator('#noticeMessageInput').fill('查阅五星分级、生效回合与完整效果，让每一次选择更有把握。');
      await dialog.locator('[data-tool-search]').fill('魔女');
      assert.equal(await dialog.locator('.notice-tool-option').count(), 1);
      await dialog.locator('[data-tool-search]').fill('不存在的工具');
      assert.match(await dialog.locator('.notice-tool-status').innerText(), /没有匹配/);
      await dialog.locator('[data-tool-search]').fill('');
      assert.match(await dialog.locator('[data-preview-target]').innerText(), /时间卡片图鉴/);
      for (const theme of ['light', 'dark']) {
        for (const width of [320, 390, 760, 1440]) {
          await page.setViewportSize({ width, height: 1100 });
          await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
          assert(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1), `${engine.name()} ${width} overflow`);
          await dialog.evaluate(el => { el.scrollTop = 0; });
          await page.screenshot({ path: `instance/notice-checks/${engine.name()}-${theme}-${width}.png` });
        }
      }
      await page.setViewportSize({ width: 1440, height: 1100 });
      // Native modal traps keyboard focus; Escape returns to its trigger.
      await dialog.getByRole('button', { name: '保存并展示', exact: true }).focus();
      await page.keyboard.press('Tab');
      assert(await dialog.evaluate(el => el.contains(document.activeElement)));
      await page.keyboard.press('Escape');
      await dialog.waitFor({ state: 'detached' });
      assert(await open.evaluate(el => el === document.activeElement));
      // Failed catalog request preserves text and offers retry.
      await page.route('**/api/admin/notice-targets', route => route.fulfill({ status: 503, json: { error: 'test catalog failure' } }));
      await open.click();
      await dialog.locator('#noticeTitleInput').fill('浏览器验证 · 保存重试');
      await dialog.locator('#noticeMessageInput').fill('保留输入与跳转选择');
      await dialog.locator('[name="target_kind"][value="tool"]').check();
      await dialog.locator('.notice-catalog-error').waitFor({ state: 'visible' });
      await page.unroute('**/api/admin/notice-targets');
      await dialog.getByRole('button', { name: '刷新选项', exact: true }).click();
      await dialog.locator('[name="tool_id"][value="orange-fortune"]').check();
      assert.equal(await dialog.locator('#noticeTitleInput').inputValue(), '浏览器验证 · 保存重试');
      // Hidden tool disappears after refresh; stale selection is rejected by the server.
      await dialog.locator('[name="tool_id"][value="lineup-simulator"]').check();
      assert.equal((await auth.put(base + '/api/admin/settings', { headers, data: { simulator_enabled: false } })).status(), 200);
      await dialog.getByRole('button', { name: '刷新选项', exact: true }).click();
      await dialog.locator('[name="tool_id"][value="lineup-simulator"]').waitFor({ state: 'detached' });
      await dialog.getByRole('button', { name: '保存通知', exact: true }).click();
      await dialog.locator('.notice-form-error').waitFor({ state: 'visible' });
      assert.match(await dialog.locator('.notice-form-error').innerText(), /隐藏|不存在/);
      await auth.put(base + '/api/admin/settings', { headers, data: { simulator_enabled: true } });
      await dialog.locator('[name="tool_id"][value="orange-fortune"]').check();
      // A failed activation must not cause another create on retry.
      const beforeSave = await (await auth.get(base + '/api/admin/notice')).json();
      await page.route('**/api/admin/notices/*/activate', route => route.fulfill({ status: 503, json: { error: '演练：展示切换失败' } }));
      await dialog.getByRole('button', { name: '保存并展示', exact: true }).click();
      await dialog.locator('.notice-form-error').filter({ hasText: '通知已保存' }).waitFor({ state: 'visible' });
      await page.unroute('**/api/admin/notices/*/activate');
      await dialog.getByRole('button', { name: '保存并展示', exact: true }).click();
      await dialog.waitFor({ state: 'detached' });
      const afterSave = await (await auth.get(base + '/api/admin/notice')).json();
      assert.equal(afterSave.items.length, beforeSave.items.length + 1);
      const created = afterSave.items.find(entry => entry.id === afterSave.active_id);
      assert.equal(created.link_url, '/tools/orange-fortune');
      assert.equal(created.jump_tab, '');
      const publicPage = await context.newPage();
      await publicPage.goto(base);
      await publicPage.locator('#siteNotice').hover();
      assert.equal(await publicPage.locator('.site-notice-marquee-track').evaluate(el => getComputedStyle(el).animationPlayState), 'paused');
      await publicPage.locator('#siteNotice .site-notice-link').click();
      await publicPage.waitForURL('**/tools/orange-fortune');
      await publicPage.close();
      // Editing a saved target keeps its selection and supports changing modes.
      await page.locator('.admin-row-card').filter({ hasText: '浏览器验证 · 保存重试' }).getByRole('button', { name: '编辑', exact: true }).click();
      await dialog.locator('[name="tool_id"][value="orange-fortune"]:checked').waitFor();
      await dialog.locator('[name="target_kind"][value="guestbook"]').check();
      await dialog.getByRole('button', { name: '保存通知', exact: true }).click();
      await dialog.waitFor({ state: 'detached' });
      const revised = (await (await auth.get(base + '/api/admin/notice')).json()).items.find(entry => entry.id === created.id);
      assert.equal(revised.link_url, '/#guestbook');
      assert.equal(revised.link_text, '去留言');
      assert.equal(revised.jump_season_id, '');
      assert.equal(errors.length, 0, errors.join('\n'));
      await auth.delete(base + `/api/admin/notices/${created.id}`, { headers });
      await auth.post(base + `/api/admin/notices/${initial.active_id}/activate`, { headers });
      console.log(engine.name() + ': layout, keyboard, search, retry, hidden tool, publish and public jump passed');
      await context.close();
    } finally { await browser.close(); }
  }
  await auth.dispose();
})().catch(error => { console.error(error); process.exitCode = 1; });
