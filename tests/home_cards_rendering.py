"""Run against serve_home_cards_preview.py; screenshots stay in ignored instance/."""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('HOME_CARD_PREVIEW_URL', 'http://127.0.0.1:5136')
OUT = Path(__file__).resolve().parents[1] / 'instance' / 'home-card-review'
OUT.mkdir(parents=True, exist_ok=True)


def open_cards(page):
    page.goto(BASE)
    page.get_by_role('tab', name='最新', exact=True).click()
    expect(page.locator('.home-lineup-card')).to_have_count(10)
    expect(page.locator('.home-lineup-card [data-slot="icon"]').first).to_be_visible()
    page.wait_for_function("getComputedStyle(document.querySelector('.t-skel-content')).opacity === '1'")


def check_layout(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.locator('.home-lineup-card').evaluate_all('''cards => cards.every(card =>
      [...card.querySelectorAll('button,pre,h3,time')].every(el => {
        const a=el.getBoundingClientRect(), b=card.getBoundingClientRect();
        return a.left >= b.left && a.right <= b.right + 1 && el.scrollWidth <= el.clientWidth + 1;
      }))''')
    assert page.evaluate("!document.documentElement.hasAttribute('data-flow')")
    assert page.locator('.home-card-social').evaluate_all('''rows => rows.every(row => {
      const boxes = [...row.children].map(el => el.getBoundingClientRect());
      return boxes.every(box => Math.abs(box.width - boxes[0].width) < 1 && Math.abs(box.top - boxes[0].top) < 1);
    })''')
    assert page.locator('.home-lineup-card').first.evaluate('''card => {
      const resolved = document.createElement('span');
      resolved.style.color = 'var(--accent-strong)';
      card.append(resolved);
      const accent = getComputedStyle(resolved).color;
      resolved.remove();
      return getComputedStyle(card.querySelector('.home-card-copy')).backgroundColor === accent;
    }''')
    if page.viewport_size['width'] <= 600:
        assert page.locator('.home-card-byline').evaluate_all('''rows => rows.every(row => {
          const author = row.querySelector('.author-link').getBoundingClientRect();
          const updated = row.querySelector('time').getBoundingClientRect();
          return updated.left >= author.right && Math.abs(updated.top + updated.height / 2 - author.top - author.height / 2) < 1;
        })''')


def check_calm_motion(page, icon):
    button = page.locator(f'.home-lineup-card [data-card-action="{icon}"]').first
    button.scroll_into_view_if_needed()
    page.mouse.move(0, 0)
    svg = button.locator('[data-slot="icon"]')
    expect(svg).to_be_visible()
    button.hover()
    expect(button.locator('[data-slot="animated-icon"]')).to_have_attribute('data-preset', 'pulse')
    samples = svg.evaluate('''svg => new Promise(resolve => {
      const samples = [], start = performance.now();
      function sample(now) {
        const ink = svg.querySelector('[data-icon-part="glyph"]');
        samples.push({elapsed: now - start, transform: ink.getAttribute('transform'),
          visible: [...svg.querySelectorAll('path,line,polyline,circle')].every(part =>
            getComputedStyle(part).opacity === '1' && !part.hasAttribute('stroke-dashoffset'))});
        if (now - start < 700) requestAnimationFrame(sample); else resolve(samples);
      }
      requestAnimationFrame(sample);
    })''')
    assert all(sample['visible'] for sample in samples), icon
    assert any(150 < sample['elapsed'] < 400 and sample['transform'] for sample in samples), icon
    assert all(not sample['transform'] for sample in samples if sample['elapsed'] > 550), icon
    page.mouse.move(0, 0)



def run():
    results = []
    with sync_playwright() as p:
        for engine_name in ['chromium', 'webkit']:
            browser = getattr(p, engine_name).launch()
            for width in [360, 390, 768, 1440]:
                for theme in ['light', 'dark']:
                    context = browser.new_context(viewport={'width': width, 'height': 1000}, device_scale_factor=1)
                    context.add_init_script(f"localStorage.setItem('theme', '{theme}')")
                    page = context.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    open_cards(page)
                    check_layout(page)
                    first = page.locator('.home-lineup-card').first
                    first.scroll_into_view_if_needed()
                    page.screenshot(path=str(OUT / f'{engine_name}-{width}-{theme}.png'))
                    first.screenshot(path=str(OUT / f'card-{engine_name}-{width}-{theme}.png'))
                    copy = first.get_by_role('button', name='复制阵容码', exact=True)
                    first.locator('.author-link').focus()
                    page.keyboard.press('Tab')
                    assert copy.evaluate("el => el === document.activeElement && el.matches(':focus-visible')")
                    expect(first.locator('[data-card-icon="copy"] [data-animated]')).to_have_count(1)
                    page.emulate_media(reduced_motion='reduce')
                    expect(first.locator('[data-animated]')).to_have_count(0)
                    first.get_by_role('button', name='收藏', exact=True).click()
                    expect(page.get_by_role('heading', name='登录后继续')).to_be_visible()
                    page.get_by_role('button', name='稍后', exact=True).click()
                    page.get_by_role('tab', name='实时阵容排行').click()
                    expect(page.locator('.home-lineup-card')).to_have_count(0)
                    expect(page.locator('#homeCardIcons [data-slot]')).to_have_count(0)
                    assert not errors, errors
                    results.append(f'{engine_name}/{width}/{theme}: layout, keyboard, reduced motion, guest intent, unmount OK')
                    context.close()
            browser.close()

        browser = p.chromium.launch()
        context = browser.new_context(permissions=['clipboard-read', 'clipboard-write'], viewport={'width': 1440, 'height': 1000})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        open_cards(page)
        first = page.locator('.home-lineup-card').first
        expected_code = first.locator('.code-preview').text_content()
        page.route('**/api/lineups/*/copy?*', lambda route: route.fulfill(status=503, content_type='application/json', body='{"error":"preview stats unavailable"}'))
        first.get_by_role('button', name='复制阵容码', exact=True).click()
        expect(first.get_by_role('button', name='已复制', exact=True)).to_be_visible()
        assert page.evaluate('navigator.clipboard.readText()') == expected_code
        page.unroute('**/api/lineups/*/copy?*')
        page.goto(BASE + '/__preview__/login/user')
        page.get_by_role('tab', name='最新', exact=True).click()
        first = page.locator('.home-lineup-card').first
        expect(first.get_by_role('button', name='编辑', exact=True)).to_be_visible()
        check_calm_motion(page, 'flag')
        check_calm_motion(page, 'pencil')
        favorite = first.locator('[data-card-action="bookmark"]')
        if favorite.get_attribute('aria-pressed') == 'true':
            favorite.click()
            expect(favorite).to_have_attribute('aria-pressed', 'false')
        favorite.click()
        expect(favorite).to_have_attribute('aria-pressed', 'true')
        assert favorite.evaluate('el => el === document.activeElement')
        favorite.click()
        expect(favorite).to_have_attribute('aria-pressed', 'false')
        like = first.locator('[data-card-action="heart"]')
        if not like.is_disabled():
            like.click()
        expect(like).to_be_disabled()
        expect(like).to_have_attribute('aria-pressed', 'true')
        first.get_by_role('button', name='失效反馈', exact=True).click()
        expect(page.get_by_role('heading', name='阵容码失效反馈')).to_be_visible()
        page.locator('#authPromptRoot').get_by_role('button', name='关闭', exact=True).click()
        first.get_by_role('button', name='查看', exact=True).click()
        page.wait_for_url('**/lineup/*')
        page.locator('[data-home-return]').click()
        expect(page.locator('.home-lineup-card').first).to_be_visible()
        expect(page.locator('.home-lineup-card [data-slot="icon"]').first).to_be_visible()
        assert not errors, errors
        page.goto(BASE + '/__preview__/login/admin')
        open_cards(page)
        check_calm_motion(page, 'eye-off')
        page.set_viewport_size({'width': 360, 'height': 1000})
        check_layout(page)
        first = page.locator('.home-lineup-card').first
        first.screenshot(path=str(OUT / 'card-admin-360-light.png'))
        first.locator('.home-card-author-name').evaluate("el => el.textContent = '一位名字很长但仍然喜欢认真研究阵容的上传者'")
        first.locator('.home-card-number').evaluate_all("nodes => nodes.forEach(el => el.textContent = '1,234,567')")
        check_layout(page)
        first.screenshot(path=str(OUT / 'card-long-name-counts-360-light.png'))
        assert not errors, errors
        results.append('Authenticated actions: clipboard despite failed stats, favorite/unfavorite, focus restoration, daily like, report, detail return, calm flag/pencil/eye motion OK')
        context.close()
        browser.close()
    (OUT / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n'.join(results))


if __name__ == '__main__':
    run()
