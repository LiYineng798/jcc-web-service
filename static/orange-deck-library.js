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
    portalToggle: $('deckPortalToggle'), portalMenu: $('deckPortalMenu'), portalText: $('deckPortalText'), count: $('deckCount'),
    pagination: $('deckPagination'), rule: $('deckRule'), status: $('deckStatus') };
  const TABS = ['latest', 'hot', 'featured', 'favorites', 'mine'];
  const PORTAL_NAMES = Object.fromEntries([...els.portalMenu.querySelectorAll('button[data-portal]')].map((item) => [item.dataset.portal, item.dataset.name]));
  const PORTALS = Object.keys(PORTAL_NAMES).filter(Boolean);
  const TAB_NAMES = { latest: '最新', hot: '热门', featured: '推荐', favorites: '我的收藏', mine: '我的卡组' };
  const STATUS = { draft: ['草稿', ''], hidden: ['已隐藏', 'is-danger'] };
  const state = { library: 'lineups', tab: 'latest', q: '', portal: '', page: 1, user: null, csrf: '', me: null,
    items: [], total: 0, totalPages: 1, controller: null, loadedKey: '' };

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
    els.portalText.textContent = PORTAL_NAMES[state.portal] || '全部传送门';
    els.portalToggle.classList.toggle('deck-portal', Boolean(state.portal));
    if (state.portal) els.portalToggle.dataset.portal = state.portal; else delete els.portalToggle.dataset.portal;
    els.portalMenu.querySelectorAll('button[data-portal]').forEach((item) => {
      item.classList.toggle('is-active', item.dataset.portal === state.portal);
      item.setAttribute('aria-checked', String(item.dataset.portal === state.portal));
    });
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
    els.count.textContent = '正在加载卡组…';
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

  // Actions share the lineup card markup so icons, focus and avatar reactions stay consistent.
  function action(label, icon, name, extra = '', count = null) {
    return `<button type="button" class="small-button home-card-action" data-action="${name}" data-card-action="${icon}" ${extra}><span class="home-card-icon" data-card-icon="${icon}" aria-hidden="true"></span><span class="home-card-action-label">${label}</span>${count === null ? '' : `<span class="home-card-number">${Number(count).toLocaleString('zh-CN')}</span>`}</button>`;
  }

  function card(deck) {
    const badges = [
      deck.featured ? '<span class="deck-badge is-featured">推荐</span>' : '',
      STATUS[deck.status] ? `<span class="deck-badge ${STATUS[deck.status][1]}">${STATUS[deck.status][0]}</span>` : '',
      deck.compat.missing_cards ? '<span class="deck-badge is-danger">含失效卡片</span>' : deck.compat.changed ? '<span class="deck-badge is-warn">资料已更新</span>' : '',
    ].join('');
    const over = !deck.compat.missing_cards && deck.cards.every(Boolean) && !deck.fits;
    const published = deck.status === 'published';
    const social = published ? [
      action(deck.is_liked_today ? '已赞' : '点赞', 'heart', 'like', `aria-pressed="${deck.is_liked_today}" title="${deck.is_liked_today ? '今日已赞' : '点赞卡组'}"`, deck.like_count),
      action(deck.is_favorited ? '已收藏' : '收藏', 'bookmark', 'favorite', `aria-pressed="${deck.is_favorited}" title="${deck.is_favorited ? '取消收藏' : '收藏卡组'}"`, deck.favorite_count),
      action('复制', 'copy', 'copy-plan', deck.plan_code ? 'title="复制方案码"' : 'disabled title="暂未提供方案码"', deck.copy_count || 0),
    ].join('') : '';
    const utilities = [
      deck.can_edit ? action('编辑', 'pencil', 'edit', '', null).replace('small-button home-card-action', 'small-button home-card-action home-card-quiet') : '',
      action('查看', 'arrow-up-right', 'open').replace('small-button home-card-action', 'small-button home-card-action home-card-detail'),
    ].join('');
    const author = `<span data-avatar></span><span class="home-card-author-name">${D.esc(deck.author.nickname)}</span>`;
    const date = (deck.published_at || deck.updated_at || '').split(' ')[0];
    return `<article class="lineup-card home-lineup-card deck-card" data-deck-id="${deck.id}" data-lineup-key="deck-${deck.id}" aria-labelledby="deck-title-${deck.id}">
      <header class="home-card-heading"><h3 class="lineup-title" id="deck-title-${deck.id}"><a href="${D.esc(deck.detail_url)}">${D.esc(deck.name)}</a></h3><span class="deck-badges">${badges}</span></header>
      <div class="home-card-byline lineup-byline">${deck.author.profile_url ? `<a class="author-link" href="${D.esc(deck.author.profile_url)}">${author}</a>` : `<span class="author-link">${author}</span>`}<time class="home-card-updated">${published ? '发布于' : '更新于'} ${D.esc(date)}</time></div>
      <div class="deck-card-body">
        <div class="deck-card-portal"><span class="deck-portal" data-portal="${D.esc(deck.portal.id)}">${D.esc(deck.portal.name)}</span><span class="deck-energy-chip${over ? ' is-over' : ''}">能量 <b>${deck.energy}</b> / ${deck.energy_limit}${over ? ' · 超限' : ''}</span></div>
        <ul class="deck-thumbs" aria-label="三张时间卡片">${deck.cards.map(D.thumb).join('')}</ul>
      </div>
      <footer class="home-card-footer"><div class="home-card-social">${social}</div><div class="home-card-utilities">${utilities}</div></footer>
    </article>`;
  }

  function hydrate(node, deck) {
    const avatar = D.avatar(deck.author, 28, `deck-${deck.id}`);
    const slot = node.querySelector('[data-avatar]');
    if (avatar && slot) slot.replaceWith(avatar);
    else slot?.remove();
  }

  function feedback(deck, kind) {
    const avatar = els.list.querySelector(`[data-deck-id="${deck.id}"] .user-avatar`);
    try { if (avatar) window.jccAvatar?.feedback?.(avatar, kind); } catch { /* Decorative only. */ }
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
    els.count.textContent = `当前展示 ${state.total} 套卡组`;
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
    let [title, text, actions] = ['还没有公开卡组', '发布第一套大橘大利卡组，把三张卡和传送门的搭配分享出来。', '<a class="deck-button is-primary" href="/lineup/new?type=deck">发布卡组</a>'];
    if (['favorites', 'mine'].includes(state.tab) && !state.user) {
      [title, text, actions] = [state.tab === 'mine' ? '登录后查看我的卡组' : '登录后查看收藏', '收藏和发布的卡组会跟随账号保存。', '<a class="deck-button is-primary" href="/auth">登录 / 注册</a>'];
    } else if (filtered) {
      [title, text, actions] = ['没有找到匹配的卡组', `${state.q ? `“${D.esc(state.q)}”` : ''}按卡组名称和所含卡片名称搜索${state.portal ? '，并按推荐传送门筛选' : ''}。`, '<button type="button" class="deck-button" data-action="clear">清除搜索与筛选</button>'];
    } else if (state.tab === 'hot') {
      [title, text] = ['还没有热门卡组', '热门只统计真实的点赞与收藏，有互动的卡组会出现在这里。'];
    } else if (state.tab === 'featured') {
      [title, text, actions] = ['暂无推荐卡组', '推荐由管理员挑选，可以先看看最新发布的卡组。', '<button type="button" class="deck-button" data-action="latest">查看最新</button>'];
    } else if (state.tab === 'favorites') {
      [title, text, actions] = ['还没有收藏卡组', '在卡组上点“收藏”，之后可以在这里找回。', '<button type="button" class="deck-button" data-action="latest">浏览卡组</button>'];
    } else if (state.tab === 'mine') {
      [title, text, actions] = ['还没有你的卡组', '草稿和已发布的卡组都会出现在这里。', '<a class="deck-button is-primary" href="/lineup/new?type=deck">发布卡组</a>'];
    }
    return `<div class="deck-empty"><h3>${title}</h3><p>${text}</p><div class="deck-actions">${actions}</div></div>`;
  }

  function renderError(error) {
    els.status.textContent = '卡组加载失败';
    els.count.textContent = '加载失败';
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

  async function interact(control, deck, kind) {
    await ensureMe();
    if (!state.user) { D.notify(kind === 'like' ? '登录后可以点赞卡组' : '登录后可以收藏卡组', 'info'); return; }
    if (kind === 'like' && deck.is_liked_today) { D.notify('今天已经点赞过这套卡组', 'info'); return; }
    control.disabled = true;
    try {
      if (kind === 'like') {
        const data = await D.api(`/api/orange-decks/${deck.id}/like`, { method: 'POST', csrf: state.csrf });
        Object.assign(deck, { is_liked_today: true, like_count: data.like_count });
        feedback(deck, 'like');
      } else {
        const data = await D.api(`/api/orange-decks/${deck.id}/favorite`, { method: deck.is_favorited ? 'DELETE' : 'POST', csrf: state.csrf });
        Object.assign(deck, { is_favorited: data.favorited, favorite_count: data.favorite_count });
        if (data.favorited) feedback(deck, 'favorite');
      }
      // Replace only this card's buttons so focus stays on the action that was used.
      const node = els.list.querySelector(`[data-deck-id="${deck.id}"]`);
      const fresh = document.createElement('div');
      fresh.innerHTML = card(deck);
      node.querySelector('.home-card-social').replaceWith(fresh.querySelector('.home-card-social'));
      node.querySelector(`[data-action="${kind}"]`)?.focus({ preventScroll: true });
    } catch (error) {
      D.notify(error.message, 'error');
      control.disabled = false;
    }
  }

  els.list.addEventListener('click', (event) => {
    const target = event.target.closest('[data-action], [data-card-index]');
    if (!target) return;
    const node = target.closest('[data-deck-id]');
    const deck = node && state.items.find((item) => String(item.id) === node.dataset.deckId);
    if (target.dataset.cardIndex !== undefined && deck) {
      if (target.disabled) return;
      const cardId = deck.cards[Number(target.dataset.cardIndex)]?.id;
      target.disabled = true;
      D.api(`/api/orange-decks/${deck.id}`).then((fresh) => {
        if (!target.isConnected) return;
        const current = fresh.cards.find(card => card?.id === cardId);
        if (current) D.openCard(current, target);
        else D.notify('作者已调整这张卡片，请刷新卡组列表', 'info');
      }).catch(error => D.notify(error.message, 'error')).finally(() => { target.disabled = false; });
      return;
    }
    const action = target.dataset.action;
    if (action === 'retry') load();
    else if (action === 'clear') change({ q: '', portal: '', page: 1 });
    else if (action === 'latest') change({ tab: 'latest', page: 1 });
    else if ((action === 'like' || action === 'favorite') && deck) interact(target, deck, action);
    else if (action === 'edit' && deck) location.href = `/orange-decks/${deck.id}/edit`;
    else if (action === 'open' && deck) location.href = deck.detail_url;
    else if (action === 'copy-plan' && deck) {
      target.disabled = true;
      D.copy(deck.plan_code).then(async (ok) => {
        D.notify(ok ? '方案码已复制' : '复制失败，请到详情页手动复制', ok ? 'success' : 'error');
        if (ok) {
          feedback(deck, 'copy'); target.querySelector('.home-card-action-label').textContent = '已复制';
          try {
            const data = await D.recordCopy(deck.id, state.csrf);
            deck.copy_count = data.copy_count;
            target.querySelector('.home-card-number').textContent = Number(data.copy_count).toLocaleString('zh-CN');
          } catch { D.notify('方案码已复制，但次数未同步，请稍后刷新', 'info'); }
        }
      }).finally(() => { target.disabled = false; });
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
  // Same dropdown as the lineup season filter.
  const closePortalMenu = () => {
    els.portalMenu.classList.add('hidden');
    els.portalToggle.classList.remove('is-open');
    els.portalToggle.setAttribute('aria-expanded', 'false');
  };
  els.portalToggle.addEventListener('click', (event) => {
    event.stopPropagation();
    const open = els.portalMenu.classList.contains('hidden');
    els.portalMenu.classList.toggle('hidden', !open);
    els.portalToggle.classList.toggle('is-open', open);
    els.portalToggle.setAttribute('aria-expanded', String(open));
    if (open) (els.portalMenu.querySelector('button.is-active') || els.portalMenu.querySelector('button[data-portal]'))?.focus();
  });
  els.portalMenu.addEventListener('click', (event) => {
    const item = event.target.closest('button[data-portal]');
    if (!item) return;
    closePortalMenu();
    els.portalToggle.focus();
    if (item.dataset.portal !== state.portal) change({ portal: item.dataset.portal, page: 1 });
  });
  els.portalMenu.addEventListener('keydown', (event) => {
    const items = [...els.portalMenu.querySelectorAll('button[data-portal]')];
    const index = items.indexOf(document.activeElement);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      items[(index + (event.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length].focus();
    }
  });
  document.addEventListener('click', (event) => { if (!event.target.closest('#deckPortalWrap')) closePortalMenu(); });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !els.portalMenu.classList.contains('hidden')) { closePortalMenu(); els.portalToggle.focus(); }
  });
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
