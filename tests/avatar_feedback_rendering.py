"""Run the real home template/scripts with intercepted APIs, without a preview server."""
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'instance/avatar-review'
ORIGIN = 'http://avatar.test'


def home_html():
    env = Environment(loader=FileSystemLoader(ROOT / 'templates'), autoescape=select_autoescape())
    env.globals.update(static_v=lambda name: '/static/' + name,
                       url_for=lambda endpoint, filename: '/static/' + filename)
    return env.get_template('index.html').render(seo={'title': '头像互动验证', 'json_ld': []},
                                                 reference_seasons=[], simulator_enabled=True)


class Fixture:
    def __init__(self):
        self.fail = None
        self.requests = []
        self.html = home_html()
        self.lineup = dict(id=901, name='暖阳 · 阵容互动演示', code='#LOCAL-PREVIEW-ONLY',
                           rank_level='S', owner_username='demo', owner_nickname='阵容研究员',
                           owner_avatar_config=dict(version=1, preset='sunee', expression='neutral', color='#d5a06f'),
                           updated_at='2026-10-17 12:30:00', like_count=12, copy_count=38,
                           is_liked_today=False, is_favorited=False, can_edit=False, can_hide=False)

    def handle(self, route):
        path = urlparse(route.request.url).path
        method = route.request.method
        if path == '/':
            route.fulfill(content_type='text/html', body=self.html)
            return
        if path.startswith('/static/'):
            file = (ROOT / path.lstrip('/')).resolve()
            if file.is_relative_to(ROOT / 'static') and file.is_file():
                route.fulfill(content_type=mimetypes.guess_type(file)[0] or 'application/octet-stream', body=file.read_bytes())
            else:
                route.fulfill(status=404, body='')
            return
        self.requests.append((method, path))
        payload = {}
        status = 200
        if path == '/api/me':
            payload = {'user': {'id': 7, 'username': 'viewer', 'nickname': '预览用户', 'role': 'user'}, 'csrf_token': 'fixture-token'}
        elif path in ('/api/lineup-seasons', '/api/live-comps/seasons'):
            payload = {'seasons': [{'id': 's17-star-god', 'name': 'S17', 'status': 'active'}], 'default_season_id': 's17-star-god'}
        elif path == '/api/lineups':
            payload = {'items': [self.lineup.copy()], 'total': 1, 'page': 1, 'total_pages': 1}
        elif path == '/api/home-stats':
            payload = {'total_public_lineups': 1}
        elif path == '/api/live-comps':
            payload = {'items': [], 'total': 0, 'page': 1, 'total_pages': 1}
        elif path == '/api/site-config':
            payload = {'notice_enabled': False, 'simulator_enabled': True}
        elif path == '/api/lineups/901/copy':
            status, payload = 503, {'error': 'statistics unavailable'}
        elif path == '/api/lineups/901/like':
            if self.fail == 'like':
                status, payload = 409, {'error': 'already liked'}
            else:
                self.lineup['is_liked_today'] = True
                payload = {'ok': True}
        elif path == '/api/lineups/901/favorite':
            if self.fail == 'favorite':
                status, payload = 503, {'error': 'favorite unavailable'}
            else:
                self.lineup['is_favorited'] = method == 'POST'
                payload = {'ok': True}
        route.fulfill(status=status, content_type='application/json', body=json.dumps(payload))


def wait_finished(page):
    page.wait_for_function("!document.querySelector('.home-lineup-card .user-avatar').dataset.avatarFeedback", timeout=4000)


