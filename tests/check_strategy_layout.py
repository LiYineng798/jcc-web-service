"""Run against the isolated S19 preview with python tests/check_strategy_layout.py."""
import os
from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get('STRATEGY_PREVIEW_URL', 'http://127.0.0.1:5194')


def check_board(page):
    page.goto(f'{BASE}/live-comps/s19/16351')
    cells = page.locator('.formation-cell')
    expect(cells).to_have_count(28)
    names = page.locator('.formation-name')
    for name in ['努努和威朗普', '弗拉基米尔']:
        expect(page.locator('.formation-name', has_text=name)).to_be_visible()
    # Check the centers of the actual tiles. A wrapped caption must never set the row pitch.
    tiles = cells.evaluate_all("""cells => cells.map(cell => {
      const tile = cell.getBoundingClientRect();
      return [tile.x + tile.width / 2, tile.y + tile.height / 2, tile.height];
    })""")
    x0, y0, height = tiles[0]
    pitch = tiles[1][0] - x0
    for i, (x, y, h) in enumerate(tiles):
        row, col = divmod(i, 7)
        assert abs(h - height) < 1
        assert abs(x - (x0 + (col + (row % 2) / 2) * pitch)) < 1
        assert abs(y - (y0 + row * height * .78)) < 1
    # Check text fragments, including wrapped lines, against their actual cell.
    failures = names.evaluate_all("""labels => labels.filter(label => {
      const cell = label.closest('.formation-cell');
      const bounds = cell.getBoundingClientRect();
      const range = document.createRange();
      range.selectNodeContents(label);
      return [...range.getClientRects()].some(r => r.left < bounds.left - 1 ||
        r.right > bounds.right + 1 || r.bottom > bounds.bottom + 1);
    }).map(label => label.textContent)""")
    assert not failures, failures
    hero = page.get_by_role('button', name='弗拉基米尔', exact=False)
    hero.press('Enter')
    expect(page.locator('#unitDetail')).to_contain_text('弗拉基米尔')
    page.locator('.toolbox-trigger').click()
    menu = page.locator('.toolbox-panel').bounding_box()
    assert 0 <= menu['x'] and menu['x'] + menu['width'] <= page.viewport_size['width'] + 1
    page.locator('.toolbox-trigger').click()
    return page.locator('.board-panel').bounding_box()


def check_solver(page):
    page.goto(f'{BASE}/tools/s19-smeech')
    group = page.locator('.team-traits').first
    expect(group).to_be_visible()
    ids = page.evaluate("""async () => (await (await fetch(document.querySelector('#smeech').dataset.catalog))
      .json()).traits.map(t => [t.name, t.id])""")
    ids_by_name = dict(ids)
    icons = group.locator('li')
    assert icons.count() >= 9
    for entry in icons.all():
        glyph = entry.locator('use')
        name = entry.locator('span').text_content()
        assert glyph.get_attribute('href').endswith('#' + ids_by_name[name])
    page.locator('#themeToggle').click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    page.wait_for_function("""() => [...document.querySelectorAll('.team-traits[open] use')]
      .every(use => use.getBBox().width > 0 && use.getBBox().height > 0)""")
    group.locator('summary').press('Enter')
    expect(icons.first).to_be_hidden()
    return page.locator('.recommendations').bounding_box()


if __name__ == '__main__':
    with sync_playwright() as pw:
        for engine, width in [(pw.chromium, 1440), (pw.chromium, 768),
                              (pw.webkit, 390), (pw.chromium, 320)]:
            with engine.launch() as browser:
                page = browser.new_page(viewport={'width': width, 'height': 900}, color_scheme='light')
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                board = check_board(page)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                results = check_solver(page)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert abs(board['x'] - results['x']) < 1
                assert abs(board['width'] - results['width']) < 1
                assert not errors, errors
                print(f'{engine.name} {width}px passed')
