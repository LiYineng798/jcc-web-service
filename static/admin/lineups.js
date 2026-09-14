(function () {
  const { el, button, badge, seasonName, openRecord } = window.JccLineupModeration;
  function createRenderer({ getState, getSeasons, api, changeFilters, refresh, searchControls, pagination, updateStatus, adjustScore }) {
    return function render() {
      const state = getState(), root = el('div', 'lm-workspace');
      const counts = state.counts || {};
      const tabs = el('div', 'lm-tabs'); tabs.setAttribute('aria-label', '阵容状态筛选');
      for (const [id, title] of [['all', '全部'], ['pending', '待审核'], ['normal', '正常'], ['hidden', '已隐藏'], ['banned', '已封禁']]) {
        const count = id === 'all' ? Object.values(counts).reduce((a, b) => a + b, 0) : counts[id] || 0;
        const item = button(`${title} ${count}`, () => changeFilters({ status: id, order: id === 'pending' ? 'oldest' : 'newest' }), `lm-tab${state.status === id ? ' is-active' : ''}`);
        item.setAttribute('aria-pressed', String(state.status === id)); tabs.append(item);
      }
      const toolbar = el('div', 'lm-toolbar'); toolbar.append(searchControls());
      const season = el('select'); season.setAttribute('aria-label', '筛选赛季');
      for (const item of [{ id: '', name: '全部赛季' }, ...getSeasons()]) {
        const option = el('option', '', item.name); option.value = item.id; season.append(option);
      }
      season.value = state.season || ''; season.addEventListener('change', () => changeFilters({ season: season.value }).catch(e => window.jccNotify.show(e.message, { variant: 'error' })));
      const order = el('select'); order.setAttribute('aria-label', '阵容排序');
      for (const [value, text] of [['newest', '最新添加'], ['oldest', '最早更新优先']]) { const option = el('option', '', text); option.value = value; order.append(option); }
      order.value = state.order; order.addEventListener('change', () => changeFilters({ order: order.value }).catch(e => window.jccNotify.show(e.message, { variant: 'error' })));
      toolbar.append(season, order, button('刷新', refresh));
      root.append(tabs, toolbar, el('p', 'lm-muted', '状态数量为全站统计；下表按搜索和赛季筛选。封禁后用户可修改并提交重审。'));
      if (!state.items.length) { root.append(el('p', 'lm-empty', '当前筛选下没有阵容')); return root; }
      const table = el('table', 'lm-table'); table.setAttribute('aria-label', '阵容管理列表');
      const head = el('thead'), headings = el('tr');
      for (const text of ['阵容 / 赛季', '作者', '状态', '数据', '操作']) { const th = el('th', '', text); th.scope = 'col'; headings.append(th); }
      head.append(headings); table.append(head); const body = el('tbody');
      for (const lineup of state.items) {
        const row = el('tr'); row.dataset.lineupId = lineup.id;
        const identity = el('td', 'lm-identity');
        const title = el('a', 'lm-lineup-title', lineup.name); title.href = `/lineup/${lineup.id}`; title.target = '_blank'; title.rel = 'noopener';
        identity.append(title, el('small', 'lm-muted', `#${lineup.id} · ${seasonName(lineup.season_id, getSeasons())}`));
        const code = el('code', 'lm-code-preview', lineup.code); code.title = lineup.code; identity.append(code);
        const author = el('td', 'lm-author'); author.dataset.label = '作者';
        const person = el('div', 'lm-person');
        if (window.jccAvatar) person.append(window.jccAvatar.image(lineup.owner_avatar_color, 30));
        const authorText = el('div'); authorText.append(el('span', '', lineup.owner_nickname), el('small', 'lm-muted', '@' + (lineup.owner_username || 'system'))); person.append(authorText); author.append(person);
        const status = el('td', 'lm-status'); status.dataset.label = '状态';
        const m = lineup.moderation;
        status.append(badge(lineup.status === 'banned' ? m?.state || 'banned' : lineup.status));
        if (lineup.status === 'banned') {
          const reason = el('small', 'lm-reason-preview', m?.review_note || m?.reason || ''); reason.title = reason.textContent; status.append(reason);
          if (m?.state === 'pending') status.append(el('small', 'lm-muted', m.submitted_at));
        }
        const stats = el('td', 'lm-stats'); stats.dataset.label = '数据'; stats.append(el('strong', '', `分 ${lineup.score}`), el('small', 'lm-muted', `赞 ${lineup.like_count} · 复制 ${lineup.copy_count}`));
        const actions = el('td', 'lm-row-actions'); const controls = el('div', 'lm-actions');
        const record = (mode = 'inspect') => openRecord({ api, lineupId: lineup.id, admin: true, mode, afterChange: refresh });
        if (lineup.status === 'banned') {
          controls.append(button(m?.state === 'pending' ? '审核修改' : '处理详情', () => record(), m?.state === 'pending' ? 'small-button lm-primary' : 'small-button'));
        } else {
          controls.append(button(lineup.status === 'hidden' ? '恢复展示' : '隐藏', () => updateStatus(lineup, lineup.status === 'hidden' ? 'normal' : 'hidden')),
            button('调分', () => adjustScore(lineup)), button('封禁', () => record('ban'), 'small-button lm-danger-button'));
          if (m) controls.append(button('记录', () => record()));
        }
        actions.append(controls); row.append(identity, author, status, stats, actions); body.append(row);
      }
      table.append(body); root.append(table, pagination()); return root;
    };
  }
  function openScore({ api, lineup, afterChange }) {
    const dialog = el('dialog', 'lm-dialog lm-score-dialog'); dialog.setAttribute('aria-labelledby', 'lmScoreTitle');
    const head = el('header', 'lm-dialog-head'); const title = el('h2', '', '调整阵容分数'); title.id = 'lmScoreTitle';
    const close = button('关闭', () => dialog.close()); head.append(title, close);
    const form = el('form', 'lm-dialog-body');
    form.append(el('strong', '', lineup.name), el('p', 'lm-muted', '设置修正总值：正数增加，负数扣减。现有点赞与复制记录会保留。'));
    const inputs = {};
    for (const [key, label] of [['admin_like_adjustment', '点赞修正数'], ['admin_copy_adjustment', '复制修正数']]) {
      const field = el('label', 'field'); field.append(el('span', '', label));
      const input = el('input'); input.type = 'number'; input.min = -1000000; input.max = 1000000; input.step = 1; input.required = true; input.value = lineup[key] || 0;
      inputs[key] = input; field.append(input); form.append(field);
    }
    const error = el('p', 'lm-error'); error.setAttribute('role', 'alert');
    const submit = el('button', 'small-button lm-primary', '保存分数修正'); submit.type = 'submit';
    form.append(error, submit); dialog.append(head, form); let busy = false;
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (busy) return; busy = true; submit.disabled = close.disabled = true; error.textContent = '';
      try {
        const body = { version: lineup.version };
        for (const key of Object.keys(inputs)) body[key] = Number(inputs[key].value);
        await api(`/api/admin/lineups/${lineup.id}/adjust-score`, { method: 'POST', body: JSON.stringify(body) });
        dialog.close(); window.jccNotify.show('分数修正已保存', { variant: 'success' });
        try { await afterChange(); } catch (_) { window.jccNotify.show('修改已保存，列表刷新失败，请手动刷新', { variant: 'warning' }); }
      } catch (err) { error.textContent = err.message; }
      finally { busy = false; submit.disabled = close.disabled = false; }
    });
    document.body.append(dialog); dialog.addEventListener('close', () => dialog.remove(), { once: true }); dialog.showModal();
  }
  window.JccAdminLineups = { createRenderer, openScore };
})();