def scenario(browser, engine, width, theme, reduced):
    fixture = Fixture()
    context = browser.new_context(viewport={'width': width, 'height': 900},
                                  reduced_motion='reduce' if reduced else 'no-preference')
    page = context.new_page()
    page.route('**/*', fixture.handle)
    page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    page.add_init_script("Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{}},configurable:true})")
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(ORIGIN)
    page.get_by_role('tab', name='最新', exact=True).click()
    card = page.locator('.home-lineup-card')
    expect(card).to_have_count(1)
    avatar = card.locator('.user-avatar')
    before = avatar.bounding_box()
    label = f'{engine}-{width}-{theme}' + ('-reduced' if reduced else '')

    for kind, action in [('copy', 'copy'), ('like', 'heart'), ('favorite', 'bookmark')]:
        button = card.locator(f'button[data-card-action="{action}"]')
        if kind != 'copy':
            fixture.fail = kind
            with page.expect_response(f'**/api/lineups/901/{kind}') as response:
                button.click()
            assert response.value.status >= 400
            assert avatar.get_attribute('data-avatar-feedback') is None
            expect(page.locator('.jcc-notification.is-error')).to_be_visible()
            page.get_by_role('button', name='关闭通知', exact=True).click()
            fixture.fail = None
        page.evaluate("window.__avatar = document.querySelector('.home-lineup-card .user-avatar')")
        with page.expect_response(f'**/api/lineups/901/{kind}' + ('?*' if kind == 'copy' else '')) as response:
            button.click()
        assert response.value.status == (503 if kind == 'copy' else 200)
        expect(avatar).to_have_attribute('data-avatar-feedback', kind)
        expect(page.locator('.jcc-notification')).to_have_count(0)
        if kind == 'copy':
            expect(button).to_have_text('已复制')
        else:
            expect(button).to_have_attribute('aria-pressed', 'true')
        expect(avatar.locator('.avatar-feedback-badge')).to_have_count(0)
        expect(avatar.locator('.avatar-feedback-ring')).to_have_count(0)
        assert avatar.evaluate('el => el.children.length') == 1
        assert avatar.evaluate('(el) => el === window.__avatar')
        assert avatar.bounding_box()['width'] == before['width'] == 28
        assert avatar.bounding_box()['height'] == before['height'] == 28
        if reduced:
            assert avatar.evaluate('el => el.getAnimations({subtree:true}).length') == 0
            expect(avatar.locator(':scope > img')).to_be_visible()
        else:
            assert avatar.evaluate('el => el.getAnimations({subtree:true}).length') == 1
            # Freeze the finite emphasis animations for reproducible inspection, then resume them.
            avatar.evaluate('el => el.getAnimations({subtree:true}).forEach(a=>{a.pause();a.currentTime=420;})')
            card.screenshot(path=str(OUT / f'feedback-{kind}-{label}.png'), animations='allow')
            avatar.evaluate('el => el.getAnimations({subtree:true}).forEach(a=>a.play())')
        page.wait_for_timeout(650)
        assert avatar.evaluate('(el) => el === window.__avatar')
        wait_finished(page)
        assert avatar.locator('.avatar-feedback-badge, .avatar-feedback-ring').count() == 0
        assert avatar.evaluate('el => el.getAnimations({subtree:true}).length') == 0
        expect(avatar).to_have_attribute('data-avatar-expression', 'neutral')

    with page.expect_response('**/api/lineups/901/favorite'):
        card.locator('button[data-card-action="bookmark"]').click()
    expect(card.locator('button[data-card-action="bookmark"]')).to_have_attribute('aria-pressed', 'false')
    assert avatar.get_attribute('data-avatar-feedback') is None
    expect(page.locator('.jcc-notification')).to_have_count(0)
    assert ('DELETE', '/api/lineups/901/favorite') in fixture.requests
    if not reduced:
        avatar.evaluate("el => {jccAvatar.feedback(el,'favorite');window.__oldMotion=el.getAnimations({subtree:true});jccAvatar.feedback(el,'favorite');}")
        assert page.evaluate("window.__oldMotion.every(a=>a.playState==='idle')")
        continuity = avatar.evaluate('''async el => {
          const visual=el.firstElementChild;
          const animation=el.getAnimations({subtree:true})[0];
          animation.pause(); animation.currentTime=420;
          const before=getComputedStyle(visual).transform;
          jccAvatar.feedback(el,'like');
          const next=el.getAnimations({subtree:true})[0];next.pause();next.currentTime=0;
          const after=getComputedStyle(visual).transform;
          await new Promise(r=>setTimeout(r,80));
          const paths=()=>[...visual.querySelectorAll('path')].map(p=>p.getAttribute('d'));
          const faceBefore=paths();jccAvatar.feedback(el,'like');const faceAfter=paths();
          return {before,after,faceContinuous:JSON.stringify(faceBefore)===JSON.stringify(faceAfter)};
        }''')
        assert continuity['before'] == continuity['after'], continuity
        assert continuity['faceContinuous'], continuity
        expect(avatar.locator('.avatar-feedback-badge')).to_have_count(0)
        assert avatar.evaluate('el => el.getAnimations({subtree:true}).length') == 1
        page.emulate_media(reduced_motion='reduce')
        wait_finished(page)
        assert avatar.evaluate('el => el.getAnimations({subtree:true}).length') == 0
        page.emulate_media(reduced_motion='no-preference')
        avatar.evaluate("el => jccAvatar.feedback(el,'favorite')")
        page.evaluate("Object.defineProperty(document,'hidden',{value:true,configurable:true});document.dispatchEvent(new Event('visibilitychange'))")
        assert avatar.get_attribute('data-avatar-feedback') is None
        assert avatar.evaluate('el => el.getAnimations({subtree:true}).length') == 0
        page.evaluate('delete document.hidden')
        avatar.evaluate("el => jccAvatar.feedback(el,'copy')")
        avatar.evaluate('el => {window.__removed = el; el.remove()}')
        page.wait_for_timeout(50)
        assert page.evaluate("!__removed.dataset.avatarFeedback && __removed.getAnimations({subtree:true}).length===0 && !__removed.querySelector('.avatar-feedback-badge')")
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert not errors, errors
    context.close()
    return {'scenario': label, 'passed': True}


