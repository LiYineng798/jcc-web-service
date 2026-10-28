(() => {
  const { el, button, revealListStart } = window.JccAdminCore;
  const root = document.querySelector('#assistantApp');
  const summary = document.querySelector('#assistantPermissions');
  const avatarButton = document.querySelector('#assistantAvatar');
  const prefix = '/api/admin/assistant';
  const zone = '北京时间（UTC+8）';
  let csrf = '', account, seasons = [], active = 'overview', revision = 0, dirty = false;
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
  // Fixed to the site's audience zone so browsers in other zones read the same time.
  const date = value => value ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '暂无记录';
  const seasonName = id => seasons.find(s => s.id === id)?.name || id;
  const seasonList = ids => ids.map(seasonName).join('、');
  function panel(title, description = '') {
    const box = el('section', 'assistant-panel'); box.append(el('h2', '', title));
    if (description) box.append(el('p', 'admin-meta', description)); return box;
  }
  function badge(text, tone = '') { return el('span', 'assistant-badge' + (tone ? ' is-' + tone : ''), text); }
  function table(columns, rows, rowClass = null) {
    const wrap = el('div', 'assistant-table-wrap');
    if (!rows.length) { wrap.append(el('p', 'admin-meta', '暂无数据')); return wrap; }
    const node = el('table', 'assistant-table'); const head = el('thead'); const tr = el('tr');
    columns.forEach(([name]) => { const th = el('th', '', name); th.scope = 'col'; tr.append(th); }); head.append(tr); node.append(head);
    const body = el('tbody'); rows.forEach(row => { const tr = el('tr', rowClass?.(row) || ''); columns.forEach(([name, key]) => { const td = el('td', '', String(row[key] ?? '—')); td.dataset.label = name; tr.append(td); }); body.append(tr); });
    node.append(body); wrap.append(node); return wrap;
  }
  function facts(entries) {
    const list = el('dl', 'assistant-facts');
    entries.forEach(([term, value]) => { const item = el('div'); const dd = el('dd'); dd.append(value); item.append(el('dt', '', term), dd); list.append(item); });
    return list;
  }
  function checklist(items) { const list = el('ul', 'assistant-checks'); items.forEach(text => list.append(el('li', '', text))); return list; }
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
  function grant(enabled, ids) { return enabled && ids.length ? seasonList(ids) : null; }
  function renderPermissions() {
    const rows = [
      ['普通阵容批量导入', grant(account.can_import, account.allowed_seasons), 'lineups'],
      ['榜单展示时间维护', grant(account.can_touch, account.touch_seasons), 'touch'],
      ['头像修改', account.can_avatar ? '仅本账号头像' : null, 'avatar'],
    ];
    const title = el('h2', '', '当前权限'); title.id = 'assistantPermissionsTitle';
    const list = el('dl', 'assistant-grants');
    for (const [name, scope, target] of rows) {
      const item = el('div', 'assistant-grant'); const value = el('dd');
      value.append(scope ? badge('已授权', 'ok') : badge('未授权', 'off'), el('span', '', scope ? ' ' + scope : ' 不可操作'));
      if (scope) value.append(target === 'avatar' ? button('修改头像', () => avatarButton.click(), 'small-button assistant-link')
        : button('前往', () => navigate(target), 'small-button assistant-link'));
      item.append(el('dt', '', name), value); list.append(item);
    }
    const detail = el('details', 'assistant-season-grants');
    detail.append(el('summary', '', '按赛季查看授权'), el('p', 'admin-meta', '标为“未授权”的赛季是本账号无权操作，不是功能缺失。'),
      table([['赛季', 'name'], ['批量导入', 'import'], ['展示时间维护', 'touch']], seasons.map(s => ({
        name: s.name,
        import: account.can_import && account.allowed_seasons.includes(s.id) ? '已授权' : '未授权',
        touch: account.can_touch && account.touch_seasons.includes(s.id) ? '已授权' : '未授权',
      }))));
    summary.replaceChildren(title, list,
      el('p', 'admin-meta', `只读：运营概览、每日报告、复制排行、全部公开赛季的普通阵容。前台“新增阵容”、点赞、评论等写操作均未授权。限额：每批导入 ≤${account.limits.rows_per_import} 行，每小时写操作 ≤${account.limits.write_requests_per_hour} 次（导入、展示时间、头像共用）。`),
      detail);
    summary.hidden = false;
  }
  function renderAvatar(user) {
    if (!window.jccAvatar) return;
    avatarButton.replaceChildren(window.jccAvatar.image(window.jccAvatar.normalize(user.avatar_config || user.avatar_color), 40, '本账号头像'));
    avatarButton.hidden = false;
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
          el('p', 'admin-meta', `报告生成：${date(report.generated_at)}（${zone}）`));
      } catch (error) { if (current === generation) result.replaceChildren(el('p', 'assistant-error', error.message), button('重试', load)); }
    }
    select.addEventListener('change', load); box.append(field('报告日期', select), result); await load(); return [box];
  }
  function previewTarget(result) {
    const target = result.target;
    return facts([['目标赛季', target.season_name], ['上传账号', target.uploader], ['发布状态', target.publish_status_label],
      ['校验范围', result.validation.content_parsed ? '格式与内容' : '仅格式（下表“最终名称”即入库名称）']]);
  }
  function previewScope(result) {
    const box = el('div', 'assistant-scope');
    box.append(el('strong', '', result.importable_count ? result.validation.summary : '校验范围：仅格式校验，未解析阵容内容'),
      el('p', 'admin-meta', '本后台只核对文本格式和重复情况，无法展开英雄、装备、站位；请在导入前自行确认阵容码来源。已执行的校验：'),
      checklist([...result.validation.batch_checks, ...result.validation.row_checks]));
    return box;
  }
  function entryRows(items) {
    return items.map(item => ({ ...item, line_label: `第 ${item.line} 行`, name_label: item.name ?? item.raw ?? '—', code_label: item.code ?? '—',
      status_label: statusLabels[item.status] || item.status,
      note: item.reason || (item.status === 'created' ? `已入库，编号 ${item.id}` : '通过全部 5 项格式校验') }));
  }
  const entryColumns = [['行号', 'line_label'], ['最终名称', 'name_label'], ['阵容码', 'code_label'], ['状态', 'status_label'], ['说明', 'note']];
  async function lineups() {
    const list = panel('普通阵容（只读查看）', '可查看全部公开赛季的普通阵容及上传者。');
    const select = seasonSelect(); const result = el('div'); let page = 1, generation = 0, fresh = new Set();
    async function load() {
      const current = ++generation; result.replaceChildren(el('p', 'admin-meta', '阵容加载中…'));
      try {
        const data = await api('/lineups?season_id=' + encodeURIComponent(select.value) + '&page=' + page); if (current !== generation) return;
        result.replaceChildren(table([['阵容', 'name'], ['编号', 'id'], ['阵容码', 'code'], ['上传者', 'uploader']], data.items, row => fresh.has(row.id) ? 'is-new' : ''));
        const actions = el('div', 'card-actions'); actions.append(button('上一页', async () => { page--; await load(); revealListStart(list); }, 'small-button', page <= 1), el('span', 'admin-meta', `第 ${page} 页`), button('下一页', async () => { page++; await load(); revealListStart(list); }, 'small-button', data.items.length < data.page_size)); result.append(actions);
      } catch (error) { if (current === generation) result.replaceChildren(el('p', 'assistant-error', error.message), button('重试', load)); }
    }
    async function showBatch(seasonId, ids) {
      fresh = new Set(ids); select.value = seasonId; page = 1; await load();
      list.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    select.addEventListener('change', () => { page = 1; fresh = new Set(); load(); }); list.append(field('查看赛季', select), result); if (select.value) await load();
    const box = panel('批量导入普通阵容');
    if (!account.can_import || !account.allowed_seasons.length) {
      box.append(badge('未授权', 'off'), el('p', 'admin-meta', '管理员尚未为本账号开放批量导入，当前只能查看下方列表。'));
      return [box, list];
    }
    box.append(el('p', 'admin-meta', `已授权赛季：${seasonList(account.allowed_seasons)}；其他赛季未授权。每批最多 ${account.limits.rows_per_import} 行，先检查预览，再确认导入；重复阵容会跳过。`));
    const season = seasonSelect(account.allowed_seasons); const text = el('textarea'); text.maxLength = 20000; text.placeholder = '每行一条，例如：【阵容码】#S11-九五至尊#ABC123';
    const preview = el('div', 'assistant-preview'); const outcome = el('div', 'assistant-outcome'); const message = el('p', 'assistant-message'); message.setAttribute('role', 'status'); let prepared = null, busy = false;
    const payload = () => ({ season_id: season.value, raw_text: text.value });
    const invalidate = () => { prepared = null; commit.disabled = true; preview.replaceChildren(); message.textContent = ''; dirty = !!text.value; };
    const check = button('检查并预览', async () => {
      if (busy) return; busy = true; check.disabled = true; commit.disabled = true;
      const snapshot = JSON.stringify(payload());
      try {
        const result = await api('/lineups/bulk-import/preview', { method: 'POST', body: snapshot });
        if (JSON.stringify(payload()) !== snapshot) return;
        prepared = snapshot; outcome.replaceChildren();
        preview.replaceChildren(el('h3', '', '导入预览'), previewTarget(result), previewScope(result), table(entryColumns, entryRows(result.items)));
        message.textContent = `可导入 ${result.importable_count} 条，重复 ${result.duplicate_existing_count + result.duplicate_in_upload_count} 条，无效 ${result.invalid_count} 条。确认后将以“${result.target.publish_status_label.split('：')[0]}”状态导入「${result.target.season_name}」。`;
        commit.disabled = !result.importable_count;
      } finally { busy = false; check.disabled = false; }
    });
    const commit = button('确认导入', async () => {
      if (busy || !prepared || prepared !== JSON.stringify(payload())) return;
      busy = true; commit.disabled = true; check.disabled = true; season.disabled = true; text.disabled = true;
      try {
        const result = await api('/lineups/bulk-import', { method: 'POST', body: prepared });
        const skipped = result.duplicate_existing_count + result.duplicate_in_upload_count;
        const ids = result.items.filter(item => item.status === 'created').map(item => item.id);
        message.textContent = `已导入 ${result.created_count} 条到「${result.target.season_name}」，重复跳过 ${skipped} 条，失败 ${result.invalid_count} 条。下方列表已切换到该赛季，本批新增记录已高亮。`;
        prepared = null; dirty = false; text.value = ''; preview.replaceChildren();
        const groups = [['新增', ['created']], ['重复跳过', ['duplicate_existing', 'duplicate_in_upload']], ['失败', ['invalid']]];
        outcome.replaceChildren(el('h3', '', '本批结果'), facts(groups.map(([name, statuses]) => [name, `${result.items.filter(item => statuses.includes(item.status)).length} 条`])));
        for (const [name, statuses] of groups) {
          const rows = result.items.filter(item => statuses.includes(item.status));
          if (rows.length) outcome.append(el('h4', '', `${name}（${rows.length}）`), table(entryColumns, entryRows(rows)));
        }
        outcome.append(button('查看本批结果', () => showBatch(result.season_id, ids)));
        await showBatch(result.season_id, ids);
      } finally { busy = false; check.disabled = false; season.disabled = false; text.disabled = false; }
    }, 'small-button is-active', true);
    text.addEventListener('input', invalidate); season.addEventListener('change', invalidate);
    const actions = el('div', 'card-actions'); actions.append(check, commit);
    box.append(field('导入赛季（仅列出已授权赛季）', season), field('阵容码', text), actions, message, preview, outcome); return [box, list];
  }
  async function touch() {
    const box = panel('榜单展示时间', `只修改首页“榜单更新于”显示的时间，不会重新抓取阵容、刷新排名或发布新榜单。时间均为${zone}。`);
    const data = await api('/live-seasons');
    if (!data.seasons.length) box.append(badge('未授权', 'off'), el('p', 'admin-meta', '管理员尚未为本账号开放榜单展示时间维护。'));
    for (const season of data.seasons) {
      const item = el('article', 'automation-card'); const current = el('span', '', date(season.updated_at)); const result = el('p', 'assistant-message'); result.setAttribute('role', 'status');
      const action = button('将展示时间设为现在', async (_, button) => {
        const before = current.textContent;
        if (!confirm(`将「${season.name}」的榜单展示时间从 ${before}（${zone}）改为现在？\n只改首页显示时间，不会更新阵容或排名。`)) return;
        button.disabled = true;
        try {
          const saved = await api('/live-seasons/' + encodeURIComponent(season.id) + '/touch', { method: 'POST', body: '{}' });
          current.textContent = date(saved.updated_at);
          result.textContent = `已保存：展示时间 ${date(saved.previous_updated_at)} → ${date(saved.updated_at)}（${zone}）。阵容和排名未改动。`;
          window.jccNotify.show(`「${saved.season_name}」展示时间已设为 ${date(saved.updated_at)}`, { variant: 'success' });
        } finally { button.disabled = false; }
      });
      item.append(el('h3', '', season.name), facts([['目标赛季', season.name], ['当前展示时间', current], ['时区', zone], ['影响范围', '仅首页显示时间，不会更新阵容或排名']]), action, result);
      box.append(item);
    }
    const others = seasons.filter(s => !data.seasons.some(item => item.id === s.id));
    if (others.length) {
      const list = el('ul', 'assistant-locked'); others.forEach(s => { const li = el('li', '', s.name + ' '); li.append(badge('未授权', 'off')); list.append(li); });
      box.append(el('h3', '', '其他赛季'), list);
    }
    return [box];
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
      document.querySelector('#assistantIdentity').textContent = `${me.user.nickname || me.user.username} · AI 自动化账号 · 有效至 ${date(account.expires_at)}（${zone}）`;
      renderPermissions();
      if (account.can_avatar && window.jccAvatarEditor) {
        renderAvatar(me.user);
        window.jccAvatarEditor.mount(me.user, csrf, { trigger: avatarButton, endpoint: prefix + '/avatar', onSave: renderAvatar });
      }
      await navigate(active);
    } catch (error) { root.replaceChildren(el('p', 'assistant-error', error.message), button('重试', boot)); }
  }
  boot();
})();
