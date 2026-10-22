// Typography, trait alignment, and embedded-font export on the isolated preview.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium, webkit} = require('playwright');
const {PNG} = require('pngjs');
const base = process.env.CREATOR_PREVIEW_URL || 'http://127.0.0.1:5139';
const out = 'instance/creator-review';
fs.mkdirSync(out, {recursive:true});

(async()=>{
  const titleInk=[];
  for(const [name, engine] of [['chromium',chromium],['webkit',webkit]]) {
    const browser = await engine.launch();
    const page = await browser.newPage({viewport:{width:1500,height:1050}});
    await page.goto(`${base}/tools/orange-fortune-creator`);
    await page.waitForFunction(()=>document.querySelector('#formation-status').textContent.includes('已连接'));
    await page.locator('#deck-name').fill('时光里的胜利配方');
    for(const [i,id] of ['7250036','7250046','7250034'].entries()) {
      await page.locator(`[data-slot="${i}"]`).click();
      await page.locator(`[data-card="${id}"]`).click();
    }
    await page.locator('#edit-formation').click();
    const units=page.frameLocator('#formation-frame').locator('.hero-button:not(.is-locked)');
    for(let i=0;i<8;i++) await units.nth(i).click();
    await page.locator('[data-close="formation-dialog"]').click();
    await page.waitForFunction(()=>!document.querySelector('#export-poster').disabled);
    await page.evaluate(()=>document.fonts.ready);
    assert.ok(await page.evaluate(()=>document.fonts.check('600 25px "JCC Editorial Serif"','时光里的胜利配方')));
    assert.match(await page.locator('.fp-header h1').evaluate(e=>getComputedStyle(e).fontFamily),/JCC Editorial Serif/);
    // Synthetic extremes verify layout only; these are not game trait thresholds.
    const alignment = await page.evaluate(()=>{
      const list=document.querySelector('.fp-traits'), original=list.innerHTML;
      const row=list.querySelector('.fp-trait');
      for(let i=1;i<8;i++) list.append(row.cloneNode(true));
      [...list.children].slice(8).forEach(e=>e.remove());
      [...list.children].forEach((e,i)=>{e.querySelector('b').textContent=i%2?'10':'2';e.lastElementChild.textContent=i%2?'比尔吉沃特':'主宰';});
      const columns=[...list.children].map(e=>[...e.children].map(c=>{const r=c.getBoundingClientRect();return {left:r.left,center:r.top+r.height/2};}));
      const fits=list.getBoundingClientRect().height<=document.querySelector('.fp-board').getBoundingClientRect().height;
      list.innerHTML=original;
      return {columns,fits};
    });
    assert.ok(alignment.fits,'eight traits must fit beside the board');
    for(const row of alignment.columns) {
      row.forEach((cell,i)=>assert.ok(Math.abs(cell.left-alignment.columns[0][i].left)<.5,'trait columns drift'));
      assert.ok(Math.max(...row.map(c=>c.center))-Math.min(...row.map(c=>c.center))<.5,'trait contents are not vertically centered');
    }
    await page.evaluate(()=>{
      const toSvg=window.htmlToImage.toSvg;
      window.htmlToImage.toSvg=(node,options)=>{
        window.posterFontEmbedded=options.fontEmbedCSS.includes('JCC Editorial Serif')&&options.fontEmbedCSS.includes('data:');
        return toSvg(node,options);
      };
    });
    const downloadEvent=page.waitForEvent('download',{timeout:90000});
    await page.locator('#export-poster').click();
    const download=await downloadEvent;
    assert.equal(await page.evaluate(()=>window.posterFontEmbedded),true);
    const file=`${out}/typography-${name}.png`;
    await download.saveAs(file);
    const png=PNG.sync.read(fs.readFileSync(file));
    assert.equal(png.width,1200);assert.equal(png.height,1600);
    let ink=0;
    for(let y=100;y<160;y++)for(let x=55;x<500;x++) {
      const i=(y*png.width+x)*4;
      if(png.data[i]>180&&png.data[i+1]>180&&png.data[i+2]>160) ink++;
    }
    assert.ok(ink>1000,'exported title is missing');
    titleInk.push(ink);
    await page.locator('#deck-name').fill('长标题边界检查'.repeat(4).slice(0,24));
    await page.locator('#deck-note').fill('运营手记与转型时机。'.repeat(10));
    const longest=await page.evaluate(()=>JSON.parse(document.querySelector('#creator-config').textContent).cards.sort((a,b)=>b.description.length-a.description.length).slice(0,3).map(c=>c.id));
    for(const [i,id] of longest.entries()) {
      await page.locator(`[data-slot="${i}"]`).click();await page.locator(`[data-card="${id}"]`).click();
    }
    const boundaries=await page.evaluate(()=>{
      const rect=s=>document.querySelector(s).getBoundingClientRect();
      return {
        clipped:[...document.querySelectorAll('.fp-card-effect,.fp-notebook p')].some(e=>e.scrollHeight>e.clientHeight+1),
        titleFits:rect('.fp-header h1').right<=rect('.fp-brand').left,
        footerFits:rect('.fp-operations').bottom<=rect('.fp-footer').top,
      };
    });
    assert.deepEqual(boundaries,{clipped:false,titleFits:true,footerFits:true});
    await browser.close();
    console.log(`${name}: local font, eight aligned traits, single/double digit counts and embedded-font PNG passed`);
  }
  assert.ok(Math.max(...titleInk)/Math.min(...titleInk)<1.25,'exported title weight differs between browsers');
})().catch(error=>{console.error(error);process.exit(1)});
