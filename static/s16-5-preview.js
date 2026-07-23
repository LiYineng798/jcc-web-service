const S16_ROOT = '/static/s16-5-preview';
const S16_COST_COLORS = {
  1: 'rgb(145, 145, 145)',
  2: 'rgb(16, 166, 14)',
  3: 'rgb(67, 156, 204)',
  4: 'rgb(175, 25, 186)',
  5: 'rgb(147, 130, 22)',
  7: 'rgb(205, 82, 61)',
};
const NEW_CHAMPIONS = new Set([
  '布兰德', '阿利斯塔', '希维尔', '墨菲特', '维克托', '萨科', '库奇',
  '伊莉丝', '凯隐', '彗', '艾瑞莉娅', '杰斯', '远古巨龙', '莫德凯撒',
]);
const mobileQuery = window.matchMedia('(max-width: 640px)');
const state = {
  champions: [],
  traits: new Map(),
  origins: [],
  professions: [],
  query: '',
  origin: 'all',
  profession: 'all',
  cost: 'all',
  showSkills: !mobileQuery.matches,
  mobileFiltersExpanded: false,
};
const elements = {
  content: document.querySelector('#s16PreviewContent'),
  count: document.querySelector('#previewCount'),
  filterToggle: document.querySelector('#championFilterToggle'),
  filterPanel: document.querySelector('#championFilterPanel'),
  filterSummary: document.querySelector('#championFilterSummary'),
  search: document.querySelector('#championSearch'),
  skillToggle: document.querySelector('#skillToggle'),
  originFilters: document.querySelector('#originFilters'),
  professionFilters: document.querySelector('#professionFilters'),
  costFilters: document.querySelector('#costFilters'),
  sections: document.querySelector('#championSections'),
  empty: document.querySelector('#championEmpty'),
  loading: document.querySelector('#s16Loading'),
  error: document.querySelector('#s16LoadError'),
};

function image(path, alt = '') {
  const img = document.createElement('img');
  img.src = `${S16_ROOT}/${path.split('/').map(encodeURIComponent).join('/')}`;
  img.alt = alt;
  img.loading = 'lazy';
  return img;
}

function traitPath(trait) {
  const category = trait.category === 'profession' ? '职业羁绊' : '种族羁绊';
  return `images/traits/${category}/${trait.id}_${trait.name}.png`;
}

function costColor(cost) {
  return S16_COST_COLORS[cost] || S16_COST_COLORS[5];
}

function filteredChampions() {
  const query = state.query.trim().toLocaleLowerCase('zh-CN');
  return state.champions.filter((champion) => {
    const searchable = [champion.name, ...champion.traits.map((trait) => trait.name)].join(' ').toLocaleLowerCase('zh-CN');
    if (query && !searchable.includes(query)) return false;
    if (state.origin !== 'all' && !champion.traits.some((trait) => trait.name === state.origin && trait.category === 'origin')) return false;
    if (state.profession !== 'all' && !champion.traits.some((trait) => trait.name === state.profession && trait.category === 'profession')) return false;
    if (state.cost !== 'all' && String(champion.price) !== state.cost) return false;
    return true;
  });
}

function updateSummary(count) {
  const active = [];
  if (state.query) active.push(`“${state.query}”`);
  if (state.origin !== 'all') active.push(state.origin);
  if (state.profession !== 'all') active.push(state.profession);
  if (state.cost !== 'all') active.push(`${state.cost}费`);
  elements.filterSummary.textContent = `${active.length ? active.join(' · ') : '全部条件'} · ${count} 名`;
  elements.count.textContent = `${count} 名弈子`;
}

function syncMobileFilters() {
  const collapsed = mobileQuery.matches && !state.mobileFiltersExpanded;
  elements.filterPanel.classList.toggle('mobile-collapsed', collapsed);
  elements.filterToggle.setAttribute('aria-expanded', String(!collapsed));
}

