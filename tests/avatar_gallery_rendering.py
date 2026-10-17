"""Compare all avatar silhouettes and card baselines in the real preview browser."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('AVATAR_PREVIEW_URL', 'http://127.0.0.1:5148')
OUT = Path(__file__).resolve().parents[1] / 'instance/avatar-review'


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        for engine in ('chromium', 'webkit'):
            browser = getattr(p, engine).launch()
            for width, theme in ((1440, 'light'), (390, 'dark'), (360, 'light')):
                page = browser.new_page(viewport={'width': width, 'height': 1000})
                page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
                page.goto(BASE)
                page.get_by_role('tab', name='最新', exact=True).click()
                cards = page.locator('.home-lineup-card')
                expect(cards).to_have_count(10)
                assert cards.locator('.user-avatar').evaluate_all("nodes => new Set(nodes.slice(0,8).map(n=>n.dataset.avatarPreset)).size") == 8
                assert cards.evaluate_all("""cards => cards.every(card => {
                    const avatar = card.querySelector('.user-avatar').getBoundingClientRect();
                    const name = card.querySelector('.home-card-author-name').getBoundingClientRect();
                    return Math.abs(avatar.width-28)<.1 && Math.abs(avatar.height-28)<.1 &&
                      Math.abs(avatar.y+avatar.height/2-name.y-name.height/2)<1 && name.x>avatar.right;
                })""")
                # Screenshot compact copies of the actual card author rows, not a synthetic layout.
                page.evaluate("""() => {
                    const panel = document.createElement('section'); panel.id='avatarAlignment';
                    panel.style.cssText='display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px;padding:20px;background:var(--bg)';
                    document.querySelectorAll('.home-lineup-card').forEach((card,i)=>{
                        if(i>=8)return; const item=document.createElement('article'); item.className='home-lineup-card';
                        item.append(card.querySelector('.home-card-byline').cloneNode(true)); panel.append(item);
                    }); document.querySelector('main').prepend(panel);
                }""")
                page.locator('#avatarAlignment').screenshot(path=str(OUT / f'alignment-{engine}-{width}-{theme}.png'))
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                page.evaluate("document.querySelector('#avatarAlignment').remove()")
                if width <= 390:
                    name = cards.first.locator('.home-card-author-name')
                    original_name = name.text_content()
                    name.evaluate("el => el.textContent='一位名字很长但认真研究阵容的上传者'")
                    assert cards.first.evaluate("""card => {
                      const avatar=card.querySelector('.user-avatar'), name=card.querySelector('.home-card-author-name');
                      const date=card.querySelector('time').getBoundingClientRect(), a=avatar.getBoundingClientRect(), n=name.getBoundingClientRect();
                      return a.width===28 && n.right<=date.left && Math.abs(a.y+a.height/2-n.y-n.height/2)<1 &&
                        getComputedStyle(avatar).overflow!=='hidden' && getComputedStyle(name).textOverflow==='ellipsis';
                    }""")
                    cards.first.screenshot(path=str(OUT / f'long-name-{engine}-{width}-{theme}.png'))
                    name.evaluate('(el,value)=>el.textContent=value', original_name)
                geometry = page.evaluate("""async () => {
                    const report=[];
                    const container=document.createElement('div'); document.body.append(container);
                    function bounds(svg) {
                      const box=svg.getBBox(), v=svg.viewBox.baseVal;
                      return {fits:box.x>=v.x-.1 && box.y>=v.y-.1 && box.x+box.width<=v.x+v.width+.1 && box.y+box.height<=v.y+v.height+.1,
                        box:[box.x,box.y,box.width,box.height], viewport:svg.getAttribute('viewBox')};
                    }
                    for(const preset of Object.keys(jccAvatar.presets)) {
                      for(const expression of Object.keys(jccAvatar.expressions)) {
                        const config={preset,expression,color:'#d5a06f'}, node=jccAvatar.image(config,176);
                        container.append(node);
                        const still=new DOMParser().parseFromString(decodeURIComponent(node.querySelector('img').src.split(',')[1]),'image/svg+xml').documentElement;
                        container.append(still); const original=bounds(still); still.remove();
                        jccAvatar.feedback(node,'copy'); const live=node.querySelector('svg');
                        if(!live) throw Error('No live SVG: '+preset);
                        const liveBounds=bounds(live);
                        if(original.viewport!==liveBounds.viewport) throw Error('Artboard jumps: '+preset);
                        report.push({preset,expression,still:original,live:liveBounds});
                        jccAvatar.dispose(node); node.remove();
                      }
                    }
                    for(const kind of ['copy','like','favorite']) {
                      const nodes=Object.keys(jccAvatar.presets).map(preset=>{const node=jccAvatar.image({preset,expression:'neutral',color:'#d5a06f'},40);container.append(node);jccAvatar.feedback(node,kind);return node;});
                      await new Promise(resolve=>setTimeout(resolve,500));
                      nodes.forEach(node=>{report.push({preset:node.dataset.avatarPreset,kind,animated:bounds(node.querySelector('svg'))});jccAvatar.dispose(node);node.remove();});
                    }
                    container.remove(); return report;
                }""")
                assert all(value['fits'] for item in geometry for key, value in item.items() if key in ('still', 'live', 'animated')), geometry
                page.goto(BASE + '/__preview__/login/user')
                page.goto(BASE + '/me#avatar')
                dialog = page.locator('.avatar-dialog')
                expect(dialog).to_be_visible()
                dialog.get_by_role('button', name='暖阳 · Sunee', exact=True).click()
                dialog.get_by_role('tab', name='配色', exact=True).click()
                dialog.get_by_role('button', name='陶杏', exact=True).click()
                dialog.get_by_role('tab', name='表情', exact=True).click()
                dialog.get_by_role('button', name='自然', exact=True).click()
                dialog.get_by_role('tab', name='形象', exact=True).click()
                dialog.screenshot(path=str(OUT / f'collection-{engine}-{width}-{theme}.png'))
                assert dialog.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
                results.append({'engine': engine, 'width': width, 'theme': theme, 'combinations': 64, 'geometry': geometry})
                page.close()
            browser.close()
    (OUT / 'alignment-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('Six browser/layout scenarios: 8 card baselines, 64 static/live artboards and 24 feedback shapes passed.')


if __name__ == '__main__':
    run()
