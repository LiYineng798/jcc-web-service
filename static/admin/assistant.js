(() => {
  const { el, button } = window.JccAdminCore;
  const root = document.querySelector('#assistantApp');
  const prefix = '/api/admin/assistant';
  let csrf = '', account, seasons = [], active = 'overview', revision = 0, dirty = false;
  const labels = {
    today_uv: '今日访客', yesterday_uv: '昨日访客', today_new_visitors: '今日新访客', today_returning_visitors: '今日回访',
    today_users: '今日注册', today_logins: '今日登录', today_authenticated_users: '今日活跃账号', today_lineup_copy_count: '今日普通阵容复制',
    today_live_comp_copy_count: '今日实时阵容复制', today_total_copy_count: '今日总复制', total_users: '用户总数', pending_reports_count: '待处理反馈',
    unique_visitors: '独立访客', page_visits: '页面访问', new_visitors: '新访客', returning_visitors: '回访访客', returning_3d: '3 日回访', returning_7d: '7 日回访',
    new_registrations: '注册账号', successful_logins: '登录账号', authenticated_active_users: '活跃账号', lineup_copies: '普通阵容复制', live_comp_copies: '实时阵容复制',
    total_copies: '总复制', new_lineups: '新增阵容', guestbook_messages: '留言数', reports_submitted: '反馈数', like_actions: '点赞数', favorite_actions: '收藏数'
  };
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
  const date = value => value ? new Date(value).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '暂无记录';
  function panel(title, description = '') {
    const box = el('section', 'assistant-panel'); box.append(el('h2', '', title));
    if (description) box.append(el('p', 'admin-meta', description)); return box;
  }
  function table(columns, rows) {
    const wrap = el('div', 'assistant-table-wrap');
    if (!rows.length) { wrap.append(el('p', 'admin-meta', '暂无数据')); return wrap; }
    const node = el('table', 'assistant-table'); const head = el('thead'); const tr = el('tr');
    columns.forEach(([name]) => { const th = el('th', '', name); th.scope = 'col'; tr.append(th); }); head.append(tr); node.append(head);
    const body = el('tbody'); rows.forEach(row => { const tr = el('tr'); columns.forEach(([name, key]) => { const td = el('td', '', String(row[key] ?? '—')); td.dataset.label = name; tr.append(td); }); body.append(tr); });
    node.append(body); wrap.append(node); return wrap;
  }
  function metrics(values) {
    const list = el('dl', 'assistant-metrics');
    Object.keys(labels).filter(key => key in values).map(key => [key, values[key]]).forEach(([key, value]) => { const item = el('div', 'assistant-metric'); item.append(el('dt', '', labels[key]), el('dd', '', String(value))); list.append(item); });
    return list;
  }
  function ranks(rows) {
    return table([['阵容', 'title'], ['赛季', 'season_name'], ['上传者', 'uploader'], ['复制次数', 'copies'], ['复制人数', 'unique_visitors']], rows);
  }
  function field(label, input) { const wrap = el('label', 'assistant-field', label); wrap.append(input); return wrap; }
  function seasonSelect(allowed = null) {
    const select = el('select'); seasons.filter(s => !allowed || allowed.includes(s.id)).forEach(s => { const option = el('option', '', s.name); option.value = s.id; select.append(option); }); return select;
  }
  async function overview() {
    const [data, copies] = await Promise.all([api('/overview'), api('/copy-rank')]);
    const box = panel('运营概览', '查看站点汇总数据，了解大家最近在使用哪些阵容。');
    box.append(metrics(data.stats), el('h3', '', '近七日访问'), table([['日期', 'date'], ['访客', 'uv']], data.traffic_7d));
    const copyBox = panel('复制排行', '仅展示汇总和上传者，不包含访问者身份与 IP。');
    const day = el('input'); day.type = 'date'; day.value = copies.date;
    const result = el('div'); result.append(ranks(copies.items)); let generation = 0;
    day.addEventListener('change', async () => {
      const current = ++generation; result.replaceChildren(el('p', 'admin-meta', '加载中…'));
      try { const data = await api('/copy-rank?date=' + encodeURIComponent(day.value)); if (generation === current) result.replaceChildren(ranks(data.items)); }
      catch (error) { if (generation === current) result.replaceChildren(el('p', 'assistant-error', error.message)); }
    });
    copyBox.append(field('查询日期', day), result); return [box, copyBox];
  }
  async function reports() {
    const data = await api('/daily-reports'); const box = panel('每日报告', '阅读已生成的运营快照。');
    if (!data.items.length) { box.append(el('p', 'admin-meta', '还没有已生成的日报')); return [box]; }
    const select = el('select'); data.items.forEach(item => { const option = el('option', '', item.report_date); option.value = item.report_date; select.append(option); });
    const result = el('div'); let generation = 0;
    async function load() {
      const current = ++generation; result.replaceChildren(el('p', 'admin-meta', '报告加载中…'));
      try {
        const report = await api('/daily-reports/' + select.value); if (current !== generation) return;
        result.replaceChildren(metrics(report.summary), el('h3', '', '复制排行'), ranks(report.top_copied), el('h3', '', '各赛季复制'),
          table([['赛季', 'season_name'], ['复制次数', 'copies'], ['复制人数', 'unique_visitors']], report.season_copy_rank),
          el('h3', '', '页面访问'), table([['页面', 'label'], ['访问次数', 'visits'], ['访客', 'uv']], report.top_pages),
          el('h3', '', '按小时统计'), table([['时段', 'hour'], ['访客', 'uv'], ['访问', 'visits'], ['复制', 'copies']],
            Array.from({ length: 24 }, (_, hour) => ({ hour: `${hour}:00`, uv: report.hourly.uv?.[hour] ?? 0, visits: report.hourly.visits?.[hour] ?? 0, copies: report.hourly.copies?.[hour] ?? 0 }))),
          el('p', 'admin-meta', `报告生成：${date(report.generated_at)}`));
      } catch (error) { if (current === generation) result.replaceChildren(el('p', 'assistant-error', error.message), button('重试', load)); }
    }
    select.addEventListener('change', load); box.append(field('报告日期', select), result); await load(); return [box];
  }
  async function lineups() {
    const list = panel('普通阵容', '查看公开的普通赛季阵容及上传者。'); const select = seasonSelect(); const result = el('div'); let page = 1, generation = 0;
    async function load() {
      const current = ++generation; result.replaceChildren(el('p', 'admin-meta', '阵容加载中…'));
      try {
        const data = await api('/lineups?season_id=' + encodeURIComponent(select.value) + '&page=' + page); if (current !== generation) return;
        result.replaceChildren(table([['阵容', 'name'], ['阵容码', 'code'], ['上传者', 'uploader']], data.items));
        const actions = el('div', 'card-actions'); actions.append(button('上一页', async () => { page--; await load(); }, 'small-button', page <= 1), el('span', 'admin-meta', `第 ${page} 页`), button('下一页', async () => { page++; await load(); }, 'small-button', data.items.length < data.page_size)); result.append(actions);
      } catch (error) { if (current === generation) result.replaceChildren(el('p', 'assistant-error', error.message), button('重试', load)); }
    }
    select.addEventListener('change', () => { page = 1; load(); }); list.append(field('查看赛季', select), result); if (select.value) await load();
    if (!account.can_import) return [list];
    const box = panel('批量导入普通阵容', '每批最多 50 行。先检查预览，再确认导入；重复阵容会跳过，上传者记为当前账号。');
    const season = seasonSelect(account.allowed_seasons); const text = el('textarea'); text.maxLength = 20000; text.placeholder = '每行粘贴一条阵容码，可包含阵容名称';
    const preview = el('div'); const message = el('p', 'assistant-message'); message.setAttribute('role', 'status'); let prepared = null, busy = false;
    const payload = () => ({ season_id: season.value, raw_text: text.value });
    const invalidate = () => { prepared = null; commit.disabled = true; preview.replaceChildren(); message.textContent = ''; dirty = !!text.value; };
    const check = button('检查并预览', async () => {
      if (busy) return; busy = true; check.disabled = true; commit.disabled = true;
      const snapshot = JSON.stringify(payload());
      try {
        const result = await api('/lineups/bulk-import/preview', { method: 'POST', body: snapshot });
        if (JSON.stringify(payload()) !== snapshot) return;
        prepared = snapshot; preview.replaceChildren(table([['阵容', 'name'], ['状态', 'status_label'], ['说明', 'reason']], result.items.map(item => ({ ...item, status_label: ({ importable: '可导入', invalid: '无效', duplicate_existing: '已存在', duplicate_in_upload: '本批重复' })[item.status] || item.status }))));
        message.textContent = `可导入 ${result.importable_count} 条，重复 ${result.duplicate_existing_count + result.duplicate_in_upload_count} 条，无效 ${result.invalid_count} 条。`;
        commit.disabled = !result.importable_count;
      } finally { busy = false; check.disabled = false; }
    });
    const commit = button('确认导入', async () => {
      if (busy || !prepared || prepared !== JSON.stringify(payload())) return;
      busy = true; commit.disabled = true; check.disabled = true; season.disabled = true; text.disabled = true;
      try {
        const result = await api('/lineups/bulk-import', { method: 'POST', body: prepared });
        message.textContent = `已导入 ${result.created_count} 条，跳过重复 ${result.duplicate_existing_count + result.duplicate_in_upload_count} 条。`;
        prepared = null; dirty = false; text.value = ''; preview.replaceChildren(); await load();
      } finally { busy = false; check.disabled = false; season.disabled = false; text.disabled = false; }
    }, 'small-button is-active', true);
    text.addEventListener('input', invalidate); season.addEventListener('change', invalidate);
    const actions = el('div', 'card-actions'); actions.append(check, commit);
    box.append(field('导入赛季', season), field('阵容码', text), actions, message, preview); return [box, list];
  }
  async function touch() {
    const box = panel('榜单更新时间', '确认本赛季榜单已核对后，可将首页显示的更新时间设为现在。此操作不会改动阵容、名次或发布新榜单。');
    const data = await api('/live-seasons');
    if (!data.seasons.length) { box.append(el('p', 'admin-meta', '管理员尚未为此账号授权更新时间维护。')); return [box]; }
    for (const season of data.seasons) {
      const item = el('article', 'automation-card'); const stamp = el('p', 'admin-meta', `当前更新时间：${date(season.updated_at)}`);
      const action = button('更新时间设为现在', async (_, button) => {
        if (!confirm(`确认已核对「${season.name}」榜单，并将更新时间设为现在？`)) return;
        button.disabled = true;
        try { const result = await api('/live-seasons/' + encodeURIComponent(season.id) + '/touch', { method: 'POST', body: '{}' }); stamp.textContent = `已更新：${date(result.updated_at)}`; }
        finally { button.disabled = false; }
      }); item.append(el('h3', '', season.name), stamp, action); box.append(item);
    } return [box];
  }
  async function navigate(tab) {
    if (dirty && !confirm('有尚未导入的内容，离开此页会丢失。继续离开？')) return;
    dirty = false; active = tab; const current = ++revision;
    document.querySelectorAll('[data-assistant-tab]').forEach(node => { const selected = node.dataset.assistantTab === tab; node.classList.toggle('is-active', selected); node.setAttribute('aria-current', selected ? 'page' : 'false'); });
    root.replaceChildren(el('p', 'admin-meta', '正在加载…'));
    try { const nodes = await ({ overview, reports, lineups, touch })[tab](); if (revision === current) root.replaceChildren(...nodes); }
    catch (error) { if (revision === current) root.replaceChildren(el('p', 'assistant-error', error.message), button('重试', () => navigate(tab))); }
  }
  document.querySelectorAll('[data-assistant-tab]').forEach(node => node.addEventListener('click', () => navigate(node.dataset.assistantTab)));
  window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
  document.querySelector('#assistantLogout').addEventListener('click', async () => { if (dirty && !confirm('有尚未导入的内容，确定退出？')) return; await api('/api/logout', { method: 'POST', body: '{}' }); dirty = false; window.location.assign('/auth'); });
  async function boot() {
    try {
      const me = await api('/api/me'); csrf = me.csrf_token;
      if (!me.user) { window.location.assign('/auth?next=/admin'); return; }
      [account, { seasons }] = await Promise.all([api('/me'), api('/lineup-seasons')]);
      document.querySelector('#assistantIdentity').textContent = `${me.user.nickname || me.user.username} · AI 自动化账号 · 有效至 ${date(account.expires_at)}`;
      await navigate(active);
    } catch (error) { root.replaceChildren(el('p', 'assistant-error', error.message), button('重试', boot)); }
  }
  boot();
})();
