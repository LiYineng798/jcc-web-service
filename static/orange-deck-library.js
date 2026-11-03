/* Home deck library: sibling of the lineup library, with its view kept in the URL
   (?library=decks&tab=…&portal=…&q=…&page=…) so links, refresh and history all work. */
(function () {
  'use strict';
  const D = window.JccOrangeDeck;
  const root = document.getElementById('deckLibrary');
  const lineupPanel = document.getElementById('lineupLibrary');
  if (!D || !root || !lineupPanel) return;
  const $ = (id) => document.getElementById(id);
  const els = { list: $('deckList'), tabs: $('deckTabs'), indicator: $('deckTabIndicator'), search: $('deckSearch'),
    portal: $('deckPortal'), pagination: $('deckPagination'), rule: $('deckRule'), status: $('deckStatus') };
  const TABS = ['latest', 'hot', 'featured', 'favorites', 'mine'];
  const PORTALS = [...els.portal.options].map((option) => option.value).filter(Boolean);
  const TAB_NAMES = { latest: '最新', hot: '热门', featured: '推荐', favorites: '我的收藏', mine: '我的卡组' };
  const STATUS = { draft: ['草稿', ''], hidden: ['已隐藏', 'is-danger'] };
  const state = { library: 'lineups', tab: 'latest', q: '', portal: '', page: 1, user: null, csrf: '', me: null,
    items: [], total: 0, totalPages: 1, controller: null, formations: new Map(), loadedKey: '' };

  function readUrl() {
    const params = new URLSearchParams(location.search);
    state.library = params.get('library') === 'decks' ? 'decks' : 'lineups';
    state.tab = TABS.includes(params.get('tab')) ? params.get('tab') : 'latest';
    state.q = (params.get('q') || '').trim().slice(0, 40);
    state.portal = PORTALS.includes(params.get('portal')) ? params.get('portal') : '';
    state.page = Math.max(1, Number.parseInt(params.get('page'), 10) || 1);
  }

  function writeUrl(push) {
    const params = new URLSearchParams(location.search);
    ['library', 'tab', 'q', 'portal', 'page'].forEach((key) => params.delete(key));
    if (state.library === 'decks') {
      params.set('library', 'decks');
      if (state.tab !== 'latest') params.set('tab', state.tab);
      if (state.q) params.set('q', state.q);
      if (state.portal) params.set('portal', state.portal);
      if (state.page > 1) params.set('page', String(state.page));
    }
    const url = `${location.pathname}${params.size ? `?${params}` : ''}`;
    if (url === `${location.pathname}${location.search}`) return;
    if (push) history.pushState({ jccDeck: true }, '', url);
    else history.replaceState(history.state, '', url);
  }

  function showLibrary(library) {
    state.library = library;
    lineupPanel.hidden = library === 'decks';
    root.hidden = library !== 'decks';
    document.body.dataset.homeLibrary = library;
    document.querySelectorAll('a[data-home-library]').forEach((link) => {
      if (link.dataset.homeLibrary === library) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    window.dispatchEvent(new CustomEvent('jcc:home-library', { detail: { library } }));
    if (library === 'decks') { syncControls(); load(); }
  }

  function syncControls() {
    els.search.value = state.q;
    els.portal.value = state.portal;
    els.tabs.querySelectorAll('[data-deck-tab]').forEach((tab) => {
      const active = tab.dataset.deckTab === state.tab;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    requestAnimationFrame(updateIndicator);
  }

  function updateIndicator() {
    const active = els.tabs.querySelector('.tab.active');
    if (!active || root.hidden) return;
    const tab = active.getBoundingClientRect(), list = els.tabs.getBoundingClientRect();
    els.tabs.style.setProperty('--active-tab-width', `${tab.width}px`);
    els.tabs.style.setProperty('--active-tab-left', `${tab.left - list.left + els.tabs.scrollLeft}px`);
  }

  async function ensureMe() {
    if (state.me) return state.me;
    state.me = D.api('/api/me').then((data) => { state.user = data.user; state.csrf = data.csrf_token; return data; })
      .catch(() => { state.me = null; return null; });
    return state.me;
  }

  async function load() {
    const key = JSON.stringify([state.tab, state.q, state.portal, state.page]);
    state.controller?.abort();
    const controller = new AbortController();
    state.controller = controller;
    await ensureMe();
    if (controller.signal.aborted) return;
    if (['favorites', 'mine'].includes(state.tab) && !state.user) {
      state.items = []; state.total = 0; state.totalPages = 1;
      render(key);
      return;
    }
    if (state.loadedKey !== key) els.list.innerHTML = '<div class="deck-skeleton"></div><div class="deck-skeleton"></div>';
    els.status.textContent = '正在加载卡组…';
    const params = new URLSearchParams({ tab: state.tab, page: String(state.page), page_size: '10' });
    if (state.q) params.set('q', state.q);
    if (state.portal) params.set('portal', state.portal);
    try {
      const data = await D.api(`/api/orange-decks?${params}`, { signal: controller.signal });
      if (state.controller !== controller) return;
      Object.assign(state, { items: data.items, total: data.total, totalPages: data.total_pages, page: data.page });
      els.rule.hidden = !data.ranking_rule && state.tab !== 'featured';
      els.rule.textContent = data.ranking_rule || (state.tab === 'featured' ? '推荐由管理员设置，按推荐时间排列。' : '');
      render(key);
    } catch (error) {
      if (error.name === 'AbortError' || state.controller !== controller) return;
      renderError(error);
    }
  }

  function button(label, action, extra = '') {
    return `<button type="button" class="deck-button" data-action="${action}" ${extra}>${label}</button>`;
  }

  function card(deck) {
    const badges = [
      deck.featured ? '<span class="deck-badge is-featured">推荐</span>' : '',
      deck.has_formation ? '<span class="deck-badge">含阵容</span>' : '',
      STATUS[deck.status] ? `<span class="deck-badge ${STATUS[deck.status][1]}">${STATUS[deck.status][0]}</span>` : '',
      deck.compat.missing_cards ? '<span class="deck-badge is-danger">含失效卡片</span>' : deck.compat.changed ? '<span class="deck-badge is-warn">资料已更新</span>' : '',
    ].join('');
    const over = deck.cards.every(Boolean) && !deck.fits;
    const actions = [
      deck.has_formation ? button('展开站位', 'formation', `aria-expanded="false" aria-controls="deck-formation-${deck.id}"`) : '',
      deck.status === 'published' ? button(deck.is_favorited ? `已收藏 ${deck.favorite_count}` : `收藏 ${deck.favorite_count}`, 'favorite', `aria-pressed="${deck.is_favorited}"`) : '',
      deck.can_share ? button('分享', 'share', 'title="复制卡组文本与详情链接"') : '',
      deck.can_edit ? `<a class="deck-button" href="/orange-decks/${deck.id}/edit">编辑</a>` : '',
      `<a class="deck-button" href="${D.esc(deck.detail_url)}">查看详情</a>`,
    ].join('');
    const author = deck.author.profile_url
      ? `<a class="deck-author" href="${D.esc(deck.author.profile_url)}"><span data-avatar></span><span>${D.esc(deck.author.nickname)}</span></a>`
      : `<span class="deck-author"><span data-avatar></span><span>${D.esc(deck.author.nickname)}</span></span>`;
    return `<article class="deck-card" data-deck-id="${deck.id}" aria-labelledby="deck-title-${deck.id}">
      <div class="deck-card-head"><h3 id="deck-title-${deck.id}"><a href="${D.esc(deck.detail_url)}">${D.esc(deck.name)}</a></h3><div class="deck-badges">${badges}</div></div>
      <p class="deck-meta"><span>推荐 <b>${D.esc(deck.portal.name)}</b></span><span class="${over ? 'is-over' : ''}">能量 <b>${deck.energy}</b> / ${deck.energy_limit}${over ? '（超限）' : ''}</span></p>
      <ul class="deck-thumbs" aria-label="三张时间卡片">${deck.cards.map(D.thumb).join('')}</ul>
      <p class="deck-note${deck.note ? '' : ' is-empty'}">${deck.note ? D.esc(deck.note) : '作者暂未填写搭配说明。'}</p>
      ${deck.status === 'hidden' && deck.hidden_reason ? `<p class="deck-issues" role="note">已被管理员隐藏：${D.esc(deck.hidden_reason)}</p>` : ''}
      <div class="deck-card-foot">${author}<div class="deck-actions">${actions}</div></div>
      <div class="deck-formation-slot" id="deck-formation-${deck.id}" hidden></div>
    </article>`;
  }

  function hydrate(node, deck) {
    const avatar = D.avatar(deck.author, 24, `deck-${deck.id}`);
    const slot = node.querySelector('[data-avatar]');
    if (avatar && slot) slot.replaceWith(avatar);
    else slot?.remove();
  }

  // The home page keeps manual scroll restoration; return to the same deck after back/forward.
  let restoreY = null;
  try {
    const type = performance.getEntriesByType('navigation')[0]?.type;
    if (['back_forward', 'reload'].includes(type) && Number.isFinite(history.state?.jccDeckScroll)) restoreY = history.state.jccDeckScroll;
  } catch { /* Restoration is optional. */ }
  window.addEventListener('pagehide', () => {
    if (state.library !== 'decks') return;
    try { history.replaceState({ ...(history.state || {}), jccDeckScroll: scrollY }, '', location.href); } catch { /* Optional. */ }
  });

  function render(key) {
    state.loadedKey = key;
    els.status.textContent = `${TAB_NAMES[state.tab]} · 共 ${state.total} 套卡组`;
    if (!state.items.length) {
      els.list.innerHTML = emptyState();
      els.pagination.replaceChildren();
      return;
    }
    els.list.innerHTML = state.items.map(card).join('');
    els.list.querySelectorAll('[data-deck-id]').forEach((node) => hydrate(node, state.items.find((deck) => String(deck.id) === node.dataset.deckId)));
    renderPagination();
    if (restoreY !== null) { const y = restoreY; restoreY = null; requestAnimationFrame(() => scrollTo({ top: y, behavior: 'instant' })); }
  }

  function emptyState() {
    const filtered = state.q || state.portal;
    let [title, text, actions] = ['还没有公开卡组', '发布第一套大橘大利卡组，把三张卡和传送门的搭配分享出来。', '<a class="deck-button is-primary" href="/orange-decks/new">发布卡组</a>'];
    if (['favorites', 'mine'].includes(state.tab) && !state.user) {
      [title, text, actions] = [state.tab === 'mine' ? '登录后查看我的卡组' : '登录后查看收藏', '收藏和发布的卡组会跟随账号保存。', '<a class="deck-button is-primary" href="/auth">登录 / 注册</a>'];
    } else if (filtered) {
      [title, text, actions] = ['没有找到匹配的卡组', `${state.q ? `“${D.esc(state.q)}”` : ''}按卡组名称和所含卡片名称搜索${state.portal ? '，并按推荐传送门筛选' : ''}。`, '<button type="button" class="deck-button" data-action="clear">清除搜索与筛选</button>'];
    } else if (state.tab === 'hot') {
      [title, text] = ['还没有被收藏的卡组', '热门只统计真实收藏，收藏后会出现在这里。'];
    } else if (state.tab === 'featured') {
      [title, text, actions] = ['暂无推荐卡组', '推荐由管理员挑选，可以先看看最新发布的卡组。', '<button type="button" class="deck-button" data-action="latest">查看最新</button>'];
    } else if (state.tab === 'favorites') {
      [title, text, actions] = ['还没有收藏卡组', '在卡组上点“收藏”，之后可以在这里找回。', '<button type="button" class="deck-button" data-action="latest">浏览卡组</button>'];
    } else if (state.tab === 'mine') {
      [title, text] = ['还没有你的卡组', '草稿和已发布的卡组都会出现在这里。'];
    }
    return `<div class="deck-empty"><h3>${title}</h3><p>${text}</p><div class="deck-actions">${actions}</div></div>`;
  }

  function renderError(error) {
    els.status.textContent = '卡组加载失败';
    els.pagination.replaceChildren();
    els.list.innerHTML = `<div class="deck-empty" role="alert"><h3>卡组加载失败</h3><p>${D.esc(error.message)}。搜索和筛选条件已保留。</p><div class="deck-actions"><button type="button" class="deck-button" data-action="retry">重新加载</button></div></div>`;
  }

  function renderPagination() {
    if (state.totalPages <= 1) { els.pagination.replaceChildren(); return; }
    els.pagination.innerHTML = `<button type="button" class="deck-button" data-page="${state.page - 1}" ${state.page <= 1 ? 'disabled' : ''}>上一页</button><span>第 ${state.page} / ${state.totalPages} 页</span><button type="button" class="deck-button" data-page="${state.page + 1}" ${state.page >= state.totalPages ? 'disabled' : ''}>下一页</button>`;
  }

  function change(next, push = true) {
    Object.assign(state, next);
    writeUrl(push);
    syncControls();
    load();
  }

  async function toggleFormation(control, deck) {
    const slot = document.getElementById(`deck-formation-${deck.id}`);
    const open = control.getAttribute('aria-expanded') !== 'true';
    control.setAttribute('aria-expanded', String(open));
    control.textContent = open ? '收起站位' : '展开站位';
    slot.hidden = !open;
    if (!open || state.formations.has(deck.id)) {
      if (open) slot.innerHTML = D.board(state.formations.get(deck.id));
      return;
    }
    slot.innerHTML = '<p>正在加载站位…</p>';
    try {
      const data = await D.api(`/api/orange-decks/${deck.id}/formation`);
      state.formations.set(deck.id, data.formation);
      if (control.getAttribute('aria-expanded') === 'true') slot.innerHTML = D.board(data.formation);
    } catch (error) {
      slot.innerHTML = `<p role="alert">站位加载失败：${D.esc(error.message)} <button type="button" class="deck-button is-quiet" data-action="formation-retry">重试</button></p>`;
    }
  }

  async function toggleFavorite(control, deck) {
    await ensureMe();
    if (!state.user) { D.notify('登录后可以收藏卡组', 'info'); return; }
    control.disabled = true;
    try {
      const data = await D.api(`/api/orange-decks/${deck.id}/favorite`, { method: deck.is_favorited ? 'DELETE' : 'POST', csrf: state.csrf });
      deck.is_favorited = data.favorited;
      deck.favorite_count = data.favorite_count;
      control.setAttribute('aria-pressed', String(data.favorited));
      control.textContent = `${data.favorited ? '已收藏' : '收藏'} ${data.favorite_count}`;
      D.notify(data.favorited ? '已收藏卡组' : '已取消收藏', 'success');
    } catch (error) {
      D.notify(error.message, 'error');
    } finally {
      control.disabled = false;
      control.focus({ preventScroll: true });
    }
  }

  els.list.addEventListener('click', (event) => {
    const target = event.target.closest('[data-action], [data-card-index]');
    if (!target) return;
    const node = target.closest('[data-deck-id]');
    const deck = node && state.items.find((item) => String(item.id) === node.dataset.deckId);
    if (target.dataset.cardIndex !== undefined && deck) { D.openCard(deck.cards[Number(target.dataset.cardIndex)], target); return; }
    const action = target.dataset.action;
    if (action === 'retry') load();
    else if (action === 'clear') change({ q: '', portal: '', page: 1 });
    else if (action === 'latest') change({ tab: 'latest', page: 1 });
    else if (action === 'formation' && deck) toggleFormation(target, deck);
    else if (action === 'formation-retry' && deck) {
      const opener = node.querySelector('[data-action="formation"]');
      opener.setAttribute('aria-expanded', 'false');
      toggleFormation(opener, deck);
    } else if (action === 'favorite' && deck) toggleFavorite(target, deck);
    else if (action === 'share' && deck) {
      D.copy(deck.share_text).then((ok) => D.notify(ok ? '已复制卡组文本与详情链接' : '复制失败，请打开详情页手动复制', ok ? 'success' : 'error'));
    }
  });
  els.pagination.addEventListener('click', (event) => {
    const target = event.target.closest('[data-page]');
    if (!target || target.disabled) return;
    change({ page: Number(target.dataset.page) });
    root.scrollIntoView({ block: 'start' });
  });
  els.tabs.addEventListener('click', (event) => {
    const tab = event.target.closest('[data-deck-tab]');
    if (tab && tab.dataset.deckTab !== state.tab) change({ tab: tab.dataset.deckTab, page: 1 });
  });
  els.tabs.addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    const tabs = [...els.tabs.querySelectorAll('[data-deck-tab]')];
    const next = tabs[(tabs.indexOf(document.activeElement) + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    next?.focus();
    next?.click();
  });
  els.portal.addEventListener('change', () => change({ portal: els.portal.value, page: 1 }));
  let timer, composing = false;
  const search = () => {
    clearTimeout(timer);
    timer = setTimeout(() => { if (!composing && els.search.value.trim() !== state.q) change({ q: els.search.value.trim().slice(0, 40), page: 1 }, false); }, 350);
  };
  els.search.addEventListener('compositionstart', () => { composing = true; });
  els.search.addEventListener('compositionend', () => { composing = false; search(); });
  els.search.addEventListener('input', search);
  els.search.addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.isComposing) { event.preventDefault(); clearTimeout(timer); change({ q: els.search.value.trim().slice(0, 40), page: 1 }, false); } });
  document.querySelectorAll('a[data-home-library]').forEach((link) => link.addEventListener('click', (event) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (link.dataset.homeLibrary === state.library) return;
    state.library = link.dataset.homeLibrary;
    writeUrl(true);
    showLibrary(state.library);
  }));
  window.addEventListener('popstate', () => {
    const before = state.library;
    readUrl();
    if (state.library !== before) showLibrary(state.library);
    else if (state.library === 'decks') { syncControls(); load(); }
  });
  window.addEventListener('resize', updateIndicator);
  readUrl();
  if (state.library === 'decks') showLibrary('decks');
})();
