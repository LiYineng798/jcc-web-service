(function () {
  const { el, button, badge, openRecord } = window.JccLineupModeration;
  function mount(root, csrfToken) {
    let status = 'all', page = 1, sequence = 0;
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
      const title = el('div', 'lm-notice-heading'); title.append(el('h3', '', '阵容处理通知'));
      if (data.counts.unread) title.append(el('span', 'lm-unread-label', `${data.counts.unread} 条未读`));
      heading.append(title);
      head.append(heading); section.append(head);
      const tabs = el('div', 'lm-tabs'); tabs.setAttribute('aria-label', '通知状态筛选');
      for (const [value, label] of [['all', '全部'], ['unread', '未读'], ['read', '已读']]) {
        const item = button(label, async () => { status = value; page = 1; await load(); }, `lm-tab${status === value ? ' is-active' : ''}`);
        item.setAttribute('aria-pressed', String(value === status)); tabs.append(item);
      }
      section.append(tabs);
      if (!data.items.length) section.append(el('p', 'account-empty', '这里暂时没有处理通知。'));
      const list = el('div', 'account-list');
      for (const item of data.items) {
        const card = el('article', `lm-notification${item.notice_state === 'unread' ? ' is-unread' : ''}`); card.dataset.lineupId = item.lineup_id;
        const header = el('div', 'account-row-main'); header.append(el('strong', '', item.name), badge(item.state));
        async function update(next) {
          await api(`/api/me/lineup-notifications/${item.lineup_id}`, { method: 'PUT', body: JSON.stringify({ status: next, revision: item.revision }) });
          await load();
        }
        const meta = el('div', 'lm-notice-meta');
        meta.append(el('time', 'lm-muted', `#${item.lineup_id} · ${item.updated_at}`));
        const readLabel = item.notice_state === 'unread' ? '标记已读' : '标记未读';
        const read = button('', () => update(item.notice_state === 'unread' ? 'read' : 'unread'), `lm-read-toggle${item.notice_state === 'read' ? ' is-read' : ''}`);
        read.setAttribute('aria-label', readLabel); read.title = readLabel;
        const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        icon.setAttribute('viewBox', '0 0 24 24'); icon.setAttribute('aria-hidden', 'true');
        icon.innerHTML = '<rect x="4" y="4" width="16" height="16" rx="4"/><path d="m8 12 3 3 5-6"/>';
        read.append(icon); meta.append(read); card.append(header, meta);
        const reason = el('div', 'lm-callout'); reason.append(el('strong', '', '封禁原因'), el('p', 'lm-reason', item.reason));
        if (item.review_note) reason.append(el('strong', '', '处理说明'), el('p', 'lm-reason', item.review_note));
        card.append(reason);
        const actions = el('div', 'lm-notice-actions');
        if (item.lineup_status === 'banned' && item.state !== 'pending') {
          const edit = el('a', 'lm-notice-edit', '修改重审'); edit.href = `/lineup/${item.lineup_id}/edit`;
          const arrow = el('span', '', '→'); arrow.setAttribute('aria-hidden', 'true'); edit.append(arrow); actions.append(edit);
        }
        actions.append(button(item.state === 'pending' ? '查看提交' : '处理记录', () => openRecord({ api, lineupId: item.lineup_id }), 'lm-notice-secondary'));
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
