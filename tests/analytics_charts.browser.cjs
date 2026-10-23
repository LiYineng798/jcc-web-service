const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium,webkit}=require('playwright');
const base=process.env.CREATOR_PREVIEW_URL||'http://127.0.0.1:5146';
const out='instance/creator-review';fs.mkdirSync(out,{recursive:true});
(async()=>{
  for(const engine of [chromium,webkit]) {
    const browser=await engine.launch();
    const page=await browser.newPage({viewport:{width:1440,height:1050},reducedMotion:'reduce'});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(`${base}/__preview__/login/admin`);
    await page.locator('[data-admin-tab="analytics"]:visible').first().click();
    await page.locator('.analytics-chart').first().waitFor();
    for(const theme of ['light','dark']) {
      await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
      await page.evaluate(()=>document.fonts.ready);
      await page.screenshot({path:`${out}/analytics-${engine.name()}-${theme}.png`,fullPage:true,animations:'disabled'});
    }
    const first=page.locator('.analytics-chart').first();
    const bar=first.locator('.analytics-bar-group').first();
    await bar.hover();
    assert.equal(await bar.evaluate(node=>node.classList.contains('is-active')),true);
    await first.locator('h3').hover();
    assert.equal(await first.locator('.is-active').count(),0,'pointer exit must clear hover highlighting');
    await bar.click();
    await first.locator('h3').hover();
    assert.equal(await first.locator('.is-active').count(),0,'click must not latch the hover highlighting');
    await first.locator('.analytics-bar-group').first().focus();
    await page.keyboard.press('ArrowRight');
    assert.match(await first.locator('.analytics-chart-detail').innerText(),/登录入口/);
    assert.ok(await first.locator('.analytics-bar-group').nth(1).evaluate(node=>node.matches(':focus-visible')),'keyboard focus must remain visible');
    await first.locator('summary').click();
    assert.equal(await first.locator('tbody tr').count(),5);
    const second=page.locator('.analytics-chart').nth(1);
    await second.locator('summary').click();
    assert.ok(await page.locator('.analytics-data-table').evaluateAll(tables=>tables.every(table=>{
      const headers=[...table.querySelectorAll('thead th')];
      return [...table.querySelectorAll('tbody tr')].every(row=>[...row.children].every((cell,index)=>{
        const header=headers[index], a=cell.getBoundingClientRect(), b=header.getBoundingClientRect();
        return Math.abs(a.left-b.left)<1 && Math.abs(a.right-b.right)<1 && getComputedStyle(cell).textAlign===getComputedStyle(header).textAlign;
      }));
    })),'expanded data columns must align');
    for(const theme of ['light','dark']) {
      await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
      await page.screenshot({path:`${out}/analytics-expanded-${engine.name()}-${theme}.png`,fullPage:true,animations:'disabled'});
    }
    for(const width of [320,390,768,1280,1920]) {
      await page.setViewportSize({width,height:900});
      await page.waitForFunction(()=>[...document.querySelectorAll('.analytics-chart-plot')].every(plot=>Math.abs(plot.clientWidth-Number(plot.firstElementChild.getAttribute('viewBox').split(' ')[2]))<2));
      assert.ok(await page.locator('.analytics-chart-plot,.analytics-table-shell,.analytics-rates').evaluateAll(nodes=>nodes.every(node=>node.scrollWidth<=node.clientWidth+1)),'charts, data tables and rates must fit without horizontal scrolling');
      assert.ok(await page.locator('.analytics-chart-plot>svg').evaluateAll(nodes=>nodes.every(node=>node.getBoundingClientRect().height<=240.5)),'chart height must not grow with width');
    }
    await page.setViewportSize({width:1440,height:1050});
    await second.locator('.analytics-legend-item').first().click();
    assert.equal(await second.locator('.analytics-legend-item').first().getAttribute('aria-pressed'),'false');
    await page.getByRole('button',{name:'搜索与设备',exact:true}).click();
    await page.locator('.experience-section .analytics-chart').waitFor();
    assert.deepEqual(await page.locator('.experience-section .analytics-legend-item').allTextContents(),['访问人数','搜索人数']);
    const metrics=await page.evaluate(async()=>{
      const [start,end]=[...document.querySelectorAll('.experience-range input')].map(input=>input.value);
      const response=await fetch(`/api/admin/experience?start=${start}&end=${end}`);return response.json();
    });
    await page.locator('.experience-section .analytics-data summary').click();
    assert.deepEqual(await page.locator('.experience-section .analytics-data tbody tr').evaluateAll(rows=>rows.map(row=>[...row.children].map(cell=>cell.textContent))),metrics.devices.map(d=>[d.label,String(d.uv),String(d.search_visitors)]));
    await page.screenshot({path:`${out}/devices-${engine.name()}.png`,fullPage:true});
    for(const width of [390,768]) {
      await page.setViewportSize({width,height:844});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      await page.screenshot({path:`${out}/devices-${engine.name()}-${width}.png`,fullPage:true});
    }
    await page.evaluate(()=>{
      const host=document.querySelector('.experience-section');
      host.replaceChildren(window.JccAnalyticsCharts.chart({title:'空数据测试',description:'没有数据',rows:[{label:'未知',a:0,b:0}],series:[{key:'a',label:'访问'},{key:'b',label:'复制',texture:'hatch'}]}));
    });
    assert.ok(!(await page.locator('.experience-section svg').first().getAttribute('viewBox')).includes('NaN'));
    assert.deepEqual(errors,[]);await browser.close();
    console.log(`${engine.name()}: chart themes, keyboard, legend, data table, zero data and responsive layout passed`);
  }
})().catch(error=>{console.error(error);process.exit(1);});
