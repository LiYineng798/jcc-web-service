(function () {
  const root = document.querySelector('#lineupNotificationRoot');
  if (!root) return;
  const toggle = root.querySelector('.ln-bell'), count = root.querySelector('.ln-count');
  const panel = root.querySelector('.ln-panel'), filters = root.querySelector('.ln-filters');
  const list = root.querySelector('.ln-list'), pagination = root.querySelector('.ln-pagination');
  const labels = { banned: '阵容已封禁', pending: '修改待审核', rejected: '修改被退回', approved: '修改审核通过', released: '封禁已解除' };
  let category = 'all';
  const categories = el('div','ln-filters'); categories.setAttribute('aria-label','通知分类'); filters.before(categories);
  let session = null, status = 'all', page = 1, requestId = 0, counts = {}, autoOpened = false;
  function el(tag, className = '', text = '') {
    const node = document.createElement(tag); node.className = className; node.textContent = text; return node;
  }
  function button(label, action, className) {
    const node = el('button', className, label); node.type = 'button';
    node.addEventListener('click', async () => {
      node.disabled = true;
      try { await action(); } catch (error) { window.jccNotify.show(error.message, { variant: 'error' }); }
      finally { node.disabled = false; }
    });
    return node;
  }
  function setCounts(value, totalUnread) {
    counts = value;
    const unread = totalUnread ?? counts.unread ?? 0;
    count.textContent = unread > 99 ? '99+' : String(unread); count.hidden = unread === 0;
    toggle.setAttribute('aria-label', unread ? `通知，${unread} 条未读` : '通知，无未读');
  }
  function renderFilters() {
    categories.replaceChildren();
    for (const [value,label] of [['all','全部消息'],['interaction','互动'],['feedback','反馈'],['moderation','审核']]) {
      const tab=button(label,async()=>{category=value;page=1;await load();},'ln-filter');tab.setAttribute('aria-pressed',String(category===value));categories.append(tab);
    }
    filters.replaceChildren();
    for (const [value, label] of [['all', '全部'], ['unread', '未读'], ['read', '已读']]) {
      const item = button(label, async () => { status = value; page = 1; await load(); }, 'ln-filter');
      item.setAttribute('aria-pressed', String(status === value));
      item.append(el('span', 'ln-filter-count', String(value === 'all' ? (counts.read || 0) + (counts.unread || 0) : counts[value] || 0)));
      filters.append(item);
    }
  }
  function render(data) {
    setCounts(data.counts, data.unread_total); renderFilters(); list.replaceChildren(); pagination.replaceChildren();
    for (const item of data.items) {
      const row = el('article', `ln-item${item.notice_state === 'unread' ? ' is-unread' : ''}`);
      row.dataset.lineupId = item.id;
      const link = el('a', 'ln-item-link'); link.href = item.url || '/me#lineup-notifications';
      if(item.category==='interaction')link.addEventListener('click',async event=>{if(event.ctrlKey||event.metaKey||event.shiftKey)return;event.preventDefault();if(item.notice_state==='unread')await session.api(`/api/me/notifications/${item.id}`,{method:'PUT',body:JSON.stringify({status:'read',revision:item.revision})}).catch(()=>{});location.href=link.href;});
      const symbol = el('span', `ln-symbol ln-${item.state}`, item.category==='interaction' ? '♡' : item.kind==='feedback' ? '↗' : item.state === 'approved' || item.state === 'released' ? '✓' : item.state === 'pending' ? '◷' : '!');
      symbol.setAttribute('aria-hidden', 'true');
      const content = el('div', 'ln-item-content');
      content.append(el('strong', 'ln-item-name', item.name), el('span', 'ln-item-status', item.category==='interaction' ? ({like:'收到点赞',favorite:'收到收藏',copy:'收到复制'}[item.kind]) : item.kind==='feedback' ? '反馈进度与回复' : labels[item.state] || '阵容处理结果'));
      const time = el('time', 'ln-time', item.updated_at); time.dateTime = item.updated_at.replace(' ', 'T'); content.append(time);
      const message = item.body;
      content.append(el('p', 'ln-preview', message));
      link.append(symbol, content); row.append(link);
      const next = item.notice_state === 'unread' ? 'read' : 'unread';
      const mark = button('', async () => {
        await session.api(`/api/me/notifications/${item.id}`, { method: 'PUT', body: JSON.stringify({ status: next, revision: item.revision }) });
        await load();
      }, 'ln-read-toggle');
      const label = next === 'read' ? '标记已读' : '标记未读'; mark.setAttribute('aria-label', label); mark.title = label;
      mark.append(el('span', 'ln-read-dot')); row.append(mark); list.append(row);
    }
    if (!data.items.length) list.append(el('p', 'ln-empty', status === 'unread' ? '没有未读通知' : status === 'read' ? '还没有已读通知' : '暂时没有通知'));
    if (data.total_pages > 1) {
      const prev = button('上一页', async () => { page -= 1; await load(); }, 'ln-page-button'); prev.disabled = page <= 1;
      const next = button('下一页', async () => { page += 1; await load(); }, 'ln-page-button'); next.disabled = page >= data.total_pages;
      pagination.append(prev, el('span', '', `${page} / ${data.total_pages}`), next);
    }
    pagination.hidden = data.total_pages <= 1;
  }
  async function load() {
    if (!session) return;
    const id = ++requestId;
    const focused = panel.contains(document.activeElement) ? document.activeElement : null;
    const focusedCategory = categories.contains(focused) ? category : null;
    const focusedFilter = filters.contains(focused) && focused?.closest('.ln-filter') ? status : null;
    const focusedRow = focused?.closest('.ln-item')?.dataset.lineupId;
    list.setAttribute('aria-busy', 'true');
    try {
      const data = await session.api(`/api/me/notifications?category=${category}&status=${status}&page=${page}&page_size=6`);
      if (id !== requestId) return;
      page = data.page; render(data);
      if (!panel.hidden && focused) {
        const target = focusedCategory ? [...categories.children].find(node => node.getAttribute('aria-pressed') === 'true') : focusedFilter ? [...filters.children].find(node => node.getAttribute('aria-pressed') === 'true')
          : focusedRow ? list.querySelector(`[data-lineup-id="${focusedRow}"] .ln-read-toggle`) : null;
        (target || filters.querySelector('button'))?.focus({ preventScroll: true });
      }
    } catch (error) {
      if (id !== requestId) return;
      setCounts({}); renderFilters(); pagination.replaceChildren();
      toggle.setAttribute('aria-label', '通知，暂时无法获取未读数量');
      list.replaceChildren(el('p', 'ln-empty', '通知加载失败'), button('重新加载', load, 'ln-retry'));
    } finally { if (id === requestId) list.setAttribute('aria-busy', 'false'); }
  }
  function position() {
    if (panel.hidden) return;
    const edge = root.parentElement.getBoundingClientRect(), rect = toggle.getBoundingClientRect();
    const viewport = window.visualViewport;
    const bottom = (viewport?.height || innerHeight) + (viewport?.offsetTop || 0);
    const top = Math.max(12, Math.min(rect.bottom + 12, bottom - 220));
    panel.style.top = `${top}px`;
    panel.style.right = `${Math.max(12, innerWidth - edge.right)}px`;
    panel.style.maxHeight = `${Math.max(160, bottom - top - 12)}px`;
  }
  function close(restoreFocus = false) {
    const wasOpen = !panel.hidden;
    panel.hidden = true; toggle.setAttribute('aria-expanded', 'false');
    if (restoreFocus) toggle.focus();
    const url = new URL(location.href);
    if (wasOpen && url.searchParams.has('notifications')) { url.searchParams.delete('notifications'); history.replaceState(null, '', url); }
  }
  async function open() {
    if (!session) return;
    session.onOpen(); panel.hidden = false; toggle.setAttribute('aria-expanded', 'true'); position();
    panel.querySelector('.ln-close').focus({ preventScroll: true });
    await load();
  }
  function setSession(value) {
    const changed = session?.user?.id !== value.user?.id;
    session = value.user ? value : null; root.hidden = !session;
    root.parentElement.classList.toggle('has-notifications', Boolean(session));
    if (!session) { ++requestId; close(); setCounts({}); list.replaceChildren(); return; }
    if (changed) { category='all'; status = 'all'; page = 1; load(); }
    if (!autoOpened && new URLSearchParams(location.search).get('notifications') === 'open') { autoOpened = true; open(); }
  }
  toggle.addEventListener('click', () => panel.hidden ? open() : close(true));
  panel.querySelector('.ln-close').addEventListener('click', () => close(true));
  document.addEventListener('pointerdown', event => { if (!root.contains(event.target)) close(); }, true);
  document.addEventListener('focusin', event => { if (!root.contains(event.target)) close(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && !panel.hidden) { close(true); event.preventDefault(); } });
  window.addEventListener('resize', position);
  window.visualViewport?.addEventListener('resize', position);
  window.addEventListener('scroll', () => { if (!panel.hidden) close(); }, { passive: true });
  window.addEventListener('focus', () => { if (session) load(); });
  window.addEventListener('pageshow', event => { if (event.persisted && session) load(); });
  window.JccLineupNotifications = { setSession, close };
})();
