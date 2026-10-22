// Validate that the editor fits a viewport without clipping controls behind its footer.
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {chromium,webkit}=require('playwright');
const base=process.env.CREATOR_PREVIEW_URL||'http://127.0.0.1:5139';
const out=path.resolve('instance/creator-review');fs.mkdirSync(out,{recursive:true});
async function fits(page) {
  const issues=await page.evaluate(()=>{
    const errors=[];const footer=document.querySelector('.creator-toolbar').getBoundingClientRect();
    if(document.documentElement.scrollHeight>innerHeight+1) errors.push('page scrolls vertically');
    if(document.documentElement.scrollWidth>innerWidth+1) errors.push('page scrolls horizontally');
    for(const el of document.querySelectorAll('.creator-controls input,.creator-controls select,.creator-controls textarea,.creator-controls button')) {
      const rect=el.getBoundingClientRect();if(!rect.width||!rect.height)continue;
      if(rect.bottom>footer.top-1 || rect.top<0 || rect.left<0 || rect.right>innerWidth)errors.push(`out of view: ${el.id||el.textContent.trim()}`);
    }
    for(const el of document.querySelectorAll('.creator-panel')){
      if(el.offsetHeight && el.scrollHeight>el.clientHeight+2)errors.push(`panel clips: ${el.id}`);
      if(el.offsetHeight && el.getBoundingClientRect().bottom>footer.top-2)errors.push(`panel intersects toolbar: ${el.id}`);
    }
    const mat=document.querySelector('.creator-workspace .creator-preview-mat');
    if(mat?.offsetHeight) {
      const box=mat.getBoundingClientRect(),poster=document.querySelector('#poster-preview').getBoundingClientRect();
      if(box.bottom>footer.top-2)errors.push('preview intersects toolbar');
      if(poster.bottom>box.bottom+.5 || poster.top<box.top-.5)errors.push('poster exceeds preview mat');
      const rect=s=>document.querySelector(s).getBoundingClientRect();
      const card=rect('.creator-preview-sticky');
      for(const selector of ['#panel-profile','#panel-content']) {
        if(Math.abs(rect(selector).top-card.top)>.5)errors.push('panel tops not aligned');
      }
      for(const selector of ['#panel-cards','#panel-materials']) {
        if(Math.abs(rect(selector).bottom-card.bottom)>.5)errors.push('panel bottoms not aligned');
      }
      if(Math.abs(rect('#panel-profile .creator-section-title').top-rect('.creator-preview-heading').top)>.5)errors.push('section headings not aligned');
    }
    return errors;
  });
  assert.deepEqual(issues,[],JSON.stringify(page.viewportSize()));
}
async function themeState(page, theme) {
  assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
  assert.equal(await page.locator('#themeToggle').getAttribute('aria-label'),theme==='dark'?'切换为白天模式':'切换为夜间模式');
  assert.equal(await page.locator('#themeToggle').evaluate(e=>e.classList.contains('is-dark')),theme==='dark');
}
async function themeFlow(page) {
  const panelColor=()=>page.locator('#panel-profile').evaluate(e=>getComputedStyle(e).backgroundColor);
  const poster=()=>page.locator('.fortune-poster').evaluate(e=>({background:getComputedStyle(e).backgroundColor,material:e.className}));
  const light=await panelColor(), material=await poster();
  await page.locator('#themeToggle').click();await themeState(page,'dark');
  assert.notEqual(await panelColor(),light);
  assert.deepEqual(await poster(),material,'page theme must not change poster material');
  assert.equal(await page.evaluate(()=>localStorage.getItem('theme')),'dark');
  await page.reload();await page.locator('.fortune-poster').waitFor({state:'attached'});
  await themeState(page,'dark');
  await page.locator('#themeToggle').focus();await page.keyboard.press('Enter');await themeState(page,'light');
  assert.equal(await panelColor(),light);
  await page.reload();await themeState(page,'light');
}
(async()=>{
  for(const [name,engine] of [['chromium',chromium],['webkit',webkit]]) {
    const browser=await engine.launch();const page=await browser.newPage();
    for(const [width,height] of [[1920,1080],[1432,828],[1366,900],[1366,901],[1366,768],[1280,720],[1024,820],[1024,720],[390,844],[375,667]]) {
      await page.setViewportSize({width,height});await page.goto(`${base}/tools/orange-fortune-creator`);
      await page.waitForFunction(()=>document.querySelector('#formation-status').textContent.includes('已连接'));
      if(width===1920||width===390) await themeFlow(page);
      if(await page.locator('.creator-slot.selected').count()===0) {
        if(width<=980)await page.locator('[data-panel="cards"]').click();
        for(const [i,id] of ['7250046','7250036','7250034'].entries()) {
          await page.locator(`[data-slot="${i}"]`).click();await page.locator(`[data-card="${id}"]`).click();
        }
        if(width<=980)await page.locator('[data-panel="profile"]').click();
      }
      await page.locator('#deck-portal').selectOption('custom');await page.locator('#custom-portal').fill('自定义传送门');
      await fits(page);
      await page.locator('#deck-portal').selectOption('stable');await page.locator('#deck-energy').fill('999');await fits(page);
      await page.locator('#deck-energy').fill('');await page.locator('#deck-portal').selectOption('unspecified');
      if(width<=980) {
        for(const key of ['profile','cards','content','materials']) {
          await page.locator(`[data-panel="${key}"]`).click();await fits(page);
        }
        await page.locator('[data-panel="content"]').click();await page.locator('#deck-note').fill('标签切换后保留运营手记');
        await page.locator('[data-panel="cards"]').click();
        await page.locator('#open-preview').click();
        const boxes=await page.locator('#preview-dialog,#poster-preview').evaluateAll(es=>es.map(e=>e.getBoundingClientRect().toJSON()));
        assert.ok(boxes[1].width>100 && boxes[1].bottom<=boxes[0].bottom-8);
        assert.equal(await page.locator('.fp-board-empty').evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)');
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('#preview-dialog').evaluate(e=>e.open),false);
        assert.equal(await page.locator('#open-preview').evaluate(e=>e===document.activeElement),true);
        await page.locator('[data-panel="content"]').click();assert.equal(await page.locator('#deck-note').inputValue(),'标签切换后保留运营手记');
        await page.locator('[data-panel="profile"]').click();
      } else {
        for(const layout of ['showcase','guide']) {
          await page.locator(`[name="poster-layout"][value="${layout}"]`).check();await fits(page);
        }
        assert.equal(await page.locator('.creator-panel:visible').count(),4);
        assert.equal(await page.locator('.fp-board-empty').evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)');
      }
      await page.screenshot({path:path.join(out,`workspace-${name}-${width}-${height}.png`)});
    }
    const blocked=await browser.newContext();
    await blocked.addInitScript(()=>{Storage.prototype.getItem=Storage.prototype.setItem=()=>{throw new DOMException('blocked','SecurityError')};});
    const blockedPage=await blocked.newPage(), errors=[];blockedPage.on('pageerror',e=>errors.push(e.message));
    await blockedPage.goto(`${base}/tools/orange-fortune-creator`);
    await blockedPage.locator('#themeToggle').click();await themeState(blockedPage,'dark');
    await blockedPage.locator('#themeToggle').click();await themeState(blockedPage,'light');
    assert.deepEqual(errors,[]);await blocked.close();
    await browser.close();console.log(`${name}: ten populated viewport sizes, toolbar separation, settings, keyboard flow and theme persistence/blocked storage passed`);
  }
})().catch(e=>{console.error(e);process.exit(1)});
