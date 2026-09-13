// Real endpoints and disposable data for each browser; no production calls.
const {chromium, webkit, request} = require('playwright');
const {spawn} = require('node:child_process');
const readline = require('node:readline');
const fs = require('node:fs');
const assert = require('node:assert/strict');

async function preview() {
  const child = spawn(process.env.PYTHON || 'python', ['tests/serve_season_display_preview.py', '--port', '0', '--stdio-control'], {stdio:['pipe','pipe','pipe']});
  let diagnostics = '';
  child.stderr.on('data', b => { diagnostics = (diagnostics + b).slice(-6000); });
  try {
    const ready = await new Promise((resolve,reject) => {
      const timer = setTimeout(() => reject(Error('Preview timeout: ' + diagnostics)), 60000);
      readline.createInterface({input:child.stdout}).on('line', line => {
        if (line.startsWith('SEASON_DISPLAY_READY=')) { clearTimeout(timer); resolve(JSON.parse(line.slice('SEASON_DISPLAY_READY='.length))); }
      });
      child.once('error', e => { clearTimeout(timer); reject(e); });
      child.once('exit', code => { clearTimeout(timer); reject(Error('Preview exited '+code+': '+diagnostics)); });
    });
    return {...ready, close: async () => {
      if (child.exitCode !== null) return;
      const stopped = new Promise(resolve => child.once('exit',resolve));
      child.stdin.end();
      await stopped;
    }};
  } catch (error) { child.stdin.end(); throw error; }
}

