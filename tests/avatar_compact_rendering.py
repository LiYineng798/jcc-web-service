"""Check tabbed editor containment and delayed ordinary-card loading in real browsers."""
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get('AVATAR_PREVIEW_URL', 'http://127.0.0.1:5148')
OUT = Path(__file__).resolve().parents[1] / 'instance/avatar-review'


def check_editor(page, width, height, label):
    page.goto(BASE + '/__preview__/login/user', wait_until='networkidle')
    page.goto(BASE + '/me#avatar', wait_until='networkidle')
    dialog = page.locator('.avatar-dialog')
    expect(dialog).to_be_visible()
    assert dialog.locator('a').count() == 0
    expect(dialog.locator('[role="tabpanel"]:visible')).to_have_count(1)
    assert dialog.evaluate('el => el.scrollHeight <= el.clientHeight + 1 && el.scrollWidth <= el.clientWidth + 1')
    assert dialog.evaluate('el => el.getBoundingClientRect().bottom <= innerHeight + 1')
    footer = dialog.locator('.avatar-editor-footer').bounding_box()
    preview = dialog.locator('.avatar-preview-stage').bounding_box()
    panel = dialog.locator('.avatar-panel-scroll')
    panel.evaluate('el => el.scrollTop = el.scrollHeight')
    assert dialog.locator('.avatar-editor-footer').bounding_box() == footer
    assert dialog.locator('.avatar-preview-stage').bounding_box() == preview
    assert panel.bounding_box()['height'] > 40
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    shape = dialog.get_by_role('tab', name='形象', exact=True)
    shape.focus()
    page.keyboard.press('ArrowRight')
    expect(dialog.get_by_role('tab', name='表情', exact=True)).to_be_focused()
    expect(dialog.locator('#avatarPanelExpression')).to_be_visible()
    expect(dialog.locator('#avatarPanelShape')).to_be_hidden()
    for name in ('好奇', '惊讶', '害羞', '酷酷'):
        dialog.get_by_role('button', name=name, exact=True).click()
        expect(dialog.get_by_role('button', name=name, exact=True)).to_have_attribute('aria-pressed', 'true')
    dialog.get_by_role('tab', name='表情', exact=True).focus()
    page.keyboard.press('End')
    expect(dialog.get_by_role('tab', name='配色', exact=True)).to_be_focused()
    dialog.locator('#avatarHex').fill('#bad')
    expect(dialog.locator('.avatar-save')).to_be_disabled()
    expect(dialog.locator('#avatarHex')).to_have_attribute('aria-invalid', 'true')
    dialog.locator('#avatarHex').fill('#7e96ad')
    expect(dialog.locator('.avatar-save')).to_be_enabled()
    recommendations = dialog.locator('.avatar-recommendation')
    expect(recommendations).to_have_count(3)
    recommendations.first.click()
    expect(dialog.locator('#avatarHex')).to_have_value(recommendations.first.get_attribute('data-color'))
    expect(recommendations.first).to_have_attribute('aria-pressed', 'true')
    dialog.locator('#avatarHex').fill('#547182')
    dialog.get_by_role('tab', name='配色', exact=True).focus()
    page.keyboard.press('Home')
    expect(shape).to_be_focused()
    dialog.get_by_role('button', name='新芽 · Sprout', exact=True).click()
    expect(dialog.locator('#avatarHex')).to_have_value('#547182')
    expect(recommendations.first).to_have_attribute('aria-label', '推荐配色：苔绿')
    sample = dialog.locator('.avatar-card-sample .user-avatar')
    expect(sample).to_be_visible()
    assert sample.bounding_box()['width'] == sample.bounding_box()['height'] == 28
    assert sample.evaluate('el => getComputedStyle(el).padding') == '0px'
    for kind in ('copy', 'like', 'favorite'):
        dialog.locator(f'.avatar-preview-actions button[data-avatar-feedback="{kind}"]').click()
        expect(sample).to_have_attribute('data-avatar-feedback', kind)
        expect(dialog.locator('#avatarLargePreview .user-avatar')).to_have_attribute('data-avatar-feedback', kind)
        assert dialog.locator('.avatar-feedback-ring, .avatar-feedback-badge').count() == 0
    dialog.get_by_role('button', name='暖阳 · Sunee', exact=True).click()
    assert sample.get_attribute('data-avatar-feedback') is None
    assert sample.evaluate('el => el.getAnimations({subtree:true}).length') == 0
    assert dialog.locator('#avatarLargePreview .user-avatar').evaluate('el => el.getAnimations({subtree:true}).length') == 0
    dialog.screenshot(path=str(OUT / f'tabs-shapes-{label}.png'))
    dialog.get_by_role('tab', name='配色', exact=True).click()
    dialog.screenshot(path=str(OUT / f'tabs-colors-{label}.png'))
    dialog.get_by_role('tab', name='表情', exact=True).click()
    panel.evaluate('el => el.scrollTop = 0')
    dialog.screenshot(path=str(OUT / f'tabs-expressions-{label}.png'))
    dialog.locator('.avatar-cancel').click()
    expect(dialog).not_to_be_visible()
    page.get_by_role('button', name='调整头像', exact=True).first.click()
    expect(shape).to_have_attribute('aria-selected', 'true')
    expect(dialog.locator('.avatar-save')).to_be_disabled()
    page.keyboard.press('Escape')
    expect(dialog).not_to_be_visible()


