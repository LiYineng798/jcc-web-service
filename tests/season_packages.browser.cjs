// Start tests/serve_season_package_preview.py and set SEASON_PACKAGE_FILE to its printed path.
// NODE_PATH must include Playwright. Uses real upload/worker/publish APIs on an isolated server.
const { chromium, webkit, request } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.PREVIEW_URL || 'http://127.0.0.1:5096';
const packageFile = process.env.SEASON_PACKAGE_FILE;
if (!packageFile) throw new Error('SEASON_PACKAGE_FILE is required');

(async () => {
  fs.mkdirSync('instance/season-package-checks', {recursive:true});
  const auth = await request.newContext();
  assert.equal((await auth.post(base+'/api/login',{data:{username:'previewadmin',password:'Preview1234'}})).status(),200);
  const storageState = await auth.storageState();
  await auth.dispose();
  for (const [name,engine] of [['chromium',chromium],['webkit',webkit]]) {
    const browser=await engine.launch();
    try {
      const context=await browser.newContext({storageState,viewport:{width:1440,height:1100},reducedMotion:'reduce'});
      const page=await context.newPage();
      const errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      let releaseSession;
      const sessionReady=new Promise(resolve=>{releaseSession=resolve;});
      await page.route('**/api/me',async route=>{await sessionReady;await route.continue();});
      await page.goto(base+'/admin');
      await page.locator('.admin-sidebar [data-admin-tab="season-packages"]').click();
      // Force navigation before boot() can obtain CSRF; no upload form may mount yet.
      assert.equal(await page.locator('#seasonPackageRoot').count(),0);
      releaseSession();
      const root=page.locator('#seasonPackageRoot');
      await root.getByText('将更新包拖到这里',{exact:true}).waitFor();
      await page.screenshot({path:`instance/season-package-checks/${name}-upload.png`,fullPage:true});
      await root.locator('input[type=file]').setInputFiles({name:'invalid.zip',mimeType:'application/zip',buffer:Buffer.from('not a zip')});
      await root.getByRole('button',{name:'重试 invalid.zip'}).waitFor();
      await root.getByRole('button',{name:'移除 invalid.zip'}).click();
      await root.locator('input[type=file]').setInputFiles(packageFile);
      await root.getByRole('link',{name:'预览资料库'}).waitFor({timeout:60000});
      await root.getByRole('button',{name:'更新说明',exact:true}).click();
      await root.getByText('测试版本说明',{exact:true}).waitFor();
      const popupPromise=page.waitForEvent('popup');
      await root.getByRole('link',{name:'预览资料库'}).click();
      const preview=await popupPromise;
      await preview.locator('.season-preview-banner').waitFor();
      await preview.getByRole('tab',{name:'赛季奖励'}).click();
      await preview.getByText('阶段一',{exact:true}).waitFor();
      assert.equal(await preview.locator('.mechanic-card').count(),1);
      await preview.locator('[data-generic-search]').fill('不存在的奖励');
      assert.equal(await preview.locator('.mechanic-card').count(),0);
      await preview.locator('[data-generic-search]').fill('');
      assert.equal(await preview.locator('.mechanic-card').count(),1);
      assert((await preview.locator('a[href*="/champions/100"]').first().getAttribute('href')).includes('preview_release='));
      await preview.close();
      const simPromise=page.waitForEvent('popup');
      await root.getByRole('link',{name:'预览模拟器'}).click();
      const sim=await simPromise;
      await sim.locator('.season-preview-banner').waitFor();
      await sim.getByRole('button',{name:'上阵 测试弈子'}).click();
      assert.equal(await sim.locator('.hex-cell.has-unit').count(),1);
      await sim.close();
      await root.getByRole('button',{name:'资料差异',exact:true}).click();
      await root.getByRole('button',{name:'重新比较',exact:true}).click();
      await root.getByRole('button',{name:'审核并发布',exact:true}).waitFor();
      await page.waitForFunction(()=>!Array.from(document.querySelectorAll('#seasonPackageRoot button')).find(b=>b.textContent.includes('审核并发布'))?.disabled);
      await root.getByRole('button',{name:'审核并发布',exact:true}).click();
      const dialog=root.locator('dialog');
      assert(await dialog.getByRole('button',{name:'确认发布',exact:true}).isDisabled());
      await dialog.locator('input[type=checkbox]').check();
      await dialog.getByRole('button',{name:'确认发布',exact:true}).click();
      await root.getByText('版本已发布，关键页面检查通过。',{exact:true}).waitFor();
      const guest=await request.newContext();
      assert.equal((await guest.get(base+'/tools/seasons/s18/champions/100')).status(),200);
      await guest.dispose();
      for (const theme of ['light','dark']) {
        await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
        for (const width of [320,390,768,1440]) {
          await page.setViewportSize({width,height:1000});
          assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${name} ${theme} ${width}: overflow`);
          if (width===390 || width===1440) await page.screenshot({path:`instance/season-package-checks/${name}-${theme}-${width}.png`,fullPage:true});
        }
      }
      await root.getByRole('button',{name:'回滚',exact:true}).first().click();
      await dialog.getByRole('button',{name:'确认回滚',exact:true}).click();
      await root.getByText('已回滚，关键页面检查通过。',{exact:true}).waitFor();
      // Navigation remount must not leave duplicate React trees or active polling for an old mount.
      await page.locator('.admin-sidebar [data-admin-tab="overview"]').click();
      assert.equal(await root.count(),0);
      await page.locator('.admin-sidebar [data-admin-tab="season-packages"]').click();
      await root.getByText('将更新包拖到这里',{exact:true}).waitFor();
      assert.equal(await root.count(),1);
      assert.deepEqual(errors,[]);
      await context.close();
      console.log(`${name}: upload, rejection, preview, publish, rollback, responsive themes passed`);
    } finally { await browser.close(); }
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
