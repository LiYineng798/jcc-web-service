import json
from pathlib import Path

from PIL import Image

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


def test_simulator_exposes_augment_library_selection_and_poster_recommendations(client):
    html = client.get('/tools/lineup-simulator').get_data(as_text=True)
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')
    stylesheet = (SIMULATOR_ROOT / 'style.css').read_text(encoding='utf-8')

    assert 'id="augmentLibraryTab"' in html
    assert 'id="augmentGroups"' in html
    assert 'id="selectedAugmentList"' in html
    assert 'class="augment-filter-bar"' in html
    assert '强化符文推荐' in html
    assert 'const MAX_SELECTED_AUGMENTS = 6;' in javascript
    assert 'augmentIds: state.selectedAugmentIds' in javascript
    assert 'function posterAugmentHtml()' in javascript
    assert 'lineup-poster-augments-panel' in javascript
    assert '.selected-augment-list' in stylesheet
    assert '.lineup-poster-insights' in stylesheet
    assert '.lineup-poster-augment' in stylesheet
    assert 'state[key] = state[key] === value ? "all" : value;' in javascript
    assert 'const AUGMENT_STAGE_ORDER = ["2-1", "3-2", "4-2"];' in javascript
    assert 'const AUGMENT_CATEGORY_ORDER = ["economy", "combat", "equipment", "trait", "exclusive", "other"];' in javascript
    assert '全部等级' not in javascript
    assert '全部时机' not in javascript
    assert '全部分类' not in javascript

    filter_rule = stylesheet.split('.augment-library-filters {', 1)[1].split('}', 1)[0]
    assert 'overflow-x' not in filter_rule
    poster_rule = stylesheet.split('.lineup-poster-augment {', 1)[1].split('}', 1)[0]
    assert 'background:' not in poster_rule
    assert 'border:' not in poster_rule


