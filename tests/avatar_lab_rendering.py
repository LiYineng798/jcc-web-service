"""Exercise the real loopback preview, including morph feedback and configuration."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('AVATAR_PREVIEW_URL', 'http://127.0.0.1:5148')
OUT = Path(__file__).resolve().parents[1] / 'instance/avatar-review'
OUT.mkdir(parents=True, exist_ok=True)


def run():
    results = []
    with sync_playwright() as p:
        for engine in ('chromium', 'webkit'):
            browser = getattr(p, engine).launch()
            for width, theme in ((1440, 'light'), (390, 'light'), (390, 'dark')):
                context = browser.new_context(viewport={'width': width, 'height': 1000})
                context.add_init_script("localStorage.setItem('theme', '" + theme + "')")
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: errors.append(message.text) if 'Avatar motion fell back' in message.text else None)
                def available_likes(route):
                    response = route.fetch()
                    payload = response.json()
                    items = payload.get('items', []) if isinstance(payload, dict) else payload
                    for item in items:
                        item['is_liked_today'] = False
                    route.fulfill(response=response, json=payload)

                page.route('**/api/lineups?*', available_likes)
                page.goto(BASE + '/__preview__/login/user')
                assert page.evaluate("""() => {
                    for (const preset of Object.keys(jccAvatar.presets)) {
                      for (const expression of Object.keys(jccAvatar.expressions)) {
                        const node = jccAvatar.image({preset, expression, color:'#7c3aed'}, 40);
                        document.body.append(node);
                        jccAvatar.feedback(node, 'copy');
                        const animated = !!node.querySelector('svg');
                        jccAvatar.dispose(node); node.remove();
                        if (!animated) return false;
                      }
                    }
                    return true;
                }""")
                page.get_by_role('tab', name='最新', exact=True).click()
                card = page.locator('.home-lineup-card').first
                expect(card).to_be_visible()
                expect(card.locator('.user-avatar img')).to_be_visible()
                page.evaluate("window.__feedbackNode = document.querySelector('.home-lineup-card .user-avatar')")
                page.evaluate("Object.defineProperty(navigator, 'clipboard', {value:{writeText:async()=>{}}, configurable:true})")
                page.route('**/api/lineups/*/copy?*', lambda route: route.fulfill(status=503, content_type='application/json', body='{"error":"test"}'))
                card.get_by_role('button', name='复制阵容码', exact=True).click()
                expect(card.locator('.user-avatar')).to_have_attribute('data-avatar-feedback', 'copy')
                assert card.locator('.avatar-feedback-ring, .avatar-feedback-badge').count() == 0
                assert card.locator('.user-avatar').evaluate('el => el.children.length') == 1
                card.locator('.user-avatar').evaluate('el => el.getAnimations({subtree:true}).forEach(a=>{a.pause();a.currentTime=420;})')
                card.screenshot(path=str(OUT / f'body-only-copy-{engine}-{width}-{theme}.png'), animations='allow')
                card.locator('.user-avatar').evaluate('el => el.getAnimations({subtree:true}).forEach(a=>a.play())')
                page.wait_for_timeout(800)
                assert page.evaluate("window.__feedbackNode === document.querySelector('.home-lineup-card .user-avatar')")
                expect(card.locator('.user-avatar')).to_have_attribute('data-avatar-feedback', 'copy')
                page.wait_for_timeout(1600)
                expect(card.locator('.user-avatar img')).to_be_visible()
                assert card.locator('.user-avatar').get_attribute('data-avatar-feedback') is None
                page.unroute('**/api/lineups/*/copy?*')
                page.route('**/api/lineups/*/like', lambda route: route.fulfill(status=200, content_type='application/json', body='{"ok":true}'))
                card.locator('[data-card-action="heart"]').click()
                expect(card.locator('.user-avatar')).to_have_attribute('data-avatar-feedback', 'like')
                page.wait_for_timeout(2300)
                page.unroute('**/api/lineups/*/like')
                page.route('**/api/lineups/*/like', lambda route: route.fulfill(status=409, content_type='application/json', body='{"error":"already liked"}'))
                card.locator('[data-card-action="heart"]').click()
                page.wait_for_timeout(200)
                assert card.locator('.user-avatar').get_attribute('data-avatar-feedback') is None
                page.unroute('**/api/lineups/*/like')
                card.screenshot(path=str(OUT / f'card-{engine}-{width}-{theme}.png'))
                page.evaluate("""async () => {
                    const me = await (await fetch('/api/me')).json();
                    await fetch('/api/me/avatar', {method:'PUT', headers:{'Content-Type':'application/json','X-CSRF-Token':me.csrf_token},
                      body:JSON.stringify({preset:'strobi',expression:'neutral',color:'#7c3aed'})});
                }""")
                page.goto(BASE + '/me#avatar')
                dialog = page.locator('.avatar-dialog')
                expect(dialog).to_be_visible()
                expect(dialog.locator('.avatar-presets .avatar-choice')).to_have_count(8)
                expect(dialog.locator('.avatar-expressions .avatar-choice')).to_have_count(8)
                dialog.get_by_role('button', name='暖阳 · Sunee', exact=True).click()
                dialog.get_by_role('tab', name='表情', exact=True).click()
                dialog.get_by_role('button', name='好奇', exact=True).click()
                dialog.get_by_role('tab', name='配色', exact=True).click()
                dialog.locator('#avatarHex').fill('#d5a06f')
                expect(dialog.locator('.avatar-save')).to_be_enabled()
                dialog.get_by_role('button', name='试试复制', exact=True).click()
                expect(dialog.locator('#avatarLargePreview .user-avatar')).to_have_attribute('data-avatar-feedback', 'copy')
                page.wait_for_timeout(2300)
                dialog.screenshot(path=str(OUT / f'editor-{engine}-{width}-{theme}.png'))
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                assert dialog.evaluate('el => el.scrollWidth <= el.clientWidth + 1')
                with page.expect_response('**/api/me/avatar') as saved:
                    dialog.locator('.avatar-save').click()
                assert saved.value.status == 200
                config = saved.value.json()['user']['avatar_config']
                assert config == {'version': 1, 'preset': 'sunee', 'expression': 'curious', 'color': '#d5a06f'}
                expect(dialog).not_to_be_visible()
                page.reload()
                expect(dialog).to_be_visible()
                expect(dialog.locator('#avatarHex')).to_have_value('#d5a06f')
                dialog.get_by_role('button', name='新星 · Nova', exact=True).click()
                page.keyboard.press('Escape')
                expect(dialog).not_to_be_visible()
                page.reload()
                expect(dialog.get_by_role('button', name='暖阳 · Sunee', exact=True)).to_have_attribute('aria-pressed', 'true')
                page.emulate_media(reduced_motion='reduce')
                dialog.get_by_role('button', name='试试点赞', exact=True).click()
                expect(dialog.locator('#avatarLargePreview .user-avatar img')).to_be_visible()
                assert dialog.locator('#avatarLargePreview .user-avatar svg').count() == 0
                page.wait_for_timeout(1900)
                assert dialog.locator('#avatarLargePreview .user-avatar').get_attribute('data-avatar-feedback') is None
                assert not errors, errors
                results.append({'engine': engine, 'width': width, 'theme': theme, 'passed': True})
                context.close()
            browser.close()
    (OUT / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    run()
