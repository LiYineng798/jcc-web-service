(function (global) {
  const { el, button } = global.JccAdminCore;
  function open({ api, afterChange }) {
    const dialog = el('dialog', 'lm-dialog automation-dialog');
    dialog.setAttribute('aria-labelledby', 'automationTitle');
    const header = el('header', 'lm-dialog-head');
    const title = el('h2', '', 'AI 自动化账号'); title.id = 'automationTitle';
    header.append(title, button('关闭', () => dialog.close()));
    const body = el('div', 'lm-dialog-body');
    dialog.append(header, body); document.body.append(dialog);
    dialog.addEventListener('close', () => { dialog.remove(); afterChange?.(); }, { once: true });
    dialog.showModal();
    const error = err => {
      if (!dialog.open) return;
      global.jccNotify.show(err.message || '操作失败，请重试', { variant: 'error' });
    };
    async function load() {
      body.replaceChildren(el('p', 'admin-meta', '正在加载自动化账号…'));
      try {
        const data = await api('/api/admin/automation-accounts');
        if (!dialog.open) return;
        body.replaceChildren(el('p', 'admin-meta', '供 AI 通过专用 API 使用，不支持网页登录。默认只读脱敏运营数据；可按赛季授权批量导入普通阵容。不能管理用户、审核、修改配置或操作实时榜单。禁用会撤销旧令牌，重新启用后请轮换令牌。'),
          button('创建自动化账号', () => edit()));
        if (!data.items.length) body.append(el('p', '', '暂无自动化账号'));
        for (const account of data.items) {
          const card = el('article', 'automation-card');
          card.append(el('strong', '', `${account.nickname} (@${account.username})`),
            el('p', 'admin-meta', `${account.status === 'active' ? '启用' : '已禁用'} · ${account.can_import ? '可导入指定赛季' : '只读'} · 令牌 ${account.token_prefix}`),
            el('p', 'admin-meta', `到期：${new Date(account.expires_at).toLocaleString('zh-CN')} · 最近调用：${account.last_used_at ? new Date(account.last_used_at).toLocaleString('zh-CN') : '尚未使用'}`));
          if (account.can_import) card.append(el('p', 'admin-meta', `授权赛季：${account.allowed_seasons.join('、')}`));
          const actions = el('div', 'card-actions');
          actions.append(
            button('调整权限', () => edit(account)),
            button(account.status === 'active' ? '禁用' : '启用', async () => {
              await api(`/api/admin/automation-accounts/${account.user_id}`, { method: 'PUT', body: JSON.stringify({ status: account.status === 'active' ? 'disabled' : 'active' }) });
              await load();
            }),
            button('轮换令牌', async () => {
              if (!confirm('轮换后旧令牌立即失效，新令牌有效期为 30 天。确定继续？')) return;
              const result = await api(`/api/admin/automation-accounts/${account.user_id}/rotate-token`, { method: 'POST', body: JSON.stringify({ expires_in_days: 30 }) });
              showToken(result);
            }),
            button('删除账号', async () => {
              if (!confirm('删除后令牌失效且无法恢复此账号；已上传阵容和审计记录会保留。确定删除？')) return;
              await api(`/api/admin/automation-accounts/${account.user_id}`, { method: 'DELETE' });
              await load();
            }, 'small-button danger-button'));
          card.append(actions); body.append(card);
        }
      } catch (err) { body.replaceChildren(el('p', '', err.message), button('重试', load)); }
    }
    function showToken(result) {
      body.replaceChildren(el('h3', '', '请保存本次令牌'), el('p', 'admin-meta', '完整令牌仅在这里展示一次。交给需要接入的 AI，并像密码一样保管。关闭后无法再次查看，可轮换生成新令牌。'));
      const token = el('textarea', 'automation-token');
      token.readOnly = true; token.rows = 3; token.value = result.token; token.setAttribute('aria-label', '一次性展示的 API 令牌');
      body.append(token, el('p', 'admin-meta', `有效期至 ${new Date(result.expires_at).toLocaleString('zh-CN')}`),
        el('p', 'admin-meta', '请求头：Authorization: Bearer <令牌>。能力查询：GET /api/automation/me。'),
        button('复制令牌', async () => {
          await navigator.clipboard.writeText(result.token);
          global.jccNotify.show('令牌已复制', { variant: 'success' });
        }), button('已保存，返回账号列表', load));
    }
    async function edit(account = null) {
      let seasons;
      try { seasons = (await api('/api/lineup-seasons')).seasons || []; } catch (err) { error(err); return; }
      if (!dialog.open) return;
      const form = el('form', 'automation-form');
      const field = (label, name, value, type = 'text') => {
        const wrap = el('label', 'patch-editor-field');
        const input = el('input'); input.type = type; input.name = name; input.value = value; input.required = true;
        wrap.append(el('span', '', label), input); return wrap;
      };
      form.append(el('h3', '', account ? `调整 ${account.username} 的权限` : '创建 AI 自动化账号'));
      if (!account) {
        const name = field('用户名', 'username', ''); name.querySelector('input').maxLength = 30;
        const nickname = field('显示名称', 'nickname', ''); nickname.querySelector('input').maxLength = 30;
        const days = field('令牌有效期（1–90 天）', 'days', '30', 'number');
        days.querySelector('input').min = '1'; days.querySelector('input').max = '90';
        form.append(name, nickname, days);
      }
      const permission = el('label', 'automation-check');
      const enabled = el('input'); enabled.type = 'checkbox'; enabled.checked = account?.can_import || false;
      permission.append(enabled, document.createTextNode('允许批量导入普通赛季阵容（默认关闭）')); form.append(permission);
      const choices = el('fieldset', 'automation-seasons'); choices.append(el('legend', '', '允许导入的赛季'));
      for (const season of seasons) {
        const label = el('label', 'automation-check'); const input = el('input');
        input.type = 'checkbox'; input.value = season.id; input.checked = account?.allowed_seasons?.includes(season.id) || false;
        label.append(input, document.createTextNode(season.name || season.id)); choices.append(label);
      }
      choices.disabled = !enabled.checked; enabled.addEventListener('change', () => { choices.disabled = !enabled.checked; });
      const message = el('p', 'patch-editor-error'); message.setAttribute('role', 'alert');
      const submit = el('button', 'small-button is-active', account ? '保存权限' : '创建并生成令牌'); submit.type = 'submit';
      form.append(choices, el('p', 'admin-meta', '只读范围：运营概览、复制排行、日报汇总及公开普通阵容。导入不会覆盖、删除、调分或审核已有阵容，上传者记录为此账号。'),
        message, submit, button('返回列表', load));
      let busy = false;
      form.addEventListener('submit', async event => {
        event.preventDefault(); if (busy) return; message.textContent = '';
        const selected = [...choices.querySelectorAll('input:checked')].map(input => input.value);
        if (enabled.checked && !selected.length) { message.textContent = '请至少选择一个允许导入的赛季。'; return; }
        const payload = { can_import: enabled.checked, allowed_seasons: selected };
        if (!account) Object.assign(payload, { username: form.elements.username.value.trim(), nickname: form.elements.nickname.value.trim(), expires_in_days: Number(form.elements.days.value) });
        busy = true; submit.disabled = true;
        try {
          const result = await api(`/api/admin/automation-accounts${account ? '/' + account.user_id : ''}`, { method: account ? 'PUT' : 'POST', body: JSON.stringify(payload) });
          if (!dialog.open) return;
          if (account) await load(); else showToken(result);
        } catch (err) { message.textContent = err.message; }
        finally { busy = false; submit.disabled = false; }
      });
      body.replaceChildren(form);
    }
    load();
  }
  global.JccAutomationAccounts = { open };
})(window);
