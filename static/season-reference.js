const COST_COLORS = {
  1: 'rgb(145, 145, 145)',
  2: 'rgb(16, 166, 14)',
  3: 'rgb(67, 156, 204)',
  4: 'rgb(175, 25, 186)',
  5: 'rgb(147, 130, 22)',
  7: 'rgb(205, 82, 61)',
};
const mobileQuery = window.matchMedia('(max-width: 640px)');

const content = document.querySelector('#seasonContent');
const config = {
  seasonId: content.dataset.seasonId,
  assetRoot: content.dataset.assetRoot,
  dataUrl: content.dataset.dataUrl,
};

const state = {
  champions: [],
  traits: [],
  mechanics: [],
  traitsById: new Map(),
  costs: [],
  activeView: 'champions',
  traitType: 'origin',
  query: '',
  origin: 'all',
  profession: 'all',
  cost: 'all',
  showSkills: !mobileQuery.matches,
  mobileFiltersExpanded: false,
};

const elements = {
  content,
  previewCount: document.querySelector('#previewCount'),
  mainTabs: Array.from(document.querySelectorAll('.s18-main-tab')),
  mainTabsWrap: document.querySelector('.s18-main-tabs'),
  panels: Array.from(document.querySelectorAll('.s18-view-panel')),
  championFilterToggle: document.querySelector('#championFilterToggle'),
  championFilterPanel: document.querySelector('#championFilterPanel'),
  championFilterSummary: document.querySelector('#championFilterSummary'),
  championSearch: document.querySelector('#championSearch'),
  skillToggle: document.querySelector('#skillToggle'),
  originFilters: document.querySelector('#originFilters'),
  professionFilters: document.querySelector('#professionFilters'),
  costFilters: document.querySelector('#costFilters'),
  championSections: document.querySelector('#championSections'),
  championEmpty: document.querySelector('#championEmpty'),
  traitTypeButtons: Array.from(document.querySelectorAll('[data-trait-type]')),
  traitGrid: document.querySelector('#traitGrid'),
  loading: document.querySelector('#seasonLoading'),
  loadError: document.querySelector('#seasonLoadError'),
};

if (elements.skillToggle) elements.skillToggle.checked = state.showSkills;

const themeElements = {
  themeToggle: document.querySelector('#themeToggle'),
  themeIcon: document.querySelector('#themeIcon'),
  themeText: document.querySelector('#themeText'),
};

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  window.jccApplyThemeToggleState?.(theme, themeElements.themeToggle, themeElements.themeIcon, themeElements.themeText);
}

setTheme(localStorage.getItem('theme') || 'light');
themeElements.themeToggle?.addEventListener('click', () => {
  setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
});

function assetUrl(path) {
  if (!path) return '';
  return `${config.assetRoot}/${String(path).split('/').map(encodeURIComponent).join('/')}`;
}

function createImage(src, alt, className = '') {
  const image = document.createElement('img');
  image.src = src;
  image.alt = alt;
  image.loading = 'lazy';
  image.decoding = 'async';
  if (className) image.className = className;
  return image;
}

function costStyle(cost) {
  return COST_COLORS[cost] || 'var(--accent)';
}

function championTraits(champion) {
  return (champion.trait_ids || [])
    .map((traitId) => state.traitsById.get(traitId))
    .filter(Boolean);
}

function mechanicById(mechanicId) {
  return state.mechanics.find((mechanic) => mechanic.id === mechanicId);
}

function updateCount() {
  if (!elements.previewCount) return;
  if (state.activeView === 'champions') {
    elements.previewCount.textContent = `${filteredChampions().length} 名弈子`;
    return;
  }
  if (state.activeView === 'traits') {
    elements.previewCount.textContent = `${filteredTraits().length} 个羁绊`;
    return;
  }
  const mechanic = mechanicById(state.activeView.replace(/^mechanic-/, ''));
  if (mechanic) elements.previewCount.textContent = `${mechanic.entries.length} 条${mechanic.display_name}`;
}

