(() => {
  const root = document.querySelector('#smeech');
  const form = document.querySelector('#conditions');
  const find = id => document.getElementById(id);
  const required = new Set(), excluded = new Set();
  const emblems = [];
  let mode = 'required', catalog, heroes, traits, worker, timer;
  const catalogUrl = new URL(root.dataset.catalog, location.href);
  function asset(path) {
    const url = new URL(path, catalogUrl);
    url.search = catalogUrl.search;
    return url.href;
  }
  function tag(name, text, className) {
    const el = document.createElement(name);
    if (text != null) el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function action(label, text, click) {
    const button = tag('button', text);
    button.type = 'button';
    button.setAttribute('aria-label', label);
    button.addEventListener('click', click);
    return button;
  }
  function picture(path) {
    const img = tag('img');
    img.src = asset(path);
    img.alt = '';
    img.loading = 'lazy';
    return img;
  }
  function heroPortrait(hero) {
    const frame = tag('span', null, 'cost-frame');
    frame.dataset.cost = hero.cost;
    frame.title = hero.name + ' · ' + hero.cost + ' 费';
    const img = picture('heroes/' + hero.id + '.webp');
    img.alt = hero.cost + ' 费';
    frame.append(img);
    return frame;
  }
  function renderResults(results) {
    find('result-count').textContent = results.length ? results.length + ' 套' : '';
    find('status').textContent = results.length ? '' : '当前条件未找到方案，可放宽候选范围或增加人口。';
    const rows = results.map(result => {
      const row = tag('article', null, 'team strategy-card');
      const head = tag('header');
      head.append(tag('h3', result.population + ' 人口'), tag('span', result.cost + ' 金币'));
      const lineup = tag('ul', null, 'team-heroes');
      for (const id of result.heroes) {
        const hero = heroes.get(id);
        const member = tag('li');
        member.append(heroPortrait(hero), tag('span', hero.name));
        lineup.append(member);
      }
      const groups = tag('details', null, 'team-traits');
      groups.open = results[0] === result;
      groups.append(tag('summary', result.traits.length + ' 个激活羁绊'));
      const list = tag('ul');
      for (const id of result.traits) {
        const item = tag('li');
        const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        icon.setAttribute('aria-hidden', 'true');
        const use = document.createElementNS(icon.namespaceURI, 'use');
        use.setAttribute('href', asset('traits.svg') + '#' + id);
        use.setAttribute('width', '100%');
        use.setAttribute('height', '100%');
        icon.append(use);
        item.append(icon, tag('span', traits.get(id).name));
        list.append(item);
      }
      groups.append(list);
      row.append(head, lineup, groups);
      if (result.assignments.length) {
        const carriers = result.assignments.map(a => heroes.get(a.hero).name + ' · ' + traits.get(a.trait).name + '纹章');
        row.append(tag('p', carriers.join(' / '), 'carriers'));
      }
      return row;
    });
    find('results').replaceChildren(...rows);
  }

  function calculate() {
    clearTimeout(timer);
    if (worker) worker.terminate();
    worker = null;
    if (!catalog) return;
    find('results').replaceChildren();
    find('result-count').textContent = '';
    find('status').textContent = '计算中…';
    find('retry').hidden = true;
    timer = setTimeout(() => {
      const current = new Worker(root.dataset.worker);
      worker = current;
      function finish(error, results) {
        if (worker !== current) return;
        current.terminate();
        worker = null;
        if (error) find('status').textContent = error;
        else renderResults(results);
      }
      current.onmessage = ({ data }) => finish(data.error, data.results);
      current.onerror = () => {
        if (current !== worker) return;
        finish('计算未完成，请重试。');
        find('retry').hidden = false;
      };
      current.postMessage({ catalog, options: {
        population: Number(form.elements.population.value),
        required: [...required], excluded: [...excluded], emblems,
        excludedCosts: [...form.querySelectorAll('[name="excludedCost"]:checked')].map(input => Number(input.value)),
        excludeUnlocks: form.elements.excludeUnlocks.checked,
      } });
    }, 100);
  }

  function toggleHero(id) {
    const selected = mode === 'required' ? required : excluded;
    const other = mode === 'required' ? excluded : required;
    other.delete(id);
    if (selected.has(id)) selected.delete(id);
    else selected.add(id);
    updateSelection();
  }
  function removeEmblem(id) {
    const index = emblems.indexOf(id);
    if (index >= 0) emblems.splice(index, 1);
    updateSelection();
  }
  function updateSelection() {
    const chips = [];
    for (const [set, label] of [[required, '必选'], [excluded, '禁用']]) {
      for (const id of set) {
        const name = label + ' ' + heroes.get(id).name;
        chips.push(action('移除' + name, name + ' ×', () => { set.delete(id); updateSelection(); }));
      }
    }
    for (const id of new Set(emblems)) {
      const name = traits.get(id).name + '纹章';
      const count = emblems.filter(value => value === id).length;
      chips.push(action('减少' + name, name + ' ×' + count + ' −', () => removeEmblem(id)));
    }
    find('selection').replaceChildren(...chips);
    find('hero-count').textContent = required.size || excluded.size ? required.size + ' 必选 · ' + excluded.size + ' 禁用' : '不限';
    find('emblem-count').textContent = emblems.length ? emblems.length + ' 枚' : '无';
    updatePicker();
    calculate();
  }
  function updatePicker() {
    const query = find('hero-search').value.trim().toLowerCase();
    let visible = 0;
    for (const button of find('hero-options').querySelectorAll('button')) {
      const id = Number(button.dataset.hero);
      button.hidden = !button.dataset.search.includes(query);
      if (!button.hidden) visible++;
      button.setAttribute('aria-pressed', (mode === 'required' ? required : excluded).has(id));
      button.dataset.selection = required.has(id) ? '必选' : excluded.has(id) ? '禁用' : '';
    }
    find('no-heroes').hidden = visible > 0;
    for (const button of find('emblem-options').children) {
      const count = emblems.filter(id => id === button.dataset.trait).length;
      button.lastElementChild.textContent = count ? '×' + count : '＋';
    }
  }
  function buildPicker() {
    for (const hero of heroes.values()) {
      const names = hero.traits.map(id => traits.get(id).name).join(' ');
      const button = action(hero.name + '，' + hero.cost + ' 费，' + names, '', () => toggleHero(hero.id));
      button.dataset.search = (hero.name + ' ' + names).toLowerCase();
      button.dataset.hero = hero.id;
      button.append(heroPortrait(hero), tag('span', hero.name));
      find('hero-options').append(button);
    }
    const empty = tag('p', '未找到匹配弈子');
    empty.id = 'no-heroes';
    find('hero-options').append(empty);
    for (const t of traits.values()) {
      if (!t.emblem) continue;
      const button = action('添加' + t.name + '纹章', '', () => { emblems.push(t.id); updateSelection(); });
      button.dataset.trait = t.id;
      button.append(picture('emblems/' + t.emblem + '.webp'), tag('span', t.name), tag('small', '＋'));
      find('emblem-options').append(button);
    }
  }
  form.addEventListener('submit', event => event.preventDefault());
  form.addEventListener('change', event => { if (event.target.name) calculate(); });
  form.addEventListener('reset', () => {
    required.clear(); excluded.clear(); emblems.length = 0;
    setMode('required');
    if (catalog) queueMicrotask(updateSelection);
  });
  function setMode(next) {
    mode = next;
    for (const button of form.querySelectorAll('[data-mode]')) button.setAttribute('aria-pressed', button.dataset.mode === mode);
    if (catalog) updatePicker();
  }
  for (const button of form.querySelectorAll('[data-mode]')) {
    button.addEventListener('click', () => setMode(button.dataset.mode));
  }
  find('hero-search').addEventListener('input', () => { if (catalog) updatePicker(); });
  async function load() {
    find('retry').hidden = true;
    try {
      const response = await fetch(catalogUrl);
      if (!response.ok) throw Error();
      catalog = await response.json();
      heroes = new Map(catalog.heroes.map(h => [h.id, h]));
      traits = new Map(catalog.traits.map(t => [t.id, t]));
      buildPicker();
      updateSelection();
    } catch {
      catalog = null;
      find('status').textContent = '弈子资料载入失败。';
      find('retry').hidden = false;
    }
  }
  find('retry').addEventListener('click', () => catalog ? calculate() : load());
  load();
})();
