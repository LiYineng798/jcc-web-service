const S18_DATA_ROOT = '/static/s18-preview';
const S18_PROFESSIONS = [
  '法师',
  '适配者',
  '毁灭者',
  '斗士',
  '迅捷射手',
  '猎手',
  '裁决使',
  '召唤使',
  '重装战士',
  '护卫',
  '主宰',
  '神谕者',
];
const S18_COST_COLORS = {
  1: 'rgb(145, 145, 145)',
  2: 'rgb(16, 166, 14)',
  3: 'rgb(67, 156, 204)',
  4: 'rgb(175, 25, 186)',
  5: 'rgb(147, 130, 22)',
};

const state = {
  champions: [],
  traits: [],
  wands: [],
  traitMap: new Map(),
  activeView: 'champions',
  traitType: 'origin',
  query: '',
  origin: 'all',
  profession: 'all',
  cost: 'all',
  showSkills: true,
};

const elements = {
  content: document.querySelector('#s18PreviewContent'),
  previewCount: document.querySelector('#previewCount'),
  mainTabs: Array.from(document.querySelectorAll('.s18-main-tab')),
  mainTabsWrap: document.querySelector('.s18-main-tabs'),
  panels: Array.from(document.querySelectorAll('.s18-view-panel')),
  championSearch: document.querySelector('#championSearch'),
  skillToggle: document.querySelector('#skillToggle'),
  originFilters: document.querySelector('#originFilters'),
  professionFilters: document.querySelector('#professionFilters'),
  costFilters: document.querySelector('#costFilters'),
  championSections: document.querySelector('#championSections'),
  championEmpty: document.querySelector('#championEmpty'),
  traitTypeButtons: Array.from(document.querySelectorAll('[data-trait-type]')),
  traitGrid: document.querySelector('#traitGrid'),
  wandGrid: document.querySelector('#wandGrid'),
  loading: document.querySelector('#s18Loading'),
  loadError: document.querySelector('#s18LoadError'),
  themeToggle: document.querySelector('#themeToggle'),
  themeIcon: document.querySelector('#themeIcon'),
  themeText: document.querySelector('#themeText'),
};

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  window.jccApplyThemeToggleState?.(theme, elements.themeToggle, elements.themeIcon, elements.themeText);
}

setTheme(localStorage.getItem('theme') || 'light');
elements.themeToggle?.addEventListener('click', () => {
  setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
});

function assetPath(...parts) {
  return `${S18_DATA_ROOT}/${parts.map((part) => encodeURIComponent(String(part))).join('/')}`;
}

function traitAssetPath(path) {
  return `${S18_DATA_ROOT}/${path.split('/').map((part) => encodeURIComponent(part)).join('/')}`;
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
  return S18_COST_COLORS[cost] || 'var(--accent)';
}

function updateCount(count) {
  const labels = {
    champions: `${count} 名弈子`,
    traits: `${count} 个羁绊`,
    wands: `${count} 条法杖`,
  };
  elements.previewCount.textContent = labels[state.activeView];
}

function setActiveView(view) {
  if (!['champions', 'traits', 'wands'].includes(view)) return;
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

  if (view === 'champions') updateCount(filteredChampions().length);
  if (view === 'traits') updateCount(filteredTraits().length);
  if (view === 'wands') updateCount(state.wands.length);
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

function appendFilterOptionContent(target, option, showTraitIcon) {
  const trait = showTraitIcon ? state.traitMap.get(option.value) : null;
  if (trait) {
    target.append(createImage(traitAssetPath(trait.svg), '', 's18-filter-select-icon'));
  } else if (showTraitIcon) {
    const spacer = document.createElement('span');
    spacer.className = 's18-filter-select-icon-spacer';
    spacer.setAttribute('aria-hidden', 'true');
    target.append(spacer);
  }
  const text = document.createElement('span');
  text.textContent = option.label;
  target.append(text);
}

function makeFilterSelect(container, values, stateKey, labelSuffix = '', showTraitIcon = false) {
  const options = [{value: 'all', label: '全部'}, ...values.map((value) => ({value: String(value), label: `${value}${labelSuffix}`}))];
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
    appendFilterOptionContent(triggerValue, option, showTraitIcon);
  }

  const buttons = options.map((option) => {
    const button = document.createElement('button');
    button.className = 's18-filter-select-option';
    button.type = 'button';
    button.role = 'option';
    button.dataset.value = option.value;
    appendFilterOptionContent(button, option, showTraitIcon);
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
    if (query && !champion.名称.toLocaleLowerCase('zh-CN').includes(query)) return false;
    if (state.origin !== 'all' && !champion.羁绊.includes(state.origin)) return false;
    if (state.profession !== 'all' && !champion.羁绊.includes(state.profession)) return false;
    if (state.cost !== 'all' && String(champion.费用) !== state.cost) return false;
    return true;
  });
}

function createTraitLine(traitName) {
  const trait = state.traitMap.get(traitName);
  const row = document.createElement('span');
  row.className = 'champion-trait';
  if (trait) row.append(createImage(traitAssetPath(trait.svg), '', ''));
  const label = document.createElement('span');
  label.textContent = traitName;
  row.append(label);
  return row;
}

function createCostBadge(cost, className) {
  const badge = document.createElement('span');
  badge.className = className;
  const icon = createImage(assetPath('system', 'gold.png'), '');
  icon.setAttribute('aria-hidden', 'true');
  const value = document.createElement('span');
  value.textContent = String(cost);
  badge.append(icon, value);
  return badge;
}