function setActiveView(view) {
  if (!elements.mainTabs.some((tab) => tab.dataset.view === view)) return;
  state.activeView = view;
  const activeIndex = elements.mainTabs.findIndex((tab) => tab.dataset.view === view);
  elements.mainTabsWrap?.style.setProperty('--active-tab', activeIndex);

  elements.mainTabs.forEach((tab) => {
    const active = tab.dataset.view === view;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', String(active));
    tab.tabIndex = active ? 0 : -1;
  });

  elements.panels.forEach((panel) => {
    const active = panel.dataset.panel === view;
    panel.classList.remove('active');
    panel.hidden = !active;
    if (active) requestAnimationFrame(() => panel.classList.add('active'));
  });
  updateCount();
}

elements.mainTabs.forEach((tab) => {
  tab.addEventListener('click', () => setActiveView(tab.dataset.view));
  tab.addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const current = elements.mainTabs.indexOf(tab);
    const direction = event.key === 'ArrowRight' ? 1 : -1;
    const next = elements.mainTabs[(current + direction + elements.mainTabs.length) % elements.mainTabs.length];
    next.focus();
    setActiveView(next.dataset.view);
  });
});

function closeFilterSelects(except = null) {
  document.querySelectorAll('.s18-filter-select.open').forEach((select) => {
    if (select === except) return;
    select.classList.remove('open');
    select.querySelector('.s18-filter-select-trigger')?.setAttribute('aria-expanded', 'false');
  });
}

function appendFilterOptionContent(target, option, iconTraits) {
  if (iconTraits) {
    const trait = iconTraits.get(option.value);
    if (trait && trait.image) {
      target.append(createImage(assetUrl(trait.image), '', 's18-filter-select-icon'));
    } else {
      const spacer = document.createElement('span');
      spacer.className = 's18-filter-select-icon-spacer';
      spacer.setAttribute('aria-hidden', 'true');
      target.append(spacer);
    }
  }
  const text = document.createElement('span');
  text.textContent = option.label;
  target.append(text);
}

function makeFilterSelect(container, options, stateKey, iconTraits = null) {
  const select = document.createElement('div');
  select.className = 's18-filter-select';

  const trigger = document.createElement('button');
  trigger.className = 's18-filter-select-trigger';
  trigger.type = 'button';
  trigger.setAttribute('aria-haspopup', 'listbox');
  trigger.setAttribute('aria-expanded', 'false');

  const triggerValue = document.createElement('span');
  triggerValue.className = 's18-filter-select-value';
  const chevron = document.createElement('span');
  chevron.className = 's18-filter-select-chevron';
  chevron.setAttribute('aria-hidden', 'true');
  chevron.textContent = '⌄';
  trigger.append(triggerValue, chevron);

  const menu = document.createElement('div');
  menu.className = 's18-filter-select-menu';
  menu.role = 'listbox';
  menu.setAttribute('aria-label', container.getAttribute('aria-label') || '筛选选项');

  function updateTrigger(option) {
    triggerValue.replaceChildren();
    appendFilterOptionContent(triggerValue, option, iconTraits);
  }

  const buttons = options.map((option) => {
    const button = document.createElement('button');
    button.className = 's18-filter-select-option';
    button.type = 'button';
    button.role = 'option';
    button.dataset.value = option.value;
    appendFilterOptionContent(button, option, iconTraits);
    const active = state[stateKey] === option.value;
    button.classList.toggle('selected', active);
    button.setAttribute('aria-selected', String(active));
    if (active) updateTrigger(option);
    button.addEventListener('click', () => {
      state[stateKey] = option.value;
      buttons.forEach((item) => {
        const selected = item === button;
        item.classList.toggle('selected', selected);
        item.setAttribute('aria-selected', String(selected));
      });
      updateTrigger(option);
      select.classList.remove('open');
      trigger.setAttribute('aria-expanded', 'false');
      renderChampions();
    });
    return button;
  });
  menu.append(...buttons);
  select.append(trigger, menu);
  container.classList.add('s18-filter-select-host');
  container.replaceChildren(select);

  trigger.addEventListener('click', () => {
    const willOpen = !select.classList.contains('open');
    closeFilterSelects(select);
    select.classList.toggle('open', willOpen);
    trigger.setAttribute('aria-expanded', String(willOpen));
  });
  trigger.addEventListener('keydown', (event) => {
    if (!['ArrowDown', 'Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    closeFilterSelects(select);
    select.classList.add('open');
    trigger.setAttribute('aria-expanded', 'true');
    const selectedButton = buttons.find((button) => button.classList.contains('selected')) || buttons[0];
    selectedButton.focus();
  });
}

document.addEventListener('click', (event) => {
  if (!event.target.closest('.s18-filter-select')) closeFilterSelects();
});

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  const openSelect = document.querySelector('.s18-filter-select.open');
  if (!openSelect) return;
  openSelect.classList.remove('open');
  const trigger = openSelect.querySelector('.s18-filter-select-trigger');
  trigger?.setAttribute('aria-expanded', 'false');
  trigger?.focus();
});

