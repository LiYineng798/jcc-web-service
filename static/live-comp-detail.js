(async () => {
  const root = document.querySelector('#liveCompDetail');
  const board = document.querySelector('#formationBoard');
  const traitPanel = document.querySelector('#traitPanel');
  const meta = document.querySelector('#detailSeason');
  const seasonId = root.dataset.seasonId;
  const liveCompId = root.dataset.liveCompId;
  const response = await fetch(`/api/live-comps/${encodeURIComponent(liveCompId)}/details?season=${encodeURIComponent(seasonId)}`);
  if (!response.ok) throw new Error('阵容详情加载失败');
  const details = await response.json();
  const librarySeason = details.season_data_id || details.season_id;
  const catalog = await fetch('/api/season-catalog?surface=library').then((value) => value.json());
  const season = (catalog.seasons || []).find((item) => item.season_id === librarySeason);
  if (!season) throw new Error('当前阵容的赛季资料不可用');
  const stamp = encodeURIComponent(season.version_id || '0');
  const [championDoc, itemDoc, traitDoc, codebook] = await Promise.all([
    fetch(`/static/season-data/${encodeURIComponent(librarySeason)}/champions.json?v=${stamp}`).then((value) => value.json()),
    fetch(`/static/season-data/${encodeURIComponent(librarySeason)}/items.json?v=${stamp}`).then((value) => value.json()),
    fetch(`/static/season-data/${encodeURIComponent(librarySeason)}/traits.json?v=${stamp}`).then((value) => value.json()),
    fetch(`/static/season-data/${encodeURIComponent(librarySeason)}/tft-codebook.json?v=${stamp}`).then((value) => value.ok ? value.json() : ({ source_ids: {} })),
  ]);
  const champions = new Map((championDoc.champions || []).map((item) => [String(item.id), item]));
  const traits = new Map((traitDoc.traits || []).map((item) => [String(item.id), item]));
  const items = new Map();
  (itemDoc.items || []).forEach((item) => {
    Object.values(item.source_ids || {}).forEach((sourceId) => {
      if (sourceId !== null && sourceId !== undefined && String(sourceId) !== '0') items.set(String(sourceId), item);
    });
  });
  (itemDoc.items || []).forEach((item) => items.set(String(item.id), item));
  const units = new Map((details.units || []).map((unit) => [Number(unit.position), unit]));
  const asset = (path) => path ? `/static/season-data/${encodeURIComponent(librarySeason)}/${path}?v=${stamp}` : '';

  const COST_COLORS = {
    1: 'rgb(175, 175, 175)',
    2: 'rgb(28, 195, 152)',
    3: 'rgb(7, 165, 241)',
    4: 'rgb(213, 105, 230)',
    5: 'rgb(255, 183, 1)',
    6: 'rgb(255, 183, 1)',
    7: 'rgb(255, 183, 1)',
  };

  // Calculate trait counts
  const traitContributors = new Map();
  const addContributor = (traitId, championId) => {
    const key = String(traitId);
    if (!traitContributors.has(key)) traitContributors.set(key, new Set());
    traitContributors.get(key).add(String(championId));
  };
  units.forEach((unit) => {
    const championId = unit.champion_id || codebook.source_ids?.[String(unit.source_champion_id)];
    const champion = championId ? champions.get(String(championId)) : null;
    if (!champion) return;
    (champion.trait_ids || []).forEach((traitId) => addContributor(traitId, championId));
    const equipmentIds = unit.items?.length ? unit.items : (unit.source_item_ids || []);
    equipmentIds.forEach((itemId) => {
      const item = items.get(String(itemId));
      const grantedTraitId = item?.extensions?.trait_id || item?.extensions?.fetter_id;
      if (grantedTraitId && traits.has(String(grantedTraitId))) addContributor(grantedTraitId, championId);
    });
  });

  // Data-driven composite traits such as S18 日月双蚀 declare their source
  // thresholds in the trait text. Add the composite contributors only when
  // every source threshold is met.
  traits.forEach((trait) => {
    const match = String(trait.description || '').match(/登场\s*(\d+)\s*个【([^】]+)】和\s*(\d+)\s*个【([^】]+)】弈子以激活/);
    const sources = match
      ? [{ name: match[2], min: Number(match[1]) }, { name: match[4], min: Number(match[3]) }]
      : (trait.name === '日月双蚀'
        ? [{ name: '日蚀骑士', min: 3 }, { name: '月蚀骑士', min: 3 }]
        : null);
    if (!sources) return;
    const sourceA = [...traits.values()].find((candidate) => candidate.name === sources[0].name);
    const sourceB = [...traits.values()].find((candidate) => candidate.name === sources[1].name);
    if (!sourceA || !sourceB) return;
    const contributorsA = traitContributors.get(String(sourceA.id));
    const contributorsB = traitContributors.get(String(sourceB.id));
    if (!contributorsA || !contributorsB || contributorsA.size < sources[0].min || contributorsB.size < sources[1].min) return;
    const composite = traitContributors.get(String(trait.id)) || new Set();
    contributorsA.forEach((id) => composite.add(id));
    contributorsB.forEach((id) => composite.add(id));
    traitContributors.set(String(trait.id), composite);
  });

  // Render traits panel
  const TRAIT_STYLE_COLORS = { 0: '#667080', 1: '#b66e3d', 2: '#aab3bd', 3: '#d7a934', 4: '#7fd2e8', unique: '#d7a934' };
  const TRAIT_STYLE_INDEX = { bronze: 1, silver: 2, gold: 3, chromatic: 4, prismatic: 4, unique: 'unique' };
  const activatedTraits = [];
  traitContributors.forEach((contributors, traitId) => {
    const count = contributors.size;
    const trait = traits.get(traitId);
    if (!trait) return;
    const activeBreakpoint = (trait.breakpoints || []).filter((bp) => count >= Number(bp.min_units)).at(-1);
    if (!activeBreakpoint) return;
    const isUnique = activeBreakpoint.style === 'unique' || trait.category === 'unique' || (trait.tags || []).some((tag) => String(tag).toLowerCase().includes('unique') || String(tag).includes('独特'));
    const styleIndex = isUnique ? 'unique' : (TRAIT_STYLE_INDEX[activeBreakpoint.style] || 1);
    activatedTraits.push({ trait, count, styleIndex, tierRank: styleIndex === 'unique' ? 5 : Number(styleIndex) || 1 });
  });
  activatedTraits.sort((a, b) => b.tierRank - a.tierRank || b.count - a.count || a.trait.name.localeCompare(b.trait.name, 'zh-CN'));

  if (traitPanel && activatedTraits.length > 0) {
    const UI_ROOT = '/static/tools/lineup-simulator/ui';
    traitPanel.innerHTML = activatedTraits.map(({ trait, count, styleIndex }) => {
      const breakpointText = (trait.breakpoints || []).map((bp) => bp.min_units).join(' > ') || '独特';
      const background = styleIndex === 'unique' ? `${UI_ROOT}/unique.svg` : `${UI_ROOT}/${styleIndex}.svg`;
      const iconPath = trait.image?.optimized_local_path || trait.image?.local_path;
      return `<div class="trait-row" style="--trait-color:${TRAIT_STYLE_COLORS[styleIndex]}">
        <span class="trait-badge"><img class="trait-badge-frame" src="${background}" alt="" />${iconPath ? `<img class="trait-badge-icon" src="${asset(iconPath)}" alt="" />` : ''}</span>
        <span class="trait-copy"><strong>${trait.name}</strong><small>${breakpointText}</small></span>
        <span class="trait-count">${count}</span>
      </div>`;
    }).join('');
  }

  for (let index = 0; index < 28; index += 1) {
    const cell = document.createElement('div');
    cell.className = 'formation-cell';
    cell.setAttribute('role', 'gridcell');
    const floor = document.createElement('span');
    floor.className = 'formation-floor';
    cell.append(floor);
    const unit = units.get(index);
    const championId = unit ? (unit.champion_id || codebook.source_ids?.[String(unit.source_champion_id)]) : null;
    const champion = championId ? champions.get(String(championId)) : null;
    if (champion) {
      const wrap = document.createElement('div');
      wrap.className = 'formation-unit';
      wrap.style.setProperty('--unit-cost-color', COST_COLORS[champion.cost] || COST_COLORS[5]);
      const portrait = document.createElement('span');
      portrait.className = 'formation-portrait';
      const portraitImage = document.createElement('img');
      portraitImage.src = asset(champion.images?.icon?.optimized_local_path || champion.images?.icon?.local_path);
      portraitImage.alt = champion.name;
      const portraitCrop = document.createElement('span');
      portraitCrop.className = 'formation-portrait-crop';
      portraitCrop.append(portraitImage);
      portrait.append(portraitCrop);
      const name = document.createElement('span');
      name.className = 'formation-name';
      name.textContent = champion.name;
      wrap.append(portrait, name);
      if (Number(unit.star || 1) > 1) {
        const star = document.createElement('span');
        star.className = 'formation-star';
        star.textContent = '★'.repeat(Math.min(3, Number(unit.star)));
        wrap.append(star);
      }
      const equipment = document.createElement('span');
      equipment.className = 'formation-items';
      const equipmentIds = unit.items?.length ? unit.items : (unit.source_item_ids || []);
      equipmentIds.slice(0, 3).forEach((id) => {
        const item = items.get(String(id));
        if (!item) return;
        const image = document.createElement('img');
        image.src = asset(item.image?.optimized_local_path || item.image?.local_path);
        image.alt = item.name;
        image.title = item.name;
        equipment.append(image);
      });
      wrap.append(equipment);
      cell.append(wrap);
    }
    board.append(cell);
  }
  meta.textContent = `${season.display_name} · ${details.units.length} 名弈子`;
})().catch((error) => { document.querySelector('#detailSeason').textContent = error.message; });
