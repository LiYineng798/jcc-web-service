// Run only against tests/serve_admin_experience_preview.py (fictional data).
const { chromium, webkit } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.ADMIN_EXPERIENCE_PREVIEW_URL || 'http://127.0.0.1:5138';
const output = 'instance/admin-experience-checks';

(async () => {
  fs.mkdirSync(output, { recursive: true });
  for (const [engineName, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const browser = await engine.launch(engineName === 'chromium' && process.env.CHROMIUM_EXECUTABLE ? { executablePath: process.env.CHROMIUM_EXECUTABLE } : {});
    try {
      for (const width of [390, 1440]) {
        const context = await browser.newContext({ viewport: { width, height: 900 }, isMobile: width < 800, hasTouch: width < 800 });
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('dialog', dialog => dialog.accept());
        const navigate = async tab => {
          if (width < 800) {
            await page.locator('#adminMoreButton').click();
            await page.locator(`#adminMoreDialog [data-admin-tab="${tab}"]`).first().click();
          } else {
            const target = page.locator(`.admin-sidebar [data-admin-tab="${tab}"]`).first();
            if (!(await target.isVisible())) await page.locator(`.admin-sidebar [data-admin-nav-toggle="${tab}"]`).click();
            await target.click();
          }
        };
        await page.goto(base + '/__preview/login');
        await page.locator('.admin-dashboard').waitFor();
        assert((await page.locator('#adminApp').innerText()).includes('上传者：演示上传者'));
        await navigate('users');
        const search = page.locator('[data-search-key="users"] input');
        await search.waitFor();
        await page.route('**/api/admin/users?**', async route => {
          await new Promise(resolve => setTimeout(resolve, 180));
          await route.continue();
        });
        await search.focus();
        await search.evaluate(input => { window.originalSearch = input; input.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true })); });
        await search.fill('演');
        await page.waitForTimeout(700);
        assert(await search.evaluate(input => input === document.activeElement && input === window.originalSearch));
        await search.evaluate(input => input.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true })));
        await page.waitForResponse(response => response.url().includes('/api/admin/users?') && response.url().includes('q='));
        await page.waitForTimeout(250);
        assert(await search.evaluate(input => input === document.activeElement && input === window.originalSearch));
        await search.fill('不存在');
        await page.waitForTimeout(750);
        assert(await search.evaluate(input => input === document.activeElement && input === window.originalSearch));
        assert((await page.locator('#adminApp').innerText()).includes('没有找到用户'));
        await search.fill('demo_author');
        await search.press('Enter');
        await page.waitForTimeout(500);
        assert((await page.locator('#adminApp').innerText()).includes('演示上传者'));
        assert(await search.evaluate(input => input === document.activeElement && input === window.originalSearch));
        await page.screenshot({ path: `${output}/${engineName}-${width}-search.png`, fullPage: true, animations: 'disabled' });
        await page.getByRole('button', { name: 'AI 自动化账号', exact: true }).click();
        await page.getByRole('button', { name: '创建自动化账号', exact: true }).click();
        await page.locator('.automation-form').waitFor();
        assert.equal(await page.locator('.automation-seasons input').first().isDisabled(), true);
        assert.equal(await page.locator('.automation-form input[type="checkbox"]').first().isChecked(), false);
        await page.screenshot({ path: `${output}/${engineName}-${width}-automation.png`, fullPage: true, animations: 'disabled' });
        const botName = `bot_${engineName}_${width}_${Date.now().toString(36)}`;
        await page.locator('.automation-form [name="username"]').fill(botName);
        await page.locator('.automation-form [name="nickname"]').fill('浏览器验收助手');
        await page.getByRole('button', { name: '创建并生成令牌', exact: true }).click();
        await page.locator('.automation-token').waitFor();
        const token = await page.locator('.automation-token').inputValue();
        const probe = () => context.request.get(base + '/api/automation/me', { headers: { Authorization: `Bearer ${token}` } });
        assert.equal((await probe()).status(), 200);
        await page.getByRole('button', { name: '已保存，返回账号列表', exact: true }).click();
        let botCard = page.locator('.automation-card').filter({ hasText: botName });
        await botCard.getByRole('button', { name: '禁用', exact: true }).click();
        await botCard.getByRole('button', { name: '启用', exact: true }).waitFor();
        assert.equal((await probe()).status(), 401);
        await botCard.getByRole('button', { name: '启用', exact: true }).click();
        await botCard.getByRole('button', { name: '禁用', exact: true }).waitFor();
        assert.equal((await probe()).status(), 401);
        await botCard.getByRole('button', { name: '删除账号', exact: true }).click();
        await botCard.waitFor({ state: 'detached' });
        await page.locator('.automation-dialog').getByRole('button', { name: '关闭', exact: true }).click();
        await navigate('lineups');
        const lineupSearch = page.locator('[data-search-key="lineups"] input');
        await lineupSearch.waitFor();
        await lineupSearch.focus();
        await lineupSearch.evaluate(input => { window.lineupSearchNode = input; });
        await lineupSearch.fill('九五');
        await page.waitForTimeout(650);
        assert(await lineupSearch.evaluate(input => input === document.activeElement && input === window.lineupSearchNode));
        assert((await page.locator('.lm-table').innerText()).includes('九五'));
        await lineupSearch.fill('绝对无结果');
        await page.waitForTimeout(650);
        assert(await lineupSearch.evaluate(input => input === document.activeElement && input === window.lineupSearchNode));
        assert((await page.locator('.lm-workspace').innerText()).includes('当前筛选下没有阵容'));
        await navigate('patch-notes');
        await page.getByRole('button', { name: '新增公告', exact: true }).click();
        await page.locator('[name="title"]').fill('验收公告');
        await page.locator('[name="version"]').fill('18.2');
        await page.locator('[name="summary_markdown"]').fill('## 英雄调整\n- [buff] 测试：伤害 100 => 120\n<script>window.bad=true</script>');
        assert((await page.locator('.patch-editor-preview').innerText()).includes('100 → 120'));
        assert.equal(await page.evaluate(() => window.bad), undefined);
        for (const theme of ['light', 'dark']) {
          await page.evaluate(theme => { document.documentElement.dataset.theme = theme; document.activeElement?.blur(); window.scrollTo(0, 0); }, theme);
          await page.waitForTimeout(400);
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
          await page.screenshot({ path: `${output}/${engineName}-${width}-announcement-${theme}.png`, fullPage: true, animations: 'disabled' });
        }
        await page.getByRole('button', { name: '保存草稿', exact: true }).click();
        await page.locator('.patch-editor').waitFor({ state: 'detached' });
        assert((await page.locator('#adminApp').innerText()).includes('验收公告'));
        await page.goto(base + '/');
        await page.locator('.live-comps-summary').waitFor();
        assert((await page.locator('#seasonFilterText').innerText()).includes('S18'));
        assert((await page.locator('.live-comps-summary').innerText()).includes('数据快照') ||
          (await page.locator('.live-comps-summary').innerText()).includes('榜单快照'));
        assert.match(await page.locator('.live-comps-summary').innerText(), /\d+月\d+日 \d+:\d+ 更新/);
        await page.locator('[data-sort="latest"][data-view="all"]').click();
        const homeSearch = page.locator('#searchInput');
        await homeSearch.focus();
        await homeSearch.evaluate(input => {
          window.homeSearchNode = input;
          input.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
        });
        await homeSearch.fill('九');
        await page.waitForTimeout(650);
        assert(await homeSearch.evaluate(input => input === document.activeElement && input === window.homeSearchNode));
        await homeSearch.evaluate(input => input.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true })));
        await page.waitForTimeout(750);
        assert(await homeSearch.evaluate(input => input === document.activeElement && input === window.homeSearchNode));
        assert((await page.locator('#lineupList').innerText()).includes('九五'));
        await page.screenshot({ path: `${output}/${engineName}-${width}-home.png`, fullPage: true, animations: 'disabled' });
        assert.deepEqual(errors, []);
        await context.close();
      }
      const context = await browser.newContext();
      const page = await context.newPage();
      await page.route('**/api/live-comps/seasons', async route => {
        await new Promise(resolve => setTimeout(resolve, 1200));
        await route.abort();
      });
      await page.route('**/api/home-stats', route => route.fulfill({ status: 503, body: '{}' }));
      await page.goto(base + '/', { waitUntil: 'domcontentloaded' });
      assert.equal(await page.locator('#seasonFilterText').innerText(), '加载赛季…');
      assert(!(await page.locator('#currentDisplayCount').innerText()).includes('0'));
      await page.getByRole('heading', { name: '阵容加载失败' }).waitFor();
      assert.equal(await page.locator('#currentDisplayCount').innerText(), '加载失败');
      assert.equal(await page.locator('#lineupCount').innerText(), '统计暂不可用');
      await page.unroute('**/api/live-comps/seasons');
      await page.getByRole('button', { name: '重新加载', exact: true }).click();
      await page.locator('.live-comps-summary').waitFor();
      await context.close();
    } finally { await browser.close(); }
  }
  console.log('PASS: mobile/desktop Chromium + WebKit; search focus/IME, draft preview, dark/light layout, loading/error/retry, account defaults');
})().catch(error => { console.error(error); process.exitCode = 1; });
