// Run against an isolated worktree preview; screenshots/downloads stay under instance/.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit, devices} = require('playwright');
const {PNG} = require('pngjs');
const base = process.env.CREATOR_PREVIEW_URL || 'http://127.0.0.1:5139';
const out = path.resolve('instance/creator-review');
fs.mkdirSync(out, {recursive:true});

async function selectCard(page, slot, id) {
  await page.locator(`[data-slot="${slot}"]`).click();
  await page.locator('#card-search').fill('');
  await page.locator('#card-tier').selectOption('');
  await page.locator(`[data-card="${id}"]`).click();
}

(async()=>{
  for (const [name,engine,mobile] of [['chromium',chromium,false],['webkit',webkit,true]]) {
    const browser = await engine.launch({headless:true});
    const page = await browser.newPage(mobile ? devices['iPhone 13'] : {viewport:{width:1500,height:1050}});
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    await page.goto(`${base}/tools/orange-fortune-creator`);
    await page.waitForFunction(()=>document.querySelector('#formation-status').textContent.includes('已连接'));
    assert.equal(await page.locator('#export-poster').isDisabled(),true);
    assert.ok(!/先遣服|测试服/.test(await page.locator('body').innerText()));
    await page.evaluate(()=>localStorage.setItem('jcc-simulator-v2:s16_5','original-simulator-draft'));
    await page.locator('#deck-name').fill('时光里的胜利配方');
    await page.locator('#deck-author').fill('橘子研究所');
    await page.locator('#deck-target').selectOption('前三');
    await page.locator('#deck-note').fill('围绕时间卡片的生效回合规划节奏。优先完成主力装备，观察场上对手，再决定冲刺更高目标。');
    await selectCard(page,0,'7250036');
    await page.locator('[data-slot="1"]').click();
    assert.equal(await page.locator('[data-card="7250036"]').isDisabled(),true);
    await page.locator('#card-search').fill('不存在的卡片');
    assert.match(await page.locator('#picker-results').innerText(),/没有匹配/);
    await page.locator('#card-search').fill('');
    await page.locator('[data-card="7250046"]').click();
    await selectCard(page,2,'7250034');
    await page.locator('#edit-formation').click();
    const frame=page.frameLocator('#formation-frame');
    await frame.locator('.hero-button:not(.is-locked)').first().waitFor();
    const units=frame.locator('.hero-button:not(.is-locked)');
    for(let i=0;i<8;i++) await units.nth(i).click();
    await frame.locator('.item-button').first().click();
    await frame.locator('.hex-cell.has-unit').first().click();
    await page.locator('[data-close="formation-dialog"]').click();
    await page.waitForFunction(()=>!document.querySelector('#export-poster').disabled);
    assert.equal(await page.locator('.fp-unit').count(),8);
    assert.ok(await page.locator('.fp-items img').count()>0);
    assert.equal(await page.evaluate(()=>localStorage.getItem('jcc-simulator-v2:s16_5')),'original-simulator-draft');
    await page.locator('#deck-portal').selectOption('stable');
    await page.locator('#deck-energy').fill('9');
    assert.equal(await page.locator('#export-poster').isDisabled(),true);
    assert.match(await page.locator('#portal-help').textContent(),/超过/);
    await page.locator('#deck-energy').fill('8');
    assert.equal(await page.locator('#export-poster').isDisabled(),false);
    await page.locator('#deck-energy').fill('');
    await page.locator('#deck-portal').selectOption('unspecified');
    for(const bg of (mobile?['jade']:['gilded','jade','astral','ivory'])) {
      await page.locator(`[data-background="${bg}"]`).click();
      const downloadEvent=page.waitForEvent('download',{timeout:90000});
      await page.locator('#export-poster').click();
      const download=await downloadEvent;
      assert.equal(await download.failure(),null);
      const file=path.join(out,`${name}-${bg}.png`);await download.saveAs(file);
      const png=PNG.sync.read(fs.readFileSync(file));assert.equal(png.width,1600);assert.equal(png.height,1200);
      // A nonblank background alone is insufficient: assert artwork and portraits.
      for(const [left,top,right,bottom] of [[100,370,240,540],[930,330,965,365]]) {
        const colors=new Set();for(let y=top;y<bottom;y++)for(let x=left;x<right;x++){const i=(y*png.width+x)*4;colors.add(`${png.data[i]},${png.data[i+1]},${png.data[i+2]}`);}
        assert.ok(colors.size>200,`missing embedded image: ${name}/${bg}`);
      }
      // Require real content in both halves, not a blank/tainted export.
      for(const [start,end] of [[0,800],[800,1600]]) {const colors=new Set();for(let y=250;y<1000;y+=7)for(let x=start;x<end;x+=7){const i=(y*png.width+x)*4;colors.add(`${png.data[i]},${png.data[i+1]},${png.data[i+2]}`);}assert.ok(colors.size>300,`blank export: ${name}/${bg}`);}
    }
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('.fp-unit'));
    assert.equal(await page.locator('#deck-name').inputValue(),'时光里的胜利配方');
    assert.equal(await page.locator('.creator-slot.selected').count(),3);
    assert.equal(await page.locator('.fp-unit').count(),8);
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert.equal(overflow,false);
    const rect=await page.locator('.fortune-poster').boundingBox();const preview=await page.locator('#poster-preview').boundingBox();assert.ok(Math.abs(rect.width-preview.width)<2);
    await page.screenshot({path:path.join(out,`${name}-page.png`),fullPage:true});
    await page.evaluate(()=>{document.documentElement.dataset.theme='dark';});
    await page.screenshot({path:path.join(out,`${name}-dark.png`),fullPage:true});
    // Missing-art card remains selectable and exports text honestly.
    await selectCard(page,2,'7250012');assert.match(await page.locator('.fortune-poster').innerText(),/卡图暂缺/);
    // Longest card descriptions must remain inside their allotted area.
    const longest=await page.evaluate(()=>JSON.parse(document.querySelector('#creator-config').textContent).cards.sort((a,b)=>b.description.length-a.description.length).slice(0,3).map(c=>c.id));
    for(let i=0;i<3;i++) await selectCard(page,i,longest[i]);
    const clipping=await page.locator('.fp-card-effect').evaluateAll(es=>es.some(e=>e.scrollHeight>e.clientHeight+1));assert.equal(clipping,false);
    if(!mobile) {
      await page.locator('[data-slot="0"]').click();await page.keyboard.press('Escape');
      assert.equal(await page.locator('#card-picker').evaluate(e=>e.open),false);
      await page.route('**/api/season-catalog?**',route=>route.fulfill({status:503,body:'unavailable'}));
      await page.reload();await page.locator('#retry-formation').waitFor({state:'visible'});
      assert.equal(await page.locator('#export-poster').isDisabled(),true);
      await page.unroute('**/api/season-catalog?**');await page.locator('#retry-formation').click();
      await page.waitForFunction(()=>document.querySelector('#formation-status').textContent.includes('已连接'));
      await page.locator('#deck-name').fill('<img onerror=alert(1)>');
      assert.equal(await page.locator('.fp-header h1 img').count(),0);
      assert.equal(await page.locator('.fp-header h1').textContent(),'<img onerror=alert(1)>');
      const isolated=await browser.newContext();
      await isolated.addInitScript(()=>{Storage.prototype.setItem=()=>{throw new DOMException('blocked','SecurityError')};Storage.prototype.getItem=()=>{throw new DOMException('blocked','SecurityError')};});
      const blocked=await isolated.newPage();blocked.on('pageerror',e=>errors.push(e.message));
      await blocked.goto(`${base}/tools/orange-fortune-creator`);
      await blocked.waitForFunction(()=>document.querySelector('#formation-status').textContent.includes('已连接'));
      await blocked.locator('#deck-name').fill('存储不可用仍可编辑');
      assert.match(await blocked.locator('#save-status').textContent(),/未能保存/);
      await isolated.close();
    }
    assert.deepEqual(errors,[]);
    await browser.close(); console.log(`${name}: selection, equipment, isolation, energy, restore, layout and PNG export passed`);
  }
})().catch(e=>{console.error(e);process.exit(1)});