function makeFilter(container, items, value, onChange, label) {
  const select = document.createElement('div');
  select.className = 's18-filter-select';
  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 's18-filter-select-trigger';
  trigger.setAttribute('aria-haspopup', 'listbox');
  trigger.setAttribute('aria-expanded', 'false');
  const valueNode = document.createElement('span');
  valueNode.className = 's18-filter-select-value';
  const chevron = document.createElement('span');
  chevron.className = 's18-filter-select-chevron';
  chevron.textContent = '⌄';
  trigger.append(valueNode, chevron);
  const menu = document.createElement('div');
  menu.className = 's18-filter-select-menu';
  menu.setAttribute('role', 'listbox');
  const buttons = [];
  items.forEach((item) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 's18-filter-select-option';
    button.dataset.value = item.value;
    button.textContent = item.label;
    button.setAttribute('role', 'option');
    button.addEventListener('click', () => {
      onChange(item.value);
      select.classList.remove('open');
      trigger.setAttribute('aria-expanded', 'false');
    });
    menu.append(button);
    buttons.push(button);
  });
  function refresh(selected) {
    const item = items.find((entry) => entry.value === selected) || items[0];
    valueNode.textContent = item.label;
    buttons.forEach((button) => {
      const active = button.dataset.value === selected;
      button.classList.toggle('selected', active);
      button.setAttribute('aria-selected', String(active));
    });
  }
  trigger.addEventListener('click', () => {
    document.querySelectorAll('.s18-filter-select.open').forEach((other) => {
      if (other !== select) other.classList.remove('open');
    });
    const open = !select.classList.contains('open');
    select.classList.toggle('open', open);
    trigger.setAttribute('aria-expanded', String(open));
  });
  select.append(trigger, menu);
  container.replaceChildren(select);
  refresh(value);
  select.dataset.label = label;
}

function renderFilters() {
  const originItems = [{ value: 'all', label: '全部种族' }, ...state.origins.map((name) => ({ value: name, label: name }))];
  const professionItems = [{ value: 'all', label: '全部职业' }, ...state.professions.map((name) => ({ value: name, label: name }))];
  const costItems = [{ value: 'all', label: '全部费用' }, ...[1, 2, 3, 4, 5, 7].map((cost) => ({ value: String(cost), label: `${cost}费` }))];
  makeFilter(elements.originFilters, originItems, state.origin, (value) => { state.origin = value; render(); }, '种族');
  makeFilter(elements.professionFilters, professionItems, state.profession, (value) => { state.profession = value; render(); }, '职业');
  makeFilter(elements.costFilters, costItems, state.cost, (value) => { state.cost = value; render(); }, '费用');
}

function traitLine(trait) {
  const row = document.createElement('span');
  row.className = 'champion-trait';
  const known = state.traits.get(trait.name);
  if (known) row.append(image(traitPath(known), ''));
  const label = document.createElement('span');
  label.textContent = trait.name;
  row.append(label);
  return row;
}

function costBadge(cost) {
  const badge = document.createElement('span');
  badge.className = 'champion-cost';
  badge.append(image('system/gold.png', ''), document.createTextNode(String(cost)));
  return badge;
}

function card(champion, index) {
  const link = document.createElement('div');
  link.className = 'champion-card-link';
  const article = document.createElement('article');
  article.className = `champion-card${state.showSkills ? '' : ' skills-hidden'}`;
  article.style.setProperty('--cost-color', costColor(champion.price));
  article.style.setProperty('--delay', `${Math.min(index, 10) * 28}ms`);
  const art = document.createElement('div');
  art.className = `champion-art${NEW_CHAMPIONS.has(champion.name) ? ' has-new' : ''}`;
  art.append(image(`images/big/${champion.price}费/${champion.id}_${champion.name}.jpg`, champion.name));
  if (NEW_CHAMPIONS.has(champion.name)) {
    const badge = document.createElement('span');
    badge.className = 's16-new-badge';
    badge.textContent = '新';
    art.append(badge);
  }
  const name = document.createElement('h3');
  name.className = 'champion-name';
  name.textContent = champion.name;
  const traits = document.createElement('div');
  traits.className = 'champion-traits';
  traits.append(...champion.traits.map(traitLine));
  art.append(name, traits, costBadge(champion.price));
  const skill = document.createElement('div');
  skill.className = 'champion-skill';
  skill.setAttribute('aria-hidden', String(!state.showSkills));
  const clip = document.createElement('div');
  const body = document.createElement('div');
  body.className = 'champion-skill-body';
  const skillName = document.createElement('h4');
  skillName.className = 'champion-skill-name';
  skillName.textContent = champion.skill.name;
  const description = document.createElement('p');
  description.className = 'champion-skill-description';
  description.textContent = champion.skill.description;
  body.append(skillName, description);
  clip.append(body); skill.append(clip); article.append(art, skill); link.append(article);
  return link;
}