def test_simulator_loads_every_season_from_catalog():
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')
    catalog = json.loads((SEASON_ROOT / 'catalog.json').read_text(encoding='utf-8'))

    assert 'fetchJson(`/api/season-catalog?surface=simulator&v=${encodeURIComponent(DATA_VERSION)}`)' in javascript
    assert 'cache: "no-cache"' in javascript
    assert '`${season.version_id}-${DATA_VERSION}`' in javascript
    assert 'await refreshCatalog();\n    await loadSeason(seasonId);' in javascript
    assert 'compareSeasons' in javascript
    assert 'season.version_id' in javascript
    assert 'champions.json?v=${stamp}' in javascript
    assert 'traits.json?v=${stamp}' in javascript
    assert 'items.json?v=${stamp}' in javascript
    assert 'board_units.json?v=${stamp}' in javascript
    for season in catalog['seasons']:
        season_root = SEASON_ROOT / season['season_id']
        assert (season_root / 'champions.json').is_file()
        assert (season_root / 'traits.json').is_file()
        assert (season_root / 'items.json').is_file()
        assert (season_root / 'board_units.json').is_file()


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
    assert 'if (state.championById.get(slot.championId)?.canEquip === false)' in javascript
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
    assert 'function boardUnitAllowance(unit)' in javascript
    assert 'const contributionTraitIds = (raw.contribution_trait_ids || []).map(String)' in javascript
    assert 'traitIds: contributionTraitIds' in javascript
    assert 'rule.champion_id' in javascript
    assert 'countPlacedUnit(String(rule.champion_id))' in javascript
    assert '需要先上阵 ${champion.name}' in javascript
    assert 'countPlacedUnit(hero.id) >= boardUnitAllowance(hero)' in javascript
    assert 'specialPlacementIsValid' in javascript
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

    shared_categories = {'component', 'completed', 'emblem', 'artifact', 'radiant', 'support', 'consumable', 'other'}
    assert all(
        categories and categories <= shared_categories
        for categories in categories_by_season.values()
    )
    assert all(
        'consumable' not in categories
        for categories in categories_by_season.values()
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


def test_simulator_wraps_long_board_unit_names_without_clipping_exports():
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')
    css = (SIMULATOR_ROOT / 'style.css').read_text(encoding='utf-8')

    assert '[...hero.name].length > 7 ? " is-long" : ""' in javascript
    assert 'class="unit-name${longNameClass}"' in javascript
    assert '.unit-name.is-long {' in css
    assert 'white-space: normal' in css
    assert 'overflow-wrap: anywhere' in css
    assert '.lineup-image-board .unit-name.is-long' in css
    assert '.lineup-poster-hex-board .unit-name.is-long' in css


def test_simulator_shows_animated_export_progress_for_both_image_formats():
    html = Path('templates/lineup_simulator.html').read_text(encoding='utf-8')
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')
    css = (SIMULATOR_ROOT / 'style.css').read_text(encoding='utf-8')

    assert 'id="exportProgress"' in html
    assert html.count('<span></span>') >= 7
    assert 'function beginExportProgress(title)' in javascript
    assert 'async function updateExportProgress(stage, percent)' in javascript
    assert 'async function finishExportProgress(startedAt)' in javascript
    assert 'beginExportProgress("图片正在导出")' in javascript
    assert 'beginExportProgress("海报正在导出")' in javascript
    assert 'elements.exportImageDialog.close();\n  elements.exportImage.disabled = true;' in javascript
    assert 'elements.posterExportDialog.close();\n  const startedAt = beginExportProgress("海报正在导出")' in javascript
    assert 'Math.max(0, 1100 - (performance.now() - startedAt))' in javascript
    assert javascript.count('await finishExportProgress(startedAt)') == 2
    assert '@keyframes export-tile-pulse' in css
    assert '.export-progress-board span:nth-child(7)' in css


def test_simulator_uses_fixed_branded_codes_and_keeps_legacy_import_support():
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')

    assert 'const FORMATION_CODE_PREFIX = "JCC2-"' in javascript
    assert 'const FORMATION_TOTAL_BYTES = FORMATION_HEADER_BYTES + (28 * FORMATION_SLOT_BYTES) + FORMATION_CHECKSUM_BYTES' in javascript
    assert 'const FORMATION_CODE_LENGTH = FORMATION_CODE_PREFIX.length + FORMATION_PAYLOAD_LENGTH' in javascript
    assert 'view.setUint32(1, fnv1a32(payload.season))' in javascript
    assert 'view.setUint32(5, codebook.hash)' in javascript
    assert 'fnv1a32(bytes.slice(0, -FORMATION_CHECKSUM_BYTES))' in javascript
    assert 'if (code.length !== FORMATION_CODE_LENGTH)' in javascript
    assert 'function decodeLegacyPayload(code)' in javascript
    assert 'return code.startsWith(FORMATION_CODE_PREFIX) ? decodeFixedFormation(code) : decodeLegacyPayload(code)' in javascript
    assert 'if (location.hash.startsWith("#lineup="))' in javascript
    assert 'history.replaceState(null, "", `${location.pathname}${location.search}`)' in javascript


def test_simulator_renders_imported_stat_tokens_in_popovers():
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')
    css = (SIMULATOR_ROOT / 'style.css').read_text(encoding='utf-8')

    assert 'function richTextHtml(text, importedTokens = null)' in javascript
    assert 'richTextHtml(skill.description, skill.description_tokens)' in javascript
    assert 'richTextHtml(trait.description, trait.descriptionTokens)' in javascript
    assert 'point.effect_tokens || point.description_tokens' in javascript
    assert '/static/season-stats/${encodeURIComponent(token.icon)}.png' in javascript
    assert '.scale-chip' in css
    assert '木灵加成: ["amp", "amp", "木灵加成", "木灵"]' in javascript
    assert 'const woodSpiritPlaceholder = !match[1]' in javascript
    assert 'background: transparent' in css
    assert 'border: 0' in css


def test_simulator_includes_s16_5_galio_as_an_unlock_champion():
    champions = json.loads((SEASON_ROOT / 's16_5' / 'champions.json').read_text(encoding='utf-8'))['champions']
    galio = next(champion for champion in champions if champion['name'] == '加里奥')

    assert galio['cost'] == 5
    assert galio['availability']['type'] == 'unlock'
    assert galio['extensions']['simulator_visible'] is True


def test_simulator_exports_a_separate_fixed_portrait_poster():
    html = Path('templates/lineup_simulator.html').read_text(encoding='utf-8')
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')
    css = (SIMULATOR_ROOT / 'style.css').read_text(encoding='utf-8')

    assert 'id="exportPosterButton"' in html
    assert 'id="posterExportDialog"' in html
    assert 'id="posterTitle"' in html
    assert 'maxlength="24"' in html
    assert 'id="posterChampionPicker"' in html
    assert 'id="posterPreview"' in html
    assert 'id="confirmExportPosterButton"' in html
    assert 'const POSTER_WIDTH = 1200' in javascript
    assert 'const POSTER_HEIGHT = 1600' in javascript
    assert 'const MAX_POSTER_TRAITS = 9' in javascript
    assert 'function defaultPosterChampionId()' in javascript
    assert 'b.hero.cost - a.hero.cost || a.index - b.index' in javascript
    assert 'function buildPosterCapture(title, championId)' in javascript
    assert 'lineup-poster-background-fill' in javascript
    assert 'lineup-poster-background-art' in javascript
    assert 'function posterBoardClone()' in javascript
    assert 'posterIcon: seasonAsset(raw.images?.icon?.local_path || raw.images?.icon?.optimized_local_path)' in javascript
    assert 'data-fallback-src="${escapeHtml(hero.icon)}"' in javascript
    assert 'await preparePosterImages(poster)' in javascript
    assert 'await rasterizePosterTitle(poster)' in javascript
    assert 'skipFonts: true' in javascript
    assert 'width: POSTER_WIDTH' in javascript
    assert 'height: POSTER_HEIGHT' in javascript
    assert 'pixelRatio: 1' in javascript
    assert 'jcc.np5.top' not in javascript
    assert '<strong>金铲铲阵容库</strong>' in javascript
    assert 'src="${UI_ROOT}/poster-brand.png"' in javascript
    poster_builder = javascript.split('function buildPosterCapture(title, championId)', 1)[1].split('function ', 1)[0]
    assert '总费用' not in poster_builder
    assert '${units.length} 个单位</span><i></i><span>${posterTraitRows().length} 个激活羁绊' in poster_builder
    assert '.lineup-poster-capture {' in css
    assert '.lineup-poster-background-art {' in css
    assert 'object-fit: contain' in css
    assert 'grid-template-rows: 250px 650px 520px 180px' in css
    assert '强化符文推荐' in poster_builder
    assert '"Source Han Serif SC Poster"' in css
    assert '.lineup-poster-brand' in css
    trait_rule = css.split('.lineup-poster-trait {', 1)[1].split('}', 1)[0]
    assert 'background:' not in trait_rule
    assert 'border:' not in trait_rule
    brand_icon_rule = css.split('.lineup-poster-brand img {', 1)[1].split('}', 1)[0]
    assert 'background: transparent' in brand_icon_rule
    assert 'padding: 0' in brand_icon_rule
    assert 'exportBoardImage(' in javascript


def test_simulator_poster_omits_domain_and_exposes_hover_details_toggle():
    html = Path('templates/lineup_simulator.html').read_text(encoding='utf-8')
    javascript = (SIMULATOR_ROOT / 'app.js').read_text(encoding='utf-8')

    assert 'id="hoverDetailsToggle"' in html
    assert 'hoverDetails: document.querySelector("#hoverDetailsToggle")' in javascript
    assert 'if (!state.hoverDetails) return' in javascript
    assert 'elements.hoverDetails.addEventListener("change"' in javascript
    assert 'hover-details' in javascript


def test_simulator_bundles_poster_font_and_license(client):
    font_path = SIMULATOR_ROOT / 'fonts' / 'source-han-serif-sc-vf-subset.woff2'
    license_path = SIMULATOR_ROOT / 'fonts' / 'LICENSE.txt'

    assert font_path.is_file()
    assert 1_000_000 < font_path.stat().st_size < 20_000_000
    assert license_path.is_file()
    assert 'SIL OPEN FONT LICENSE Version 1.1' in license_path.read_text(encoding='utf-8')
    assert client.get('/static/tools/lineup-simulator/fonts/source-han-serif-sc-vf-subset.woff2').status_code == 200


def test_simulator_bundles_trait_and_status_assets(client):
    for filename in ('0.svg', '1.svg', '2.svg', '3.svg', '4.svg', 'unique.svg', 'poster-brand.png', 'gold.png', 'unlock.png'):
        path = SIMULATOR_ROOT / 'ui' / filename
        assert path.is_file()
        assert client.get(f'/static/tools/lineup-simulator/ui/{filename}').status_code == 200

    with Image.open(SIMULATOR_ROOT / 'ui' / 'poster-brand.png') as brand:
        assert brand.mode == 'RGBA'
        assert brand.getchannel('A').getextrema() == (0, 255)