def check_skeleton(page, width, label, reduced):
    page.goto(BASE)
    pending = []
    def hold_lineups(route):
        pending.append(route)
        page.evaluate('window.__lineupRequestHeld = true')

    page.route('**/api/lineups?*', hold_lineups)
    page.get_by_role('tab', name='最新', exact=True).click()
    skeletons = page.locator('.t-skel-card')
    expect(skeletons).to_have_count(3)
    page.wait_for_function('window.__lineupRequestHeld === true')
    assert pending
    expect(page.locator('.home-lineup-card')).to_have_count(0)
    assert skeletons.first.locator('button, a, [tabindex], [data-card-icon]').count() == 0
    assert skeletons.first.get_attribute('aria-hidden') == 'true'
    geometry = skeletons.first.evaluate('''el => {
      const rect = name => el.querySelector('.t-skel-' + name).getBoundingClientRect();
      const avatar=rect('avatar'), copy=rect('copy'), code=rect('code-text'), social=rect('social'), utilities=rect('utilities');
      return {avatar:avatar.width, copyBelow:copy.top>=code.bottom, copyRight:copy.left>=code.right,
        utilitiesBelow:utilities.top>=social.bottom, pulse:getComputedStyle(el).animationName};
    }''')
    assert geometry['avatar'] == 28
    assert geometry['copyBelow' if width <= 600 else 'copyRight']
    if width <= 600:
        assert geometry['utilitiesBelow']
    if reduced:
        assert geometry['pulse'] == 'none'
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    loading_height = page.locator('.t-skel').bounding_box()['height']
    page.locator('.t-skel').screenshot(path=str(OUT / f'skeleton-{label}.png'))
    response = pending[0].fetch()
    payload = response.json()
    if isinstance(payload, dict):
        payload['items'] = payload['items'][:1]
    else:
        payload = payload[:1]
    pending[0].fulfill(response=response, json=payload)
    expect(page.locator('.home-lineup-card')).to_have_count(1)
    expect(page.locator('.t-skel')).to_have_class('t-skel is-revealed')
    page.wait_for_timeout(650)
    final_height = page.locator('.t-skel').bounding_box()['height']
    card_height = page.locator('.home-lineup-card').bounding_box()['height']
    assert abs(final_height - card_height) < 1
    assert final_height < loading_height
    assert page.locator('.t-skel-skeleton').evaluate('el => getComputedStyle(el).overflow') == 'clip'
    page.unroute('**/api/lineups?*')
    return geometry


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        for engine in ('chromium', 'webkit'):
            browser = getattr(p, engine).launch()
            for width, height, theme in ((1440, 1000, 'light'), (390, 844, 'dark'), (360, 640, 'light'),
                                         (390, 420, 'light'), (844, 390, 'dark')):
                reduced = height == 420
                context = browser.new_context(viewport={'width': width, 'height': height},
                                              reduced_motion='reduce' if reduced else 'no-preference')
                page = context.new_page()
                page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                label = f'{engine}-{width}x{height}-{theme}'
                check_editor(page, width, height, label)
                geometry = check_skeleton(page, width, label, reduced)
                assert not errors, errors
                results.append({'scenario': label, 'passed': True, 'skeleton': geometry})
                context.close()
            browser.close()
    (OUT / 'compact-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    run()
