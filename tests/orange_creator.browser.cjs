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
    await page.locator('#deck-tempo').fill('8 级启动 · 稳定提质量');
    await page.locator('#deck-items').fill('优先主力输出装备，再补前排坦度');
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
    // Verify regular geometry and the stagger independently of exported pixels.
    const geometry=await page.locator('.fp-cell').evaluateAll(es=>es.slice(0,8).map(e=>({x:e.offsetLeft,y:e.offsetTop,w:e.offsetWidth,h:e.getBoundingClientRect().height})));
    const scale=(await page.locator('.fortune-poster').boundingBox()).width/1200;
    assert.ok(Math.abs(geometry[0].w/(geometry[0].h/scale)-Math.sqrt(3)/2)<.001);
    assert.equal(geometry[7].x-geometry[0].x,(geometry[1].x-geometry[0].x)/2);
    assert.ok(Math.abs(geometry[7].y-(geometry[1].x-geometry[0].x)*Math.sqrt(3)/2)<.6);
    assert.ok(await page.locator('.fp-trait-frame').count()>0);
    assert.ok(await page.locator('.fp-trait-frame').evaluateAll(es=>es.every(e=>/\/(1|2|3|4|unique)\.svg/.test(e.src))));
    assert.ok(await page.locator('.fp-trait').evaluateAll(es=>es.every(e=>getComputedStyle(e).borderTopWidth==='0px')));
    for(const layout of ['guide','showcase']) {
      await page.locator(`[name="poster-layout"][value="${layout}"]`).check();
      assert.equal(await page.locator('.fp-operations').count(),layout==='guide'?1:0);
      assert.equal(await page.locator('#deck-note').isVisible(),layout==='guide');
      for(const bg of (mobile?['jade','gilded','astral','ivory']:layout==='showcase'?['gilded']:['gilded','jade','astral','ivory'])) {
        await page.locator(`[data-background="${bg}"]`).click();
        const crops=await page.evaluate(()=>{
          const poster=document.querySelector('.fortune-poster').getBoundingClientRect(),scale=poster.width/1200;
          return ['.fp-card-art','.fp-unit','.fp-trait-emblem'].map(selector=>{
            const box=document.querySelector(selector).getBoundingClientRect();
            const trait=selector==='.fp-trait-emblem';
            return [(box.x-poster.x+box.width*(trait?0:.3))/scale,(box.y-poster.y+box.height*(trait?0:.4))/scale,(box.x-poster.x+box.width*(trait?1:.7))/scale,(box.y-poster.y+box.height*(trait?1:.6))/scale].map(Math.round);
          });
        });
        const downloadEvent=page.waitForEvent('download',{timeout:90000});
        await page.locator('#export-poster').click();
        const download=await downloadEvent;
        assert.equal(await download.failure(),null);
        const file=path.join(out,`portrait-${name}-${bg}-${layout}.png`);await download.saveAs(file);
        const png=PNG.sync.read(fs.readFileSync(file));assert.equal(png.width,1200);assert.equal(png.height,1600);
        for(const [index,[left,top,right,bottom]] of crops.entries()) {
          const colors=new Set();let bronze=0;
          for(let y=top;y<bottom;y++)for(let x=left;x<right;x++){
            const i=(y*png.width+x)*4,[r,g,b]=png.data.subarray(i,i+3);
            colors.add(`${r},${g},${b}`);
            if(r>100 && r>g*1.2 && r>b*1.7) bronze++;
          }
          assert.ok(index===2?bronze>150:colors.size>200,`missing embedded image ${index}: ${name}/${bg}/${layout}`);
        }
      }
    }
    await page.locator('[name="poster-layout"][value="guide"]').check();
    assert.equal(await page.locator('#deck-tempo').inputValue(),'8 级启动 · 稳定提质量');
    assert.match(await page.locator('.fp-notebook').innerText(),/围绕时间卡片/);
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('.fp-unit'));
    assert.equal(await page.locator('#deck-name').inputValue(),'时光里的胜利配方');
    assert.equal(await page.locator('.creator-slot.selected').count(),3);
    assert.equal(await page.locator('.fp-unit').count(),8);
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert.equal(overflow,false);
    const rect=await page.locator('.fortune-poster').boundingBox();const preview=await page.locator('#poster-preview').boundingBox();assert.ok(Math.abs(rect.width-preview.width)<2);
    await page.evaluate(()=>scrollTo(0,0));
    await page.screenshot({path:path.join(out,`portrait-${name}-page.png`),fullPage:true});
    await page.evaluate(()=>{document.documentElement.dataset.theme='dark';});
    await page.screenshot({path:path.join(out,`portrait-${name}-dark.png`),fullPage:true});
    // Missing-art card remains selectable and exports text honestly.
    await selectCard(page,2,'7250012');assert.match(await page.locator('.fortune-poster').innerText(),/卡图暂缺/);
    // Longest card descriptions must remain inside their allotted area.
    const longest=await page.evaluate(()=>JSON.parse(document.querySelector('#creator-config').textContent).cards.sort((a,b)=>b.description.length-a.description.length).slice(0,3).map(c=>c.id));
    for(let i=0;i<3;i++) await selectCard(page,i,longest[i]);
    const clipping=await page.locator('.fp-card-effect').evaluateAll(es=>es.some(e=>e.scrollHeight>e.clientHeight+1));assert.equal(clipping,false);
    await page.locator('#deck-name').fill('长标题边界检查'.repeat(4).slice(0,24));
    await page.locator('#deck-tempo').fill('启动节奏'.repeat(6));
    await page.locator('#deck-items').fill('装备优先'.repeat(10));
    await page.locator('#deck-note').fill('运营手记与转型时机。'.repeat(10));
    assert.equal(await page.locator('.fp-notebook p,.fp-plan p').evaluateAll(es=>es.some(e=>e.scrollHeight>e.clientHeight+1)),false);
    const sections=await page.locator('.fp-operations,.fp-footer').evaluateAll(es=>es.map(e=>e.getBoundingClientRect().toJSON()));
    assert.ok(sections[0].bottom<=sections[1].top,'operations overlap footer');
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
