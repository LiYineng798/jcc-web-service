// Real browser coverage for fresh gestures, cancellation and blocked-save fallbacks.
const assert = require('node:assert/strict');
const {chromium, webkit, devices} = require('playwright');
const base = process.env.CREATOR_PREVIEW_URL || 'http://127.0.0.1:5146';
(async()=>{
  for(const engine of [chromium,webkit]) {
    const browser=await engine.launch();
    const page=await browser.newPage(devices['iPhone 13']);
    await page.goto(`${base}/tools/orange-fortune-creator`);
    await page.evaluate(()=>{
      window.shareCalls=[]; window.shareFailure='AbortError';
      Object.defineProperty(navigator,'canShare',{configurable:true,value:()=>true});
      Object.defineProperty(navigator,'share',{configurable:true,value:async payload=>{
        window.shareCalls.push({active:navigator.userActivation.isActive,name:payload.files[0].name});
        if(window.shareFailure) throw new DOMException('test',window.shareFailure);
      }});
      const canvas=document.createElement('canvas');canvas.width=1200;canvas.height=1600;
      canvas.toBlob(blob=>window.JccPosterSave.present(blob,'测试海报.png'));
    });
    await page.locator('.creator-save-dialog[open]').waitFor();
    assert.equal(await page.locator('[data-save-share]').isVisible(),true);
    await page.locator('[data-save-share]').click();
    await page.waitForFunction(()=>document.querySelector('.poster-save-status').textContent.includes('已取消'));
    assert.equal(await page.evaluate(()=>shareCalls[0].active),true);
    assert.equal(await page.locator('.creator-save-dialog').isVisible(),true);
    await page.evaluate(()=>window.shareFailure='NotAllowedError');
    await page.locator('[data-save-share]').click();
    await page.waitForFunction(()=>document.querySelector('.poster-save-status').textContent.includes('长按'));
    const downloadEvent=page.waitForEvent('download');await page.locator('[data-save-download]').click();
    const download=await downloadEvent;assert.equal(await download.failure(),null);
    assert.equal(download.suggestedFilename(),'测试海报.png');
    const url=await page.locator('.poster-save-image').getAttribute('src');
    await page.locator('[data-save-close]').click();
    assert.equal(await page.evaluate(async url=>(await fetch(url)).ok,url),true);
    await page.evaluate(()=>{
      Object.defineProperty(navigator,'canShare',{configurable:true,value:()=>false});
      window.JccPosterSave.present(new Blob(['png'],{type:'image/png'}),'再次导出.png');
    });
    assert.equal(await page.locator('[data-save-share]').isVisible(),false);
    assert.notEqual(await page.locator('.poster-save-image').getAttribute('src'),url);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('.creator-save-dialog').isVisible(),false);
    await browser.close();console.log(`${engine.name()}: save gesture, cancel, denied, download and URL lifetime passed`);
  }
})().catch(error=>{console.error(error);process.exit(1);});