function filteredChampions() {
  const query = state.query.trim().toLocaleLowerCase('zh-CN');
  return state.champions.filter((champion) => {
    const traits = championTraits(champion);
    if (query) {
      const searchable = [champion.name, ...traits.map((trait) => trait.name)].join(' ').toLocaleLowerCase('zh-CN');
      if (!searchable.includes(query)) return false;
    }
    if (state.origin !== 'all' && !traits.some((trait) => trait.category === 'origin' && trait.name === state.origin)) return false;
    if (state.profession !== 'all' && !traits.some((trait) => trait.category === 'class' && trait.name === state.profession)) return false;
    if (state.cost !== 'all' && String(champion.cost) !== state.cost) return false;
    return true;
  });
}

function updateChampionFilterSummary(resultCount) {
  if (!elements.championFilterSummary) return;
  const active = [];
  if (state.query) active.push(`“${state.query}”`);
  if (state.origin !== 'all') active.push(state.origin);
  if (state.profession !== 'all') active.push(state.profession);
  if (state.cost !== 'all') active.push(`${state.cost}费`);
  elements.championFilterSummary.textContent = `${active.length ? active.join(' · ') : '全部条件'} · ${resultCount} 名`;
}

function syncChampionFilterLayout() {
  const collapsed = mobileQuery.matches && !state.mobileFiltersExpanded;
  elements.championFilterPanel?.classList.toggle('mobile-collapsed', collapsed);
  elements.championFilterToggle?.setAttribute('aria-expanded', String(!collapsed));
}

elements.championFilterToggle?.addEventListener('click', () => {
  state.mobileFiltersExpanded = !state.mobileFiltersExpanded;
  syncChampionFilterLayout();
});

mobileQuery.addEventListener('change', syncChampionFilterLayout);
syncChampionFilterLayout();

function createTraitLine(trait) {
  const row = document.createElement('span');
  row.className = 'champion-trait';
  if (trait.image) row.append(createImage(assetUrl(trait.image), ''));
  const label = document.createElement('span');
  label.textContent = trait.name;
  row.append(label);
  return row;
}

function createCostBadge(cost, className) {
  const badge = document.createElement('span');
  badge.className = className;
  const icon = createImage('/static/season-gold.png', '');
  icon.setAttribute('aria-hidden', 'true');
  const value = document.createElement('span');
  value.textContent = String(cost);
  badge.append(icon, value);
  return badge;
}

