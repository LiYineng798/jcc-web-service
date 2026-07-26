(function initializeSeasonChampionUi() {
  const COST_COLORS = {
    1: 'rgb(145, 145, 145)',
    2: 'rgb(16, 166, 14)',
    3: 'rgb(67, 156, 204)',
    4: 'rgb(175, 25, 186)',
    5: 'rgb(147, 130, 22)',
    7: 'rgb(205, 82, 61)',
  };
  let seasonId = '';
  let assetRoot = '';
  const championsById = new Map();
  let traitsById = new Map();
  let activeTrigger = null;

  function assetUrl(path) {
    if (!path) return '';
    return `${assetRoot}/${String(path).split('/').map(encodeURIComponent).join('/')}`;
  }

  function championUrl(championId) {
    return `/tools/seasons/${encodeURIComponent(seasonId)}/champions/${encodeURIComponent(championId)}`;
  }

  function costStyle(cost) {
    return COST_COLORS[cost] || 'var(--accent)';
  }

  function image(src, alt, className = '') {
    const element = document.createElement('img');
    element.src = src;
    element.alt = alt;
    element.decoding = 'async';
    if (className) element.className = className;
    return element;
  }

  function configure(config) {
    seasonId = config.seasonId;
    assetRoot = config.assetRoot;
    championsById.clear();
    (config.champions || []).forEach((champion) => championsById.set(String(champion.id), champion));
    traitsById = config.traitsById instanceof Map
      ? config.traitsById
      : new Map((config.traits || []).map((trait) => [trait.id, trait]));
  }

  function createHoverCard(champion) {
    const card = document.createElement('article');
    card.className = 'champion-hover-card';
    card.style.setProperty('--cost-color', costStyle(champion.cost));

    const art = document.createElement('div');
    art.className = 'champion-hover-art';
    const artPath = champion.splash || champion.icon;
    if (artPath) art.append(image(assetUrl(artPath), champion.name));

    const overlay = document.createElement('div');
    overlay.className = 'champion-hover-overlay';
    const name = document.createElement('strong');
    name.textContent = champion.name;
    const traits = document.createElement('div');
    traits.className = 'champion-hover-traits';
    (champion.trait_ids || []).forEach((traitId) => {
      const trait = traitsById.get(traitId);
      if (!trait) return;
      const row = document.createElement('span');
      if (trait.image) row.append(image(assetUrl(trait.image), ''));
      row.append(document.createTextNode(trait.name));
      traits.append(row);
    });
    const cost = document.createElement('span');
    cost.className = 'champion-hover-cost';
    cost.append(image('/static/season-gold.png', ''), document.createTextNode(String(champion.cost)));
    overlay.append(name, traits, cost);
    art.append(overlay);

    const skill = document.createElement('div');
    skill.className = 'champion-hover-skill';
    const skillName = document.createElement('strong');
    skillName.textContent = (champion.skill && champion.skill.name) || '';
    const skillDescription = document.createElement('p');
    skillDescription.textContent = (champion.skill && champion.skill.description) || '';
    skill.append(skillName, skillDescription);
    card.append(art, skill);
    return card;
  }

  function layerElement() {
    let layer = document.querySelector('#championHoverLayer');
    if (!layer) {
      layer = document.createElement('div');
      layer.id = 'championHoverLayer';
      layer.className = 'champion-hover-layer';
      layer.hidden = true;
      document.body.append(layer);
    }
    return layer;
  }

  function positionLayer(trigger, layer) {
    const triggerRect = trigger.getBoundingClientRect();
    const layerRect = layer.getBoundingClientRect();
    const gap = 12;
    const edge = 10;
    let left = triggerRect.right + gap;
    if (left + layerRect.width > window.innerWidth - edge) left = triggerRect.left - layerRect.width - gap;
    left = Math.max(edge, Math.min(left, window.innerWidth - layerRect.width - edge));

    let top = triggerRect.top + (triggerRect.height - layerRect.height) / 2;
    top = Math.max(edge, Math.min(top, window.innerHeight - layerRect.height - edge));
    layer.style.left = `${Math.round(left)}px`;
    layer.style.top = `${Math.round(top)}px`;
  }

  function showTooltip(trigger, champion) {
    if (!window.matchMedia('(hover: hover), (pointer: fine)').matches && !trigger.matches(':focus-visible')) return;
    const layer = layerElement();
    activeTrigger = trigger;
    layer.replaceChildren(createHoverCard(champion));
    layer.hidden = false;
    requestAnimationFrame(() => {
      if (activeTrigger !== trigger) return;
      positionLayer(trigger, layer);
      layer.classList.add('visible');
    });
  }

  function hideTooltip(trigger) {
    if (activeTrigger !== trigger) return;
    activeTrigger = null;
    const layer = layerElement();
    layer.classList.remove('visible');
    window.setTimeout(() => {
      if (!activeTrigger) layer.hidden = true;
    }, 140);
  }

  function bindChampionLink(link, champion = championsById.get(String(link.dataset.championId))) {
    if (!champion || link.dataset.championUiReady === 'true') return;
    link.dataset.championUiReady = 'true';
    link.addEventListener('pointerenter', () => showTooltip(link, champion));
    link.addEventListener('pointerleave', () => hideTooltip(link));
    link.addEventListener('focus', () => showTooltip(link, champion));
    link.addEventListener('blur', () => hideTooltip(link));
  }

  function bindChampionLinks(root = document) {
    root.querySelectorAll('[data-champion-id]').forEach((link) => bindChampionLink(link));
  }

  function createMemberLink(champion) {
    const link = document.createElement('a');
    link.className = 'trait-champion';
    link.href = championUrl(champion.id);
    link.dataset.championId = String(champion.id);
    link.setAttribute('aria-label', `查看${champion.name}详情`);
    link.style.setProperty('--cost-color', costStyle(champion.cost));
    const iconPath = champion.icon || champion.splash;
    if (iconPath) link.append(image(assetUrl(iconPath), champion.name));
    const name = document.createElement('span');
    name.textContent = champion.name;
    link.append(name);
    bindChampionLink(link, champion);
    return link;
  }

  window.addEventListener('scroll', () => {
    if (activeTrigger) positionLayer(activeTrigger, layerElement());
  }, {passive: true});
  window.addEventListener('resize', () => {
    if (activeTrigger) positionLayer(activeTrigger, layerElement());
  });

  window.JccSeasonChampionUi = {
    assetUrl: (path) => assetUrl(path),
    bindChampionLinks,
    championUrl,
    configure,
    costStyle,
    createMemberLink,
  };
}());
