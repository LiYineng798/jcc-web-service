// Render a real ten-unit, eight-trait composition and verify poster geometry.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium,webkit}=require('playwright');
const base=process.env.CREATOR_PREVIEW_URL||'http://127.0.0.1:5139';
const out='instance/creator-review';fs.mkdirSync(out,{recursive:true});
const team=['4345','1412','2411','4368','5397','3336','2403','4352','1402','4339'];

async function geometry(page) {
  const result=await page.evaluate(()=>{
    const rect=s=>document.querySelector(s).getBoundingClientRect();
    const header=rect('.fp-header'),brand=rect('.fp-brand'),board=rect('.fp-board'),traits=rect('.fp-traits');
    const scale=rect('.fortune-poster').width/1200;
    const names=[...document.querySelectorAll('.fp-trait:not(.fp-muted)>span:last-child')].map(e=>e.getBoundingClientRect().left);
    return {
      topDelta:Math.abs(board.top-traits.top)/scale,
      brandCenter:Math.abs((brand.top+brand.bottom)/2-(header.top+header.bottom)/2)/scale,
      traitsFit:traits.bottom<=board.bottom+.5,
      columnsAlign:Math.max(...names)-Math.min(...names)<.5,
      headingFits:rect('.fp-heading').bottom<=header.bottom+.5 && rect('.fp-header h1').bottom<=header.bottom+.5,
    };
  });
  assert.ok(result.topDelta<1);assert.ok(result.brandCenter<1);
  assert.ok(result.traitsFit);assert.ok(result.columnsAlign);assert.ok(result.headingFits);
}

(async()=>{
  for(const [name,engine] of [['chromium',chromium],['webkit',webkit]]) {
    const browser=await engine.launch();const page=await browser.newPage({viewport:{width:1432,height:828}});
    await page.goto(`${base}/tools/orange-fortune-creator`);
    await page.waitForFunction(()=>document.querySelector('#formation-status').textContent.includes('已连接'));
    await page.locator('#deck-name').fill('百川归流 · 多羁绊构筑');
    for(const [i,id] of ['7250046','7250036','7250034'].entries()) {
      await page.locator(`[data-slot="${i}"]`).click();await page.locator(`[data-card="${id}"]`).click();
    }
    await page.locator('#edit-formation').click();
    const frame=page.frameLocator('#formation-frame');
    for(const id of team) await frame.locator(`[data-hero-id="${id}"]`).click();
    await page.locator('[data-close="formation-dialog"]').click();
    await page.waitForFunction(()=>!document.querySelector('#export-poster').disabled);
    assert.equal(await page.locator('.fp-unit').count(),10);
    assert.equal(await page.locator('.fp-trait:not(.fp-muted)').count(),8);
    await page.evaluate(()=>document.fonts.ready);
    await geometry(page);
    assert.equal(await page.locator('.fp-meta').isVisible(),false);
    assert.equal(await page.locator('.fp-header h1').evaluate(e=>getComputedStyle(e).fontSize),'60px');
    for(const length of [14,18,24]) {
      await page.locator('#deck-name').fill('时光里的胜利配方'.repeat(3).slice(0,length));await geometry(page);
    }
    await page.locator('#deck-name').fill('百川归流 · 多羁绊构筑');
    for(const layout of ['guide','showcase']) {
      await page.locator(`[name="poster-layout"][value="${layout}"]`).check();await geometry(page);
      const download=page.waitForEvent('download',{timeout:90000});await page.locator('#export-poster').click();
      await (await download).saveAs(`${out}/full-traits-${name}-${layout}.png`);
    }
    await page.locator('[name="poster-layout"][value="guide"]').check();
    await page.locator('#deck-portal').selectOption('stable');await page.locator('#deck-energy').fill('6');
    await geometry(page);assert.equal(await page.locator('.fp-meta').isVisible(),true);
    assert.equal(await page.locator('.fp-header h1').evaluate(e=>getComputedStyle(e).fontSize),'46px');
    await page.screenshot({path:`${out}/layout-populated-${name}.png`});
    await browser.close();console.log(`${name}: real eight-trait posters, top alignment, centered brand, adaptive heading and both layouts passed`);
  }
})().catch(e=>{console.error(e);process.exit(1)});
