// Run against an isolated worktree preview; screenshots/downloads stay under instance/.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium, webkit, devices} = require('playwright');
const {PNG} = require('pngjs');
const base = process.env.CREATOR_PREVIEW_URL || 'http://127.0.0.1:5139';
const out = path.resolve('instance/creator-review');
fs.mkdirSync(out, {recursive:true});

async function panel(page, name) {
  const button=page.locator(`[data-panel="${name}"]`);
  if(await button.isVisible()) await button.click();
}
async function preview(page, open) {
  const button=page.locator('#open-preview');
  if(await button.isVisible()) {
    if(open) await button.click();
    else await page.locator('[data-close="preview-dialog"]').click();
  }
}
async function selectCard(page, slot, id) {
  await panel(page,'cards');
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
    await panel(page,'content');
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
    // Three Legendary cards: energy 15 exceeds the Stable portal but stays exportable.
    await panel(page,'profile');
    await page.locator('label[data-portal="stable"]').click();
    assert.equal(await page.locator('#energy-value').textContent(),'15 / 8');
    assert.match(await page.locator('#portal-help').textContent(),/能量 15 超出上限 8.*仍可导出/);
    assert.equal(await page.locator('#energy-meter.is-over').count(),1);
    assert.equal(await page.locator('#card-slots.is-over').count(),1);
    assert.equal(await page.locator('.fp-energy-chip.is-over').count(),1);
    assert.equal(await page.locator('#export-poster').isDisabled(),false);
    assert.equal(await page.locator('label[data-portal="unknown"]').getAttribute('data-fit'),'fit');
    await page.locator('label[data-portal="unknown"]').click();
    assert.equal(await page.locator('#energy-value').textContent(),'15 / 15');
    assert.equal(await page.locator('.fp-energy-chip.is-over').count(),0);
    assert.match(await page.locator('.fp-meta').innerText(),/未知传送门[\s\S]*入场 2,000 金橘币[\s\S]*失败随机损失 3 张/);
    assert.match(await page.locator('.fp-card-round').first().innerText(),/传说\s*能量 5/);
    await preview(page,true);
    // Verify regular geometry and the stagger independently of exported pixels.
    const geometry=await page.locator('.fp-cell').evaluateAll(es=>es.slice(0,8).map(e=>({x:e.offsetLeft,y:e.offsetTop,w:e.offsetWidth,h:e.getBoundingClientRect().height})));
    const scale=(await page.locator('.fortune-poster').boundingBox()).width/1200;
    assert.ok(Math.abs(geometry[0].w/(geometry[0].h/scale)-Math.sqrt(3)/2)<.001);
    assert.equal(geometry[7].x-geometry[0].x,(geometry[1].x-geometry[0].x)/2);
    assert.ok(Math.abs(geometry[7].y-(geometry[1].x-geometry[0].x)*Math.sqrt(3)/2)<.6);
    assert.ok(await page.locator('.fp-trait-frame').count()>0);
    assert.ok(await page.locator('.fp-trait-frame').evaluateAll(es=>es.every(e=>/\/(1|2|3|4|unique)\.svg/.test(e.src))));
    assert.ok(await page.locator('.fp-trait').evaluateAll(es=>es.every(e=>getComputedStyle(e).borderTopWidth==='0px')));
    await preview(page,false);
    for(const layout of ['guide','showcase']) {
      await panel(page,'content');
      await page.locator(`[name="poster-layout"][value="${layout}"]`).check();
      assert.equal(await page.locator('.fp-operations').count(),layout==='guide'?1:0);
      assert.equal(await page.locator('#deck-note').isVisible(),layout==='guide');
      for(const bg of (mobile?['jade','gilded','astral','ivory']:layout==='showcase'?['gilded']:['gilded','jade','astral','ivory'])) {
        await panel(page,'materials');
        await page.locator(`[data-background="${bg}"]`).click();
        await preview(page,true);
        const crops=await page.evaluate(()=>{
          const poster=document.querySelector('.fortune-poster').getBoundingClientRect(),scale=poster.width/1200;
          return ['.fp-card-art','.fp-unit','.fp-trait-emblem'].map(selector=>{
            const box=document.querySelector(selector).getBoundingClientRect();
            const trait=selector==='.fp-trait-emblem';
            return [(box.x-poster.x+box.width*(trait?0:.3))/scale,(box.y-poster.y+box.height*(trait?0:.4))/scale,(box.x-poster.x+box.width*(trait?1:.7))/scale,(box.y-poster.y+box.height*(trait?1:.6))/scale].map(Math.round);
          });
        });
        await preview(page,false);
        const downloadEvent=page.waitForEvent('download',{timeout:90000});
        await page.locator('#export-poster').click();
        if (mobile) {
          await page.locator('.creator-save-dialog[open]').waitFor({timeout:90000});
          await page.locator('[data-save-download]').click();
        }
        const download=await downloadEvent;
        assert.equal(await download.failure(),null);
        const file=path.join(out,`portrait-${name}-${bg}-${layout}.png`);await download.saveAs(file);
        await page.locator('[data-save-close]').click();
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
    // Card recommendation layout: no board, energy and portal panels, exported at full size.
    await panel(page,'profile');
    await page.locator('label[data-portal="volatile"]').click();
    await panel(page,'content');
    await page.locator('[name="poster-layout"][value="cards"]').check();
    assert.equal(await page.locator('#deck-note').isVisible(),true);
    assert.equal(await page.locator('#deck-tempo').isVisible(),false);
    assert.equal(await page.locator('.fp-formation').count(),0);
    assert.equal(await page.locator('.fp-eq-total').textContent(),'15');
    assert.match(await page.locator('.fp-portal-panel').innerText(),/波动传送门[\s\S]*400 金橘币[\s\S]*随机损失两张卡片/);
    assert.match(await page.locator('.fp-energy-note').innerText(),/超出波动传送门上限 5 点/);
    for(const bg of (mobile?['editorial']:['editorial','folio'])) {
      await panel(page,'materials');
      await page.locator(`[data-background="${bg}"]`).click();
      await preview(page,true);
      const crop=await page.evaluate(()=>{
        const poster=document.querySelector('.fortune-poster').getBoundingClientRect(),scale=poster.width/1200;
        const box=document.querySelector('.fp-card-art').getBoundingClientRect();
        return [(box.x-poster.x+box.width*.3)/scale,(box.y-poster.y+box.height*.4)/scale,(box.x-poster.x+box.width*.7)/scale,(box.y-poster.y+box.height*.6)/scale].map(Math.round);
      });
      await preview(page,false);
      const downloadEvent=page.waitForEvent('download',{timeout:90000});
      await page.locator('#export-poster').click();
      if (mobile) {
        await page.locator('.creator-save-dialog[open]').waitFor({timeout:90000});
        await page.locator('[data-save-download]').click();
      }
      const download=await downloadEvent;
      assert.match(download.suggestedFilename(),/卡组推荐版\.png$/);
      const file=path.join(out,`portrait-${name}-${bg}-cards.png`);await download.saveAs(file);
      await page.locator('[data-save-close]').click();
      const png=PNG.sync.read(fs.readFileSync(file));assert.equal(png.width,1200);assert.equal(png.height,1600);
      const colors=new Set();const [left,top,right,bottom]=crop;
      for(let y=top;y<bottom;y++)for(let x=left;x<right;x++){const i=(y*png.width+x)*4;colors.add(png.data.subarray(i,i+3).join());}
      assert.ok(colors.size>200,`missing card art: ${name}/${bg}/cards`);
    }
    await panel(page,'content');
    await page.locator('[name="poster-layout"][value="guide"]').check();
    assert.equal(await page.locator('#deck-tempo').inputValue(),'8 级启动 · 稳定提质量');
    assert.match(await page.locator('.fp-notebook').innerText(),/围绕时间卡片/);
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('.fp-unit'));
    assert.equal(await page.locator('#deck-name').inputValue(),'时光里的胜利配方');
    assert.equal(await page.locator('.creator-slot.selected').count(),3);
    assert.equal(await page.locator('.fp-unit').count(),8);
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert.equal(overflow,false);
    await preview(page,true);
    const rect=await page.locator('.fortune-poster').boundingBox();const previewBox=await page.locator('#poster-preview').boundingBox();assert.ok(Math.abs(rect.width-previewBox.width)<2);
    await page.evaluate(()=>scrollTo(0,0));
    await page.screenshot({path:path.join(out,`portrait-${name}-page.png`),fullPage:true});
    await page.evaluate(()=>{document.documentElement.dataset.theme='dark';});
    await page.screenshot({path:path.join(out,`portrait-${name}-dark.png`),fullPage:true});
    await preview(page,false);
    // Missing-art card remains selectable and exports text honestly.
    await selectCard(page,2,'7250012');assert.match(await page.locator('.fortune-poster').innerText(),/卡图暂缺/);
    // Longest card descriptions must remain inside their allotted area.
    const longest=await page.evaluate(()=>JSON.parse(document.querySelector('#creator-config').textContent).cards.sort((a,b)=>b.description.length-a.description.length).slice(0,3).map(c=>c.id));
    for(let i=0;i<3;i++) await selectCard(page,i,longest[i]);
    await preview(page,true);
    const clipping=await page.locator('.fp-card-effect').evaluateAll(es=>es.some(e=>e.scrollHeight>e.clientHeight+1));assert.equal(clipping,false);
    await preview(page,false);
    await panel(page,'profile');
    await page.locator('#deck-name').fill('长标题边界检查'.repeat(4).slice(0,24));
    await panel(page,'content');
    await page.locator('#deck-tempo').fill('启动节奏'.repeat(6));
    await page.locator('#deck-items').fill('装备优先'.repeat(10));
    await page.locator('#deck-note').fill('运营手记与转型时机。'.repeat(10));
    await preview(page,true);
    assert.equal(await page.locator('.fp-notebook p,.fp-plan p').evaluateAll(es=>es.some(e=>e.scrollHeight>e.clientHeight+1)),false);
    const sections=await page.locator('.fp-operations,.fp-footer').evaluateAll(es=>es.map(e=>e.getBoundingClientRect().toJSON()));
    assert.ok(sections[0].bottom<=sections[1].top,'operations overlap footer');
    await preview(page,false);
    await panel(page,'content');
    await page.locator('[name="poster-layout"][value="cards"]').check();
    await preview(page,true);
    assert.equal(await page.locator('.fp-card-effect,.fp-recommend p').evaluateAll(es=>es.some(e=>e.scrollHeight>e.clientHeight+1)),false);
    const stacked=await page.locator('.fp-deck,.fp-summary,.fp-recommend,.fp-footer').evaluateAll(es=>es.map(e=>e.getBoundingClientRect().toJSON()));
    for(let i=1;i<stacked.length;i++) assert.ok(stacked[i-1].bottom<=stacked[i].top+.5,`cards layout section ${i} overlaps`);
    await preview(page,false);
    await page.locator('[name="poster-layout"][value="guide"]').check();
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
