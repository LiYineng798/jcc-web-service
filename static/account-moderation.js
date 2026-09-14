(function () {
  const { el, button, badge, openRecord } = window.JccLineupModeration;
  function mount(root, csrfToken) {
    let status = 'active', page = 1, sequence = 0;
    const section = el('section', 'account-section'); section.id = 'lineup-notifications'; root.append(section);
    async function api(url, options = {}) {
      const response = await fetch(url, { ...options, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken } });
      const data = await response.json(); if (!response.ok) throw new Error(data.error || '操作失败'); return data;
    }
    async function load() {
      const requestId = ++sequence;
      const data = await api(`/api/me/lineup-notifications?status=${status}&page=${page}&page_size=6`);
      if (requestId !== sequence) return;
      page = data.page; section.replaceChildren();
      const head = el('div', 'account-section-head'); const heading = el('div');
      heading.append(el('p', 'section-kicker', 'Lineup Updates'));
      const title = el('div', 'lm-notice-heading'); title.append(el('h3', '', '阵容处理通知'));
      if (data.counts.unread) title.append(el('span', 'lm-unread-label', `${data.counts.unread} 条未读`));
      heading.append(title, el('p', 'account-subtitle', '查看封禁原因、修改重审和审核结果。归档只收起通知，不改变阵容状态。'));
      head.append(heading); section.append(head);
      const tabs = el('div', 'lm-tabs'); tabs.setAttribute('aria-label', '通知状态筛选');
      for (const [value, label] of [['active', '未归档'], ['unread', '未读'], ['read', '已读'], ['archived', '已归档'], ['all', '全部']]) {
        const item = button(label, async () => { status = value; page = 1; await load(); }, `lm-tab${status === value ? ' is-active' : ''}`);
        item.setAttribute('aria-pressed', String(value === status)); tabs.append(item);
      }
      section.append(tabs);
      if (!data.items.length) section.append(el('p', 'account-empty', '这里暂时没有处理通知。'));
      const list = el('div', 'account-list');
      for (const item of data.items) {
        const card = el('article', `lm-notification${item.notice_state === 'unread' ? ' is-unread' : ''}`); card.dataset.lineupId = item.lineup_id;
        const header = el('div', 'account-row-main'); header.append(el('strong', '', item.name), badge(item.state));
        if (item.notice_state === 'unread') header.append(el('span', 'lm-unread-label', '未读'));
        card.append(header, el('p', 'account-row-meta', `#${item.lineup_id} · 更新于 ${item.updated_at}`));
        const reason = el('div', 'lm-callout'); reason.append(el('strong', '', '封禁原因'), el('p', 'lm-reason', item.reason));
        if (item.review_note) reason.append(el('strong', '', '处理说明'), el('p', 'lm-reason', item.review_note));
        card.append(reason);
        if (item.state === 'pending') card.append(el('p', 'account-row-meta', '修改已提交，等待管理员审核；审核期间保持封禁。'));
        else if (item.lineup_status === 'banned') card.append(el('p', 'account-row-meta', '可修改名称、阵容码和赛季后提交重审；封禁期间不能删除。'));
        else card.append(el('p', 'account-row-meta', item.lineup_status === 'hidden' ? '限制已解除，阵容恢复为隐藏状态。' : item.lineup_status === 'deleted' ? '阵容已删除，处理记录保留。' : '限制已解除，阵容已恢复展示。'));
        const actions = el('div', 'lm-actions');
        if (item.lineup_status === 'banned' && item.state !== 'pending') {
          const edit = el('a', 'small-button lm-primary', '修改并提交重审'); edit.href = `/lineup/${item.lineup_id}/edit`; actions.append(edit);
        }
        actions.append(button(item.state === 'pending' ? '查看提交与记录' : '查看处理记录', () => openRecord({ api, lineupId: item.lineup_id })));
        async function update(next) {
          await api(`/api/me/lineup-notifications/${item.lineup_id}`, { method: 'PUT', body: JSON.stringify({ status: next, revision: item.revision }) });
          await load();
        }
        if (item.notice_state === 'archived') actions.append(button('移出归档', () => update('read')));
        else actions.append(button(item.notice_state === 'unread' ? '标记已读' : '标记未读', () => update(item.notice_state === 'unread' ? 'read' : 'unread')), button('归档', () => update('archived')));
        card.append(actions); list.append(card);
      }
      section.append(list);
      const pagination = el('div', 'lm-notice-pagination');
      const prev = button('上一页', async () => { page -= 1; await load(); }); prev.disabled = page <= 1;
      const next = button('下一页', async () => { page += 1; await load(); }); next.disabled = page >= data.total_pages;
      pagination.append(prev, el('span', 'lm-muted', `${page} / ${data.total_pages} · ${data.total} 条`), next); section.append(pagination);
    }
    load().then(() => { if (location.hash === '#lineup-notifications') section.scrollIntoView({ block: 'start' }); }).catch(error => {
      section.replaceChildren(el('p', 'lm-error', error.message), button('重新加载通知', load));
    });
  }
  window.JccAccountModeration = { mount };
})();
