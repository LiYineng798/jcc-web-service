/* Workspace for AI automation accounts.
   The menu only lists what this account may do; every page is one title row plus its data. */
(() => {
  const { el, button } = window.JccAdminCore;
  const root = document.querySelector('#assistantApp');
  const avatarButton = document.querySelector('#assistantAvatar');
  const prefix = '/api/admin/assistant';
  const tabs = ['overview', 'reports', 'lineups', 'decks', 'touch'];
  let csrf = '', account, seasons = [], deckSeasons = [], revision = 0, dirty = false;
  let active = tabs.includes(location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
  const labels = {
    today_uv: '今日访客', yesterday_uv: '昨日访客', today_new_visitors: '今日新访客', today_returning_visitors: '今日回访',
    today_users: '今日注册', today_logins: '今日登录', today_authenticated_users: '今日活跃账号', today_lineup_copy_count: '今日普通阵容复制',
    today_live_comp_copy_count: '今日实时阵容复制', today_total_copy_count: '今日总复制', total_users: '用户总数', pending_reports_count: '待处理反馈',
    unique_visitors: '独立访客', page_visits: '页面访问', new_visitors: '新访客', returning_visitors: '回访访客', returning_3d: '3 日回访', returning_7d: '7 日回访',
    new_registrations: '注册账号', successful_logins: '登录账号', authenticated_active_users: '活跃账号', lineup_copies: '普通阵容复制', live_comp_copies: '实时阵容复制',
    total_copies: '总复制', new_lineups: '新增阵容', guestbook_messages: '留言数', reports_submitted: '反馈数', like_actions: '点赞数', favorite_actions: '收藏数'
  };
  const statusLabels = { importable: '可导入', created: '已新增', invalid: '无效', duplicate_existing: '站内已存在', duplicate_in_upload: '本批重复' };

  async function api(path, options = {}) {
    const response = await fetch(path.startsWith('/api/') ? path : prefix + path, {
      ...options, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }
    });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401) { dirty = false; window.location.assign('/auth?next=/admin'); }
      throw new Error(data.error || '加载失败，请重试');
    }
    return data;
  }

  // Shown in the site's audience zone; <time datetime> keeps the exact instant machine-readable.
  const format = (value, parts) => new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false, ...parts });
  const full = { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' };
  function time(value, parts = full) {
    if (!value) return el('span', 'assistant-muted', '—');
    const node = el('time', '', format(value, parts)); node.dateTime = value; node.title = format(value, full) + ' 北京时间';
    return node;
  }

  function heading(level, title, ...controls) {
    const row = el('div', level === 1 ? 'assistant-head' : 'assistant-subhead');
    row.append(el(level === 1 ? 'h1' : 'h2', '', title));
    if (controls.length) { const tools = el('div', 'assistant-tools'); tools.append(...controls); row.append(tools); }
    return row;
  }
  const muted = text => el('p', 'assistant-muted', text);
  function select(options, label) {
    const node = el('select'); node.setAttribute('aria-label', label);
    options.forEach(({ id, name }) => { const option = el('option', '', name); option.value = id; node.append(option); });
    return node;
  }
  function table(columns, rows, rowClass = null) {
    if (!rows.length) return muted('暂无数据');
    const wrap = el('div', 'assistant-table-wrap'); const node = el('table', 'assistant-table');
    const head = el('tr'); columns.forEach(([name]) => { const th = el('th', '', name); th.scope = 'col'; head.append(th); });
    const thead = el('thead'); thead.append(head);
    const body = el('tbody');
    rows.forEach(row => {
      const tr = el('tr', rowClass?.(row) || '');
      columns.forEach(([name, key]) => {
        const value = typeof key === 'function' ? key(row) : row[key];
        const td = el('td'); td.dataset.label = name;
        td.append(value instanceof Node ? value : String(value ?? '—')); tr.append(td);
      });
      body.append(tr);
    });
    node.append(thead, body); wrap.append(node); return wrap;
  }
  function metrics(values) {
    const list = el('dl', 'assistant-metrics');
    Object.keys(labels).filter(key => key in values).forEach(key => {
      const item = el('div'); item.append(el('dt', '', labels[key]), el('dd', '', Number(values[key]).toLocaleString('zh-CN'))); list.append(item);
    });
    return list;
  }
  const ranks = rows => table([['阵容', 'title'], ['赛季', 'season_name'], ['上传者', 'uploader'], ['复制次数', 'copies'], ['复制人数', 'unique_visitors']], rows);
  const deckMetrics = (data, compact) => window.JccAdminDeckMetrics.render({ ...(data || {}), compact, readOnly: true });
  // Re-runs only the latest request, so a slow answer never overwrites a newer choice.
  function loader(target, fetchNodes) {
    let generation = 0;
    return async function load() {
      const current = ++generation; target.replaceChildren(muted('加载中…'));
      try { const nodes = await fetchNodes(); if (current === generation) target.replaceChildren(...nodes); }
      catch (error) { if (current === generation) target.replaceChildren(el('p', 'assistant-error', error.message), button('重试', load, 'assistant-button')); }
    };
  }

  async function overview() {
    const [data, copies] = await Promise.all([api('/overview'), api('/copy-rank')]);
    const day = el('input'); day.type = 'date'; day.value = copies.date; day.setAttribute('aria-label', '复制排行日期');
    const result = el('div'); result.append(ranks(copies.items));
    const load = loader(result, async () => [ranks((await api('/copy-rank?date=' + encodeURIComponent(day.value))).items)]);
    day.addEventListener('change', load);
    return [heading(1, '运营概览'), metrics(data.stats),
      heading(2, '近七日访问'), table([['日期', 'date'], ['访客', 'uv']], data.traffic_7d),
      heading(2, '卡组库'), deckMetrics(data.deck, true),
      heading(2, '复制排行', day), result];
  }

  async function reports() {
    const data = await api('/daily-reports');
    if (!data.items.length) return [heading(1, '每日报告'), muted('暂无日报')];
    const day = select(data.items.map(item => ({ id: item.report_date, name: item.report_date })), '报告日期');
    const result = el('div');
    const load = loader(result, async () => {
      const report = await api('/daily-reports/' + day.value);
      const hours = Array.from({ length: 24 }, (_, hour) => ({ hour: `${hour}:00`, uv: report.hourly.uv?.[hour] ?? 0, visits: report.hourly.visits?.[hour] ?? 0, copies: report.hourly.copies?.[hour] ?? 0 }));
      const generated = el('p', 'assistant-muted assistant-foot'); generated.append('生成于 ', time(report.generated_at));
      return [metrics(report.summary),
        heading(2, '卡组库'), deckMetrics(report.deck, false),
        heading(2, '复制排行'), ranks(report.top_copied),
        heading(2, '各赛季复制'), table([['赛季', 'season_name'], ['复制次数', 'copies'], ['复制人数', 'unique_visitors']], report.season_copy_rank),
        heading(2, '页面访问'), table([['页面', 'label'], ['访问次数', 'visits'], ['访客', 'uv']], report.top_pages),
        heading(2, '按小时统计'), table([['时段', 'hour'], ['访客', 'uv'], ['访问', 'visits'], ['复制', 'copies']], hours),
        generated];
    });
    day.addEventListener('change', load); await load();
    return [heading(1, '每日报告', day), result];
  }

  const entryStatus = item => [item.status === 'created' ? `${statusLabels.created} #${item.id}` : statusLabels[item.status] || item.status, item.reason].filter(Boolean).join(' · ');
  const entries = items => table([['名称', item => item.name ?? item.raw ?? '—'], ['阵容码', 'code'], ['状态', entryStatus], ['行', 'line']], items, item => 'is-' + item.status);

  async function lineups() {
    const view = select(seasons, '查看赛季'); const list = el('div'); let page = 1, fresh = new Set();
    const load = loader(list, async () => {
      const data = await api('/lineups?season_id=' + encodeURIComponent(view.value) + '&page=' + page);
      const nodes = [table([['阵容', 'name'], ['编号', 'id'], ['阵容码', 'code'], ['上传者', 'uploader']], data.items, row => fresh.has(row.id) ? 'is-new' : '')];
      const hasNext = data.items.length >= data.page_size;
      if (page > 1 || hasNext) {
        const turn = step => async () => { page += step; await load(); window.JccAdminCore.revealListStart(list); };
        const pager = el('div', 'assistant-pager');
        pager.append(button('上一页', turn(-1), 'assistant-button', page <= 1), el('span', 'assistant-muted', String(page)), button('下一页', turn(1), 'assistant-button', !hasNext));
        nodes.push(pager);
      }
      return nodes;
    });
    const show = id => { view.value = id; page = 1; fresh = new Set(); return load(); };
    view.addEventListener('change', () => show(view.value));
    const allowed = account.can_import ? seasons.filter(s => account.allowed_seasons.includes(s.id)) : [];
    if (!allowed.length) { if (view.value) await load(); return [heading(1, '普通阵容', view), list]; }

    const panel = el('section', 'assistant-import'); panel.hidden = true; panel.id = 'assistantImport'; panel.setAttribute('aria-label', '批量导入');
    const toggle = button('导入', () => {
      panel.hidden = !panel.hidden; toggle.setAttribute('aria-expanded', String(!panel.hidden));
      if (!panel.hidden) text.focus();
    }, 'assistant-button');
    toggle.setAttribute('aria-controls', panel.id); toggle.setAttribute('aria-expanded', 'false');
    const season = select(allowed, '导入赛季');
    if (allowed.some(s => s.id === view.value)) season.value = view.value;
    const text = el('textarea'); text.maxLength = 20000; text.rows = 6; text.setAttribute('aria-label', '阵容码');
    text.placeholder = '【阵容码】#S11-九五至尊#ABC123';
    const limit = account.limits.rows_per_import;
    const count = el('span', 'assistant-muted', `0 / ${limit}`);
    const status = el('p', 'assistant-status'); status.setAttribute('role', 'status');
    const result = el('div'); let prepared = null, busy = false;
    const payload = () => JSON.stringify({ season_id: season.value, raw_text: text.value });
    const invalidate = () => {
      prepared = null; commit.disabled = true; result.replaceChildren(); status.textContent = ''; dirty = !!text.value;
      const rows = text.value.split('\n').filter(line => line.trim()).length;
      count.textContent = `${rows} / ${limit}`; count.classList.toggle('is-over', rows > limit);
    };
    const check = button('预览', async () => {
      if (busy) return; busy = true; check.disabled = true; commit.disabled = true;
      const snapshot = payload();
      try {
        const preview = await api('/lineups/bulk-import/preview', { method: 'POST', body: snapshot });
        if (payload() !== snapshot) return;
        prepared = snapshot;
        status.textContent = `可导入 ${preview.importable_count} · 重复 ${preview.duplicate_existing_count + preview.duplicate_in_upload_count} · 无效 ${preview.invalid_count}`;
        result.replaceChildren(entries(preview.items));
        commit.disabled = !preview.importable_count;
      } finally { busy = false; check.disabled = false; }
    }, 'assistant-button');
    const commit = button('确认导入', async () => {
      if (busy || !prepared || prepared !== payload()) return;
      busy = true; commit.disabled = true; check.disabled = true; season.disabled = true; text.disabled = true;
      try {
        const done = await api('/lineups/bulk-import', { method: 'POST', body: prepared });
        const skipped = done.duplicate_existing_count + done.duplicate_in_upload_count;
        status.textContent = [`已导入 ${done.created_count}`, skipped && `跳过 ${skipped}`, done.invalid_count && `失败 ${done.invalid_count}`].filter(Boolean).join(' · ');
        prepared = null; dirty = false; text.value = ''; count.textContent = `0 / ${limit}`;
        result.replaceChildren(entries(done.items));
        const created = new Set(done.items.filter(item => item.status === 'created').map(item => item.id));
        view.value = done.season_id; page = 1; fresh = created; await load();
      } finally { busy = false; check.disabled = false; season.disabled = false; text.disabled = false; }
    }, 'assistant-button is-primary', true);
    // The list follows the import target, so what you see below is where the batch lands.
    text.addEventListener('input', invalidate);
    season.addEventListener('change', () => { invalidate(); show(season.value); });
    view.addEventListener('change', () => { if (!busy && allowed.some(s => s.id === view.value) && season.value !== view.value) { season.value = view.value; invalidate(); } });
    const actions = el('div', 'assistant-actions'); actions.append(season, count, check, commit);
    panel.append(text, actions, status, result);
    if (view.value) await load();
    return [heading(1, '普通阵容', view, toggle), panel, list];
  }

  async function touch() {
    const data = await api('/live-seasons');
    if (!data.seasons.length) return [heading(1, '榜单展示时间'), muted('暂无可维护的赛季')];
    const list = el('ul', 'assistant-rows');
    for (const season of data.seasons) {
      const item = el('li'); const current = el('span'); current.append(time(season.updated_at));
      const action = button('设为现在', async (_, node) => {
        if (!confirm(`将「${season.name}」的榜单展示时间设为现在？`)) return;
        node.disabled = true;
        try {
          const saved = await api('/live-seasons/' + encodeURIComponent(season.id) + '/touch', { method: 'POST', body: '{}' });
          current.replaceChildren(time(saved.updated_at));
          window.jccNotify.show(`「${saved.season_name}」已设为 ${format(saved.updated_at, full)}`, { variant: 'success' });
        } finally { node.disabled = false; }
      }, 'assistant-button');
      action.setAttribute('aria-label', `${season.name} 设为现在`);
      item.append(el('strong', '', season.name), current, action); list.append(item);
    }
    return [heading(1, '榜单展示时间'), list];
  }

  function deckChoices() { return account.can_upload_decks ? deckSeasons.filter(s => account.deck_seasons.includes(s.id)) : []; }
  async function decks() {
    // Refresh grants when entering: an administrator may have changed them since login.
    account = await api('/me'); applyGrants();
    const available = deckChoices();
    if (!available.length) return [heading(1, '卡组上传'), muted('暂无可上传的赛季')];
    const season = select(available, '上传赛季');
    const link = el('a', 'assistant-button is-primary', '新建卡组');
    const update = () => { link.href = '/admin/assistant/decks/new?season_id=' + encodeURIComponent(season.value); };
    season.addEventListener('change', update); update();
    return [heading(1, '卡组上传', season, link)];
  }

  const navItems = () => document.querySelectorAll('[data-assistant-tab]');
  function applyGrants() {
    const granted = { decks: deckChoices().length > 0, touch: account.can_touch && account.touch_seasons.length > 0 };
    navItems().forEach(node => { if (node.dataset.assistantTab in granted) node.hidden = !granted[node.dataset.assistantTab]; });
  }
  async function navigate(tab) {
    if (dirty && !confirm('放弃未导入的内容？')) return;
    dirty = false; active = tab; const current = ++revision;
    history.replaceState(null, '', tab === 'overview' ? location.pathname : '#' + tab);
    navItems().forEach(node => { const selected = node.dataset.assistantTab === tab; node.classList.toggle('is-active', selected); node.setAttribute('aria-current', selected ? 'page' : 'false'); });
    root.replaceChildren(muted('加载中…'));
    try { const nodes = await ({ overview, reports, lineups, decks, touch })[tab](); if (revision === current) root.replaceChildren(...nodes); }
    catch (error) { if (revision === current) root.replaceChildren(el('p', 'assistant-error', error.message), button('重试', () => navigate(tab), 'assistant-button')); }
  }
  navItems().forEach(node => node.addEventListener('click', () => navigate(node.dataset.assistantTab)));
  window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
  document.querySelector('#assistantLogout').addEventListener('click', async () => {
    if (dirty && !confirm('放弃未导入的内容？')) return;
    await api('/api/logout', { method: 'POST', body: '{}' }); dirty = false; window.location.assign('/auth');
  });

  function renderAvatar(user) {
    if (!window.jccAvatar) return;
    avatarButton.replaceChildren(window.jccAvatar.image(window.jccAvatar.normalize(user.avatar_config || user.avatar_color), 32, '头像'));
    avatarButton.hidden = false;
  }
  async function boot() {
    try {
      const me = await api('/api/me'); csrf = me.csrf_token;
      if (!me.user) { window.location.assign('/auth?next=/admin'); return; }
      [account, { seasons }, { seasons: deckSeasons }] = await Promise.all([api('/me'), api('/lineup-seasons'), api('/deck-seasons')]);
      document.querySelector('#assistantName').textContent = me.user.nickname || me.user.username;
      const expiry = document.querySelector('#assistantExpiry'); expiry.replaceChildren('有效至 ', time(account.expires_at, { month: '2-digit', day: '2-digit' }));
      if (account.can_avatar && window.jccAvatarEditor) {
        renderAvatar(me.user);
        window.jccAvatarEditor.mount(me.user, csrf, { trigger: avatarButton, endpoint: prefix + '/avatar', onSave: renderAvatar });
      }
      applyGrants();
      const target = document.querySelector(`.admin-sidebar [data-assistant-tab="${active}"]`);
      await navigate(target && !target.hidden ? active : 'overview');
    } catch (error) { root.replaceChildren(el('p', 'assistant-error', error.message), button('重试', boot, 'assistant-button')); }
  }
  boot();
})();
