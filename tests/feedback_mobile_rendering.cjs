const { chromium, webkit, request } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.PREVIEW_URL || 'http://127.0.0.1:5087';
(async () => {
 const auth = await request.newContext();
 const login = await auth.post(base+'/api/login',{data:{account:'previewadmin',password:'Preview1234'}});
 assert.equal(login.status(),200);
 const storageState = await auth.storageState();
 await auth.dispose();
 for (const [engineName, engine] of [['chromium',chromium],['webkit',webkit]]) {
  const browser = await engine.launch();
  try {
   for (const width of [320,390,768,1280]) {
    const context = await browser.newContext({viewport:{width,height:844},deviceScaleFactor:1,storageState});
    const page = await context.newPage();
    await page.goto(base+'/admin');
    await page.locator('.admin-stat-card').first().waitFor();
    for (const y of [0,200,650,1200,250,0]) {
     await page.evaluate(y=>window.scrollTo(0,y),y);
     await page.waitForTimeout(80);
     const rect = await page.locator('.admin-topbar').boundingBox();
     assert(Math.abs(rect.y)<1, `${engineName} ${width}: header jumped to ${rect.y}`);
    }
    if(width<=820) {
     for(const height of [640,920,844]) {
      await page.setViewportSize({width,height});
      await page.evaluate(()=>scrollTo(0,400));
      await page.waitForTimeout(80);
      assert(Math.abs((await page.locator('.admin-topbar').boundingBox()).y)<1);
     }
     await page.evaluate(()=>scrollTo(0,0));
    }
    const overflow = await page.evaluate(()=>document.documentElement.scrollWidth > innerWidth);
    assert(!overflow, `admin overflow at ${width}`);
    if(width===390) await page.screenshot({path:path.join('instance',engineName+'-admin.png')});
    await page.goto(base+'/');
    await page.locator('[data-sort="latest"][data-view="all"]').click();
    await page.locator('.lineup-card-actions').first().waitFor();
    const card = page.locator('.lineup-card').filter({has:page.locator('.lineup-card-actions')}).first();
    await card.scrollIntoViewIfNeeded();
    const boxes = await card.evaluate(card=>{
     const outer=card.getBoundingClientRect();
     return [...card.querySelectorAll('.small-button')].map(b=>({text:b.textContent,width:b.clientWidth,scroll:b.scrollWidth,left:b.getBoundingClientRect().left-outer.left,right:b.getBoundingClientRect().right-outer.right}));
    });
    assert.equal(boxes.filter(b=>b.text==='失效反馈').length,1);
    assert(!boxes.some(b=>/删除|举报/.test(b.text)));
    assert(boxes.every(b=>b.scroll<=b.width+1 && b.left>=0 && b.right<=1),JSON.stringify(boxes));
    if(width===390) {
     await card.screenshot({path:path.join('instance',engineName+'-card.png')});
     await card.getByRole('button',{name:'失效反馈',exact:true}).click();
     await page.getByRole('heading',{name:'阵容码失效反馈',exact:true}).waitFor();
     await page.screenshot({path:path.join('instance',engineName+'-feedback.png')});
    }
    console.log(`${engineName} ${width}: header stable, no overflow, all actions fit`);
    await context.close();
   }
  } finally { await browser.close(); }
 }
 const browser = await chromium.launch();
 try {
  const context = await browser.newContext({viewport:{width:390,height:844}});
  assert.equal((await context.request.post(base+'/api/login',{data:{account:'previewuser',password:'Preview1234'}})).status(),200);
  const page = await context.newPage();
  await page.goto(base+'/');
  await page.locator('[data-sort="latest"][data-view="all"]').click();
  const actions = page.locator('.lineup-card-actions').first();
  await actions.getByRole('button',{name:'失效反馈',exact:true}).click();
  const reason = `浏览器验收反馈 ${Date.now()}：阵容码无法导入`;
  await page.locator('.modal-backdrop textarea').fill(reason);
  const submitted = page.waitForResponse(r=>r.url().includes('/report') && r.request().method()==='POST');
  await page.getByRole('button',{name:'提交失效反馈',exact:true}).click();
  assert((await submitted).ok());
  const admin = await request.newContext({storageState});
  const reports = await (await admin.get(base+'/api/admin/reports')).json();
  const feedback = reports.items.find(r=>r.reason===reason && r.status==='pending');
  assert(feedback);
  const lineup = await (await context.request.get(base+'/api/lineups/'+feedback.lineup_id)).json();
  assert.equal(lineup.status,'normal');
  await admin.dispose();
  console.log('ordinary user feedback submitted and visible in admin pending queue');
 } finally {await browser.close()}
})().catch(e=>{console.error(e); process.exit(1)});
