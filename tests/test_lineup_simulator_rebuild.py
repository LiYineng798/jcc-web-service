import json
from pathlib import Path

from assets_version import asset_stamp


SIMULATOR_ROOT = Path('static/tools/lineup-simulator')
SEASON_ROOT = Path('static/season-data')


def test_simulator_page_uses_new_tool_workspace(client):
    response = client.get('/tools/lineup-simulator')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="seasonSwitcher"' in html
    assert 'id="boardGrid"' in html
    assert 'id="traitSummary"' in html
    assert 'id="componentSummary"' in html
    assert 'id="heroGroups"' in html
    assert 'id="traitFilterButton"' in html
    assert 'id="traitFilterMenu"' in html
    assert 'id="itemGrid"' in html
    assert 'id="detailPopover"' in html
    assert 'data-season-data-version="' in html
    assert 'data/version.json' not in html
    assert 'local-data.js' not in html


def test_simulator_loads_every_season_from_catalog():
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')
    catalog = json.loads((SEASON_ROOT / 'catalog.json').read_text(encoding='utf-8'))

    assert 'fetchJson(`${DATA_ROOT}/catalog.json?v=${encodeURIComponent(DATA_VERSION)}`)' in javascript
    assert 'cache: "no-cache"' in javascript
    assert '`${season.version_id}-${DATA_VERSION}`' in javascript
    assert 'await refreshCatalog();\n    await loadSeason(seasonId);' in javascript
    assert 'compareSeasons' in javascript
    assert 'season.version_id' in javascript
    assert 'champions.json?v=${stamp}' in javascript
    assert 'traits.json?v=${stamp}' in javascript
    assert 'items.json?v=${stamp}' in javascript
    for season in catalog['seasons']:
        season_root = SEASON_ROOT / season['season_id']
        assert (season_root / 'champions.json').is_file()
        assert (season_root / 'traits.json').is_file()
        assert (season_root / 'items.json').is_file()


def test_mutable_season_json_requires_revalidation(client):
    response = client.get('/static/season-data/catalog.json')

    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'public, max-age=0, must-revalidate'


def test_static_asset_stamp_covers_simulator_assets(monkeypatch, tmp_path):
    import assets_version

    simulator_root = tmp_path / 'tools' / 'lineup-simulator'
    simulator_root.mkdir(parents=True)
    simulator_app = simulator_root / 'app.js'
    simulator_app.write_text('console.log("simulator")', encoding='utf-8')
    monkeypatch.setattr(assets_version, 'STATIC_ROOT', tmp_path)
    monkeypatch.setattr(assets_version, '_stamp', None)

    assert asset_stamp() == str(simulator_app.stat().st_mtime_ns)


def test_simulator_prefers_versioned_webp_images_for_every_season():
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')
    catalog = json.loads((SEASON_ROOT / 'catalog.json').read_text(encoding='utf-8'))

    assert 'optimized_local_path || raw.images?.icon?.local_path' in javascript
    assert 'optimized_local_path || raw.image?.local_path' in javascript
    for season in catalog['seasons']:
        season_root = SEASON_ROOT / season['season_id']
        documents = (
            ('champions.json', 'champions', lambda row: (row.get('images') or {}).get('icon')),
            ('traits.json', 'traits', lambda row: row.get('image')),
            ('items.json', 'items', lambda row: row.get('image')),
        )
        for filename, collection, get_image in documents:
            rows = json.loads((season_root / filename).read_text(encoding='utf-8')).get(collection) or []
            for row in rows:
                image = get_image(row)
                if not isinstance(image, dict) or not image.get('local_path'):
                    continue
                optimized = image.get('optimized_local_path')
                assert optimized, f"{season['season_id']} {collection} {row['id']} missing optimized image"
                assert optimized.endswith('.webp')
                assert f"/{season['version_id']}/" in f"/{optimized}"
                assert (season_root / optimized).is_file()


