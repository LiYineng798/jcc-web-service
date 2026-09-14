// Requires the isolated tests/serve_lineup_moderation_preview.py server.
const { chromium, webkit } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.MODERATION_PREVIEW_URL || 'http://127.0.0.1:5112';
const out = 'instance/moderation-checks';

(async () => {
  fs.mkdirSync(out, { recursive: true });
  for (const [engineName, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch(engineName === 'chromium' ? { channel: process.env.PLAYWRIGHT_CHROMIUM_CHANNEL || 'msedge' } : {});
    const admin = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const owner = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    for (const [context, account] of [[admin, 'previewadmin'], [owner, 'previewuser']]) {
      assert.equal((await context.request.post(`${base}/api/login`, { data: { account, password: 'Preview1234' } })).status(), 200);
    }
    const page = await admin.newPage(), accountPage = await owner.newPage(), errors = [];
    page.on('pageerror', e => errors.push(e.message)); accountPage.on('pageerror', e => errors.push(e.message));
    await page.goto(`${base}/admin`);
    await page.locator('.admin-sidebar [data-admin-nav-toggle="lineups"]').click();
    await page.locator('.admin-sidebar [data-admin-workspace="list"][data-admin-tab="lineups"]').click();
    await page.locator('.lm-table').waitFor();
    await accountPage.goto(`${base}/me#lineup-notifications`);
    await accountPage.locator('.lm-notification').first().waitFor();
    for (const theme of ['light', 'dark']) for (const width of [320, 390, 768, 1440]) {
      for (const [surface, tab] of [['admin', page], ['account', accountPage]]) {
        await tab.setViewportSize({ width, height: 1000 });
        await tab.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
        assert(await tab.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${engineName} ${surface} ${theme} ${width}: overflow`);
        if (surface === 'account') await tab.locator('#lineup-notifications').scrollIntoViewIfNeeded();
        await tab.screenshot({ path: `${out}/${engineName}-${surface}-${theme}-${width}.png` });
      }
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.evaluate(() => document.documentElement.dataset.theme = 'light');
    await page.getByRole('button', { name: '审核修改', exact: true }).first().click();
    await page.locator('.lm-dialog').waitFor();
    assert.equal(await page.locator('.lm-compare .lm-content-block').count(), 2);
    assert(await page.locator('.lm-changed').count() >= 1);
    for (const width of [320, 390, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      assert(await page.locator('.lm-dialog').evaluate(d => d.scrollWidth <= d.clientWidth), 'dialog overflow');
      await page.screenshot({ path: `${out}/${engineName}-review-${width}.png` });
    }
    await page.getByRole('button', { name: '关闭详情' }).click();
    await page.setViewportSize({ width: 1440, height: 1000 });
    await accountPage.setViewportSize({ width: 390, height: 1000 });
    await accountPage.evaluate(() => document.documentElement.dataset.theme = 'light');

    // Independent new row per run; execute actual user/admin UI writes.
    const csrf = (await (await owner.request.get(`${base}/api/me`)).json()).csrf_token;
    const name = `浏览器验收-${engineName}-${Date.now()}`;
    const creation = await owner.request.post(`${base}/api/lineups`, { headers: { 'X-CSRF-Token': csrf }, data: { name, code: '#Browser' + Date.now(), season_id: 's17-star-god' } });
    assert.equal(creation.status(), 201); const lineup = await creation.json();
    await page.locator('.lm-toolbar input[type=search]').fill(name);
    const row = page.locator(`tr[data-lineup-id="${lineup.id}"]`); await row.waitFor();
    await row.getByRole('button', { name: '调分', exact: true }).click();
    await page.getByLabel('点赞修正数', { exact: true }).fill('2');
    await page.getByLabel('复制修正数', { exact: true }).fill('3');
    await page.getByRole('button', { name: '保存分数修正', exact: true }).click();
    await page.locator('.lm-score-dialog').waitFor({ state: 'detached' });
    await row.locator('.lm-stats').getByText('赞 2 · 复制 3', { exact: true }).waitFor();
    await row.getByRole('button', { name: '封禁', exact: true }).click();
    const reason = '<img src=x onerror=alert(1)> 阵容码与名称不符，请核对后重审。';
    await page.locator('.lm-dialog textarea').fill(reason);
    await page.getByRole('button', { name: '确认封禁阵容', exact: true }).click();
    await page.locator('.lm-dialog').waitFor({ state: 'detached' });
    await row.getByText('已封禁', { exact: true }).waitFor();
    await accountPage.reload();
    const notice = accountPage.locator(`.lm-notification[data-lineup-id="${lineup.id}"]`); await notice.waitFor();
    assert(await notice.getByText(reason, { exact: true }).isVisible());
    assert.equal(await notice.locator('.lm-callout img').count(), 0);
    await notice.getByRole('button', { name: '标记已读', exact: true }).click();
    await notice.getByRole('button', { name: '标记未读', exact: true }).waitFor();
    assert.equal(await accountPage.getByRole('button', { name: /归档/ }).count(), 0);
    assert.equal(await notice.getByText('可修改名称、阵容码和赛季后提交重审；封禁期间不能删除。', { exact: true }).count(), 0);
    await notice.getByRole('button', { name: '标记未读', exact: true }).click();
    await notice.getByRole('button', { name: '标记已读', exact: true }).waitFor();
    await notice.getByRole('link', { name: '修改重审', exact: true }).click();
    await accountPage.locator('#submitButton').waitFor();
    await accountPage.getByRole('heading', { name: '修改并提交重审', exact: true }).waitFor();
    assert(!(await accountPage.locator('.visibility-toggle').isVisible()));
    await accountPage.locator('#nameInput').fill(name + '已修正');
    await accountPage.locator('#codeInput').fill('#CorrectedBrowser' + Date.now());
    await accountPage.locator('#editorSeasonToggle').click();
    await accountPage.locator('#editorSeasonMenu').getByRole('button', { name: 'S16 · 英雄联盟传奇', exact: true }).click();
    await accountPage.screenshot({ path: `${out}/${engineName}-editor-390.png` });
    await accountPage.getByRole('button', { name: '提交修改并申请重审', exact: true }).click();
    await accountPage.waitForURL('**/me#lineup-notifications');
    await notice.getByText('待审核', { exact: true }).waitFor();
    await page.getByRole('button', { name: '刷新', exact: true }).click();
    await row.getByRole('button', { name: '审核修改', exact: true }).click();
    await page.locator('.lm-dialog .lm-compare').waitFor();
    assert.equal(await page.locator('.lm-compare .lm-changed').count(), 3);
    await page.getByRole('button', { name: '退回修改', exact: true }).click();
    await page.locator('.lm-dialog textarea').fill('请再确认阵容名称。');
    await page.getByRole('button', { name: '确认退回修改', exact: true }).click();
    await page.locator('.lm-dialog').waitFor({ state: 'detached' });
    await accountPage.reload(); await notice.getByText('已退回', { exact: true }).waitFor();
    await notice.getByRole('link', { name: '修改重审', exact: true }).click();
    await accountPage.getByRole('heading', { name: '修改并提交重审', exact: true }).waitFor();
    assert.equal(await accountPage.locator('#nameInput').inputValue(), name + '已修正');
    await accountPage.locator('#nameInput').fill(name + '最终版');
    await accountPage.getByRole('button', { name: '提交修改并申请重审', exact: true }).click();
    await accountPage.waitForURL('**/me#lineup-notifications');
    await page.getByRole('button', { name: '刷新', exact: true }).click();
    await row.getByRole('button', { name: '审核修改', exact: true }).click();
    await page.getByRole('button', { name: '通过并恢复', exact: true }).click();
    await page.getByRole('button', { name: '确认审核通过', exact: true }).click();
    await page.locator('.lm-dialog').waitFor({ state: 'detached' });
    await row.getByText('正常', { exact: true }).waitFor();
    await accountPage.reload(); await notice.getByText('审核通过', { exact: true }).waitFor();
    const publicData = await (await owner.request.get(`${base}/api/lineups/${lineup.id}`)).json();
    assert.equal(publicData.name, name + '最终版'); assert.equal(publicData.season_id, 's16-legends');
    const latestCsrf = (await (await owner.request.get(`${base}/api/me`)).json()).csrf_token;
    assert.equal((await owner.request.delete(`${base}/api/lineups/${lineup.id}`, { headers: { 'X-CSRF-Token': latestCsrf } })).status(), 204);
    assert.deepEqual(errors, []);
    await browser.close(); console.log(engineName + ': responsive themes, accessible modal, read/unread, ban/reject/resubmit/approve passed');
  }
})().catch(error => { console.error(error); process.exit(1); });
