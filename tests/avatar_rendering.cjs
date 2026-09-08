// Run with Playwright available in NODE_PATH: node tests/avatar_rendering.cjs
const { chromium, webkit } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

(async () => {
  for (const engine of [chromium, webkit]) {
    const browser = await engine.launch(engine === chromium && process.env.PLAYWRIGHT_CHROMIUM_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHROMIUM_CHANNEL } : {});
    try {
      const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3 });
      await page.addScriptTag({ path: path.join(__dirname, '../static/avatar.js') });
      const samples = await page.evaluate(async () => {
        const results = [];
        for (const color of ['#0021ed', '#ea580c', '#059669', '#abcdef']) {
          for (const size of [30, 34, 56, 112, 160]) {
            const img = window.jccAvatar.image(color, size);
            document.body.append(img);
            await img.decode();
            const canvas = document.createElement('canvas');
            canvas.width = canvas.height = size * 3;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            const alpha = (x, y) => ctx.getImageData(Math.floor(x / 104 * canvas.width), Math.floor(y / 104 * canvas.height), 1, 1).data[3];
            const angle = -47.989 * Math.PI / 180;
            const sample = (x, y) => alpha(52.328 + x*Math.cos(angle)-y*Math.sin(angle), 52.328 + x*Math.sin(angle)+y*Math.cos(angle));
            results.push({ color, size, hole: sample(.146, 24), ink: sample(.146+13.608/2, 24), corner: alpha(1, 1) });
            img.remove();
          }
        }
        return results;
      });
      for (const s of samples) {
        assert.equal(s.hole, 0, `Slit must stay transparent: ${JSON.stringify(s)}`);
        assert.equal(s.corner, 0, 'Avatar background must stay transparent');
        assert.ok(s.ink > 80, `Stripe must remain visible: ${JSON.stringify(s)}`);
      }
      console.log(`${engine.name()}: ${samples.length} color/size combinations passed at DPR 3`);
    } finally {
      await browser.close();
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