function render() {
  const champions = filteredChampions();
  updateSummary(champions.length);
  const sections = [];
  [1, 2, 3, 4, 5, 7].forEach((cost) => {
    const matches = champions.filter((champion) => champion.price === cost);
    if (!matches.length) return;
    const section = document.createElement('section');
    section.className = 'champion-cost-section';
    const heading = document.createElement('div');
    heading.className = 'champion-cost-heading';
    const title = document.createElement('h2'); title.textContent = `${cost}费弈子`;
    const count = document.createElement('span'); count.textContent = `${matches.length} 名`;
    heading.append(title, count);
    const grid = document.createElement('div'); grid.className = 'champion-grid';
    grid.append(...matches.map(card)); section.append(heading, grid); sections.push(section);
  });
  elements.sections.replaceChildren(...sections);
  elements.empty.classList.toggle('hidden', champions.length > 0);
}

async function boot() {
  try {
    const [heroResponse, traitResponse] = await Promise.all([
      fetch(`${S16_ROOT}/heroes.json`, { cache: 'no-cache' }),
      fetch(`${S16_ROOT}/traits.json`, { cache: 'no-cache' }),
    ]);
    if (!heroResponse.ok || !traitResponse.ok) throw new Error('asset load failed');
    const heroData = await heroResponse.json();
    const traitData = await traitResponse.json();
    const originNames = new Set(traitData.races.map((trait) => trait.name));
    const professionNames = new Set(traitData.jobs.map((trait) => trait.name));
    [...traitData.races].forEach((trait) => state.traits.set(trait.name, { ...trait, category: 'origin' }));
    [...traitData.jobs].forEach((trait) => state.traits.set(trait.name, { ...trait, category: 'profession' }));
    state.champions = heroData.heroes.map((champion) => ({
      ...champion,
      traits: champion.traits.map((trait) => ({ ...trait, category: originNames.has(trait.name) ? 'origin' : (professionNames.has(trait.name) ? 'profession' : 'origin') })),
    }));
    state.origins = [...new Set(state.champions.flatMap((champion) => champion.traits.filter((trait) => trait.category === 'origin').map((trait) => trait.name)))].sort();
    state.professions = [...new Set(state.champions.flatMap((champion) => champion.traits.filter((trait) => trait.category === 'profession').map((trait) => trait.name)))].sort();
    renderFilters(); render();
    elements.content.setAttribute('aria-busy', 'false');
    elements.loading.classList.add('hidden');
  } catch (error) {
    elements.loading.classList.add('hidden');
    elements.error.classList.remove('hidden');
  }
}

elements.search.addEventListener('input', (event) => { state.query = event.target.value; render(); });
elements.skillToggle.addEventListener('change', (event) => {
  state.showSkills = event.target.checked;
  document.querySelectorAll('.champion-card').forEach((item) => item.classList.toggle('skills-hidden', !state.showSkills));
  document.querySelectorAll('.champion-skill').forEach((item) => item.setAttribute('aria-hidden', String(!state.showSkills)));
});
elements.filterToggle.addEventListener('click', () => { state.mobileFiltersExpanded = !state.mobileFiltersExpanded; syncMobileFilters(); });
mobileQuery.addEventListener('change', syncMobileFilters);
document.addEventListener('click', (event) => {
  if (!event.target.closest('.s18-filter-select')) document.querySelectorAll('.s18-filter-select.open').forEach((item) => item.classList.remove('open'));
});
syncMobileFilters();
boot();
