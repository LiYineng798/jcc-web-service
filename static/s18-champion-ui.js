(function initializeS18ChampionUi() {
  const DATA_ROOT = '/static/s18-preview';
  const COST_COLORS = {
    1: 'rgb(145, 145, 145)',
    2: 'rgb(16, 166, 14)',
    3: 'rgb(67, 156, 204)',
    4: 'rgb(175, 25, 186)',
    5: 'rgb(147, 130, 22)',
  };
  const championsByName = new Map();
  let traitMap = new Map();
  let activeTrigger = null;

  function assetPath(...parts) {
    return `${DATA_ROOT}/${parts.map((part) => encodeURIComponent(String(part))).join('/')}`;
  }

  function traitAssetPath(path) {
    return `${DATA_ROOT}/${path.split('/').map((part) => encodeURIComponent(part)).join('/')}`;
  }

  function championUrl(name) {
    return `/tools/s18-preview/champions/${encodeURIComponent(name)}`;
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

  function configure(champions, traits) {
    championsByName.clear();
    champions.forEach((champion) => championsByName.set(champion.名称, champion));
    traitMap = traits instanceof Map ? traits : new Map(traits.map((trait) => [trait.名称, trait]));
  }

  function createHoverCard(champion) {
    const card = document.createElement('article');
    card.className = 'champion-hover-card';
    card.style.setProperty('--cost-color', costStyle(champion.费用));

    const art = document.createElement('div');
    art.className = 'champion-hover-art';
    art.append(image(assetPath('bg', champion.费用, `${champion.名称}.jpg`), champion.名称));

    const overlay = document.createElement('div');
    overlay.className = 'champion-hover-overlay';
    const name = document.createElement('strong');
    name.textContent = champion.名称;
    const traits = document.createElement('div');
    traits.className = 'champion-hover-traits';
    champion.羁绊.forEach((traitName) => {
      const trait = traitMap.get(traitName);
      const row = document.createElement('span');
      if (trait) row.append(image(traitAssetPath(trait.svg), ''));
      row.append(document.createTextNode(traitName));
      traits.append(row);
    });
    const cost = document.createElement('span');
    cost.className = 'champion-hover-cost';
    cost.append(image(assetPath('system', 'gold.png'), ''), document.createTextNode(String(champion.费用)));
    overlay.append(name, traits, cost);
    art.append(overlay);

    const skill = document.createElement('div');
    skill.className = 'champion-hover-skill';
    const skillName = document.createElement('strong');
    skillName.textContent = champion.技能名称;
    const skillDescription = document.createElement('p');
    skillDescription.textContent = champion.技能描述;
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

  function bindChampionLink(link, champion = championsByName.get(link.dataset.championName)) {
    if (!champion || link.dataset.championUiReady === 'true') return;
    link.dataset.championUiReady = 'true';
    link.addEventListener('pointerenter', () => showTooltip(link, champion));
    link.addEventListener('pointerleave', () => hideTooltip(link));
    link.addEventListener('focus', () => showTooltip(link, champion));
    link.addEventListener('blur', () => hideTooltip(link));
  }

  function bindChampionLinks(root = document) {
    root.querySelectorAll('[data-champion-name]').forEach((link) => bindChampionLink(link));
  }

  function createMemberLink(champion) {
    const link = document.createElement('a');
    link.className = 'trait-champion';
    link.href = championUrl(champion.名称);
    link.dataset.championName = champion.名称;
    link.setAttribute('aria-label', `查看${champion.名称}详情`);
    link.style.setProperty('--cost-color', costStyle(champion.费用));
    link.append(image(assetPath('xt', champion.费用, `${champion.名称}.jpg`), champion.名称));
    const name = document.createElement('span');
    name.textContent = champion.名称;
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

  window.JccS18ChampionUi = {
    bindChampionLinks,
    championUrl,
    configure,
    costStyle,
    createMemberLink,
  };
}());
