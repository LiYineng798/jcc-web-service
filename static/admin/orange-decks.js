/* Admin deck library: feature published decks and hide or restore violating ones. Drafts stay private. */
(function (global) {
  const { el, button } = global.JccAdminCore;
  const FILTERS = [['all', '全部'], ['published', '公开中'], ['featured', '已推荐'], ['hidden', '已隐藏']];

  function create({ api, render, notify, workbenchPanel, pill, empty }) {
    let status = 'all', query = '', page = 1, data = null, loading = false, error = '', sequence = 0, timer = null;
    async function load() {
      const ticket = ++sequence;
      loading = true; error = ''; render();
      try {
        const params = new URLSearchParams({ status, page: String(page), page_size: '20' });
        if (query) params.set('q', query);
        const result = await api(`/api/admin/orange-decks?${params}`);
        if (ticket === sequence) data = result;
      } catch (err) {
        if (ticket === sequence) error = err.message || '卡组读取失败';
      } finally {
        if (ticket === sequence) { loading = false; render(); }
      }
    }
    async function act(deck, action, extra = {}) {
      await api(`/api/admin/orange-decks/${deck.id}/${action}`, { method: 'POST', body: JSON.stringify({ version: deck.version, ...extra }) });
      notify({ feature: '已设为推荐', unfeature: '已取消推荐', hide: '卡组已隐藏，详情、搜索和分享入口同步关闭', restore: '卡组已恢复公开' }[action]);
      // A refresh failure must not misreport a successful write.
      await load();
    }
    function card(deck) {
      const item = el('article', 'admin-card admin-card-tight');
      const head = el('div', 'admin-card-head');
      const title = el('a', '', deck.name);
      title.href = deck.detail_url; title.target = '_blank'; title.rel = 'noopener'; title.style.color = 'inherit';
      const heading = el('h3');
      heading.append(title);
      head.append(heading, pill(deck.status === 'hidden' ? '已隐藏' : deck.featured ? '公开 · 推荐' : '公开'));
      const cards = deck.cards.map((c) => (c ? `${c.name}（${c.status === 'missing' ? '失效' : c.energy}）` : '—')).join(' ＋ ');
      item.append(head,
        el('p', 'admin-meta', `${deck.author.nickname} · ${deck.portal.name} · 能量 ${deck.energy}/${deck.energy_limit} · 收藏 ${deck.favorite_count} · 更新 ${deck.updated_at}`),
        el('p', 'admin-reason', cards));
      if (deck.note) item.append(el('p', 'admin-meta', deck.note));
      if (deck.status === 'hidden' && deck.hidden_reason) item.append(el('p', 'admin-reason', `隐藏原因：${deck.hidden_reason}`));
      if (deck.compat.issues.length) item.append(el('p', 'admin-meta', `资料变化：${deck.compat.issues.join(' ')}`));
      const actions = el('div', 'card-actions');
      if (deck.status === 'published') {
        actions.append(button(deck.featured ? '取消推荐' : '设为推荐', () => act(deck, deck.featured ? 'unfeature' : 'feature'), `small-button${deck.featured ? ' is-active' : ''}`));
        actions.append(button('隐藏', async () => {
          const reason = prompt(`隐藏“${deck.name}”的原因（2–200 字，作者可见）：`);
          if (reason === null) return;
          await act(deck, 'hide', { reason });
        }, 'small-button danger-button'));
      } else {
        actions.append(button('恢复公开', () => act(deck, 'restore'), 'small-button'));
      }
      item.append(actions);
      return item;
    }
    function view() {
      const panel = workbenchPanel('卡组库', '大橘大利卡组：推荐与违规隐藏；草稿仅作者可见，不在此列出');
      const body = panel.querySelector('.admin-workspace-body');
      const controls = el('div', 'admin-segmented');
      FILTERS.forEach(([value, label]) => {
        const count = value === 'all' ? '' : ` ${data?.counts?.[value] ?? ''}`;
        controls.append(button(`${label}${count}`, async () => { if (status === value) return; status = value; page = 1; await load(); }, `small-button${status === value ? ' is-active' : ''}`));
      });
      const search = el('input');
      search.type = 'search'; search.placeholder = '搜索卡组名或作者'; search.value = query; search.maxLength = 40;
      search.setAttribute('aria-label', '搜索卡组名或作者');
      search.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => { query = search.value.trim(); page = 1; load().then(() => document.querySelector('[aria-label="搜索卡组名或作者"]')?.focus()); }, 350);
      });
      body.append(controls, search);
      const list = el('div', 'admin-list');
      if (error) list.append(empty(error));
      else if (loading && !data) list.append(empty('正在读取卡组…'));
      else if (!data?.items.length) list.append(empty(query ? '没有匹配的卡组' : '暂无卡组'));
      else data.items.forEach((deck) => list.append(card(deck)));
      body.append(list);
      if ((data?.total_pages || 1) > 1) {
        const pager = el('div', 'admin-pagination');
        pager.append(button('上一页', async () => { page -= 1; await load(); }, 'small-button', page <= 1),
          el('span', 'admin-meta', `第 ${page} / ${data.total_pages} 页`),
          button('下一页', async () => { page += 1; await load(); }, 'small-button', page >= data.total_pages));
        body.append(pager);
      }
      return panel;
    }
    return { load, view };
  }

  global.JccAdminOrangeDecks = { create };
})(window);
