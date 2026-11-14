// Run against the isolated deck review preview. Verifies the actual asset geometry,
// public gallery, SSR/JS deck cards and the fixed-size PNG export on both engines.
const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {PNG}=require('pngjs');
const base=process.env.DECK_REVIEW_URL||'http://127.0.0.1:5143';
const out='instance/full-card-review';fs.mkdirSync(out,{recursive:true});
(async()=>{
 for(const [name,engine] of [['chromium',chromium],['webkit',webkit]]) {
  const browser=await engine.launch();const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/tools/orange-fortune');
  await page.evaluate(()=>document.fonts.ready);
  assert.equal(await page.locator('.fortune-card .is-official').count(),201);
  assert.equal(await page.locator('.fortune-card .fortune-card-bezel').count(),0);
  await page.locator('.fortune-card').first().evaluate(e=>e.scrollIntoView({block:'start'}));
  await page.locator('.fortune-card img').evaluateAll(es=>Promise.all(es.slice(0,10).map(e=>{e.loading='eager';return e.decode();})));
  await page.screenshot({path:`${out}/gallery-${name}-light.png`});
  for (const tier of ['1','2','3','4','5']) {
   await page.locator(`input[name=tier][value="${tier}"]`).check({force:true});
   const card=page.locator('.fortune-card:visible').first();await card.scrollIntoViewIfNeeded();
   const shape=await card.locator('.is-official').evaluate(e=>({ratio:e.clientWidth/e.clientHeight,clip:getComputedStyle(e).clipPath,loaded:e.querySelector('img').naturalWidth===512}));
   assert.ok(Math.abs(shape.ratio-.625)<.01);assert.equal(shape.clip,'none');assert.ok(shape.loaded);
   await card.locator('button').click();assert.ok(await page.locator('.fortune-dialog').isVisible());
   assert.ok((await page.locator('#fortune-detail-effect').innerText()).length>0);
   await page.keyboard.press('Escape');await page.waitForFunction(()=>document.activeElement?.classList.contains('fortune-card-button'));
  }
  await page.locator('input[name=tier][value=""]').check({force:true});
  await page.locator('[name=q]').fill('不存在的卡片xyz');assert.ok(await page.locator('.fortune-empty').isVisible());
  await page.locator('[name=q]').fill('黑玫瑰');assert.equal(await page.locator('.fortune-card:visible').count(),1);
  await page.locator('#themeToggle').click();await page.locator('.fortune-card:visible').scrollIntoViewIfNeeded();await page.screenshot({path:`${out}/gallery-${name}-dark.png`});
  await page.setViewportSize({width:390,height:844});await page.locator('[name=q]').fill('');await page.locator('.fortune-card').first().evaluate(e=>e.scrollIntoView({block:'start'}));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:`${out}/gallery-${name}-mobile.png`});
  await page.goto(base+'/?library=decks');await page.waitForSelector('.deck-thumb .is-official');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.locator('.deck-card').first().scrollIntoViewIfNeeded();await page.screenshot({path:`${out}/home-${name}-mobile.png`});
  await page.locator('.deck-thumb').first().click();await page.locator('.deck-dialog .is-official').waitFor({state:'visible'});await page.keyboard.press('Escape');
  await page.route('**/static/tools/orange-fortune/images/7250036.png*',route=>route.abort());
  await page.goto(base+'/tools/orange-fortune?q=黑玫瑰');await page.locator('.fortune-card:visible .fortune-missing').waitFor();
  assert.match(await page.locator('.fortune-card:visible .fortune-card-description').innerText(),/弈子/);
  await page.unroute('**/static/tools/orange-fortune/images/7250036.png*');
  await page.setViewportSize({width:1440,height:1050});await page.goto(base+'/tools/orange-fortune-creator');
  await page.evaluate(()=>localStorage.setItem('jcc-orange-creator-v1',JSON.stringify({version:1,title:'把好运，留给关键回合',author:'橘子研究所',layout:'cards',background:'gilded',portal:'unknown',cards:['7210014','7230005','7250036'],note:'围绕生效回合规划节奏，让资源在关键时刻兑现价值。优先稳住经济，再用高品质卡片完成构筑。'})));
  await page.reload();await page.waitForSelector('.fp-card .is-official');
  await page.locator('[data-slot="0"]').click();
  const pickerRatios=await page.locator('.creator-pick .is-official').evaluateAll(es=>es.map(e=>e.clientWidth/e.clientHeight));
  assert.equal(pickerRatios.length,201);assert.ok(pickerRatios.every(r=>Math.abs(r-.625)<.01),'picker must not stretch or crop full cards');
  await page.keyboard.press('Escape');
  const rects=await page.locator('.fp-card .is-official').evaluateAll(es=>es.map(e=>({h:e.clientHeight,w:e.clientWidth})));
  assert.ok(rects.every(r=>r.h===rects[0].h&&r.w===rects[0].w));
  for(const material of ['gilded','ivory']) {
   await page.locator(`[data-background="${material}"]`).click();
   const download=page.waitForEvent('download',{timeout:90000});await page.locator('#export-poster').click();
   const path=`${out}/poster-${name}-${material}.png`;await(await download).saveAs(path);await page.locator('[data-save-close]').click();
   const png=PNG.sync.read(fs.readFileSync(path));assert.equal(png.width,1200);assert.equal(png.height,1600);
   // Full artwork must survive foreignObject export, including the colored art at each tier.
   for(const [x,y] of [[225,400],[600,400],[975,400]]){let colorful=0;for(let yy=y;yy<y+140;yy++)for(let xx=x-60;xx<x+60;xx++){const i=(yy*png.width+xx)*4;const rgb=[...png.data.subarray(i,i+3)];if(Math.max(...rgb)-Math.min(...rgb)>40)colorful++;}assert.ok(colorful>2000,`${name}/${material}: card artwork missing`);}
  }
  assert.deepEqual(errors,[]);await browser.close();console.log(`${name}: all five tiers, mobile/dark gallery, card dialogs and light/dark 1200x1600 exports passed`);
 }
})().catch(e=>{console.error(e);process.exit(1)});