def runtime_geometry(browser):
    page = browser.new_page()
    page.set_content('<div id="avatars"></div>')
    page.add_style_tag(path=str(ROOT / 'static/avatar.css'))
    page.add_script_tag(path=str(ROOT / 'static/avatar-lab/app.js'))
    result = page.evaluate('''async () => {
      const results=[]; const root=document.querySelector('#avatars');
      for(const kind of ['copy','like','favorite']) {
        const nodes=Object.keys(jccAvatar.presets).map(preset=>{
          const node=jccAvatar.image({preset,expression:'neutral',color:'#d5a06f'},28);
          root.append(node);jccAvatar.feedback(node,kind);return node;
        });
        await new Promise(r=>setTimeout(r,500));
        for(const node of nodes) {
          const svg=node.firstElementChild.querySelector('svg'), b=svg.getBBox(),v=svg.viewBox.baseVal;
          results.push({kind,preset:node.dataset.avatarPreset,
            fits:b.x>=v.x-.1&&b.y>=v.y-.1&&b.x+b.width<=v.x+v.width+.1&&b.y+b.height<=v.y+v.height+.1});
          jccAvatar.dispose(node);node.remove();
        }
      }
      const restored=Object.keys(jccAvatar.expressions).map((expression,i)=>{
        const node=jccAvatar.image({preset:'sunee',expression,color:'#d5a06f'},28);
        root.append(node);const original=node.querySelector('img').src;
        jccAvatar.feedback(node,['copy','like','favorite'][i%3]);return {node,original,expression};
      });
      await new Promise(r=>setTimeout(r,2300));
      for(const {node,original,expression} of restored) {
        if(node.dataset.avatarExpression!==expression || node.querySelector('img')?.src!==original ||
          node.getAnimations({subtree:true}).length || node.querySelector('.avatar-feedback-badge')) {
          throw Error('Saved expression was not restored: '+expression);
        }
        node.remove();
      }
      return results;
    }''')
    assert all(row['fits'] for row in result), result
    assert page.locator('svg').count() == 0
    page.close()
    return result


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    geometry = []
    with sync_playwright() as p:
        for engine in ('chromium', 'webkit'):
            browser = getattr(p, engine).launch()
            for width, theme, reduced in ((1440, 'light', False), (390, 'dark', False), (360, 'light', True)):
                results.append(scenario(browser, engine, width, theme, reduced))
            geometry.append({'engine': engine, 'shapes': runtime_geometry(browser)})
            browser.close()
    report = {'scenarios': results, 'geometry': geometry}
    (OUT / 'feedback-results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    run()
