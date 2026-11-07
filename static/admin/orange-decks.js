/* Admin deck library: feature published decks and hide or restore violating ones. Drafts stay private.
   One text row per deck: what an admin decides on (name, author, portal, traction). Status and problems appear only
   when they differ from the normal public state, so an ordinary deck stays a single quiet line. */
(function (global) {
  const { el, button } = global.JccAdminCore;
  const FILTERS = [['all', '全部'], ['published', '公开中'], ['featured', '已推荐'], ['hidden', '已隐藏']];
  const COLUMNS = ['卡组', '作者', '传送门 · 能量', '互动', '发布时间', '操作'];
  const ICONS = {
    like: 'M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10Z',
    favorite: 'M7 4h10a1 1 0 0 1 1 1v15l-6-4-6 4V5a1 1 0 0 1 1-1Z',
    copy: 'M9 9h10v11H9zM15 9V5H5v11h4',
    search: 'M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14Zm9 2-4-4',
  };
  const REASON_MIN = 2, REASON_MAX = 200;

  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', ICONS[name]);
    svg.append(path);
    return svg;
  }

  // Same year: "11-07 00:40"; older: the date alone. The full timestamp stays in the tooltip.
  function shortTime(value) {
    const [date = '', time = ''] = String(value || '').split(' ');
    if (!date) return '—';
    return date.startsWith(String(new Date().getFullYear())) ? `${date.slice(5)} ${time.slice(0, 5)}`.trim() : date;
  }

  function create({ api, render, notify, workbenchPanel, empty }) {
    let status = 'all', query = '', page = 1, data = null, loading = false, error = '', sequence = 0, timer = null;
    let hidingId = null, reasonDraft = '', actingId = null, focusReason = false;
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
      if (actingId) return;
      actingId = deck.id; render();
      try {
        await api(`/api/admin/orange-decks/${deck.id}/${action}`, { method: 'POST', body: JSON.stringify({ version: deck.version, ...extra }) });
      } catch (err) {
        // Keep the typed reason; the shared button handler reports the error.
        actingId = null; render();
        throw err;
      }
      actingId = null;
      hidingId = null; reasonDraft = '';
      notify({ feature: '已设为推荐', unfeature: '已取消推荐', hide: '卡组已隐藏，详情、搜索和分享入口同步关闭', restore: '卡组已恢复公开' }[action]);
      // A refresh failure must not misreport a successful write.
      await load();
    }

    // Public is the default and needs no badge.
    function stateLabel(deck) {
      if (deck.status === 'hidden') return [el('span', 'admin-deck-state is-hidden', '已隐藏')];
      return deck.featured ? [el('span', 'admin-deck-state is-featured', '推荐中')] : [];
    }

    function portal(deck) {
      const name = el('span', 'admin-deck-portal', deck.portal.name.replace(/传送门$/, ''));
      name.dataset.portal = deck.portal.id;
      name.title = deck.portal.name;
      const energy = el('span', `admin-deck-energy${deck.fits ? '' : ' is-over'}`, `${deck.energy}/${deck.energy_limit}`);
      energy.title = deck.fits ? `能量 ${deck.energy}，上限 ${deck.energy_limit}` : `能量 ${deck.energy} 超出${deck.portal.name}上限 ${deck.energy_limit}`;
      const wrap = el('span', 'admin-deck-portal-cell');
      wrap.append(name, energy);
      return wrap;
    }

    // Only what needs attention: why it is hidden, broken data, and the author's own words. Energy overflow shows in its column.
    function notes(deck) {
      const lines = [];
      const add = (text, tone, title = text) => { const line = el('p', `admin-deck-note ${tone}`, text); line.title = title; lines.push(line); };
      if (deck.status === 'hidden' && deck.hidden_reason) add(`隐藏原因：${deck.hidden_reason}`, 'is-danger');
      if (deck.compat.missing_cards) add(`含 ${deck.compat.missing_cards} 张失效卡片`, 'is-warning', deck.compat.issues.join(' ') || '');
      else if (deck.compat.issues.length) add(`资料已变化：${deck.compat.issues.join(' ')}`, 'is-warning');
      if (deck.note) add(deck.note, 'is-quiet');
      return lines;
    }

    function stats(deck) {
      const wrap = el('span', 'admin-deck-stats');
      [['like', deck.like_count, '点赞'], ['favorite', deck.favorite_count, '收藏'], ['copy', deck.copy_count, '有效复制']].forEach(([name, value, label]) => {
        const item = el('span', 'admin-deck-stat');
        item.title = `${label} ${value}`;
        item.setAttribute('aria-label', `${label} ${value}`);
        item.append(icon(name), el('span', '', Number(value || 0).toLocaleString('zh-CN')));
        wrap.append(item);
      });
      return wrap;
    }

    function cell(content, className, label) {
      const td = el('td', className);
      if (label) td.dataset.label = label;
      td.append(...[].concat(content));
      return td;
    }

    function row(deck) {
      const tr = el('tr', `admin-deck-row${hidingId === deck.id ? ' is-confirming' : ''}`);
      tr.dataset.deckId = deck.id;
      const title = el('div', 'admin-deck-title');
      const name = el('a', 'admin-deck-name', deck.name);
      name.href = deck.detail_url; name.target = '_blank'; name.rel = 'noopener';
      title.append(name, ...stateLabel(deck));
      const summary = el('div', 'admin-deck-summary');
      summary.append(title, ...notes(deck));
      const author = el(deck.author.profile_url ? 'a' : 'span', 'admin-deck-author', deck.author.nickname);
      author.title = deck.author.nickname;
      if (deck.author.profile_url) { author.href = deck.author.profile_url; author.target = '_blank'; author.rel = 'noopener'; }

      const time = el('time', 'admin-deck-time', shortTime(deck.published_at || deck.updated_at));
      time.dateTime = String(deck.published_at || deck.updated_at || '').replace(' ', 'T');
      time.title = [deck.published_at && `发布于 ${deck.published_at}`, `更新于 ${deck.updated_at}`].filter(Boolean).join('\n');

      const busy = actingId !== null;
      const actions = [];
      if (deck.status === 'published') {
        const feature = button(deck.featured ? '取消推荐' : '设为推荐', () => act(deck, deck.featured ? 'unfeature' : 'feature'),
          `small-button admin-deck-action${deck.featured ? ' is-active' : ''}`, busy);
        feature.setAttribute('aria-pressed', String(Boolean(deck.featured)));
        const hide = button('隐藏', () => { hidingId = hidingId === deck.id ? null : deck.id; reasonDraft = ''; focusReason = true; render(); },
          'small-button admin-deck-action danger-button', busy);
        hide.setAttribute('aria-expanded', String(hidingId === deck.id));
        hide.setAttribute('aria-controls', `admin-deck-hide-${deck.id}`);
        actions.push(feature, hide);
      } else {
        actions.push(button('恢复公开', () => act(deck, 'restore'), 'small-button admin-deck-action', busy));
      }
      tr.append(
        cell(summary, 'admin-deck-main'),
        cell(author, 'admin-deck-cell is-author', COLUMNS[1]),
        cell(portal(deck), 'admin-deck-cell is-portal', COLUMNS[2]),
        cell(stats(deck), 'admin-deck-cell is-stats', COLUMNS[3]),
        cell(time, 'admin-deck-cell is-time', COLUMNS[4]),
        cell(actions, 'admin-deck-actions'),
      );
      return tr;
    }

    // Inline confirmation replaces the browser prompt: the reason is visible to the author, so it is typed with care.
    function hideForm(deck) {
      const tr = el('tr', 'admin-deck-hide-row');
      const td = el('td');
      td.colSpan = COLUMNS.length;
      const form = el('form', 'admin-deck-hide');
      form.id = `admin-deck-hide-${deck.id}`;
      const label = el('label', 'admin-deck-hide-label', '隐藏原因');
      const hint = el('span', '', '作者可见，2–200 字；隐藏后同步取消推荐');
      label.htmlFor = `admin-deck-reason-${deck.id}`;
      const input = el('input');
      Object.assign(input, { id: `admin-deck-reason-${deck.id}`, type: 'text', maxLength: REASON_MAX, value: reasonDraft, placeholder: '例如：卡组名称含不当内容', autocomplete: 'off' });
      const counter = el('span', 'admin-deck-hide-count');
      const cancel = button('取消', () => { hidingId = null; reasonDraft = ''; render(); }, 'small-button');
      const confirm = button('确认隐藏', () => act(deck, 'hide', { reason: reasonDraft.trim() }), 'small-button danger-button is-solid');
      confirm.type = 'submit';
      const sync = () => {
        const length = reasonDraft.trim().length;
        counter.textContent = `${length} / ${REASON_MAX}`;
        confirm.disabled = actingId !== null || length < REASON_MIN || length > REASON_MAX;
      };
      input.addEventListener('input', () => { reasonDraft = input.value; sync(); });
      form.addEventListener('submit', (event) => { event.preventDefault(); if (!confirm.disabled) confirm.click(); });
      form.addEventListener('keydown', (event) => { if (event.key === 'Escape') { event.preventDefault(); cancel.click(); } });
      sync();
      const field = el('div', 'admin-deck-hide-field');
      field.append(input, counter);
      const heading = el('div', 'admin-deck-hide-heading');
      heading.append(label, hint);
      const buttons = el('div', 'admin-deck-hide-buttons');
      buttons.append(cancel, confirm);
      form.append(heading, field, buttons);
      td.append(form);
      tr.append(td);
      // Focus when the form opens, or keep it while typing through a re-render; never steal it otherwise.
      if (focusReason || document.activeElement?.id === input.id) {
        focusReason = false;
        queueMicrotask(() => {
          if (!input.isConnected) return;
          input.focus({ preventScroll: true });
          input.setSelectionRange(input.value.length, input.value.length);
        });
      }
      return tr;
    }

    function toolbar() {
      const bar = el('div', 'admin-deck-toolbar');
      const filters = el('div', 'admin-deck-filters');
      filters.setAttribute('role', 'group');
      filters.setAttribute('aria-label', '按状态筛选');
      const counts = data?.counts || {};
      const totals = { all: (counts.published || 0) + (counts.hidden || 0), published: counts.published || 0, featured: counts.featured || 0, hidden: counts.hidden || 0 };
      FILTERS.forEach(([value, label]) => {
        const control = button('', async () => { if (status === value) return; status = value; page = 1; hidingId = null; await load(); },
          `admin-deck-filter${status === value ? ' is-active' : ''}`);
        control.setAttribute('aria-pressed', String(status === value));
        control.append(el('span', '', label), el('span', 'admin-deck-filter-count', data ? String(totals[value]) : ''));
        filters.append(control);
      });
      const search = el('label', 'admin-deck-search');
      const input = el('input');
      Object.assign(input, { type: 'search', placeholder: '搜索卡组名或作者', value: query, maxLength: 40 });
      input.setAttribute('aria-label', '搜索卡组名或作者');
      input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          query = input.value.trim(); page = 1; hidingId = null;
          load().then(() => {
            const next = document.querySelector('.admin-deck-search input');
            if (next) { next.focus(); next.setSelectionRange(next.value.length, next.value.length); }
          });
        }, 350);
      });
      search.append(icon('search'), input);
      bar.append(filters, search);
      return bar;
    }

    function view() {
      const panel = workbenchPanel('卡组库', '推荐优质卡组，隐藏违规内容；草稿仅作者可见，不在此列出');
      const body = panel.querySelector('.admin-workspace-body');
      body.classList.add('admin-deck-workspace');
      body.append(toolbar());
      if (error) body.append(empty(error));
      else if (loading && !data) body.append(empty('正在读取卡组…'));
      else if (!data?.items.length) body.append(empty(query ? '没有匹配的卡组' : status === 'all' ? '暂无卡组' : '这个分类下暂无卡组'));
      else {
        const table = el('table', 'admin-deck-table');
        table.setAttribute('aria-busy', String(loading));
        const head = el('thead');
        const headRow = el('tr');
        COLUMNS.forEach((name) => headRow.append(el('th', '', name)));
        head.append(headRow);
        const rows = el('tbody');
        data.items.forEach((deck) => {
          rows.append(row(deck));
          if (hidingId === deck.id) rows.append(hideForm(deck));
        });
        table.append(head, rows);
        body.append(table);
      }
      if (data) {
        const footer = el('div', 'admin-deck-footer');
        footer.append(el('span', 'admin-meta', `共 ${data.total} 个卡组`));
        if ((data.total_pages || 1) > 1) {
          const pager = el('div', 'admin-pagination');
          pager.append(button('上一页', async () => { page -= 1; hidingId = null; await load(); }, 'small-button', page <= 1),
            el('span', 'admin-meta', `第 ${page} / ${data.total_pages} 页`),
            button('下一页', async () => { page += 1; hidingId = null; await load(); }, 'small-button', page >= data.total_pages));
          footer.append(pager);
        }
        body.append(footer);
      }
      return panel;
    }
    return { load, view };
  }

  global.JccAdminOrangeDecks = { create };
})(window);
