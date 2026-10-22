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
    }
    return errors;
  });
  assert.deepEqual(issues,[]);
}
(async()=>{
  for(const [name,engine] of [['chromium',chromium],['webkit',webkit]]) {
    const browser=await engine.launch();const page=await browser.newPage();
    for(const [width,height] of [[1920,1080],[1366,768],[1280,720],[1024,720],[390,844],[375,667]]) {
      await page.setViewportSize({width,height});await page.goto(`${base}/tools/orange-fortune-creator`);
      await page.waitForFunction(()=>document.querySelector('#formation-status').textContent.includes('已连接'));
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
        assert.equal(await page.locator('.creator-panel:visible').count(),4);
        assert.equal(await page.locator('.fp-board-empty').evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)');
      }
      await page.screenshot({path:path.join(out,`workspace-${name}-${width}-${height}.png`)});
    }
    await browser.close();console.log(`${name}: six viewport sizes, all settings, validation states, transparent board and preview keyboard flow passed`);
  }
})().catch(e=>{console.error(e);process.exit(1)});