def test_simulator_implements_board_and_equipment_rules():
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')

    assert 'Array(28).fill(null)' in javascript
    assert 'if (slot.items.length >= 3)' in javascript
    assert 'contributors.get(traitId).add(hero.id)' in javascript
    assert 'raw.extensions?.trait_id ?? raw.extensions?.fetter_id' in javascript
    assert 'grantedTraitId: rawGrantedTraitId == null' in javascript
    assert 'state.itemById.get(itemId)?.grantedTraitId' in javascript
    assert 'state.traitById.has(traitId)' in javascript
    assert 'item?.recipe?.component_ids' in javascript
    assert 'hero.availability?.type === "unlock"' in javascript
    assert 'moveUnit(fromIndex, toIndex)' in javascript
    assert 'localStorage.setItem' in javascript
    assert 'exportBoardImage' in javascript
    assert 'if (itemChip) {\n    event.preventDefault();\n    hidePopover();' in javascript
    assert 'if (!cell) return;\n  event.preventDefault();\n  hidePopover();\n  mutate(() => { state.board' in javascript


def test_every_simulator_emblem_maps_to_a_known_trait():
    catalog = json.loads((SEASON_ROOT / 'catalog.json').read_text(encoding='utf-8'))

    for season in catalog['seasons']:
        season_root = SEASON_ROOT / season['season_id']
        items = json.loads((season_root / 'items.json').read_text(encoding='utf-8')).get('items') or []
        traits = json.loads((season_root / 'traits.json').read_text(encoding='utf-8')).get('traits') or []
        trait_ids = {str(trait['id']) for trait in traits}
        for item in items:
            if item.get('category') != 'emblem':
                continue
            extensions = item.get('extensions') or {}
            granted_trait_id = extensions.get('trait_id') or extensions.get('fetter_id')
            assert granted_trait_id is not None, f"{season['season_id']} {item['id']} missing granted trait"
            assert str(granted_trait_id) in trait_ids, (
                f"{season['season_id']} {item['id']} references unknown trait {granted_trait_id}"
            )


def test_simulator_uses_flat_hex_board_and_requested_cost_colors():
    css = (SIMULATOR_ROOT / 'style.css').read_text(encoding='utf-8')

    assert '--cost-1: rgb(175, 175, 175)' in css
    assert '--cost-2: rgb(28, 195, 152)' in css
    assert '--cost-3: rgb(7, 165, 241)' in css
    assert '--cost-4: rgb(213, 105, 230)' in css
    assert '--cost-5: rgb(255, 183, 1)' in css
    assert '--cost-7: rgb(255, 183, 1)' in css
    assert 'polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%)' in css
    assert '--col-step: calc(var(--hex-w) + var(--hex-gap))' in css
    assert 'grid-template-columns: 220px minmax(640px, 1fr) 248px' in css
    assert 'container-type: inline-size' in css
    assert '--hex-w: min(105px, calc(13.333cqw - 6.933px))' in css
    assert 'width: calc(var(--col-step) * 6.5 + var(--hex-w))' in css
    assert '@container (max-width: 700px)' in css
    assert '.hex-board-wrap { width: 100%; min-width: 0;' in css
    assert '@media (max-width: 600px)' in css


def test_simulator_item_library_has_no_redundant_clear_button():
    html = Path('templates/lineup_simulator.html').read_text(encoding='utf-8')
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')

    assert 'clearItemButton' not in html
    assert 'clearItemButton' not in javascript


def test_simulator_exposes_every_shared_item_category():
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')

    for category in ('component', 'completed', 'emblem', 'artifact', 'radiant', 'support', 'consumable', 'other'):
        assert f'"{category}"' in javascript


def test_simulator_only_renders_item_categories_populated_by_the_current_season():
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')
    catalog = json.loads((SEASON_ROOT / 'catalog.json').read_text(encoding='utf-8'))

    assert 'function availableItemCategories()' in javascript
    assert 'category.source.some((source) => populated.has(source))' in javascript
    assert 'availableItemCategories().map((category)' in javascript
    assert 'availableCategories[0]?.id || "normal"' in javascript

    categories_by_season = {}
    for season in catalog['seasons']:
        payload = json.loads(
            (SEASON_ROOT / season['season_id'] / 'items.json').read_text(encoding='utf-8')
        )
        categories_by_season[season['season_id']] = {item['category'] for item in payload['items']}

    assert 'consumable' in categories_by_season['s18']
    assert all(
        'consumable' not in categories
        for season_id, categories in categories_by_season.items()
        if season_id != 's18'
    )