(async () => {
  const out = 'instance/season-display-checks';
  fs.mkdirSync(out, {recursive:true});
  for (const [name, engine] of [['chromium', chromium], ['webkit', webkit]]) {
    const server = await preview();
    let browser, auth;
    try {
      browser = await engine.launch();
      auth = await request.newContext({baseURL:server.url});
      assert.equal((await auth.post('/api/login', {data:{username:'previewadmin', password:'Preview1234'}})).status(), 200);
      const context = await browser.newContext({storageState:await auth.storageState(), viewport:{width:1440,height:1000}});
      const page = await context.newPage();
      page.setDefaultTimeout(15000);
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.goto(server.url+'/admin');
      await page.locator('.admin-sidebar [data-admin-tab="season-display"]').click();
      const hub = page.locator('.admin-season-hub');
      const surface = kind => page.locator(`[data-season-surface="${kind}"]`);
      const lib = surface('library'), sim = surface('simulator');
      const publicIds = section => section.locator('.season-display-public > li').evaluateAll(rows => rows.map(row => row.dataset.seasonId));
      const api = async kind => (await auth.get(`/api/season-catalog?surface=${kind}`)).json();
      const settle = () => page.locator('.admin-season-hub[aria-busy="false"]').waitFor();
      const status = async (section, id, value) => {
        await section.locator(`[data-season-id="${id}"] select`).selectOption(value);
        await settle();
      };
      await lib.locator('.season-display-public > li').first().waitFor();
      await sim.locator('.season-display-public > li').first().waitFor();
      await settle();
      assert.deepEqual(await publicIds(lib), ['s18','s16_5']);
      assert.deepEqual(await lib.locator('.season-display-rank').allTextContents(), ['1','2']);
      assert.equal(await lib.locator('.season-display-inactive .season-display-rank').count(), 0);
      assert.equal(await lib.locator('.season-display-inactive .season-display-arrow').count(), 0);
      await page.screenshot({path:`${out}/${name}-desktop-collapsed.png`, fullPage:true});
      await lib.locator('summary').click();
      await sim.locator('summary').click();
      for (const theme of ['light','dark']) {
        if (await page.evaluate(() => document.documentElement.dataset.theme) !== theme) await page.locator('#themeToggle').click();
        await page.waitForFunction(value => getComputedStyle(document.body).color === (value === 'dark' ? 'rgb(243, 238, 230)' : 'rgb(33, 31, 28)'), theme);
        for (const width of [1440,1024,768,390,320]) {
          await page.setViewportSize({width,height:1000});
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name} ${theme} ${width} overflow`);
          const controls = await hub.locator('button,select,summary').evaluateAll(nodes => nodes.filter(n => n.getClientRects().length).map(n => {
            const r=n.getBoundingClientRect(); return {left:r.left,right:r.right,height:r.height};
          }));
          assert(controls.every(r => r.left>=0 && r.right<=width+1), `${name} ${width} controls out of bounds`);
          if (width <= 520) assert(controls.every(r => r.height>=44), `${name} mobile touch target`);
          if ([1440,390].includes(width)) await page.screenshot({path:`${out}/${name}-${theme}-${width}.png`,fullPage:width>520});
        }
      }
      await page.setViewportSize({width:1440,height:1000});
      await page.evaluate(() => document.documentElement.dataset.theme='light');
      await lib.getByRole('button',{name:'下移S18 自然之力',exact:true}).click();
      await settle();
      assert.deepEqual(await publicIds(lib), ['s16_5','s18']);
      assert.deepEqual((await api('library')).seasons.map(s=>s.order), [1,2]);
      assert.deepEqual(await publicIds(sim), ['s18','s16_5']);
      await sim.getByRole('button',{name:'将S16.5 英雄联盟传奇设为模拟器默认赛季',exact:true}).click();
      await settle();
      assert.equal((await api('simulator')).default_season_id,'s16_5');
      assert.deepEqual(await publicIds(sim), ['s18','s16_5']);
      await sim.getByRole('button',{name:'将S18 自然之力设为模拟器默认赛季',exact:true}).click();
      await settle();
      await lib.getByRole('button',{name:'重新展示S17 星神',exact:true}).click();
      await settle();
      assert.deepEqual(await publicIds(lib), ['s16_5','s18','s17']);
      assert(await lib.locator('details').evaluate(n=>n.open), 'Keep expanded management area open');
      await status(lib,'s17','hidden');
      assert.deepEqual(await publicIds(lib), ['s16_5','s18']);
      assert.equal((await auth.get('/tools/seasons/s17')).status(),404);
      await status(sim,'s18','disabled');
      assert.equal((await api('simulator')).default_season_id,'s16_5');
      assert.equal(await sim.locator('[data-season-id="s16_5"] .season-display-badge').textContent(),'默认');
      assert.deepEqual(await publicIds(lib), ['s16_5','s18']);
      await status(sim,'s16_5','disabled');
      assert.equal((await api('simulator')).default_season_id,null);
      await sim.getByText('暂无展示中的赛季，可从下方重新展示。',{exact:true}).waitFor();
      await sim.getByRole('button',{name:'重新展示S18 自然之力',exact:true}).click();
      await settle();
      assert.equal((await api('simulator')).default_season_id,'s18');
      assert.deepEqual(await sim.locator('.season-display-rank').allTextContents(),['1']);

      // A failed save keeps the last server state and displays real feedback.
      await page.route('**/api/admin/season-display/library/s18', route => route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'演练：保存未完成'})}));
      await status(lib,'s18','disabled');
      await page.getByText('演练：保存未完成',{exact:true}).waitFor();
      assert.deepEqual(await publicIds(lib), ['s16_5','s18']);
      assert.equal(await lib.locator('[data-season-id="s18"] select').inputValue(),'active');
      await page.unroute('**/api/admin/season-display/library/s18');
      await page.reload();
      await page.locator('.admin-sidebar [data-admin-tab="season-display"]').click();
      await lib.locator('.season-display-public > li').first().waitFor();
      assert.deepEqual(await publicIds(lib), ['s16_5','s18']);
      // Mobile menu reaches the same workspace; collapse works with keyboard.
      await page.setViewportSize({width:390,height:1000});
      await page.locator('#adminMoreButton').click();
      await page.locator('#adminMoreDialog [data-admin-tab="season-display"]').click();
      assert.equal(await page.locator('#adminMoreDialog').evaluate(n=>n.open),false);
      await lib.locator('summary').focus();
      await page.keyboard.press('Enter');
      assert(await lib.locator('details').evaluate(n=>n.open));
      await page.setViewportSize({width:1440,height:1000});
      await page.getByRole('button',{name:'管理资料版本',exact:true}).click();
      await page.locator('#seasonPackageRoot').getByText('上传赛季更新包',{exact:true}).waitFor();
      // A failed read is isolated to its own surface and offers a retry.
      await page.route('**/api/admin/season-display/library', route => route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'演练：资料库暂时不可用'})}));
      await page.reload();
      await page.locator('.admin-sidebar [data-admin-tab="season-display"]').click();
      await lib.getByText('演练：资料库暂时不可用',{exact:true}).waitFor();
      await sim.locator('.season-display-public > li').first().waitFor();
      await page.unroute('**/api/admin/season-display/library');
      await lib.getByRole('button',{name:'重新加载',exact:true}).click();
      await lib.locator('.season-display-public > li').first().waitFor();
      assert.deepEqual(await publicIds(lib), ['s16_5','s18']);
      assert.deepEqual(errors, []);
      console.log(`${name}: layout, mobile, independent ordering, restore, default fallback, persistence and failed save passed`);
    } finally {
      await auth?.dispose();
      await browser?.close();
      await server.close();
    }
  }
})().catch(error => { console.error(error); process.exitCode=1; });
