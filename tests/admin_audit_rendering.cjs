// Run against tests/serve_admin_audit_preview.py. NODE_PATH must provide Playwright.
const { chromium, webkit, request } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.AUDIT_PREVIEW_URL || 'http://127.0.0.1:5098';
(async () => {
  fs.mkdirSync('instance/audit-checks', { recursive: true });
  const auth = await request.newContext();
  assert.equal((await auth.post(base + '/api/login', { data: { account: 'previewadmin', password: 'Preview1234' } })).status(), 200);
  const storageState = await auth.storageState();
  await auth.dispose();
  for (const [name, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch();
    try {
      const context = await browser.newContext({ storageState, viewport: { width: 1440, height: 1100 }, reducedMotion: 'reduce' });
      const page = await context.newPage();
      const errors = [], auditRequests = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', req => { if (req.url().includes('/api/admin/audit-logs')) auditRequests.push(req.url()); });
      await page.goto(base + '/admin');
      await page.locator('.admin-dashboard').waitFor();
      assert.equal(auditRequests.length, 0, 'no audit data requested on overview');
      await page.locator('.admin-sidebar [data-admin-tab="audit"]').click();
      const root = page.locator('#auditLogRoot');
      await root.locator('.al-record').first().waitFor();
      assert.equal(await root.locator('.al-record').count(), 20);
      assert.equal(auditRequests.filter(url => /audit-logs\/\d+/.test(url)).length, 0);
      await page.screenshot({ path: 'instance/audit-checks/' + name + '-desktop-list.png' });
      await root.locator('.al-row').first().click();
      await root.getByText('本次记录 / 提交内容', { exact: true }).waitFor();
      assert(await root.getByText('[已隐藏敏感字段]', { exact: true }).count() >= 2);
      assert(!(await root.textContent()).includes('preview-secret'));
      assert.equal(auditRequests.filter(url => /audit-logs\/\d+/.test(url)).length, 1);
      await page.screenshot({ path: 'instance/audit-checks/' + name + '-desktop-detail.png' });
      await root.getByRole('button', { name: '筛选', exact: true }).click();
      for (const theme of ['light', 'dark']) {
        for (const width of [320, 390, 640, 768, 820, 821, 900, 1024, 1200, 1440]) {
          await page.setViewportSize({ width, height: 1100 });
          await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), name + ' ' + width + ' ' + theme + ' page overflow');
          assert(await root.evaluate(el => el.scrollWidth <= el.clientWidth + 1), 'audit panel overflow');
          await page.screenshot({ path: 'instance/audit-checks/' + name + '-' + theme + '-' + width + '.png' });
        }
      }
      await page.setViewportSize({ width: 1440, height: 1100 });
      await page.evaluate(() => document.documentElement.dataset.theme = 'light');
      await root.getByRole('button', { name: /^新增\s*\d+$/ }).click();
      await root.locator('.al-record').first().waitFor();
      assert((await root.locator('.al-kind').allTextContents()).every(text => text === '新增'));
      await root.getByRole('button', { name: '清除全部', exact: true }).click();
      await root.locator('.al-record').first().waitFor();
      await page.setViewportSize({ width: 390, height: 1000 });
      await root.getByRole('button', { name: '收起筛选，查看结果', exact: true }).click();
      await root.locator('.al-row').first().click();
      await root.getByText('本次记录 / 提交内容', { exact: true }).waitFor();
      await page.screenshot({ path: 'instance/audit-checks/' + name + '-mobile-detail.png' });
      await root.locator('.al-row').first().click();
      await page.screenshot({ path: 'instance/audit-checks/' + name + '-mobile-list.png' });
      await page.setViewportSize({ width: 1440, height: 1100 });
      await root.getByRole('button', { name: '下一页', exact: true }).click();
      await root.getByText('显示 21–40 条，共 67 条', { exact: true }).waitFor();
      await root.getByRole('searchbox').fill('s18');
      await root.locator('.al-row[aria-expanded="false"]').first().waitFor();
      await page.waitForFunction(() => document.querySelector('.al-result-status')?.textContent === '找到 11 条记录');
      assert.equal(await root.locator('.al-page-number').textContent(), '1 / 1');
      await root.getByRole('searchbox').fill('no-such-record');
      await root.getByText('没有符合条件的记录', { exact: true }).waitFor();
      await root.getByRole('button', { name: '清除全部条件', exact: true }).click();
      await root.locator('.al-record').first().waitFor();
      await root.getByRole('searchbox').fill('create_lineup');
      await page.waitForFunction(() => document.querySelectorAll('.al-record').length === 5);
      await root.locator('.al-row').first().click();
      await root.getByText('<img src=x onerror=alert(1)>', { exact: true }).waitFor();
      assert.equal(await root.locator('.al-details img').count(), 0, 'snapshot HTML stays text');
      await root.getByRole('button', { name: '清除全部', exact: true }).click();
      await root.locator('.al-record').first().waitFor();
      await page.route('**/api/admin/audit-logs?**', route => route.fulfill({ status: 500, contentType: 'application/json', body: '{"error":"测试读取错误"}' }));
      await root.getByRole('button', { name: '刷新日志', exact: true }).click();
      await root.getByText('暂时无法读取日志', { exact: true }).waitFor();
      await page.unroute('**/api/admin/audit-logs?**');
      await root.getByRole('button', { name: '重新加载', exact: true }).click();
      await root.locator('.al-record').first().waitFor();
      await page.locator('.admin-sidebar [data-admin-tab="season-packages"]').click();
      await page.locator('#seasonPackageRoot').waitFor();
      assert.equal(await root.count(), 0);
      await page.locator('.admin-sidebar [data-admin-tab="audit"]').click();
      await root.locator('.al-record').first().waitFor();
      await root.locator('.al-row').first().focus();
      await page.keyboard.press('Enter');
      await root.locator('.al-details').waitFor();
      assert.deepEqual(errors, []);
      console.log(name + ': search, filters, pagination, details, redaction, errors, navigation, keyboard and responsive themes passed');
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exit(1); });
