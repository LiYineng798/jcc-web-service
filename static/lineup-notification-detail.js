(function () {
  const root = document.querySelector('#lineupNotificationDetail');
  const { el, button, badge, contentBlock, timeline } = window.JccLineupModeration;
  const id = root.dataset.lineupId;
  let csrfToken = '';
  async function api(url, options = {}) {
    const response = await fetch(url, { ...options, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken } });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '加载失败，请重试');
    return data;
  }
  async function load() {
    root.setAttribute('aria-busy', 'true');
    try {
      const [me, record, manifest] = await Promise.all([api('/api/me'), api(`/api/lineups/${id}/moderation`), api('/api/lineup-seasons')]);
      csrfToken = me.csrf_token;
      const { lineup, moderation: m, events } = record;
      if (!m) throw new Error('这条通知已不可用');
      root.replaceChildren();
      const heading = el('header', 'lm-detail-heading');
      heading.append(badge(m.state), el('h1', '', lineup.name), el('p', 'lm-muted', `#${id} · ${m.updated_at}`));
      root.append(heading);
      const reason = el('section', 'lm-callout'); reason.append(el('strong', '', '封禁原因'), el('p', 'lm-reason', m.reason));
      if (m.review_note) reason.append(el('strong', '', '最新处理说明'), el('p', 'lm-reason', m.review_note));
      root.append(reason);
      const actions = el('div', 'lm-detail-actions');
      if (lineup.status === 'banned' && m.state !== 'pending') {
        const edit = el('a', 'lm-notice-edit', '修改重审'); edit.href = `/lineup/${id}/edit`; actions.append(edit);
      } else if (m.state === 'pending') {
        actions.append(el('p', 'lm-muted', '修改已提交，等待管理员审核。'));
      } else if (lineup.status !== 'deleted') {
        const link = el('a', 'lm-notice-edit', '查看阵容'); link.href = `/lineup/${id}`; actions.append(link);
        actions.append(el('p', 'lm-muted', lineup.status === 'hidden' ? '已恢复为隐藏状态。' : '阵容已恢复展示。'));
      } else actions.append(el('p', 'lm-muted', '阵容已删除，处理记录保留。'));
      root.append(actions);
      const comparison = el('div', m.proposal ? 'lm-compare' : '');
      comparison.append(contentBlock(m.proposal ? '原阵容' : '阵容内容', lineup, manifest.seasons));
      if (m.proposal) comparison.append(contentBlock('提交的修改', m.proposal, manifest.seasons, lineup));
      root.append(comparison, timeline(events, manifest.seasons));
      // Mark only the revision actually rendered. A newer review must remain unread.
      if (m.notice_state === 'unread') {
        try { await api(`/api/me/lineup-notifications/${id}`, { method: 'PUT', body: JSON.stringify({ status: 'read', revision: m.revision }) }); }
        catch (_) {
          const warning = el('p', 'lm-muted', '已读状态未更新，重新加载可查看最新通知。');
          warning.append(button('重新加载', load)); root.append(warning);
        }
      }
    } catch (error) { root.replaceChildren(el('p', 'lm-error', error.message), button('重新加载', load)); }
    finally { root.setAttribute('aria-busy', 'false'); }
  }
  load();
})();
