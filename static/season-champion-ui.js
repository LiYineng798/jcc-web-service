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
  let assetVersion = '';
  const championsById = new Map();
  let traitsById = new Map();
  let activeTrigger = null;

  function assetUrl(path) {
    if (!path) return '';
    const url = `${assetRoot}/${String(path).split('/').map(encodeURIComponent).join('/')}`;
    return assetVersion ? `${url}?v=${encodeURIComponent(assetVersion)}` : url;
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

  const SCALE_MARKERS = {
    AD: ['attack_damage', 'ad', 'ad', '物理加成', 'AD'], 物理加成: ['attack_damage', 'ad', 'ad', '物理加成', 'AD'], 攻击力: ['attack_damage', 'ad', 'ad', '物理加成', 'AD'],
    AP: ['ability_power', 'ap', 'ap', '法术加成', 'AP'], 法术加成: ['ability_power', 'ap', 'ap', '法术加成', 'AP'], 法强: ['ability_power', 'ap', 'ap', '法术加成', 'AP'],
    AS: ['attack_speed', 'attack-speed', 'as', '攻击速度', 'AS'], 攻击速度: ['attack_speed', 'attack-speed', 'as', '攻击速度', 'AS'], 攻速: ['attack_speed', 'attack-speed', 'as', '攻击速度', 'AS'],
    HP: ['health', 'health', 'hp', '生命值', 'HP'], 生命上限: ['health', 'health', 'hp', '生命值', 'HP'], 最大生命值: ['health', 'health', 'hp', '生命值', 'HP'],
    MR: ['magic_resist', 'magic-resist', 'mr', '魔法抗性', 'MR'], 魔法抗性: ['magic_resist', 'magic-resist', 'mr', '魔法抗性', 'MR'], 魔抗: ['magic_resist', 'magic-resist', 'mr', '魔法抗性', 'MR'],
    护甲: ['armor', 'armor', 'armor', '护甲', 'AR'], ARMOR: ['armor', 'armor', 'armor', '护甲', 'AR'], 攻击范围: ['attack_range', 'range', 'range', '攻击范围', 'RNG'], RANGE: ['attack_range', 'range', 'range', '攻击范围', 'RNG'], 射程: ['attack_range', 'range', 'range', '攻击范围', 'RNG'],
    暴击率: ['critical_strike_chance', 'crit', 'crit', '暴击率', 'CRIT'], 暴击几率: ['critical_strike_chance', 'crit', 'crit', '暴击率', 'CRIT'], CRIT: ['critical_strike_chance', 'crit', 'crit', '暴击率', 'CRIT'], 暴击伤害: ['critical_strike_damage', 'crit-multiplier', 'critmult', '暴击伤害', 'CRIT'], 暴击倍率: ['critical_strike_damage', 'crit-multiplier', 'critmult', '暴击伤害', 'CRIT'],
    法力值: ['mana', 'mana', 'mana', '法力值', 'MP'], MANA: ['mana', 'mana', 'mana', '法力值', 'MP'], MP: ['mana', 'mana', 'mana', '法力值', 'MP'], 法力回复: ['mana_regeneration', 'mana-regen', 'manaregen', '法力回复', 'MP'], 全能吸血: ['omnivamp', 'omnivamp', 'sv', '全能吸血', '吸'], OMNIVAMP: ['omnivamp', 'omnivamp', 'sv', '全能吸血', '吸'],
    伤害加成: ['damage_amplification', 'damage-amplification', 'da', '伤害加成', '增伤'], AMP: ['damage_amplification', 'damage-amplification', 'da', '伤害加成', '增伤'], DA: ['damage_amplification', 'damage-amplification', 'da', '伤害加成', '增伤'], 伤害增幅: ['damage_amplification', 'damage-amplification', 'da', '伤害加成', '增伤'],
    木灵加成: ['wood_spirit_bonus', 'amp', 'amp', '木灵加成', '木灵'],
    DR: ['damage_reduction', 'damage-reduction', 'dr', '伤害减免', '减伤'], 伤害减免: ['damage_reduction', 'damage-reduction', 'dr', '伤害减免', '减伤'],
    技能暴击: ['skill_critical_strike', 'skill-crit', 'crit', '技能暴击', 'CRIT'],
    灵魂: ['soul', 'soul', 'soul', '灵魂', '魂'], SOUL: ['soul', 'soul', 'soul', '灵魂', '魂'],
    银蛇币: ['serpent', 'serpent', 'serpent', '银蛇币', '币'], SERPENT: ['serpent', 'serpent', 'serpent', '银蛇币', '币'],
    太阳碎片: ['ixtal', 'ixtal', 'ixtal', '太阳碎片', '碎片'], IXTAL: ['ixtal', 'ixtal', 'ixtal', '太阳碎片', '碎片'],
  };
  const SCALE_TOKEN_RE = new RegExp(`\\(?【(${Object.keys(SCALE_MARKERS).filter((key) => key !== '木灵加成').join('|')})】\\)?|\\(\\)`, 'g');

  function fallbackDescriptionTokens(text) {
    const value = String(text || '');
    const tokens = [];
    let cursor = 0;
    for (const match of value.matchAll(SCALE_TOKEN_RE)) {
      const woodSpiritPlaceholder = !match[1]
        && value.includes('木灵加成')
        && match.index > 0
        && /[0-9%]/.test(value[match.index - 1]);
      if (!match[1] && !woodSpiritPlaceholder) continue;
      const markerStart = woodSpiritPlaceholder ? match.index + 1 : match.index;
      const markerEnd = woodSpiritPlaceholder ? markerStart : match.index + match[0].length;
      if (markerStart > cursor) tokens.push({type: 'text', value: value.slice(cursor, markerStart)});
      const sourceLabel = woodSpiritPlaceholder ? '木灵加成' : match[1];
      const [stat, kind, icon, label, fallback] = SCALE_MARKERS[sourceLabel];
      tokens.push({type: 'stat', stat, kind, icon, label, fallback, source_label: sourceLabel});
      cursor = markerEnd;
    }
    if (cursor < value.length) tokens.push({type: 'text', value: value.slice(cursor)});
    return tokens;
  }

  function appendSkillDescription(target, text, importedTokens = null) {
    const tokens = Array.isArray(importedTokens) && importedTokens.some((token) => token.type === 'stat')
      ? importedTokens
      : fallbackDescriptionTokens(text);
    tokens.forEach((token) => {
      if (token.type === 'text') {
        target.append(document.createTextNode(token.value || ''));
        return;
      }
      const chip = document.createElement('span');
      const label = token.label || token.source_label || token.stat;
      chip.className = `scale-chip scale-chip-${token.kind || String(token.stat || '').replaceAll('_', '-')}`;
      chip.setAttribute('role', 'img');
      chip.setAttribute('aria-label', label);
      chip.title = label;
      if (token.icon) {
        const icon = image(`/static/season-stats/${encodeURIComponent(token.icon)}.png`, '');
        icon.setAttribute('aria-hidden', 'true');
        chip.append(icon);
      } else {
        const fallback = document.createElement('span');
        fallback.setAttribute('aria-hidden', 'true');
        fallback.textContent = token.fallback || token.source_label || label;
        chip.append(fallback);
      }
      target.append(chip);
    });
  }

  function configure(config) {
    seasonId = config.seasonId;
    assetRoot = config.assetRoot;
    assetVersion = config.assetVersion || '';
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
    const artPath = champion.splash || champion.card || champion.icon;
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
    appendSkillDescription(
      skillDescription,
      champion.skill && champion.skill.description,
      champion.skill && champion.skill.description_tokens,
    );
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
    appendSkillDescription,
    assetUrl: (path) => assetUrl(path),
    bindChampionLinks,
    championUrl,
    configure,
    costStyle,
    createMemberLink,
  };
}());