def test_simulator_only_shows_item_selection_hint_when_an_item_is_selected():
    html = Path('templates/lineup_simulator.html').read_text(encoding='utf-8')
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')

    assert 'id="selectedHelp" hidden' in html
    assert 'elements.selectedHelp.hidden = !item' in javascript
    assert 'item ? `待装备：${item.name}` : ""' in javascript
    assert '未选择装备' not in html
    assert '未选择装备' not in javascript


def test_simulator_trait_filter_is_a_single_select_and_badges_keep_full_background():
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')
    css = (SIMULATOR_ROOT / 'style.css').read_text(encoding='utf-8')

    assert 'traitFilterButton.addEventListener("click"' in javascript
    assert 'traitFilterMenu.addEventListener("click"' in javascript
    assert 'data-trait-filter="all"' in javascript
    assert 'trait-option-icon' in javascript
    assert 'traitFilterClear.addEventListener("click"' in javascript
    assert '.hero-button.is-dimmed:hover' in css
    assert 'trait-badge-frame' in javascript
    assert '.trait-badge-frame' in css
    assert 'grid-template-columns: 36px 28px minmax(0, 1fr)' in css
    assert 'trait.breakpoints.map((breakpoint) => breakpoint.min_units).join(" > ")' in javascript
    assert 'background: #343943' in css
    assert 'function traitTierRank(status)' in javascript
    assert 'if (!status?.active) return 0' in javascript
    assert 'active?.style === "unique"' in javascript
    assert 'if (status.styleIndex === "unique") return 5' in javascript
    assert 'traitTierRank(b.status) - traitTierRank(a.status)' in javascript
    assert '.filter(Boolean).sort(compareTraitRows)' in javascript
    assert 'status.styleIndex === "unique" ? `${UI_ROOT}/unique.svg`' in javascript
    assert 'data-tier-rank="${traitTierRank(status)}"' in javascript


def test_simulator_exports_the_rendered_board_and_keeps_items_inside_units():
    html = Path('templates/lineup_simulator.html').read_text(encoding='utf-8')
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')
    css = (SIMULATOR_ROOT / 'style.css').read_text(encoding='utf-8')

    assert 'tools/lineup-simulator/vendor/html-to-image.min.js' in html
    assert 'id="exportTransparentBackground"' in html
    assert 'window.htmlToImage.toPng(capture' in javascript
    assert 'buildImageCapture(includeTraits, transparentBackground)' in javascript
    assert 'backgroundColor: transparentBackground ? "transparent" : "#0d101a"' in javascript
    assert 'elements.exportTransparentBackground.checked' in javascript
    assert 'style: { position: "static", left: "auto", top: "auto", zIndex: "auto" }' in javascript
    assert '.lineup-image-capture.is-transparent { background: transparent; }' in css
    assert 'function drawHex(' not in javascript
    assert 'MAX_EXPORT_TRAITS = 8' in javascript
    assert 'unit-portrait-image' in javascript
    assert '.unit-items { position: absolute; z-index: 40; top: 10px;' in css
    assert '.hex-cell.has-items { z-index: 20; }' in css
    assert '.unlock-mark { position: absolute; z-index: 41; right: -1px; bottom: 18px;' in css
    assert '.lineup-image-board .hex-board' in css


def test_simulator_bundles_trait_and_status_assets(client):
    for filename in ('0.svg', '1.svg', '2.svg', '3.svg', '4.svg', 'unique.svg', 'gold.png', 'unlock.png'):
        path = SIMULATOR_ROOT / 'ui' / filename
        assert path.is_file()
        assert client.get(f'/static/tools/lineup-simulator/ui/{filename}').status_code == 200
