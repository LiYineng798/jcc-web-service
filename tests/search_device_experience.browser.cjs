const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
const base=process.env.SEARCH_DEVICE_PREVIEW_URL||'http://127.0.0.1:5128';
const out=path.resolve('instance/search-device-preview/screenshots');fs.mkdirSync(out,{recursive:true});
const phone='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1';
const desktop='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36';
async function metrics(context){return (await (await context.request.get(base+'/__preview__/metrics')).json()).searches;}
async function restored(page,query,key,offset){
  await page.locator('.lineup-card[data-lineup-key]').first().waitFor();
  await page.waitForFunction(()=>history.state?.jccHome?.page===2);
  await page.waitForTimeout(950);
  assert.equal(await page.locator('#searchInput').inputValue(),query);
  assert.equal(await page.locator('.tab.active').getAttribute('data-sort'),'latest');
  assert.ok((await page.locator('#seasonFilterText').textContent()).includes('S11'));
  const top=await page.locator(`[data-lineup-key="${key}"]`).evaluate(node=>node.getBoundingClientRect().top);
  assert.ok(Math.abs(top-offset)<8,`restored offset ${top}, expected ${offset}`);
}
(async()=>{
  const results=[];
  for(const [name,engine] of [['chromium',chromium],['webkit',webkit]]){
    if(process.env.EXPERIENCE_BROWSER&&process.env.EXPERIENCE_BROWSER!==name)continue;
    const browser=await engine.launch();
    try{
      for(const width of [390,1440])for(const theme of ['light','dark']){
        const context=await browser.newContext({viewport:{width,height:844},userAgent:width===390?phone:desktop});
        await context.addInitScript(theme=>localStorage.setItem('theme',theme),theme);
        const page=await context.newPage(),errors=[];page.on('pageerror',error=>{errors.push(error.message);console.error('PAGE_ERROR',error.stack);});
        await page.goto(base);await page.locator('.live-comp-card').first().waitFor();
        assert.equal(await page.locator('#imageModeText').textContent(),'有图');
        await page.locator('.tab[data-sort="latest"][data-view="all"]').click();
        await page.locator('.lineup-card[data-lineup-key]').first().waitFor();
        const before=await metrics(context);
        const recorded=page.waitForResponse(r=>r.url().endsWith('/api/search-events')&&r.request().method()==='POST');
        await page.locator('#searchInput').fill('九五');
        assert.equal((await recorded).status(),204);
        assert.equal(await metrics(context),before+1);
        await page.locator('[data-page="2"]').first().click();
        await page.waitForFunction(()=>history.state?.jccHome?.page===2);
        await page.waitForTimeout(850);
        const target=page.locator('.lineup-card[data-lineup-key]').nth(3);
        await target.evaluate(node=>scrollTo({top:scrollY+node.getBoundingClientRect().top-160,behavior:'instant'}));
        const key=await target.getAttribute('data-lineup-key');
        const offset=await target.evaluate(node=>node.getBoundingClientRect().top);
        await Promise.all([page.waitForURL(/\/lineup\/\d+$/),target.getByRole('button',{name:'查看',exact:true}).click()]);
        await page.locator('[data-home-return]').click();
        await restored(page,'九五',key,offset);
        assert.equal(await metrics(context),before+1);
        await page.reload();await restored(page,'九五',key,offset);
        assert.equal(await metrics(context),before+1);
        await Promise.all([page.waitForURL(/\/lineup\/\d+$/),page.locator(`[data-lineup-key="${key}"]`).getByRole('button',{name:'查看',exact:true}).click()]);
        await page.goBack();await restored(page,'九五',key,offset);
        assert.equal(await metrics(context),before+1);
        await page.route('**/api/lineups?**',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'preview network failure'})}));
        await page.locator('#searchInput').fill(`不存在阵容${name}${width}${theme}`);
        try { await page.getByRole('heading',{name:'阵容加载失败'}).waitFor({timeout:7000}); }
        catch(error) { console.error(await page.evaluate(()=>({empty:document.querySelector('#emptyState').outerHTML,query:state.query,generation:homeLoadGeneration,controller:!!state.requestControllers.lineups,input:document.querySelector('#searchInput').value})));throw error; }
        assert.equal(await page.locator('.lineup-card[data-lineup-key]').count(),0);
        await page.waitForTimeout(900);assert.equal(await metrics(context),before+1);
        await page.unroute('**/api/lineups?**');
        const retried=page.waitForResponse(r=>r.url().endsWith('/api/search-events'));
        await page.getByRole('button',{name:'重新加载',exact:true}).click();
        await page.getByRole('heading',{name:'没有找到匹配的阵容'}).waitFor();
        assert.equal((await retried).status(),204);
        assert.ok((await page.locator('#emptyState p').textContent()).includes('S11'));
        await page.screenshot({path:path.join(out,`${name}-${width}-${theme}-empty.png`),fullPage:true});
        await page.locator('#emptyState').getByRole('button',{name:'清除搜索',exact:true}).click();
        await page.locator('.lineup-card[data-lineup-key]').first().waitFor();assert.equal(await page.locator('#searchInput').inputValue(),'');
        await page.goto(base+'/__preview__/login/user');
        await page.locator('.live-comp-card').first().waitFor();
        await page.locator('#favoritesTab').click();await page.getByRole('heading',{name:'还没有收藏阵容'}).waitFor();
        await page.getByRole('button',{name:'浏览公开阵容',exact:true}).click();await page.locator('.lineup-card[data-lineup-key]').first().waitFor();
        await page.locator('#mineTab').click();await page.getByRole('heading',{name:'还没有你的阵容'}).waitFor();
        assert.equal(await page.locator('#emptyState').getByRole('button',{name:'新增阵容',exact:true}).count(),1);
        await page.locator('.tab[data-sort="ss"]').click();
        await page.locator('#seasonFilterToggle').click();await page.locator('#seasonFilterMenu button').filter({hasText:'S17'}).click();
        await page.getByRole('heading',{name:'当前赛季暂无 SS 阵容'}).waitFor();
        await page.locator('.tab[data-view="live-comps"]').click();
        await page.locator('#seasonFilterToggle').click();await page.locator('#seasonFilterMenu button').filter({hasText:'S18'}).click();
        await page.getByRole('heading',{name:'还没有实时阵容'}).waitFor();
        assert.ok(!(await page.locator('#emptyState').textContent()).includes('json'));
        await page.locator('#seasonFilterToggle').click();await page.locator('#seasonFilterMenu button').filter({hasText:'S11'}).click();
        await page.locator('.live-comp-detail-link').first().waitFor();
        const liveLink=page.locator('.live-comp-detail-link').nth(2);
        await liveLink.evaluate(node=>scrollTo({top:scrollY+node.closest('[data-lineup-key]').getBoundingClientRect().top-120,behavior:'instant'}));
        const liveKey=await liveLink.evaluate(node=>node.closest('[data-lineup-key]').dataset.lineupKey);
        const liveOffset=await liveLink.evaluate(node=>node.closest('[data-lineup-key]').getBoundingClientRect().top);
        await Promise.all([page.waitForURL(/\/live-comps\//),liveLink.click()]);
        await page.locator('.formation-board').waitFor();await page.locator('[data-home-return]').click();
        await page.locator('.live-comp-card').first().waitFor();await page.waitForTimeout(950);
        assert.equal(await page.locator('.tab.active').getAttribute('data-view'),'live-comps');
        const actual=await page.locator(`[data-lineup-key="${liveKey}"]`).evaluate(node=>node.getBoundingClientRect().top);
        assert.ok(Math.abs(actual-liveOffset)<8,`live restored ${actual}, expected ${liveOffset}`);
        await page.goto(base+'/__preview__/login/admin');
        await page.locator('[data-admin-tab="analytics"]:visible').first().click();
        await page.getByRole('button',{name:'搜索与设备',exact:true}).click();
        await page.locator('.experience-stats').waitFor();
        assert.equal(await page.locator('.experience-stats .admin-row-card').count(),4);
        assert.equal(await page.locator('.experience-section').first().locator('tbody tr').count(),4);
        assert.ok((await page.locator('.experience-section').first().textContent()).includes('未知设备'));
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
        // The existing Safari bottom-bar fill paints beyond the viewport;
        // suppress that offscreen paint only while taking the full-page QA image.
        const fullPageStyle=await page.addStyleTag({content:'.admin-mobile-nav::after{box-shadow:none!important}'});
        await page.screenshot({path:path.join(out,`${name}-${width}-${theme}-analytics.png`),fullPage:true});
        await fullPageStyle.evaluate(node=>node.remove());
        await page.getByLabel('开始日期').fill('2000-01-01');await page.getByLabel('结束日期').fill('2000-01-05');
        await page.getByRole('button',{name:'查询',exact:true}).click();
        await page.getByText('所选日期没有普通阵容搜索记录。',{exact:false}).waitFor();
        assert.equal(await page.locator('.experience-stats .admin-row-card').first().locator('strong').textContent(),'0');
        await page.getByLabel('开始日期').fill('2000-01-01');await page.getByLabel('结束日期').fill('2000-05-01');
        await page.getByRole('button',{name:'查询',exact:true}).click();
        await page.getByText('请选择不超过 90 天、且不包含未来日期的范围',{exact:true}).waitFor();
        await page.getByRole('button',{name:'近 7 天',exact:true}).click();await page.locator('.experience-stats').waitFor();
        assert.deepEqual(errors,[],`${name}/${width}/${theme}`);
        results.push(`${name}/${width}/${theme}: search, restore, empty/error, live return, analytics passed`);
        await context.close();
      }
      // Storage failures leave the history-entry fallback and default image mode usable.
      const blocked=await browser.newContext({viewport:{width:390,height:844},userAgent:phone});
      await blocked.addInitScript(()=>{Storage.prototype.getItem=()=>{throw new Error('blocked');};Storage.prototype.setItem=()=>{throw new Error('blocked');};});
      const p=await blocked.newPage(),blockedErrors=[];p.on('pageerror',error=>blockedErrors.push(error.message));await p.goto(base);await p.locator('.live-comp-card').first().waitFor();
      assert.equal(await p.locator('#imageModeText').textContent(),'有图');
      await p.locator('.tab[data-sort="latest"][data-view="all"]').click();await p.locator('.lineup-card[data-lineup-key]').first().waitFor();
      await p.locator('#searchInput').fill('九五');await p.waitForFunction(()=>history.state?.jccHome?.query==='九五');
      await p.waitForFunction(()=>!document.querySelector('#lineupList .lineup-loader') && document.querySelector('#lineupList .lineup-card button'));
      await p.waitForTimeout(850);
      await Promise.all([p.waitForURL(/\/lineup\/\d+$/),p.locator('.lineup-card[data-lineup-key]').first().getByRole('button',{name:'查看',exact:true}).click()]);
      await p.locator('[data-home-return]').click();await p.locator('.lineup-card[data-lineup-key]').first().waitFor();
      assert.equal(await p.locator('#searchInput').inputValue(),'九五');assert.deepEqual(blockedErrors,[]);await blocked.close();
      results.push(`${name}: blocked storage fallback passed`);
      const edge=await browser.newContext({viewport:{width:390,height:844},userAgent:phone});
      const e=await edge.newPage(),edgeErrors=[];e.on('pageerror',error=>edgeErrors.push(error.message));
      await e.goto(base);await e.locator('.live-comp-card').first().waitFor();
      await e.locator('.tab[data-sort="latest"][data-view="all"]').click();
      await e.locator('.lineup-card[data-lineup-key]').first().waitFor();
      await e.route('**/api/lineups?**',async route=>{
        if(new URL(route.request().url()).searchParams.get('q')==='天龙'){
          const response=await route.fetch();await new Promise(resolve=>setTimeout(resolve,600));
          await route.fulfill({response}).catch(()=>{});
        }else await route.continue();
      });
      const beforeEdge=await metrics(edge);
      await e.locator('#searchInput').fill('天龙');
      await e.waitForRequest(r=>r.url().includes('/api/lineups?')&&new URL(r.url()).searchParams.get('q')==='天龙');
      await e.locator('#searchInput').fill('卡莎');
      await e.waitForFunction(()=>history.state?.jccHome?.query==='卡莎');await e.waitForTimeout(1600);
      for(const title of await e.locator('.lineup-card[data-lineup-key] .lineup-title').allTextContents())assert.ok(title.includes('卡莎'));
      assert.equal(await metrics(edge),beforeEdge+1);
      await Promise.all([e.waitForURL(/\/lineup\/\d+$/),e.locator('.lineup-card[data-lineup-key]').first().getByRole('button',{name:'查看',exact:true}).click()]);
      await edge.request.get(base+'/__preview__/login/user');
      await e.goBack();await e.locator('.live-comp-card').first().waitFor();
      assert.equal(await e.locator('#searchInput').inputValue(),'');
      assert.equal(await e.locator('.tab.active').getAttribute('data-view'),'live-comps');
      assert.deepEqual(edgeErrors,[]);await edge.close();
      results.push(`${name}: late response and account-change fallback passed`);
    }finally{await browser.close();}
  }
  fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));console.log(results.join('\n'));
})().catch(error=>{console.error(error);process.exit(1);});
