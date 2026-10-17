"""Measure the avatar runtime in a browser without unrelated page animations."""
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.environ.get('AVATAR_PREVIEW_URL', 'http://127.0.0.1:5148')
OUT = Path(__file__).resolve().parents[1] / 'instance/avatar-review'

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    offline = '--offline' in sys.argv
    if offline:
        page.set_content('<title>Avatar performance fixture</title>')
        page.add_style_tag(path=str(OUT.parents[1] / 'static/avatar.css'))
    else:
        page.goto(BASE + '/avatar-source')
    page.evaluate("""() => {
      window.__rafCount = 0;
      window.__realRaf = requestAnimationFrame.bind(window);
      window.requestAnimationFrame = cb => { window.__rafCount++; return __realRaf(cb); };
    }""")
    if offline:
        page.add_script_tag(path=str(OUT.parents[1] / 'static/avatar-lab/app.js'))
    else:
        page.add_script_tag(url=BASE + '/static/avatar-lab/app.js')
    result = page.evaluate("""async () => {
      const root = document.createElement('section');
      root.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px';
      document.body.prepend(root);
      const presets = ['sunee','cloudee','bloom','sprout','strobi','freddy','citrus','nova'];
      const expressions = Object.keys(jccAvatar.expressions);
      const inputs = Array.from({length:100}, (_,i) => ({preset:presets[i%presets.length],
        expression:expressions[Math.floor(i/presets.length)%expressions.length],color:'#'+(0x336699+i*111).toString(16)}));
      const render = () => { const start=performance.now(); root.replaceChildren(...inputs.map(c=>jccAvatar.image(c,36))); return performance.now()-start; };
      const coldMs = render(), warmMs = render();
      const idleStart = __rafCount;
      await new Promise(r=>setTimeout(r,250));
      const idleFrameRequests = __rafCount-idleStart;
      const nodes = [...root.children].slice(0,3);
      const frames = [];
      const start = performance.now();
      nodes.forEach((node,i)=>jccAvatar.feedback(node,['copy','like','favorite'][i]));
      await new Promise(resolve => {
        let previous;
        function sample(now) { if(previous) frames.push(now-previous); previous=now;
          if(now-start<2400) __realRaf(sample); else resolve(); }
        __realRaf(sample);
      });
      const frameRequestsAfterFeedback = __rafCount;
      await new Promise(r=>setTimeout(r,300));
      const idleAfterFeedback = __rafCount-frameRequestsAfterFeedback;
      frames.sort((a,b)=>a-b);
      const cleanupNode = root.firstElementChild;
      jccAvatar.feedback(cleanupNode,'copy'); cleanupNode.remove();
      await new Promise(r=>setTimeout(r,100));
      const before=__rafCount; await new Promise(r=>setTimeout(r,150));
      return {avatars:100,coldMs,warmMs,idleFrameRequests,
        simultaneousReactions:3,frameMedianMs:frames[Math.floor(frames.length/2)],
        frameP95Ms:frames[Math.floor(frames.length*.95)],idleAfterFeedback,
        detachedFrameRequests:__rafCount-before,remainingLiveSvg:root.querySelectorAll('svg').length,
        remainingAnimations:root.getAnimations({subtree:true}).length};
    }""")
    assert result['idleFrameRequests'] == 0
    assert result['idleAfterFeedback'] == 0
    assert result['detachedFrameRequests'] == 0
    assert result['remainingLiveSvg'] == 0
    assert result['remainingAnimations'] == 0
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'performance.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    browser.close()