function createChampionCard(champion, index) {
  const link = document.createElement('a');
  link.className = 'champion-card-link';
  link.href = window.JccSeasonChampionUi.championUrl(champion.id);
  link.setAttribute('aria-label', `查看${champion.name}详情`);
  const card = document.createElement('article');
  card.className = `champion-card${state.showSkills ? '' : ' skills-hidden'}`;
  card.style.setProperty('--cost-color', costStyle(champion.cost));
  card.style.setProperty('--delay', `${Math.min(index, 10) * 28}ms`);

  const isNew = (champion.tags || []).includes('new');
  const art = document.createElement('div');
  art.className = `champion-art${isNew ? ' has-new' : ''}`;
  const artPath = champion.splash || champion.icon;
  if (artPath) art.append(createImage(assetUrl(artPath), champion.name));
  if (isNew) {
    const badge = document.createElement('span');
    badge.className = 'champion-new-badge';
    badge.textContent = '新';
    art.append(badge);
  }
  if (champion.availability && champion.availability.type === 'unlock') {
    const badge = document.createElement('span');
    badge.className = 'champion-unlock-badge';
    badge.textContent = '解锁';
    if (champion.availability.description) badge.title = champion.availability.description;
    art.append(badge);
  }

  const name = document.createElement('h3');
  name.className = 'champion-name';
  name.textContent = champion.name;

  const traits = document.createElement('div');
  traits.className = 'champion-traits';
  traits.append(...championTraits(champion).map(createTraitLine));
  art.append(name, traits, createCostBadge(champion.cost, 'champion-cost'));

  const skill = document.createElement('div');
  skill.className = 'champion-skill';
  skill.setAttribute('aria-hidden', String(!state.showSkills));
  const skillClip = document.createElement('div');
  const skillBody = document.createElement('div');
  skillBody.className = 'champion-skill-body';
  const skillName = document.createElement('h4');
  skillName.className = 'champion-skill-name';
  skillName.textContent = (champion.skill && champion.skill.name) || '';
  const description = document.createElement('p');
  description.className = 'champion-skill-description';
  window.JccSeasonChampionUi.appendSkillDescription(description, champion.skill && champion.skill.description);
  skillBody.append(skillName, description);
  skillClip.append(skillBody);
  skill.append(skillClip);
  card.append(art, skill);
  link.append(card);
  return link;
}

function renderChampions() {
  const champions = filteredChampions();
  updateChampionFilterSummary(champions.length);
  const sections = [];
  state.costs.forEach((cost) => {
    const costChampions = champions.filter((champion) => champion.cost === cost);
    if (!costChampions.length) return;
    const section = document.createElement('section');
    section.className = 'champion-cost-section';
    section.setAttribute('aria-labelledby', `championCost${cost}`);
    const heading = document.createElement('div');
    heading.className = 'champion-cost-heading';
    const title = document.createElement('h2');
    title.id = `championCost${cost}`;
    title.textContent = `${cost}费弈子`;
    const count = document.createElement('span');
    count.textContent = `${costChampions.length} 名`;
    heading.append(title, count);
    const grid = document.createElement('div');
    grid.className = 'champion-grid';
    grid.append(...costChampions.map(createChampionCard));
    section.append(heading, grid);
    sections.push(section);
  });
  elements.championSections.replaceChildren(...sections);
  elements.championEmpty.classList.toggle('hidden', champions.length > 0);
  if (state.activeView === 'champions') updateCount();
}

elements.championSearch?.addEventListener('input', (event) => {
  state.query = event.target.value;
  renderChampions();
});

elements.skillToggle?.addEventListener('change', (event) => {
  state.showSkills = event.target.checked;
  document.querySelectorAll('.champion-card').forEach((card) => card.classList.toggle('skills-hidden', !state.showSkills));
  document.querySelectorAll('.champion-skill').forEach((skill) => skill.setAttribute('aria-hidden', String(!state.showSkills)));
});

function filteredTraits() {
  return state.traits.filter((trait) => (state.traitType === 'class'
    ? trait.category === 'class'
    : trait.category !== 'class'));
}

