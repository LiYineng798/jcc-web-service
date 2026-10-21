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
        body.replaceChildren(el('p', 'admin-meta', '使用正常登录页进入受限后台。默认可查看脱敏运营数据；可分别授权普通阵容批量导入和榜单更新时间维护。账号只能由管理员创建，密码仅保存加密摘要。'),
          button('创建自动化账号', () => edit()));
        if (!data.items.length) body.append(el('p', '', '暂无自动化账号'));
        for (const account of data.items) {
          const card = el('article', 'automation-card');
          card.append(el('strong', '', `${account.nickname} (@${account.username})`),
            el('p', 'admin-meta', `${account.status === 'active' ? '启用' : '已禁用'} · ${account.can_import ? '可导入指定赛季' : '普通阵容只读'}${account.can_touch ? ' · 可维护更新时间' : ''}`),
            el('p', 'admin-meta', `到期：${new Date(account.expires_at).toLocaleString('zh-CN')} · 最近使用：${account.last_used_at ? new Date(account.last_used_at).toLocaleString('zh-CN') : '尚未使用'}`));
          if (account.can_touch) card.append(el('p', 'admin-meta', `更新时间授权：${account.touch_seasons.join('、')}`));
          if (account.can_import) card.append(el('p', 'admin-meta', `授权赛季：${account.allowed_seasons.join('、')}`));
          const actions = el('div', 'card-actions');
          actions.append(
            button('调整权限', () => edit(account)),
            button(account.status === 'active' ? '禁用' : '启用', async () => {
              await api(`/api/admin/automation-accounts/${account.user_id}`, { method: 'PUT', body: JSON.stringify({ status: account.status === 'active' ? 'disabled' : 'active' }) });
              await load();
            }),
            button('重设密码 / 续期', () => resetPassword(account)),
            button('删除账号', async () => {
              if (!confirm('删除后已有登录立即失效且无法恢复此账号；已上传阵容和审计记录会保留。确定删除？')) return;
              await api(`/api/admin/automation-accounts/${account.user_id}`, { method: 'DELETE' });
              await load();
            }, 'small-button danger-button'));
          card.append(actions); body.append(card);
        }
      } catch (err) { body.replaceChildren(el('p', '', err.message), button('重试', load)); }
    }
    function resetPassword(account) {
      const form = el('form', 'automation-form');
      form.append(el('h3', '', `重设 ${account.username}`), el('p', 'admin-meta', '留空的项目保持不变。重设密码将使已有登录失效；续期按当前时间起算。'));
      const label = el('label', 'patch-editor-field', '新密码（12–128 字符，含字母和数字）');
      const password = el('input'); password.type = 'password'; password.autocomplete = 'new-password'; password.minLength = 12; password.maxLength = 128; label.append(password);
      const daysLabel = el('label', 'patch-editor-field', '续期天数（1–90 天）');
      const days = el('input'); days.type = 'number'; days.min = 1; days.max = 90; daysLabel.append(days);
      const message = el('p', 'patch-editor-error'); message.setAttribute('role', 'alert');
      const submit = el('button', 'small-button is-active', '保存'); submit.type = 'submit';
      form.append(label, daysLabel, message, submit, button('返回列表', load));
      form.addEventListener('submit', async event => {
        event.preventDefault(); if (submit.disabled) return;
        const data = {};
        if (password.value) data.password = password.value;
        if (days.value) data.expires_in_days = Number(days.value);
        if (!Object.keys(data).length) { message.textContent = '请填写新密码或续期天数。'; return; }
        submit.disabled = true;
        try { await api(`/api/admin/automation-accounts/${account.user_id}`, { method: 'PUT', body: JSON.stringify(data) }); await load(); }
        catch (err) { message.textContent = err.message; }
        finally { submit.disabled = false; }
      });
      body.replaceChildren(form);
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
        const days = field('账号有效期（1–90 天）', 'days', '30', 'number');
        days.querySelector('input').min = '1'; days.querySelector('input').max = '90';
        const password = field('登录密码（至少 12 字符，含字母和数字）', 'password', '', 'password');
        password.querySelector('input').minLength = 12; password.querySelector('input').maxLength = 128; password.querySelector('input').autocomplete = 'new-password';
        form.append(name, nickname, password, days);
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
      const touchLabel = el('label', 'automation-check');
      const touch = el('input'); touch.type = 'checkbox'; touch.checked = account?.can_touch || false;
      touchLabel.append(touch, document.createTextNode('允许将实时阵容更新时间设为现在（默认关闭）'));
      const touchChoices = choices.cloneNode(true); touchChoices.querySelector('legend').textContent = '允许维护更新时间的赛季';
      touchChoices.querySelectorAll('input').forEach(input => { input.checked = account?.touch_seasons?.includes(input.value) || false; });
      touchChoices.disabled = !touch.checked; touch.addEventListener('change', () => { touchChoices.disabled = !touch.checked; });
      const message = el('p', 'patch-editor-error'); message.setAttribute('role', 'alert');
      const submit = el('button', 'small-button is-active', account ? '保存权限' : '创建账号'); submit.type = 'submit';
      form.append(choices, touchLabel, touchChoices, el('p', 'admin-meta', '只读范围：运营概览、复制排行、日报汇总及公开普通阵容。导入不会覆盖、删除、调分或审核已有阵容，上传者记录为此账号。'),
        message, submit, button('返回列表', load));
      let busy = false;
      form.addEventListener('submit', async event => {
        event.preventDefault(); if (busy) return; message.textContent = '';
        const selected = [...choices.querySelectorAll('input:checked')].map(input => input.value);
        if (enabled.checked && !selected.length) { message.textContent = '请至少选择一个允许导入的赛季。'; return; }
        const touched = [...touchChoices.querySelectorAll('input:checked')].map(input => input.value);
        if (touch.checked && !touched.length) { message.textContent = '请选择允许维护更新时间的赛季。'; return; }
        const payload = { can_import: enabled.checked, allowed_seasons: selected, can_touch: touch.checked, touch_seasons: touched };
        if (!account) Object.assign(payload, { password: form.elements.password.value, username: form.elements.username.value.trim(), nickname: form.elements.nickname.value.trim(), expires_in_days: Number(form.elements.days.value) });
        busy = true; submit.disabled = true;
        try {
          const result = await api(`/api/admin/automation-accounts${account ? '/' + account.user_id : ''}`, { method: account ? 'PUT' : 'POST', body: JSON.stringify(payload) });
          if (!dialog.open) return;
          await load();
          global.jccNotify.show(account ? '权限已保存' : `账号 ${result.username} 已创建，可从登录页进入后台`, { variant: 'success' });
        } catch (err) { message.textContent = err.message; }
        finally { busy = false; submit.disabled = false; }
      });
      body.replaceChildren(form);
    }
    load();
  }
  global.JccAutomationAccounts = { open };
})(window);
