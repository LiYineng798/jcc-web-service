(function () {
  const labels = { normal: '正常', hidden: '已隐藏', banned: '已封禁', pending: '待审核', rejected: '已退回', approved: '审核通过', released: '已解除封禁', deleted: '已删除' };
  const actionLabels = { ban: '封禁阵容', submit: '提交修改', approve: '审核通过', reject: '退回修改', release: '解除封禁' };
  function el(tag, className = '', text = '') {
    const node = document.createElement(tag); node.className = className; node.textContent = text; return node;
  }
  function button(text, action, className = 'small-button') {
    const node = el('button', className, text); node.type = 'button';
    node.addEventListener('click', async () => {
      node.disabled = true;
      try { await action(); } catch (error) { window.jccNotify.show(error.message, { variant: 'error' }); }
      finally { node.disabled = false; }
    });
    return node;
  }
  function badge(state) { return el('span', `lm-badge lm-${state}`, labels[state] || state); }
  function seasonName(id, seasons = []) { return seasons.find(s => s.id === id)?.name || id || '—'; }
  function contentBlock(title, value, seasons, original) {
    const block = el('section', 'lm-content-block'); block.append(el('h3', '', title));
    for (const [key, label] of [['name', '名称'], ['season_id', '赛季'], ['code', '阵容码']]) {
      const field = el('div', `lm-content-field${original && original[key] !== value[key] ? ' lm-changed' : ''}`);
      field.append(el('small', '', label + (original && original[key] !== value[key] ? ' · 已修改' : '')),
        el(key === 'code' ? 'pre' : 'p', '', key === 'season_id' ? seasonName(value[key], seasons) : value[key]));
      block.append(field);
    }
    return block;
  }
  function timeline(events, seasons) {
    const box = el('details', 'lm-history'); box.append(el('summary', '', `处理记录 · ${events.length}`));
    if (!events.length) box.append(el('p', 'lm-muted', '暂无处理记录'));
    for (const event of events) {
      const item = el('article', 'lm-event');
      item.append(el('strong', '', actionLabels[event.action]), el('time', 'lm-muted', event.created_at));
      if (event.reason) item.append(el('p', 'lm-reason', event.reason));
      if (event.action === 'submit') {
        const details = el('details'); details.append(el('summary', '', '查看本次提交内容'));
        details.append(contentBlock('提交版本', event.after, seasons, event.before)); item.append(details);
      }
      box.append(item);
    }
    return box;
  }
  async function openRecord({ api, lineupId, admin = false, mode = 'inspect', afterChange = async () => {} }) {
    const [record, manifest] = await Promise.all([api(`/api/lineups/${lineupId}/moderation`), api('/api/lineup-seasons')]);
    const { lineup, moderation: m, events } = record;
    const seasons = manifest.seasons || [];
    const dialog = el('dialog', 'lm-dialog'); dialog.setAttribute('aria-labelledby', 'lmDialogTitle');
    const head = el('header', 'lm-dialog-head');
    const heading = el('div'); heading.append(el('p', 'lm-eyebrow', `阵容管理 / #${lineupId}`), el('h2', '', mode === 'ban' ? '封禁阵容' : m?.state === 'pending' ? '修改审核' : '处理详情'));
    heading.querySelector('h2').id = 'lmDialogTitle';
    const close = button('关闭', () => dialog.close()); close.setAttribute('aria-label', '关闭详情');
    head.append(heading, close); dialog.append(head);
    const body = el('div', 'lm-dialog-body');
    body.append(badge(lineup.status === 'banned' ? m?.state || 'banned' : lineup.status));
    if (m) {
      const reason = el('div', 'lm-callout'); reason.append(el('strong', '', '封禁原因'), el('p', 'lm-reason', m.reason));
      if (m.review_note) reason.append(el('strong', '', '最新处理说明'), el('p', 'lm-reason', m.review_note));
      body.append(reason);
    }
    const comparison = el('div', m?.proposal ? 'lm-compare' : '');
    comparison.append(contentBlock(m?.proposal ? '原阵容' : '阵容内容', lineup, seasons));
    if (m?.proposal) comparison.append(contentBlock('用户提交版本', m.proposal, seasons, lineup));
    body.append(comparison);
    if (m?.state === 'pending') body.append(el('p', 'lm-muted', `提交于 ${m.submitted_at}。审核通过前，原阵容保持封禁。`));
    if (m) body.append(el('p', 'lm-muted', `通过审核或解除封禁后恢复为「${labels[m.prior_status]}」。`));
    body.append(timeline(events, seasons)); dialog.append(body);
    const footer = el('footer', 'lm-dialog-footer'); dialog.append(footer);
    function confirmAction(action) {
      footer.replaceChildren();
      const form = el('form', 'lm-decision');
      form.append(el('p', 'lm-muted', action === 'release' ? '本次按原阵容的名称、阵容码和赛季解除封禁。' : action === 'ban' ? '封禁后阵容从公开列表下架，作者会收到站内处理通知。' : action === 'approve' ? '审核通过后，以用户提交版本替换原阵容，并通知作者。' : '退回后继续封禁，作者可按说明再次修改并提交。'));
      const label = el('label', 'field');
      label.append(el('span', '', `${actionLabels[action]}${action === 'approve' ? '说明（选填）' : '原因（必填，用户可见）'}`));
      const input = el('textarea'); input.rows = 3; input.maxLength = 500; input.required = action !== 'approve'; input.name = 'reason';
      input.placeholder = action === 'ban' ? '说明存在的问题，以及用户需要如何修改…' : action === 'reject' ? '明确哪些内容仍需修改…' : '填写本次处理说明…';
      label.append(input);
      const error = el('p', 'lm-error'); error.setAttribute('role', 'alert');
      const actions = el('div', 'lm-actions');
      const submit = el('button', `small-button ${action === 'ban' || action === 'reject' ? 'lm-danger-button' : 'lm-primary'}`, `确认${actionLabels[action]}`); submit.type = 'submit';
      const cancel = button('取消', () => mode === 'ban' ? dialog.close() : renderActions());
      actions.append(cancel, submit); form.append(label, error, actions); footer.append(form);
      let busy = false;
      form.addEventListener('submit', async (event) => {
        event.preventDefault(); if (busy) return;
        busy = true; submit.disabled = cancel.disabled = close.disabled = true; error.textContent = '';
        try {
          await api(`/api/admin/lineups/${lineupId}/moderation/${action}`, { method: 'POST', body: JSON.stringify({ reason: input.value.trim(), version: lineup.version }) });
          dialog.close(); window.jccNotify.show(`${actionLabels[action]}已完成`, { variant: 'success' });
          try { await afterChange(); } catch (_) { window.jccNotify.show('处理已保存，列表刷新失败，请手动刷新', { variant: 'warning' }); }
        } catch (err) { error.textContent = err.message; }
        finally { busy = false; submit.disabled = cancel.disabled = close.disabled = false; }
      });
      input.focus();
    }
    function renderActions() {
      footer.replaceChildren();
      const actions = el('div', 'lm-actions');
      if (admin) {
        if (lineup.status === 'banned' && m?.state === 'pending') {
          actions.append(button('退回修改', () => confirmAction('reject'), 'small-button lm-danger-button'), button('通过并恢复', () => confirmAction('approve'), 'small-button lm-primary'));
        } else if (lineup.status === 'banned') {
          actions.append(button('解除封禁', () => confirmAction('release')));
        } else if (['normal', 'hidden'].includes(lineup.status)) {
          actions.append(button('封禁阵容', () => confirmAction('ban'), 'small-button lm-danger-button'));
        }
      } else if (lineup.status === 'banned' && m?.state !== 'pending') {
        const link = el('a', 'lm-notice-edit', '修改重审'); link.href = `/lineup/${lineupId}/edit`; actions.append(link);
      }
      footer.append(actions);
    }
    renderActions();
    document.body.append(dialog);
    dialog.addEventListener('close', () => dialog.remove(), { once: true });
    dialog.showModal();
    if (mode === 'ban') confirmAction('ban');
  }
  window.JccLineupModeration = { el, button, badge, labels, seasonName, openRecord, contentBlock, timeline };
})();
