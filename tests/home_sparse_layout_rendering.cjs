// Real local preview endpoints; check geometry after both uncached and cached results.
const {chromium, webkit} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.MOBILE_ADMIN_REPORT_PREVIEW_URL || 'http://127.0.0.1:5127';
const out = 'instance/mobile-admin-report-preview/screenshots';
fs.mkdirSync(out, {recursive:true});

async function waitForResults(page, count) {
  await page.waitForFunction(expected => {
    const cards = document.querySelectorAll('#lineupList .lineup-card:not(.t-skel-card)');
    if (expected === 0) return cards.length === 0 && !document.querySelector('#emptyState').classList.contains('hidden');
    const wrapper = document.querySelector('#lineupList .t-skel');
    const content = wrapper?.querySelector('.t-skel-content');
    return cards.length === expected && wrapper?.classList.contains('is-revealed') && getComputedStyle(content).opacity === '1';
  }, count);
}

async function checkScrollExtent(page) {
  await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
  const size = await page.evaluate(() => ({
    body: document.body.getBoundingClientRect().height,
    scroll: document.documentElement.scrollHeight,
    viewport: innerHeight,
  }));
  assert.ok(size.scroll <= Math.ceil(Math.max(size.body, size.viewport)) + 1,
    `hidden placeholders extend the page: ${JSON.stringify(size)}`);
}

(async () => {
  for (const [engineName, engine] of [['chromium',chromium],['webkit',webkit]]) {
    const browser = await engine.launch();
    try {
      for (const width of [390, 1440, 1920]) {
        for (const theme of ['light','dark']) {
          const context = await browser.newContext({
            viewport:{width,height:width === 390 ? 844 : width === 1920 ? 1080 : 828},
            reducedMotion:theme === 'dark' ? 'reduce' : 'no-preference',
          });
          await context.addInitScript(value => localStorage.setItem('theme',value), theme);
          const page = await context.newPage();
          const errors = []; page.on('pageerror',e=>errors.push(e.message));
          await page.goto(base);
          await page.locator('.live-comp-card').first().waitFor();

          let release, started;
          const held = new Promise(resolve => {started=resolve;});
          const gate = new Promise(resolve => {release=resolve;});
          await page.route('**/api/lineups?**', async route => {
            started(); await gate; await route.continue();
          });
          await page.locator('[data-sort="ss"]').click();
          await held;
          assert.equal(await page.locator('.t-skel-skeleton .t-skel-card').count(),3);
          release();
          await waitForResults(page,1);
          await page.unroute('**/api/lineups?**');
          await checkScrollExtent(page);
          await page.screenshot({path:`${out}/${engineName}-single-${width}-${theme}.png`,animations:'disabled'});

          await page.locator('[data-sort="latest"][data-view="all"]').click();
          await waitForResults(page,10);
          await checkScrollExtent(page);
          // Returning to the SS tab exercises the cached render path.
          await page.locator('[data-sort="ss"]').click();
          await waitForResults(page,1);
          await checkScrollExtent(page);

          await page.locator('#searchInput').fill('不存在的阵容测试');
          await waitForResults(page,0);
          await checkScrollExtent(page);
          assert.deepEqual(errors,[]);
          await context.close();
        }
      }
      console.log(`${engineName}: single/empty/multiple results, cached rendering, 390/1440/1920 widths and both themes passed`);
    } finally {await browser.close();}
  }
})().catch(error=>{console.error(error);process.exitCode=1});
