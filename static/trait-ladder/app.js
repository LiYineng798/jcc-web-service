(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    window.jccApplyThemeToggleState?.(theme, $('themeToggle'), $('themeIcon'), $('themeText'));
    try { localStorage.setItem('theme', theme); } catch (_) { /* Switching still works without storage. */ }
  }
  applyTheme(document.documentElement.dataset.theme || 'light');
  $('themeToggle')?.addEventListener('click', () => {
    applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  });
  const data = JSON.parse($('ladder-data').textContent);
  const esc = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('[data-view]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    $('calculator-view').hidden = button.dataset.view !== 'calculator';
    $('rewards-view').hidden = button.dataset.view !== 'rewards';
  }));
  if (!data) return;
  const traits = new Map(data.traits.map(t => [t.id, t]));
  const heroes = new Map(data.champions.map(c => [c.id, c]));
  let locked = new Set(), banned = new Set(), emblems = [], khazix = new Set(), mode = 'locked';
  let worker = null, generation = 0, results = [];
  const options = () => ({ population: Number($('population').value), locked: [...locked], banned: [...banned],
    emblems: [...emblems], khazix: [...khazix], lux: $('lux').value,
    minTank: Number($('min-tank').value), minCarry: Number($('min-carry').value) });
  function stop() {
    generation++; worker?.terminate(); worker = null;
    $('calculate').disabled = false; $('cancel').hidden = true;
  }
  function changed() {
    stop(); results = []; $('results').replaceChildren();
    $('status').textContent = '条件已更新，点击「开始计算」生成新的推荐。';
    $('result-count').textContent = '待重新计算';
    renderSummary();
  }
  function portrait(c, button = false) {
    const state = locked.has(c.id) ? 'locked' : banned.has(c.id) ? 'banned' : '';
    const title = `${c.name} · ${c.cost}费 · ${Object.keys(c.traits).map(id => traits.get(id)?.name).join(' / ')}${c.slots > 1 ? ' · 占2人口' : ''}${c.role ? ' · ' + (c.role === 'tank' ? '前排' : '输出') : ''}`;
    return `<${button ? 'button type="button"' : 'div'} class="champion cost-${c.cost} ${button ? state : ''}" ${button ? `data-hero="${esc(c.id)}" aria-pressed="${state ? 'true' : 'false'}" aria-label="${esc(title + (state === 'locked' ? '，已锁定' : state === 'banned' ? '，已禁用' : ''))}"` : ''} title="${esc(title)}"><span class="portrait"><img src="${esc(c.icon)}" alt="" loading="lazy"/>${button && state ? `<b class="selection-mark">${state === 'locked' ? '+' : '−'}</b>` : ''}<small>${c.cost}</small></span><span class="champion-name">${esc(c.name)}</span></${button ? 'button' : 'div'}>`;
  }
  // Keep image-bearing nodes mounted: selection must not restart image loading.
  function element(html) {
    const template = document.createElement('template');
    template.innerHTML = html;
    return template.content.firstElementChild;
  }
  const poolNodes = new Map(data.champions.map(c => [c.id, element(portrait(c, true))]));
  const poolEmpty = element('<p class="pool-empty" hidden>没有匹配的弈子，试试其他名称或费用。</p>');
  $('champion-pool').append(...poolNodes.values(), poolEmpty);
  const selectedNodes = new Map();
  const clearSelected = element('<button type="button" class="clear-selected" data-clear-selected aria-label="清空已选弈子" title="清空已选弈子"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/></svg><span>清空</span></button>');
  const selectionEmpty = element('<p class="selection-empty">点击上方弈子，将你想保留的核心放在这里。</p>');
  $('selected-summary').append(clearSelected, selectionEmpty);
  function renderPool() {
    const search = $('search').value.trim().toLowerCase(), cost = Number($('cost').value);
    let visible = 0;
    data.champions.forEach(c => {
      const node = poolNodes.get(c.id);
      const matches = (!cost || c.cost === cost) && [c.name, ...c.aliases, ...Object.keys(c.traits).map(id => traits.get(id)?.name || ''), ...(c.khazix ? ['螳螂'] : [])].join(' ').toLowerCase().includes(search);
      node.hidden = !matches;
      if (matches) visible++;
      const state = locked.has(c.id) ? 'locked' : banned.has(c.id) ? 'banned' : '';
      node.classList.toggle('locked', state === 'locked');
      node.classList.toggle('banned', state === 'banned');
      node.setAttribute('aria-pressed', String(Boolean(state)));
      node.setAttribute('aria-label', node.title + (state === 'locked' ? '，已锁定' : state === 'banned' ? '，已禁用' : ''));
      let mark = node.querySelector('.selection-mark');
      if (state) {
        if (!mark) { mark = element('<b class="selection-mark"></b>'); node.querySelector('.portrait').append(mark); }
        const symbol = state === 'locked' ? '+' : '−';
        if (mark.textContent !== symbol) mark.textContent = symbol;
      } else { mark?.remove(); }
    });
    poolEmpty.hidden = visible > 0;
  }
  function renderSummary() {
    $('pool-summary').textContent = `必选 ${locked.size} · 禁用 ${banned.size}`;
    $('selected-count').textContent = `${locked.size} 位 · ${[...locked].reduce((n,id)=>n+heroes.get(id).slots,0)} 人口`;
    for (const [id, node] of selectedNodes) {
      if (!locked.has(id)) { node.remove(); selectedNodes.delete(id); }
    }
    for (const id of locked) {
      if (selectedNodes.has(id)) continue;
      const hero = heroes.get(id);
      const node = element(`<button class="selected-hero cost-${hero.cost}" type="button" data-remove="${esc(id)}" aria-label="移除${esc(hero.name)}" title="点击移除${esc(hero.name)}"><img src="${esc(hero.icon)}" alt=""/><span>${esc(hero.name)}</span><b aria-hidden="true">×</b></button>`);
      selectedNodes.set(id, node);
      $('selected-summary').insertBefore(node, clearSelected);
    }
    clearSelected.hidden = !locked.size;
    selectionEmpty.hidden = Boolean(locked.size);
    $('banned-summary').innerHTML = [...banned].map(id => `<button class="banned-chip" type="button" data-remove="${esc(id)}" aria-label="取消禁用${esc(heroes.get(id).name)}">禁用 ${esc(heroes.get(id).name)} <span aria-hidden="true">×</span></button>`).join('');
    $('emblem-selected').innerHTML = [...new Set(emblems)].map(id => `<button type="button" data-remove-emblem="${esc(id)}">${esc(traits.get(id).name)} <b>×${emblems.filter(t => t === id).length}</b> −<span class="sr-only">移除一枚</span></button>`).join('') || '<p class="setting-help">暂无转职。每枚纹章都会给出可用的携带者。</p>';
    document.querySelectorAll('[data-emblem]').forEach(b => {
      const n = emblems.filter(id => id === b.dataset.emblem).length;
      b.setAttribute('aria-label', `添加${traits.get(b.dataset.emblem).name}纹章，已选${n}枚`);
      b.querySelector('b').textContent = n || '';
      b.classList.toggle('is-selected', n > 0);
    });
  }
  function removeHero(id) {
    locked.delete(id); banned.delete(id);
    if (heroes.get(id).lux) $('lux').value = '';
    if (heroes.get(id).khazix) { khazix.clear(); renderKhazix(); }
  }
  $('champion-pool').addEventListener('click', e => {
    const b = e.target.closest('[data-hero]'); if (!b) return;
    const id = b.dataset.hero, selected = (mode === 'locked' ? locked : banned).has(id);
    removeHero(id);
    if (!selected) (mode === 'locked' ? locked : banned).add(id);
    changed(); renderPool();
    $('champion-pool').querySelector(`[data-hero="${id}"]`)?.focus({ preventScroll: true });
  });
  function removeSelected(e) {
    if (e.target.closest('[data-clear-selected]')) {
      [...locked].forEach(removeHero); changed(); renderPool(); return;
    }
    const b = e.target.closest('[data-remove]');
    if (b) { removeHero(b.dataset.remove); changed(); renderPool(); }
  }
  $('selected-summary').addEventListener('click', removeSelected);
  $('banned-summary').addEventListener('click', removeSelected);
  document.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => {
    mode = b.dataset.mode; document.querySelectorAll('[data-mode]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  }));
  $('search').addEventListener('input', renderPool); $('cost').addEventListener('change', renderPool);
  $('emblem-pool').innerHTML = data.emblems.map(e => `<button type="button" data-emblem="${esc(e.trait)}" title="${esc(e.name)}"><img src="${esc(e.icon)}" alt="" loading="lazy"/><span>${esc(traits.get(e.trait).name)}</span><b></b></button>`).join('');
  $('emblem-pool').addEventListener('click', e => {
    const b = e.target.closest('[data-emblem]'); if (!b) return;
    if (emblems.length >= 39) { $('status').textContent = '最多选择 39 枚纹章。'; return; }
    emblems.push(b.dataset.emblem); changed();
  });
  $('emblem-selected').addEventListener('click', e => { const b = e.target.closest('[data-remove-emblem]'); if (b) { emblems.splice(emblems.lastIndexOf(b.dataset.removeEmblem), 1); changed(); } });
  function renderKhazix() {
    $('khazix-choices').innerHTML = data.khazixChoices.map(id => `<button type="button" data-khazix="${esc(id)}" aria-pressed="${khazix.has(id)}">${esc(traits.get(id).name)}</button>`).join('');
  }
  $('khazix-choices').addEventListener('click', e => {
    const b = e.target.closest('[data-khazix]'); if (!b) return;
    const id = b.dataset.khazix; khazix.has(id) ? khazix.delete(id) : khazix.add(id);
    if (khazix.size) { const hero = data.champions.find(c => c.khazix); locked.add(hero.id); banned.delete(hero.id); }
    changed(); renderKhazix(); renderPool();
    $('khazix-choices').querySelector(`[data-khazix="${id}"]`)?.focus({ preventScroll: true });
  });
  data.luxChoices.forEach(c => $('lux').add(new Option(traits.get(c.id).name + ' ×2', c.id)));
  $('lux').addEventListener('change', () => {
    if ($('lux').value) { const c = data.champions.find(c => c.lux); locked.add(c.id); banned.delete(c.id); }
    changed(); renderPool();
  });
  ['population', 'min-tank', 'min-carry'].forEach(id => $(id).addEventListener('change', changed));
  $('population').addEventListener('input', changed);
  $('pop-minus').onclick = () => { $('population').value = Math.max(2, Number($('population').value) - 1); changed(); };
  $('pop-plus').onclick = () => { $('population').value = Math.min(13, Number($('population').value) + 1); changed(); };
  $('reset').onclick = () => {
    locked.clear(); banned.clear(); emblems = []; khazix.clear(); $('lux').value = ''; $('population').value = 9;
    $('min-tank').value = $('min-carry').value = '0'; $('search').value = $('cost').value = '';
    changed(); renderPool(); renderKhazix();
  };
  $('cancel').onclick = () => { stop(); $('status').textContent = '已取消搜索，可调整条件后重新计算。'; $('result-count').textContent = '已取消'; };
  function renderResults(list) {
    results = list;
    $('results').innerHTML = list.length ? list.map((r, i) => {
      const names = r.ids.map(id => heroes.get(id)).sort((a, b) => a.cost - b.cost || a.id.localeCompare(b.id));
      const active = r.rows.filter(t => t.active && !t.unique);
      const inactive = r.rows.filter(t => !t.active && !t.unique);
      const special = r.rows.filter(t => t.active && t.unique);
      const chips = rows => rows.map(t => `<span class="trait-chip ${t.active ? 'active' : ''}" title="${esc(traits.get(t.id).name)}：${t.count}/${t.threshold}"><img src="${esc(traits.get(t.id).icon)}" alt=""/>${esc(traits.get(t.id).name)}<b>${t.count}${t.active ? '' : '/' + t.threshold}</b></span>`).join('');
      return `<article class="result-card"><header><span class="rank">${String(i + 1).padStart(2, '0')}</span><span class="score-badge"><strong>${r.active}</strong> 有效羁绊</span><span class="team-meta">${r.population} 人口 · ${r.cost} 金币</span></header><div class="team-line">${names.map(c => portrait(c)).join('')}</div><div class="trait-line">${chips(active)}</div>${r.assignments.length ? `<div class="assignment"><span>纹章分配</span>${r.assignments.map(a => `<span>${esc(traits.get(a.trait).name)} → <b>${esc(heroes.get(a.hero).name)}</b></span>`).join('')}</div>` : ''}${$('lux').value && names.some(c => c.lux) ? `<p class="special-note">拉克丝 · ${esc(traits.get($('lux').value).name)}贡献 2</p>` : ''}${khazix.size && names.some(c => c.khazix) ? `<p class="special-note">螳螂进化 · ${[...khazix].map(id => esc(traits.get(id).name)).join(' / ')}</p>` : ''}<details class="trait-details"><summary>查看未激活与单档羁绊</summary><div class="trait-line">${chips(inactive) || '<span>无未激活羁绊</span>'}</div>${special.length ? `<p>单档 / 独有羁绊（不计入天梯）</p><div class="trait-line">${chips(special)}</div>` : ''}</details><footer><span>达到 ${r.active} 羁绊档</span><button type="button" data-reward="${Math.min(14, Math.max(2, r.active))}">查看阶段奖励 ↗</button></footer></article>`;
    }).join('') : '<div class="empty-result"><h3>本次搜索未找到满足条件的阵容</h3><p>试试增加人口、减少必选或转职，或放宽高费核心筛选。</p></div>';
  }
  $('calculate').onclick = () => {
    stop(); results = []; $('results').replaceChildren(); $('calculate').disabled = true; $('cancel').hidden = false;
    $('result-count').textContent = '搜索中'; $('status').textContent = '正在组合弈子并核对羁绊…';
    const token = generation, start = performance.now();
    try {
      worker = new Worker($('ladder').dataset.worker);
      worker.onmessage = ({ data: message }) => {
        if (token !== generation) return;
        if (message.progress) { $('status').textContent = `正在搜索 · 已比较 ${message.progress.visited.toLocaleString()} 个组合`; return; }
        stop();
        if (message.error) { $('status').textContent = message.error; $('result-count').textContent = '请调整条件'; return; }
        renderResults(message.result.results);
        $('result-count').textContent = `${results.length} 个方案`;
        $('status').textContent = `已比较 ${message.result.visited.toLocaleString()} 个组合 · 用时 ${((performance.now() - start) / 1000).toFixed(1)} 秒。有限候选搜索，不保证全局最优。`;
      };
      worker.onerror = () => { if (token !== generation) return; stop(); $('status').textContent = '计算模块加载失败，请刷新页面后重试。'; $('result-count').textContent = '加载失败'; };
      worker.postMessage({ data, options: options() });
    } catch (_) { stop(); $('status').textContent = '浏览器未能启动计算，请使用支持 Web Worker 的浏览器重试。'; $('result-count').textContent = '启动失败'; }
  };
  $('results').addEventListener('click', e => {
    const reward = e.target.closest('[data-reward]');
    if (reward) { document.querySelector('[data-view="rewards"]').click(); const card = $('reward-' + reward.dataset.reward); card.scrollIntoView({ block: 'center' }); card.classList.add('highlight'); setTimeout(() => card.classList.remove('highlight'), 1800); }

  });
  window.addEventListener('pagehide', stop);
  renderPool(); renderKhazix(); renderSummary();
})();
