(async () => {
  const root = document.querySelector('#liveCompDetail');
  const board = document.querySelector('#formationBoard');
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
  const [championDoc, itemDoc, codebook] = await Promise.all([
    fetch(`/static/season-data/${encodeURIComponent(librarySeason)}/champions.json?v=${stamp}`).then((value) => value.json()),
    fetch(`/static/season-data/${encodeURIComponent(librarySeason)}/items.json?v=${stamp}`).then((value) => value.json()),
    fetch(`/static/season-data/${encodeURIComponent(librarySeason)}/tft-codebook.json?v=${stamp}`).then((value) => value.ok ? value.json() : ({ source_ids: {} })),
  ]);
  const champions = new Map((championDoc.champions || []).map((item) => [String(item.id), item]));
  const items = new Map();
  (itemDoc.items || []).forEach((item) => {
    Object.values(item.source_ids || {}).forEach((sourceId) => {
      if (sourceId !== null && sourceId !== undefined && String(sourceId) !== '0') items.set(String(sourceId), item);
    });
  });
  (itemDoc.items || []).forEach((item) => items.set(String(item.id), item));
  const units = new Map((details.units || []).map((unit) => [Number(unit.position), unit]));
  const asset = (path) => path ? `/static/season-data/${encodeURIComponent(librarySeason)}/${path}?v=${stamp}` : '';
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
      const portrait = document.createElement('span');
      portrait.className = 'formation-portrait';
      const portraitImage = document.createElement('img');
      portraitImage.src = asset(champion.images?.icon?.optimized_local_path || champion.images?.icon?.local_path);
      portraitImage.alt = champion.name;
      portrait.append(portraitImage);
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