function createTraitCard(trait, index) {
  const card = document.createElement('article');
  card.className = 'trait-card';
  card.style.setProperty('--delay', `${Math.min(index, 10) * 30}ms`);

  const title = document.createElement('h2');
  title.className = 'trait-card-title';
  if (trait.image) title.append(createImage(assetUrl(trait.image), ''));
  const titleText = document.createElement('span');
  titleText.textContent = trait.name;
  title.append(titleText);

  const description = document.createElement('p');
  description.className = 'trait-description';
  window.JccSeasonChampionUi.appendSkillDescription(description, trait.description);
  card.append(title, description);

  const breakpoints = trait.breakpoints || [];
  if (breakpoints.length) {
    const levels = document.createElement('div');
    levels.className = 'trait-levels';
    breakpoints.forEach((breakpoint) => {
      const row = document.createElement('div');
      row.className = 'trait-level';
      const count = document.createElement('span');
      count.className = 'trait-level-count';
      count.textContent = String(breakpoint.min_units);
      const effect = document.createElement('span');
      effect.className = 'trait-level-effect';
      window.JccSeasonChampionUi.appendSkillDescription(effect, breakpoint.effect);
      row.append(count, effect);
      levels.append(row);
    });
    card.append(levels);
  }

  const members = state.champions.filter((champion) => (champion.trait_ids || []).includes(trait.id));
  if (members.length) {
    const champions = document.createElement('div');
    champions.className = 'trait-champions';
    members.forEach((champion) => {
      champions.append(window.JccSeasonChampionUi.createMemberLink(champion));
    });
    card.append(champions);
  } else {
    const empty = document.createElement('p');
    empty.className = 'trait-no-champions';
    empty.textContent = '暂无弈子';
    card.append(empty);
  }
  return card;
}

function renderTraits() {
  elements.traitGrid.replaceChildren(...filteredTraits().map(createTraitCard));
  if (state.activeView === 'traits') updateCount();
}

elements.traitTypeButtons.forEach((button) => {
  button.addEventListener('click', () => {
    state.traitType = button.dataset.traitType;
    elements.traitTypeButtons.forEach((item) => {
      const active = item === button;
      item.classList.toggle('active', active);
      item.setAttribute('aria-selected', String(active));
      item.tabIndex = active ? 0 : -1;
    });
    renderTraits();
  });
});

function createWandCard(entry, index) {
  const card = document.createElement('article');
  card.className = `wand-card${index < 18 ? ' animate-in' : ''}`;
  if (index < 18) card.style.setProperty('--delay', `${index * 22}ms`);
  const header = document.createElement('div');
  header.className = 'wand-card-header';
  const title = document.createElement('h2');
  title.textContent = entry.name;
  header.append(title);
  const cost = entry.data && entry.data.cost;
  if (cost !== null && cost !== undefined) header.append(createCostBadge(cost, 'wand-cost'));
  const effect = document.createElement('p');
  effect.className = 'wand-effect';
  window.JccSeasonChampionUi.appendSkillDescription(effect, entry.description);
  card.append(header, effect);
  const condition = entry.data && entry.data.appearance_condition;
  if (condition) {
    const conditionNode = document.createElement('p');
    conditionNode.className = 'wand-condition';
    conditionNode.textContent = `出现条件：${condition}`;
    card.append(conditionNode);
  }
  return card;
}

function createWishRow(wish) {
  const row = document.createElement('div');
  row.className = 'mechanic-wish';
  if (wish.image) row.append(createImage(assetUrl(wish.image), ''));
  const body = document.createElement('div');
  const name = document.createElement('strong');
  name.textContent = wish.name || '';
  const description = document.createElement('p');
  window.JccSeasonChampionUi.appendSkillDescription(description, wish.description);
  body.append(name, description);
  row.append(body);
  return row;
}