function createChampionCard(champion, index) {
  const card = document.createElement('article');
  card.className = `champion-card${state.showSkills ? '' : ' skills-hidden'}`;
  card.style.setProperty('--cost-color', costStyle(champion.费用));
  card.style.setProperty('--delay', `${Math.min(index, 10) * 28}ms`);

  const art = document.createElement('div');
  art.className = 'champion-art';
  art.append(createImage(assetPath('bg', champion.费用, `${champion.名称}.jpg`), champion.名称));

  const name = document.createElement('h3');
  name.className = 'champion-name';
  name.textContent = champion.名称;

  const traits = document.createElement('div');
  traits.className = 'champion-traits';
  traits.append(...champion.羁绊.map(createTraitLine));
  art.append(name, traits, createCostBadge(champion.费用, 'champion-cost'));

  const skill = document.createElement('div');
  skill.className = 'champion-skill';
  skill.setAttribute('aria-hidden', String(!state.showSkills));
  const skillClip = document.createElement('div');
  const skillBody = document.createElement('div');
  skillBody.className = 'champion-skill-body';
  const skillName = document.createElement('h4');
  skillName.className = 'champion-skill-name';
  skillName.textContent = champion.技能名称;
  const description = document.createElement('p');
  description.className = 'champion-skill-description';
  description.textContent = champion.技能描述;
  skillBody.append(skillName, description);
  skillClip.append(skillBody);
  skill.append(skillClip);
  card.append(art, skill);
  return card;
}

function renderChampions() {
  const champions = filteredChampions();
  const sections = [];
  for (let cost = 1; cost <= 5; cost += 1) {
    const costChampions = champions.filter((champion) => champion.费用 === cost);
    if (!costChampions.length) continue;
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
  }
  elements.championSections.replaceChildren(...sections);
  elements.championEmpty.classList.toggle('hidden', champions.length > 0);
  if (state.activeView === 'champions') updateCount(champions.length);
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
  const professionSet = new Set(S18_PROFESSIONS);
  return state.traits.filter((trait) => state.traitType === 'profession' ? professionSet.has(trait.名称) : !professionSet.has(trait.名称));
}

function createTraitCard(trait, index) {
  const card = document.createElement('article');
  card.className = 'trait-card';
  card.style.setProperty('--delay', `${Math.min(index, 10) * 30}ms`);

  const title = document.createElement('h2');
  title.className = 'trait-card-title';
  title.append(createImage(traitAssetPath(trait.svg), ''));
  const titleText = document.createElement('span');
  titleText.textContent = trait.名称;
  title.append(titleText);

  const description = document.createElement('p');
  description.className = 'trait-description';
  description.textContent = trait.介绍;
  card.append(title, description);

  if (trait.层级.length) {
    const levels = document.createElement('div');
    levels.className = 'trait-levels';
    trait.层级.forEach((level) => {
      const row = document.createElement('div');
      row.className = 'trait-level';
      const count = document.createElement('span');
      count.className = 'trait-level-count';
      count.textContent = String(level.数量);
      const effect = document.createElement('span');
      effect.className = 'trait-level-effect';
      effect.textContent = level.效果;
      row.append(count, effect);
      levels.append(row);
    });
    card.append(levels);
  }

  const matchingChampions = state.champions.filter((champion) => champion.羁绊.includes(trait.名称));
  if (matchingChampions.length) {
    const champions = document.createElement('div');
    champions.className = 'trait-champions';
    matchingChampions.forEach((champion) => {
      const item = document.createElement('div');
      item.className = 'trait-champion';
      item.style.setProperty('--cost-color', costStyle(champion.费用));
      item.title = `${champion.名称} · ${champion.费用}费`;
      item.append(createImage(assetPath('xt', champion.费用, `${champion.名称}.jpg`), champion.名称));
      const name = document.createElement('span');
      name.textContent = champion.名称;
      item.append(name);
      champions.append(item);
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
  const traits = filteredTraits();
  elements.traitGrid.replaceChildren(...traits.map(createTraitCard));
  if (state.activeView === 'traits') updateCount(traits.length);
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

function createWandCard(wand, index) {
  const card = document.createElement('article');
  card.className = `wand-card${index < 18 ? ' animate-in' : ''}`;
  if (index < 18) card.style.setProperty('--delay', `${index * 22}ms`);
  const header = document.createElement('div');
  header.className = 'wand-card-header';
  const title = document.createElement('h2');
  title.textContent = wand.名称;
  header.append(title, createCostBadge(wand.费用, 'wand-cost'));
  const effect = document.createElement('p');
  effect.className = 'wand-effect';
  effect.textContent = wand.效果;
  card.append(header, effect);
  if (wand.出现条件) {
    const condition = document.createElement('p');
    condition.className = 'wand-condition';
    condition.textContent = `出现条件：${wand.出现条件}`;
    card.append(condition);
  }
  return card;
}

function renderWands() {
  elements.wandGrid.replaceChildren(...state.wands.map(createWandCard));
}

async function loadData() {
  try {
    const responses = await Promise.all([
      fetch(`${S18_DATA_ROOT}/champions.json`),
      fetch(`${S18_DATA_ROOT}/traits.json`),
      fetch(`${S18_DATA_ROOT}/wands.json`),
    ]);
    if (responses.some((response) => !response.ok)) throw new Error('S18 data request failed');
    [state.champions, state.traits, state.wands] = await Promise.all(responses.map((response) => response.json()));
    state.traitMap = new Map(state.traits.map((trait) => [trait.名称, trait]));

    const professionSet = new Set(S18_PROFESSIONS);
    const origins = state.traits.map((trait) => trait.名称).filter((name) => !professionSet.has(name));
    makeFilterSelect(elements.originFilters, origins, 'origin', '', true);
    makeFilterSelect(elements.professionFilters, S18_PROFESSIONS, 'profession', '', true);
    makeFilterSelect(elements.costFilters, [1, 2, 3, 4, 5], 'cost', '费');
    renderChampions();
    renderTraits();
    renderWands();
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