function createMechanicCard(entry, index) {
  const data = entry.data || {};
  const stages = Array.isArray(data.stages) ? data.stages : [];
  const card = document.createElement('article');
  card.className = `mechanic-card${entry.image && stages.length ? ' has-splash' : ''}`;
  card.style.setProperty('--delay', `${Math.min(index, 10) * 26}ms`);

  const body = document.createElement('div');
  body.className = 'mechanic-card-body';

  const header = document.createElement('div');
  header.className = 'mechanic-card-header';
  if (entry.image && !stages.length) header.append(createImage(assetUrl(entry.image), ''));
  const title = document.createElement('h2');
  title.textContent = entry.name || '';
  header.append(title);
  body.append(header);

  if (entry.description) {
    const description = document.createElement('p');
    description.className = 'mechanic-description';
    window.JccSeasonChampionUi.appendSkillDescription(description, entry.description);
    body.append(description);
  }

  stages.forEach((stage) => {
    const stageNode = document.createElement('div');
    stageNode.className = 'mechanic-stage';
    if (stage.stage !== null && stage.stage !== undefined) {
      const stageTitle = document.createElement('p');
      stageTitle.className = 'mechanic-stage-title';
      stageTitle.textContent = `阶段 ${stage.stage}`;
      stageNode.append(stageTitle);
    }
    (stage.wishes || []).forEach((wish) => stageNode.append(createWishRow(wish)));
    body.append(stageNode);
  });

  if (entry.image && stages.length) {
    card.append(createImage(assetUrl(entry.image), entry.name || '', 'mechanic-splash'));
  }
  card.append(body);
  return card;
}

function renderMechanics() {
  state.mechanics.forEach((mechanic) => {
    const grid = document.querySelector(`[data-mechanic-grid="${CSS.escape(mechanic.id)}"]`);
    if (!grid) return;
    const factory = mechanic.kind === 'wand' ? createWandCard : createMechanicCard;
    grid.replaceChildren(...mechanic.entries.map((entry, index) => factory(entry, index)));
  });
}

async function loadData() {
  try {
    const response = await fetch(config.dataUrl);
    if (!response.ok) throw new Error('season data request failed');
    const data = await response.json();
    state.champions = data.champions || [];
    state.traits = data.traits || [];
    state.mechanics = data.mechanics || [];
    state.traitsById = new Map(state.traits.map((trait) => [trait.id, trait]));
    state.costs = [...new Set(state.champions.map((champion) => champion.cost).filter((cost) => cost !== null))].sort((a, b) => a - b);
    window.JccSeasonChampionUi.configure({
      seasonId: config.seasonId,
      assetRoot: config.assetRoot,
      champions: state.champions,
      traitsById: state.traitsById,
    });

    const traitNames = (category) => state.traits
      .filter((trait) => trait.category === category)
      .map((trait) => trait.name);
    const traitByName = new Map(state.traits.map((trait) => [trait.name, trait]));
    const nameOptions = (names, allLabel) => [{value: 'all', label: allLabel}, ...names.map((name) => ({value: name, label: name}))];
    makeFilterSelect(elements.originFilters, nameOptions(traitNames('origin'), '全部种族'), 'origin', traitByName);
    makeFilterSelect(elements.professionFilters, nameOptions(traitNames('class'), '全部职业'), 'profession', traitByName);
    makeFilterSelect(
      elements.costFilters,
      [{value: 'all', label: '全部费用'}, ...state.costs.map((cost) => ({value: String(cost), label: `${cost}费`}))],
      'cost',
    );
    renderChampions();
    renderTraits();
    renderMechanics();
    setActiveView('champions');
    elements.loading.classList.add('hidden');
    elements.content.setAttribute('aria-busy', 'false');
  } catch (error) {
    elements.loading.classList.add('hidden');
    elements.loadError.classList.remove('hidden');
    elements.content.setAttribute('aria-busy', 'false');
    console.error(error);
  }
}

loadData();
