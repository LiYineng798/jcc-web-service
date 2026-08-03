(async function () {
  const {
    button,
    debounce,
    el,
    escapeAttribute,
    escapeHtml,
    formatPercent,
    todayInputValue,
  } = window.JccAdminCore;
  const root = document.querySelector('#adminApp');
  const dialogRoot = document.querySelector('#adminDialogRoot');
  const elements = {
    themeToggle: document.querySelector('#themeToggle'),
    themeIcon: document.querySelector('#themeIcon'),
    themeText: document.querySelector('#themeText'),
    adminIdentity: document.querySelector('#adminIdentity'),
    adminIdentityName: document.querySelector('#adminIdentity .admin-identity-copy strong'),
    pageTitle: document.querySelector('#adminPageTitle'),
    pageSubtitle: document.querySelector('#adminPageSubtitle'),
    pendingReportCount: document.querySelector('#pendingReportCount'),
    moreButton: document.querySelector('#adminMoreButton'),
    moreDialog: document.querySelector('#adminMoreDialog'),
    moreClose: document.querySelector('#adminMoreClose'),
  };
  if (!root) return;

  const state = {
    me: null,
    csrfToken: '',
    activeTab: 'overview',
    overview: null,
    growth: null,
    growthDate: todayInputValue(),
    reports: { items: [], total: 0, page: 1, page_size: 20, total_pages: 1, status: 'pending', loadedAt: 0 },
    lineups: { items: [], total: 0, page: 1, page_size: 20, total_pages: 1, query: '', searched: false, loadedAt: 0 },
    lineupSeasons: { seasons: [], default_season_id: '', loadedAt: 0 },
    lineupBulkImport: { season_id: '', raw_text: '', result: null, preview_raw_text: '', preview_season_id: '' },
    liveComps: { items: [], total: 0, page: 1, page_size: 20, total_pages: 1, query: '', updated_at: null, source_meta: null, selectedSeasonId: '', loadedAt: 0 },
    liveCompsSeasons: { seasons: [], default_season_id: '', loadedAt: 0 },
    copyRank: { date: '', items: [], loadedAt: 0 },
    liveSeasonCreating: null,
    liveSeasonCreateError: '',
    patchNotes: { items: [], loadedAt: 0 },
    users: { items: [], total: 0, page: 1, page_size: 20, total_pages: 1, query: '', searched: false, loadedAt: 0 },
    audit: { items: [], total: 0, page: 1, page_size: 30, total_pages: 1, loadedAt: 0 },
    settings: { data: {}, loadedAt: 0 },
    noticeData: { data: null, loadedAt: 0 },
    guestbook: { items: [], total: 0, page: 1, page_size: 20, total_pages: 1, loadedAt: 0 },
    controllers: {},
    cacheTtlMs: 30000,
    notice: '',
    passwordUser: null,
    passwordError: '',
    liveCompManualCodeTarget: null,
    liveCompManualCodeError: '',
    patchNoteEditing: null,
    noticeEditing: null,
  };
  const statusText = {
    pending: '待处理',
    resolved: '已处理',
    dismissed: '已驳回',
    normal: '正常',
    hidden: '已隐藏',
    deleted: '已删除',
    active: '正常',
    archived: '已归档',
    disabled: '已禁用',
  };
  const liveSeasonStatusOptions = [
    ['active', '启用展示'],
    ['archived', '归档展示'],
    ['hidden', '后台隐藏'],
    ['disabled', '停用'],
  ];
  const tabMeta = {
    overview: ['运营概览', '今日关键指标与待处理事项'],
    reports: ['举报处理', '核查用户反馈并记录处理结果'],
    lineups: ['阵容管理', '搜索、审核与维护普通阵容'],
    'live-comps': ['实时阵容', '维护赛季状态与阵容码'],
    'patch-notes': ['更新公告', '编辑版本内容与发布状态'],
    users: ['用户管理', '查询账号、权限和可用状态'],
    analytics: ['增长分析', '查看访问、注册与转化数据'],
    audit: ['审计日志', '追踪管理员关键操作记录'],
    guestbook: ['留言管理', '处理访客提交的站点反馈'],
    settings: ['系统设置', '管理功能开关与全站通知'],
  };
  const PATCH_NOTE_TEMPLATE = `## 英雄调整

- [buff] 名称：旧值 => 新值
- [nerf] 名称：旧值 => 新值
- [adjust] 名称：机制说明

## 羁绊调整

- [buff] 名称：旧值 => 新值

## 装备调整

- [nerf] 名称：旧值 => 新值`;

  const renderOverviewDashboardFromModule = window.JccAdminOverview.createOverviewRenderer({
    activateTab,
    button,
    empty,
    getOverview: () => state.overview,
    getCopyRank: () => state.copyRank,
    refreshCopyRank: async () => {
      await loadCopyRank({ force: true });
      render();
    },
    trafficMetric,
    workbenchPanel,
  });

  initTheme();
  elements.themeToggle?.addEventListener('click', () => {
    setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  });
  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-admin-tab]');
    if (!button) return;
    await activateTab(button.dataset.adminTab);
  });
  elements.moreButton?.addEventListener('click', () => elements.moreDialog?.showModal());
  elements.moreClose?.addEventListener('click', () => elements.moreDialog?.close());
  elements.moreDialog?.addEventListener('click', (event) => {
    if (event.target === elements.moreDialog) elements.moreDialog.close();
  });

  refreshIcons();

  await boot();

  async function boot() {
    const me = await fetch('/api/me').then((response) => response.json());
    state.me = me.user;
    state.csrfToken = me.csrf_token;
    await Promise.all([
      loadOverview({ force: true }),
      loadCopyRank({ force: true }),
      loadAdminLiveCompsSeasons({ force: true }),
    ]);
    render();
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': state.csrfToken,
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || '操作失败');
    }
    if (response.status === 204) return null;
    return response.json();
  }

  function isFresh(loadedAt) {
    return loadedAt && (Date.now() - loadedAt < state.cacheTtlMs);
  }

  function abortRequest(key) {
    if (state.controllers[key]) {
      state.controllers[key].abort();
      delete state.controllers[key];
    }
  }

  async function activateTab(tabKey) {
    if (!tabKey) return;
    elements.moreDialog?.close();
    state.activeTab = tabKey;
    render();
    if (tabKey === 'overview') await Promise.all([loadOverview(), loadCopyRank()]);
    if (tabKey === 'reports') await loadReports();
    if (tabKey === 'lineups') await loadLineupSeasons();
    if (tabKey === 'live-comps') await loadAdminLiveComps();
    if (tabKey === 'patch-notes') await loadPatchNotes();
    if (tabKey === 'analytics') await loadGrowth();
    if (tabKey === 'audit') await loadAudit();
    if (tabKey === 'guestbook') await loadGuestbook();
    if (tabKey === 'settings') await Promise.all([loadSettings(), loadNotice()]);
    render();
  }

  async function loadOverview({ force = false } = {}) {
    if (!force && state.overview && isFresh(state.overview.loadedAt)) return;
    const payload = await api('/api/admin/overview');
    state.overview = { ...payload, loadedAt: Date.now() };
  }

  async function loadCopyRank({ force = false } = {}) {
    if (!force && state.copyRank && isFresh(state.copyRank.loadedAt)) return;
    const payload = await api('/api/admin/copy-rank?page_size=10');
    state.copyRank = { ...payload, loadedAt: Date.now() };
  }

  async function loadReports({ force = false } = {}) {
    if (!force && isFresh(state.reports.loadedAt)) return;
    const query = new URLSearchParams({
      status: state.reports.status,
      page: String(state.reports.page),
      page_size: String(state.reports.page_size),
    });
    const payload = await api(`/api/admin/reports?${query.toString()}`);
    state.reports = { ...state.reports, ...payload, loadedAt: Date.now() };
  }

  async function loadLineups({ force = false } = {}) {
    if (!state.lineups.searched) return;
    if (!force && isFresh(state.lineups.loadedAt)) return;
    abortRequest('lineups');
    state.controllers.lineups = new AbortController();
    const query = new URLSearchParams({
      q: state.lineups.query,
      page: String(state.lineups.page),
      page_size: String(state.lineups.page_size),
    });
    const payload = await api(`/api/admin/lineups?${query.toString()}`, { signal: state.controllers.lineups.signal });
    state.lineups = { ...state.lineups, ...payload, loadedAt: Date.now() };
  }

  async function loadLineupSeasons({ force = false } = {}) {
    if (!force && isFresh(state.lineupSeasons.loadedAt)) return;
    const payload = await api('/api/lineup-seasons');
    state.lineupSeasons = { ...payload, loadedAt: Date.now() };
    if (!state.lineupBulkImport.season_id) {
      state.lineupBulkImport.season_id = payload.default_season_id || (payload.seasons?.[0] || {}).id || '';
    }
  }

  async function loadAdminLiveComps({ force = false } = {}) {
    if (!state.liveComps.selectedSeasonId) {
      state.liveComps.selectedSeasonId = state.liveCompsSeasons.default_season_id || (state.liveCompsSeasons.seasons[0] || {}).id || '';
    }
    if (!force && isFresh(state.liveComps.loadedAt)) return;
    abortRequest('liveComps');
    state.controllers.liveComps = new AbortController();
    const query = new URLSearchParams({
      season: state.liveComps.selectedSeasonId,
      page: String(state.liveComps.page),
      page_size: String(state.liveComps.page_size),
    });
    const payload = await api(`/api/admin/live-comps?${query.toString()}`, { signal: state.controllers.liveComps.signal });
    state.liveComps = { ...state.liveComps, ...payload, loadedAt: Date.now() };
  }

  async function loadAdminLiveCompsSeasons({ force = false } = {}) {
    if (!force && isFresh(state.liveCompsSeasons.loadedAt)) return;
    const payload = await api('/api/admin/live-comps/seasons');
    state.liveCompsSeasons = { ...payload, loadedAt: Date.now() };
  }

  async function loadPatchNotes({ force = false } = {}) {
    if (!force && isFresh(state.patchNotes.loadedAt)) return;
    const payload = await api('/api/admin/patch-notes');
    state.patchNotes = { items: payload.items || [], loadedAt: Date.now() };
  }

  async function loadUsers({ force = false } = {}) {
    if (!state.users.searched) return;
    if (!force && isFresh(state.users.loadedAt)) return;
    abortRequest('users');
    state.controllers.users = new AbortController();
    const query = new URLSearchParams({
      q: state.users.query,
      page: String(state.users.page),
      page_size: String(state.users.page_size),
    });
    const payload = await api(`/api/admin/users?${query.toString()}`, { signal: state.controllers.users.signal });
    state.users = { ...state.users, ...payload, loadedAt: Date.now() };
  }

  async function loadAudit({ force = false } = {}) {
    if (!force && isFresh(state.audit.loadedAt)) return;
    const query = new URLSearchParams({
      page: String(state.audit.page),
      page_size: String(state.audit.page_size),
    });
    const payload = await api(`/api/admin/audit-logs?${query.toString()}`);
    state.audit = { ...state.audit, ...payload, loadedAt: Date.now() };
  }

  async function loadGrowth({ force = false } = {}) {
    if (!force && state.growth && state.growth.date === state.growthDate && isFresh(state.growth.loadedAt)) return;
    const payload = await api(`/api/admin/growth?date=${encodeURIComponent(state.growthDate)}`);
    state.growth = { ...payload, loadedAt: Date.now() };
  }

  async function loadSettings({ force = false } = {}) {
    if (!force && isFresh(state.settings.loadedAt)) return;
    const payload = await api('/api/admin/settings');
    state.settings = { data: payload, loadedAt: Date.now() };
  }

  async function loadNotice({ force = false } = {}) {
    if (!force && isFresh(state.noticeData.loadedAt)) return;
    const payload = await api('/api/admin/notice');
    state.noticeData = { data: payload, loadedAt: Date.now() };
  }

  async function loadGuestbook({ force = false } = {}) {
    if (!force && isFresh(state.guestbook.loadedAt)) return;
    const query = new URLSearchParams({
      page: String(state.guestbook.page),
      page_size: String(state.guestbook.page_size),
    });
    const payload = await api(`/api/guestbook?${query.toString()}`);
    state.guestbook = { ...state.guestbook, ...payload, loadedAt: Date.now() };
  }

  function render() {
    syncHeader();
    syncTabs();
    root.classList.remove('admin-app-loading');
    root.replaceChildren();
    if (state.notice) root.append(el('div', 'message admin-inline-message', state.notice));
    if (state.activeTab === 'overview') root.append(renderOverviewDashboardFromModule());
    if (state.activeTab === 'reports') root.append(renderReportsWorkspace());
    if (state.activeTab === 'lineups') root.append(renderLineupsWorkspace());
    if (state.activeTab === 'live-comps') root.append(renderLiveCompsWorkspace());
    if (state.activeTab === 'patch-notes') root.append(renderPatchNotesWorkspace());
    if (state.activeTab === 'users') root.append(renderUsersWorkspace());
    if (state.activeTab === 'analytics') root.append(renderAnalyticsWorkspace());
    if (state.activeTab === 'audit') root.append(renderAuditWorkspace());
    if (state.activeTab === 'guestbook') root.append(renderGuestbookWorkspace());
    if (state.activeTab === 'settings') root.append(renderSettingsWorkspace());
    renderDialogs();
    refreshIcons();
  }

  function syncHeader() {
    if (elements.adminIdentityName) {
      elements.adminIdentityName.textContent = state.me?.nickname || '后台账号';
    }
    const [title, subtitle] = tabMeta[state.activeTab] || tabMeta.overview;
    if (elements.pageTitle) elements.pageTitle.textContent = title;
    if (elements.pageSubtitle) elements.pageSubtitle.textContent = subtitle;
    if (elements.pendingReportCount) {
      elements.pendingReportCount.textContent = String(state.overview?.stats?.pending_reports_count || 0);
    }
  }

  function syncTabs() {
    document.querySelectorAll('[data-admin-tab]').forEach((node) => {
      node.classList.toggle('is-active', node.dataset.adminTab === state.activeTab);
      if (node.matches('.admin-nav-item, .admin-mobile-nav-item')) {
        node.setAttribute('aria-current', node.dataset.adminTab === state.activeTab ? 'page' : 'false');
      }
    });
    const primaryMobileTabs = ['overview', 'reports', 'lineups', 'analytics'];
    elements.moreButton?.classList.toggle('is-active', !primaryMobileTabs.includes(state.activeTab));
  }

  function refreshIcons() {
    window.lucide?.createIcons({ attrs: { 'aria-hidden': 'true' } });
  }

  function renderReportsWorkspace() {
    const panel = workbenchPanel('用户举报', '进入该工作台后再加载数据；支持分页切换');
    const body = panel.querySelector('.admin-workspace-body');
    body.append(renderReportStatusTabs());

    const list = el('div', 'admin-list');
    if (!state.reports.items.length) {
      list.append(empty(state.reports.status === 'pending' ? '暂无待处理举报' : '该状态下没有举报记录'));
    } else {
      state.reports.items.forEach((report) => list.append(reportCard(report)));
    }
    body.append(list, renderPagination('reports'));
    return panel;
  }

  function renderReportStatusTabs() {
    const wrap = el('div', 'admin-filter-pills');
    [
      ['pending', '待处理'],
      ['resolved', '已处理'],
      ['dismissed', '已驳回'],
    ].forEach(([value, label]) => {
      const node = button(label, async () => {
        state.reports.status = value;
        state.reports.page = 1;
        await loadReports({ force: true });
        render();
      }, `small-button ${state.reports.status === value ? 'is-active' : ''}`.trim());
      wrap.append(node);
    });
    return wrap;
  }

  function reportCard(report) {
    const card = el('article', 'admin-card is-alert');
    const head = el('div', 'admin-card-head');
    head.append(el('h3', '', `#${report.id} ${report.lineup_name || '阵容已删除'}`), pill(statusText[report.status] || report.status));
    const meta = el('p', 'admin-meta', `举报人：${report.reporter_nickname || '-'} · 作者：${report.owner_nickname || '-'} · 提交：${report.created_at}`);
    const reason = el('p', 'admin-reason', report.reason);
    const code = el('pre', 'admin-code', report.lineup_code || '无阵容码');
    card.append(head, meta, reason, code);
    if (report.status === 'pending') {
      const actions = el('div', 'card-actions');
      actions.append(
        button('处理并隐藏阵容', () => handleReport(report.id, 'resolved', true)),
        button('仅标记已处理', () => handleReport(report.id, 'resolved', false)),
        button('驳回举报', () => handleReport(report.id, 'dismissed', false), 'small-button danger-button'),
      );
      card.append(actions);
    }
    return card;
  }

  async function handleReport(id, status, hideLineup) {
    const actionText = hideLineup ? '处理举报并隐藏阵容' : (status === 'dismissed' ? '驳回举报' : '标记举报为已处理');
    if (!confirm(`确定要${actionText}吗？`)) return;
    await api(`/api/admin/reports/${id}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ status, hide_lineup: hideLineup }),
    });
    await Promise.all([loadReports({ force: true }), loadOverview({ force: true })]);
    setNotice(hideLineup ? '举报已处理，阵容已隐藏' : '举报状态已更新');
  }

  function renderLineupsWorkspace() {
    const panel = workbenchPanel('阵容管理', '默认不加载列表，输入阵容名、阵容码、作者后开始查找');
    const body = panel.querySelector('.admin-workspace-body');
    body.append(renderLineupBulkImportPanel(), lineupSearchControls());
    if (!state.lineups.searched) {
      body.append(empty('输入阵容名、阵容码、作者后开始查找', 'admin-empty-search'));
      return panel;
    }
    const list = el('div', 'admin-list compact');
    if (!state.lineups.items.length) {
      list.append(empty('没有找到阵容'));
    } else {
      state.lineups.items.forEach((lineup) => {
        const card = el('article', 'admin-row-card');
        const info = el('div');
        info.append(
          el('strong', '', lineup.name),
          el('p', 'admin-meta', `作者：${lineup.owner_nickname || '-'} · ${statusText[lineup.status] || lineup.status} · 赞 ${lineup.like_count} · 复制 ${lineup.copy_count} · 分 ${lineup.score}`),
        );
        const code = el('pre', 'admin-code', lineup.code || '无阵容码');
        info.append(code);
        const actions = el('div', 'card-actions');
        actions.append(
          button(lineup.status === 'hidden' ? '恢复' : '隐藏', async () => {
            await updateLineupStatus(lineup, lineup.status === 'hidden' ? 'normal' : 'hidden');
          }),
          button('调整分数', async () => {
            await adjustScore(lineup);
          }),
        );
        card.append(info, actions);
        list.append(card);
      });
    }
    body.append(list, renderPagination('lineups'));
    return panel;
  }

  function renderLineupBulkImportPanel() {
    const panel = el('div', 'admin-subpanel lineup-bulk-import');
    const head = el('div', 'admin-subpanel-head');
    const title = el('div');
    title.append(el('h3', '', '批量导入阵容码'), el('p', 'admin-meta', '先解析预览，确认名称、赛季和重复项后再写入普通阵容库'));
    head.append(title);

    const form = el('form', 'lineup-bulk-import-form');
    const seasonField = el('label', 'lineup-bulk-import-field');
    seasonField.append(el('span', '', '导入赛季'));
    seasonField.append(renderLineupBulkImportSeasonPicker());

    const codeField = el('label', 'lineup-bulk-import-field');
    codeField.append(el('span', '', '阵容码文本'));
    const textarea = adminTextarea(
      'lineupBulkImportRawText',
      '【阵容码】#Suyu-星守岩雀#MjIwMDQ2MDI3MjA4Mzk1NjkxNzgyNzM4MDk2MTQ2',
      state.lineupBulkImport.raw_text,
      6,
    );
    textarea.addEventListener('input', () => {
      state.lineupBulkImport.raw_text = textarea.value;
    });
    codeField.append(textarea);

    const actions = el('div', 'card-actions');
    const submit = el('button', 'small-button is-active', '解析阵容码');
    submit.type = 'submit';
    submit.disabled = !(state.lineupSeasons.seasons || []).length;
    actions.append(submit);
    if ((state.lineupBulkImport.result?.importable_count || 0) > 0) {
      actions.append(button('确认导入', async (event, buttonNode) => {
        await confirmLineupBulkImport(buttonNode);
      }, 'small-button'));
    }
    form.append(seasonField, codeField, actions);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      state.lineupBulkImport.raw_text = textarea.value;
      state.lineupBulkImport.season_id = document.querySelector('#lineupBulkImportSeasonInput')?.value || '';
      await previewLineupBulkImport(submit);
    });

    setTimeout(setupLineupBulkImportSeasonDropdown, 0);
    panel.append(head, form, renderLineupBulkImportResult());
    return panel;
  }

  function renderLineupBulkImportSeasonPicker() {
    const selected = state.lineupBulkImport.season_id || state.lineupSeasons.default_season_id || '';
    const selectedSeason = (state.lineupSeasons.seasons || []).find((season) => season.id === selected);
    const wrap = el('div', 'season-menu-wrap lineup-bulk-import-season-wrap');
    wrap.id = 'lineupBulkImportSeasonWrap';
    wrap.innerHTML = `
      <button class="account-toggle season-toggle" id="lineupBulkImportSeasonToggle" type="button" aria-haspopup="menu" aria-expanded="false">
        <span id="lineupBulkImportSeasonText">${escapeHtml(selectedSeason?.name || selectedSeason?.id || '请选择赛季')}</span>
        <i class="account-chevron" data-lucide="chevron-down" aria-hidden="true"></i>
      </button>
      <div class="account-menu hidden season-menu" id="lineupBulkImportSeasonMenu" role="menu"></div>
      <input type="hidden" id="lineupBulkImportSeasonInput" value="${escapeAttribute(selected)}" />
    `;
    return wrap;
  }

  function renderLineupBulkImportResult() {
    const result = state.lineupBulkImport.result;
    const wrap = el('div', 'lineup-bulk-import-result');
    if (!result) return wrap;
    const primaryCount = result.created_count ? result.created_count : result.importable_count || 0;
    const primaryLabel = result.created_count ? '已导入' : '可导入';
    const primaryCaption = result.created_count ? '已写入普通阵容库' : '解析成功，待确认写入';
    const metrics = el('div', 'traffic-grid');
    metrics.append(
      trafficMetric(primaryLabel, primaryCount, primaryCaption),
      trafficMetric('库内重复', result.duplicate_existing_count || 0, '已存在，未重复写入'),
      trafficMetric('上传重复', result.duplicate_in_upload_count || 0, '同次粘贴重复，已跳过'),
      trafficMetric('错误', result.invalid_count || 0, '未识别为有效阵容码'),
    );
    wrap.append(metrics);

    const items = result.items || [];
    if (items.length) {
      const list = el('div', 'admin-list compact lineup-bulk-import-result-list');
      items.forEach((item) => {
        const row = el('article', 'admin-row-card');
        const info = el('div');
        info.append(
          el('strong', '', `第 ${item.line} 行 · ${bulkImportStatusLabel(item.status)}${item.name ? ` · ${item.name}` : ''}`),
          el('p', 'admin-meta', item.reason || item.code || item.raw || ''),
        );
        row.append(info);
        list.append(row);
      });
      wrap.append(list);
    }
    return wrap;
  }

  function bulkImportStatusLabel(status) {
    return {
      importable: '可导入',
      created: '已导入',
      duplicate_existing: '库内重复',
      duplicate_in_upload: '上传重复',
      invalid: '无效',
    }[status] || status || '未知';
  }

  function renderLiveCompsWorkspace() {
    const panel = workbenchPanel('实时阵容', '按实时阵容专区整体统计与赛季管理，支持按赛季查看并给缺少阵容码的条目补码');
    const body = panel.querySelector('.admin-workspace-body');
    body.append(renderLiveCompSeasonPicker());
    const updatedRow = el('p', 'admin-meta admin-updated-row');
    updatedRow.append(state.liveComps.updated_at ? `实时阵容数据更新时间：${state.liveComps.updated_at}` : '实时阵容数据更新时间：暂无');
    updatedRow.append(button('更新时间设为现在', async () => {
      await runLiveCompMutation(
        () => api(`/api/admin/live-comps/seasons/${encodeURIComponent(state.liveComps.selectedSeasonId)}/touch-updated-at`, { method: 'POST' }),
        '已把当前赛季的更新时间刷新为现在',
      );
    }, 'small-button'));
    body.append(updatedRow);
    body.append(renderLiveCompMetrics(), el('p', 'admin-meta', `最近统计更新：${state.liveComps.copy_updated_at || '未复制'}`));
    body.append(renderLiveCompItemList(), renderPagination('liveComps'));
    body.append(renderLiveCompSeasonManager());
    return panel;
  }

  function renderLiveCompSeasonPicker() {
    const wrap = el('div', 'admin-filter-pills');
    (state.liveCompsSeasons.seasons || []).forEach((season) => {
      wrap.append(button(season.name || season.id, async () => {
        state.liveComps.selectedSeasonId = season.id;
        state.liveComps.page = 1;
        await loadAdminLiveComps({ force: true });
        render();
      }, `small-button ${state.liveComps.selectedSeasonId === season.id ? 'is-active' : ''}`.trim()));
    });
    return wrap;
  }

  function renderLiveCompMetrics() {
    const metrics = el('div', 'traffic-grid');
    metrics.append(
      trafficMetric('今日复制', state.liveComps.today_copy_count || 0, '今天实时阵容专区所有复制点击'),
      trafficMetric('累计复制', state.liveComps.total_copy_count || 0, '从统计开始至今的所有复制点击'),
    );
    return metrics;
  }

  function renderLiveCompItemList() {
    const list = el('div', 'admin-list compact');
    if (!state.liveComps.items.length) {
      list.append(empty('当前赛季暂无实时阵容'));
      return list;
    }
    state.liveComps.items.forEach((item) => {
      const card = el('article', 'admin-row-card');
      const info = el('div');
      info.append(
        el('strong', '', `${item.tier} · ${item.title}`),
        el('p', 'admin-meta', `ID：${item.id} · 阵容码状态：${item.hasCode ? '有' : '无'} · 来源：${item.codeSource === 'manual' ? '管理员补码' : item.codeSource === 'original' ? '原始阵容码' : '暂无阵容码'}`),
      );
      if (item.hasCode) {
        info.append(el('pre', 'admin-code', item.resolvedJccCode || item.jccCode || ''));
      }
      const actions = el('div', 'card-actions');
      if (!item.hasCode && !item.originalJccCode) {
        actions.append(button('补码', async () => openLiveCompManualCodeDialog(item)));
      }
      card.append(info, actions);
      list.append(card);
    });
    return list;
  }

  function renderLiveCompSeasonManager() {
    const seasonPanel = el('div', 'admin-subpanel');
    const seasonHeader = el('div', 'admin-subpanel-head');
    seasonHeader.append(el('h3', '', '赛季管理'));
    seasonHeader.append(button('新增赛季', () => {
      state.liveSeasonCreating = { id: '', name: '', description: '', status: 'active' };
      state.liveSeasonCreateError = '';
      renderDialogs();
    }));
    seasonHeader.append(button('刷新赛季', async () => {
      await loadAdminLiveCompsSeasons({ force: true });
      render();
    }));
    seasonPanel.append(seasonHeader);

    const seasonList = el('div', 'admin-season-list');
    const seasons = state.liveCompsSeasons.seasons || [];
    seasons.forEach((season, index) => {
      const card = el('article', 'admin-season-card');
      const info = el('div', 'admin-season-info');
      info.append(
        el('strong', '', season.name || season.id),
        el('p', 'admin-meta', `顺序 ${Number(season.order || index + 1)} · ${season.id} · ${statusText[season.status] || season.status || '正常'} · ${season.description || '无说明'}`),
      );
      const controls = el('div', 'admin-season-controls');
      controls.append(
        button('上移', async () => {
          await moveLiveCompSeason(season, -1);
        }, 'small-button', index === 0),
        button('下移', async () => {
          await moveLiveCompSeason(season, 1);
        }, 'small-button', index === seasons.length - 1),
      );
      liveSeasonStatusOptions.forEach(([status, label]) => {
        controls.append(button(label, async () => {
          await runLiveCompMutation(
            () => api(`/api/admin/live-comps/seasons/${encodeURIComponent(season.id)}`, {
              method: 'PUT',
              body: JSON.stringify({ status }),
            }),
            `已将「${season.name || season.id}」设为${label}`,
          );
        }, `small-button${season.status === status ? ' is-active' : ''}`));
      });
      if (season.id !== state.liveCompsSeasons.default_season_id) {
        controls.append(button('设为默认', async () => {
          await runLiveCompMutation(
            () => api(`/api/admin/live-comps/seasons/${encodeURIComponent(season.id)}`, {
              method: 'PUT',
              body: JSON.stringify({ default_season_id: season.id }),
            }),
            `已将「${season.name || season.id}」设为默认赛季`,
          );
        }));
      }
      card.append(info, controls);
      seasonList.append(card);
    });
    seasonPanel.append(seasonList);
    return seasonPanel;
  }

  async function moveLiveCompSeason(season, direction) {
    const seasons = state.liveCompsSeasons.seasons || [];
    const currentIndex = seasons.findIndex((item) => item.id === season.id);
    if (currentIndex < 0) return;
    const nextIndex = Math.max(0, Math.min(seasons.length - 1, currentIndex + direction));
    if (nextIndex === currentIndex) return;
    const nextOrder = nextIndex + 1;
    await runLiveCompMutation(
      () => api(`/api/admin/live-comps/seasons/${encodeURIComponent(season.id)}`, {
        method: 'PUT',
        body: JSON.stringify({ order: nextOrder }),
      }),
      `已调整「${season.name || season.id}」的赛季顺序`,
    );
  }

  async function runLiveCompMutation(action, successMessage) {
    try {
      const result = await action();
      if (result?.updated_at) state.liveComps.updated_at = result.updated_at;
      await loadAdminLiveCompsSeasons({ force: true });
      // A successful manifest/file mutation should not be reported as failed
      // merely because the follow-up data refresh is temporarily unavailable.
      try {
        await loadAdminLiveComps({ force: true });
      } catch (refreshError) {
        console.warn('实时阵容操作已完成，但刷新详情失败', refreshError);
      }
      setNotice(successMessage);
    } catch (error) {
      setNotice(error.message || '操作失败');
    }
    render();
  }

  function lineupSearchControls() {
    const wrap = el('form', 'admin-search');
    const input = el('input');
    input.type = 'search';
    input.placeholder = '搜索阵容名、阵容码、作者';
    input.value = state.lineups.query;
    const submit = el('button', 'small-button', '查找');
    submit.type = 'submit';
    const reset = button('清空', async () => {
      abortRequest('lineups');
      state.lineups = { ...state.lineups, items: [], total: 0, page: 1, total_pages: 1, query: '', searched: false, loadedAt: 0 };
      input.value = '';
      render();
    });
    const triggerSearch = debounce(async () => {
      const nextValue = input.value.trim();
      if (!nextValue) return;
      state.lineups.query = nextValue;
      state.lineups.page = 1;
      state.lineups.searched = true;
      await loadLineups({ force: true });
      render();
    }, 360);
    input.addEventListener('input', () => {
      if (!input.value.trim()) {
        abortRequest('lineups');
        state.lineups = { ...state.lineups, items: [], total: 0, page: 1, total_pages: 1, query: '', searched: false, loadedAt: 0 };
        render();
        return;
      }
      triggerSearch();
    });
    wrap.addEventListener('submit', async (event) => {
      event.preventDefault();
      const nextValue = input.value.trim();
      if (!nextValue) {
        render();
        return;
      }
      state.lineups.query = nextValue;
      state.lineups.page = 1;
      state.lineups.searched = true;
      await loadLineups({ force: true });
      render();
    });
    wrap.append(input, submit, reset);
    return wrap;
  }

  function liveCompSearchControls() {
    const wrap = el('form', 'admin-search');
    const input = el('input');
    input.type = 'search';
    input.placeholder = '搜索阵容名或 ID';
    input.value = state.liveComps.query;
    const submit = el('button', 'small-button', '查找');
    submit.type = 'submit';
    const reset = button('清空', async () => {
      abortRequest('liveComps');
      state.liveComps = { ...state.liveComps, items: [], total: 0, page: 1, total_pages: 1, query: '', loadedAt: 0 };
      input.value = '';
      await loadAdminLiveComps({ force: true });
      render();
    });
    const triggerSearch = debounce(async () => {
      state.liveComps.query = input.value.trim();
      state.liveComps.page = 1;
      await loadAdminLiveComps({ force: true });
      render();
    }, 360);
    input.addEventListener('input', () => {
      triggerSearch();
    });
    wrap.addEventListener('submit', async (event) => {
      event.preventDefault();
      state.liveComps.query = input.value.trim();
      state.liveComps.page = 1;
      await loadAdminLiveComps({ force: true });
      render();
    });
    wrap.append(input, submit, reset);
    return wrap;
  }

  async function previewLineupBulkImport(buttonNode) {
    const rawText = state.lineupBulkImport.raw_text.trim();
    if (!rawText) {
      setNotice('请粘贴阵容码');
      return;
    }
    if (buttonNode) buttonNode.disabled = true;
    try {
      const result = await api('/api/admin/lineups/bulk-import/preview', {
        method: 'POST',
        body: JSON.stringify({
          season_id: state.lineupBulkImport.season_id,
          raw_text: rawText,
        }),
      });
      state.lineupBulkImport.result = result;
      state.lineupBulkImport.preview_raw_text = rawText;
      state.lineupBulkImport.preview_season_id = state.lineupBulkImport.season_id;
      setNotice(`解析完成：可导入 ${result.importable_count || 0} 条，错误 ${result.invalid_count || 0} 条`);
      render();
    } catch (error) {
      alert(error.message || '解析失败，请检查内容后重试');
      if (buttonNode) buttonNode.disabled = false;
    }
  }

  async function confirmLineupBulkImport(buttonNode) {
    const rawText = document.querySelector('#lineupBulkImportRawText')?.value?.trim() || '';
    const seasonId = document.querySelector('#lineupBulkImportSeasonInput')?.value || '';
    if (!state.lineupBulkImport.result || !state.lineupBulkImport.preview_raw_text) {
      setNotice('请先解析阵容码');
      return;
    }
    if (rawText !== state.lineupBulkImport.preview_raw_text || seasonId !== state.lineupBulkImport.preview_season_id) {
      setNotice('阵容码文本或赛季已变化，请重新解析');
      return;
    }
    if (!confirm(`确认导入 ${state.lineupBulkImport.result.importable_count || 0} 条阵容吗？`)) return;
    if (buttonNode) buttonNode.disabled = true;
    try {
      const result = await api('/api/admin/lineups/bulk-import', {
        method: 'POST',
        body: JSON.stringify({
          season_id: seasonId,
          raw_text: rawText,
        }),
      });
      state.lineupBulkImport.result = result;
      state.lineupBulkImport.preview_raw_text = rawText;
      state.lineupBulkImport.preview_season_id = seasonId;
      if (state.lineups.searched) {
        await loadLineups({ force: true });
      }
      await loadOverview({ force: true });
      setNotice(`导入完成：新增 ${result.created_count || 0} 条，跳过 ${Number(result.duplicate_existing_count || 0) + Number(result.duplicate_in_upload_count || 0)} 条`);
      render();
    } catch (error) {
      alert(error.message || '导入失败，请检查内容后重试');
      if (buttonNode) buttonNode.disabled = false;
    }
  }

  async function updateLineupStatus(lineup, status) {
    await api(`/api/admin/lineups/${lineup.id}`, { method: 'PUT', body: JSON.stringify({ status }) });
    await Promise.all([loadLineups({ force: true }), loadOverview({ force: true })]);
    setNotice(status === 'hidden' ? '阵容已隐藏' : '阵容已恢复');
  }

  async function adjustScore(lineup) {
    const likeValue = prompt('设置管理员点赞修正数', lineup.admin_like_adjustment || 0);
    if (likeValue === null) return;
    const copyValue = prompt('设置管理员复制修正数', lineup.admin_copy_adjustment || 0);
    if (copyValue === null) return;
    await api(`/api/admin/lineups/${lineup.id}/adjust-score`, {
      method: 'POST',
      body: JSON.stringify({ admin_like_adjustment: Number(likeValue), admin_copy_adjustment: Number(copyValue) }),
    });
    await loadLineups({ force: true });
    setNotice('热度修正已保存');
  }

  function renderUsersWorkspace() {
    const panel = workbenchPanel('用户管理', '默认不加载列表，搜索用户名、邮箱或昵称后开始查找');
    const body = panel.querySelector('.admin-workspace-body');
    body.append(userSearchControls());
    if (!state.users.searched) {
      body.append(empty('搜索用户名、邮箱或昵称后开始查找', 'admin-empty-search'));
      return panel;
    }
    const list = el('div', 'admin-list compact');
    if (!state.users.items.length) {
      list.append(empty('没有找到用户'));
    } else {
      state.users.items.forEach((user) => {
        const card = el('article', 'admin-row-card');
        const info = el('div');
        info.append(
          el('strong', '', `${user.nickname}（${user.username}）`),
          el('p', 'admin-meta', `${user.email} · ${user.role} · ${statusText[user.status] || user.status} · 注册 ${user.created_at}`),
        );
        const actions = el('div', 'card-actions');
        actions.append(button('修改密码', async () => {
          openPasswordDialog(user);
        }));
        if (user.status !== 'disabled') {
          actions.append(button('禁用', async () => {
            await disableUser(user.id);
          }, 'small-button danger-button'));
        }
        card.append(info, actions);
        list.append(card);
      });
    }
    body.append(list, renderPagination('users'));
    return panel;
  }

  function userSearchControls() {
    const wrap = el('form', 'admin-search');
    const input = el('input');
    input.type = 'search';
    input.placeholder = '搜索用户名、邮箱或昵称';
    input.value = state.users.query;
    const submit = el('button', 'small-button', '查找');
    submit.type = 'submit';
    const reset = button('清空', async () => {
      abortRequest('users');
      state.users = { ...state.users, items: [], total: 0, page: 1, total_pages: 1, query: '', searched: false, loadedAt: 0 };
      input.value = '';
      render();
    });
    const triggerSearch = debounce(async () => {
      const nextValue = input.value.trim();
      if (!nextValue) return;
      state.users.query = nextValue;
      state.users.page = 1;
      state.users.searched = true;
      await loadUsers({ force: true });
      render();
    }, 360);
    input.addEventListener('input', () => {
      if (!input.value.trim()) {
        abortRequest('users');
        state.users = { ...state.users, items: [], total: 0, page: 1, total_pages: 1, query: '', searched: false, loadedAt: 0 };
        render();
        return;
      }
      triggerSearch();
    });
    wrap.addEventListener('submit', async (event) => {
      event.preventDefault();
      const nextValue = input.value.trim();
      if (!nextValue) {
        render();
        return;
      }
      state.users.query = nextValue;
      state.users.page = 1;
      state.users.searched = true;
      await loadUsers({ force: true });
      render();
    });
    wrap.append(input, submit, reset);
    return wrap;
  }

  function renderAnalyticsWorkspace() {
    const panel = workbenchPanel('增长分析', '按自然日查询，不在首页默认加载', growthDateControl());
    const body = panel.querySelector('.admin-workspace-body');
    const growth = state.growth || {};
    const list = el('div', 'admin-list compact');
    [
      ['首页 UV', growth.home_uv || 0],
      ['点击登录入口人数', growth.login_entry_visitors || 0],
      ['进入登录页面人数', growth.auth_page_visitors || 0],
      ['注册成功人数', growth.successful_registrations || 0],
      ['登录成功人数', growth.successful_logins || 0],
      ['游客尝试点赞人数', growth.guest_like_visitors || 0],
      ['游客尝试收藏人数', growth.guest_favorite_visitors || 0],
      ['登录后 10 分钟内完成点赞人数', growth.post_login_like_users || 0],
      ['登录后 10 分钟内完成收藏人数', growth.post_login_favorite_users || 0],
      ['登录后 10 分钟内上传阵容人数', growth.post_login_create_lineup_users || 0],
    ].forEach(([label, value]) => {
      const card = el('article', 'admin-row-card');
      card.append(el('strong', '', label), el('span', 'admin-meta', String(value)));
      list.append(card);
    });

    const rates = el('div', 'admin-list compact');
    [
      ['登录入口到登录页转化率', formatPercent(growth.conversion_rates?.entry_to_auth_page_pct)],
      ['登录页到注册/登录成功转化率', formatPercent(growth.conversion_rates?.auth_page_to_auth_success_pct)],
      ['登录后完成点赞转化率', formatPercent(growth.conversion_rates?.auth_success_to_like_pct)],
      ['登录后完成收藏转化率', formatPercent(growth.conversion_rates?.auth_success_to_favorite_pct)],
      ['登录后上传阵容转化率', formatPercent(growth.conversion_rates?.auth_success_to_create_lineup_pct)],
    ].forEach(([label, value]) => {
      const card = el('article', 'admin-row-card');
      card.append(el('strong', '', label), el('span', 'admin-meta', value));
      rates.append(card);
    });
    body.append(list, rates);
    return panel;
  }

  function growthDateControl() {
    const wrap = el('form', 'admin-search');
    const input = el('input');
    input.type = 'date';
    input.value = state.growthDate;
    const submit = el('button', 'small-button', '查询');
    submit.type = 'submit';
    const reset = button('今天', async () => {
      state.growthDate = todayInputValue();
      await loadGrowth({ force: true });
      render();
    });
    wrap.append(input, submit, reset);
    wrap.addEventListener('submit', async (event) => {
      event.preventDefault();
      state.growthDate = input.value || todayInputValue();
      await loadGrowth({ force: true });
      render();
    });
    return wrap;
  }

  function renderAuditWorkspace() {
    const panel = workbenchPanel('审计日志', '进入该工作台后再加载，支持分页查看最近后台操作');
    const body = panel.querySelector('.admin-workspace-body');
    const list = el('div', 'admin-log-list');
    if (!state.audit.items.length) {
      list.append(empty('暂无审计日志'));
    } else {
      state.audit.items.forEach((log) => {
        const item = el('div', 'admin-log-item');
        item.append(el('strong', '', log.action), el('span', '', `${log.target_type} #${log.target_id || '-'} · ${log.created_at}`));
        list.append(item);
      });
    }
    body.append(list, renderPagination('audit'));
    return panel;
  }

  function renderPatchNotesWorkspace() {
    const panel = workbenchPanel('更新公告', '维护游戏官网更新公告、精简版和原文归档');
    const body = panel.querySelector('.admin-workspace-body');
    const actions = el('div', 'card-actions');
    actions.append(button('新增公告', () => {
      state.patchNoteEditing = emptyPatchNoteDraft();
      render();
    }, 'small-button'));
    body.append(actions);

    if (state.patchNoteEditing) {
      body.append(renderPatchNoteForm(state.patchNoteEditing));
    }

    const list = el('div', 'admin-list');
    if (!state.patchNotes.items.length) {
      list.append(empty('暂无更新公告'));
    } else {
      state.patchNotes.items.forEach((item) => list.append(patchNoteAdminCard(item)));
    }
    body.append(list);
    return panel;
  }

  function emptyPatchNoteDraft() {
    return {
      id: null,
      title: '',
      version: '',
      source_url: '',
      summary_markdown: PATCH_NOTE_TEMPLATE,
      original_text: '',
      status: 'draft',
      published_at: todayInputValue(),
    };
  }

  function patchNoteAdminCard(item) {
    const card = el('article', 'admin-card admin-card-tight');
    const head = el('div', 'admin-card-head');
    head.append(el('h3', '', item.title), el('span', 'admin-pill', item.status));
    const meta = el('p', 'admin-meta', `${item.version || '版本公告'} · ${item.published_at} · 更新 ${item.updated_at}`);
    const actions = el('div', 'card-actions');
    actions.append(
      button('编辑', () => {
        state.patchNoteEditing = { ...item };
        render();
      }, 'small-button'),
      button(item.status === 'published' ? '下线' : '发布', async () => {
        await savePatchNote({ ...item, status: item.status === 'published' ? 'hidden' : 'published' });
      }, 'small-button'),
      button('隐藏', async () => {
        if (!confirm('确定隐藏这条公告吗？')) return;
        await api(`/api/admin/patch-notes/${item.id}`, { method: 'DELETE' });
        await loadPatchNotes({ force: true });
        setNotice('公告已隐藏');
        state.patchNoteEditing = null;
        render();
      }, 'small-button danger-button'),
    );
    card.append(head, meta, actions);
    return card;
  }

  function renderPatchNoteForm(item) {
    const form = el('form', 'admin-card');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const payload = readPatchNoteForm();
      await savePatchNote(payload);
    });

    const fields = el('div');
    fields.style.cssText = 'display:grid;gap:12px;width:100%';
    fields.append(
      adminInput('patchNoteTitle', '标题', item.title),
      adminInput('patchNoteVersion', '版本号，例如 17.4', item.version),
      adminInput('patchNotePublishedAt', '发布日期，例如 2026-05-28', item.published_at),
      adminInput('patchNoteSourceUrl', '来源链接（可选）', item.source_url),
      adminTextarea('patchNoteSummary', '精简版 Markdown', item.summary_markdown, 10),
      adminTextarea('patchNoteOriginal', '原文（可选）', item.original_text, 10),
    );

    const statusRow = el('div', 'card-actions');
    ['draft', 'published', 'hidden'].forEach((status) => {
      statusRow.append(button(status, () => {
        document.querySelector('#patchNoteStatus').value = status;
        renderPatchNoteStatusButtons(statusRow, status);
      }, `small-button${item.status === status ? ' is-active' : ''}`));
    });
    const hiddenStatus = el('input');
    hiddenStatus.type = 'hidden';
    hiddenStatus.id = 'patchNoteStatus';
    hiddenStatus.value = item.status || 'draft';
    fields.append(hiddenStatus, statusRow);

    const actions = el('div', 'card-actions');
    actions.append(
      button('插入模板', () => {
        document.querySelector('#patchNoteSummary').value = PATCH_NOTE_TEMPLATE;
      }, 'small-button'),
      button('取消', () => {
        state.patchNoteEditing = null;
        render();
      }, 'small-button'),
    );
    const submit = el('button', 'small-button is-active', item.id ? '保存公告' : '创建公告');
    submit.type = 'submit';
    actions.append(submit);
    form.append(fields, actions);
    return form;
  }

  function renderPatchNoteStatusButtons(row, activeStatus) {
    row.querySelectorAll('.small-button').forEach((buttonNode) => {
      buttonNode.classList.toggle('is-active', buttonNode.textContent === activeStatus);
    });
  }

  function adminInput(id, placeholder, value) {
    const input = el('input');
    input.id = id;
    input.placeholder = placeholder;
    input.value = value || '';
    return input;
  }

  function adminTextarea(id, placeholder, value, rows) {
    const textarea = el('textarea');
    textarea.id = id;
    textarea.placeholder = placeholder;
    textarea.value = value || '';
    textarea.rows = rows;
    return textarea;
  }

  function readPatchNoteForm() {
    return {
      id: state.patchNoteEditing?.id || null,
      title: document.querySelector('#patchNoteTitle')?.value?.trim() || '',
      version: document.querySelector('#patchNoteVersion')?.value?.trim() || '',
      published_at: document.querySelector('#patchNotePublishedAt')?.value?.trim() || '',
      source_url: document.querySelector('#patchNoteSourceUrl')?.value?.trim() || '',
      summary_markdown: document.querySelector('#patchNoteSummary')?.value?.trim() || '',
      original_text: document.querySelector('#patchNoteOriginal')?.value?.trim() || '',
      status: document.querySelector('#patchNoteStatus')?.value || 'draft',
    };
  }

  async function savePatchNote(payload) {
    const url = payload.id ? `/api/admin/patch-notes/${payload.id}` : '/api/admin/patch-notes';
    const method = payload.id ? 'PUT' : 'POST';
    await api(url, { method, body: JSON.stringify(payload) });
    await loadPatchNotes({ force: true });
    state.patchNoteEditing = null;
    setNotice('公告已保存');
    render();
  }

  async function toggleSimulator(enabled, actionsPanel) {
    try {
      await api('/api/admin/settings', {
        method: 'PUT',
        body: JSON.stringify({ simulator_enabled: enabled ? 'true' : 'false' }),
      });
      await loadSettings({ force: true });
      setNotice(enabled ? '阵容模拟器已开启' : '阵容模拟器已关闭');
      render();
    } catch (error) {
      alert(error.message || '保存失败');
    }
  }

  async function toggleNotice(enabled) {
    await api('/api/admin/notice', {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    });
    await loadNotice({ force: true });
    setNotice(enabled ? '通知已开启' : '通知已关闭');
    render();
  }

  async function saveNoticeContent() {
    openNoticeDialog(null);
  }

  async function activateNotice(noticeId) {
    await api(`/api/admin/notices/${noticeId}/activate`, { method: 'POST' });
    await loadNotice({ force: true });
    setNotice('已切换展示公告');
    render();
  }

  async function deleteNotice(noticeId) {
    if (!confirm('确定删除这条通知吗？')) return;
    await api(`/api/admin/notices/${noticeId}`, { method: 'DELETE' });
    await loadNotice({ force: true });
    setNotice('通知已删除');
    render();
  }

  function openNoticeDialog(notice) {
    state.noticeEditing = notice || { title: '', message: '', link_url: '', link_text: '', jump_season_id: '', jump_tab: '', marquee_enabled: true };
    renderDialogs();
  }

  function closeNoticeDialog() {
    state.noticeEditing = null;
    renderDialogs();
  }

  function setupJumpDropdown(wrapId, toggleId, menuId, inputId, items, selectedValue, placeholder, onSelect) {
    var wrap = document.getElementById(wrapId);
    var toggle = document.getElementById(toggleId);
    var menu = document.getElementById(menuId);
    var input = document.getElementById(inputId);
    if (!wrap || !toggle || !menu || !input) return;

    var textEl = toggle.querySelector('span:first-child');

    function closeMenu() {
      menu.classList.add('hidden');
      toggle.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
    }

    function openMenu() {
      menu.classList.remove('hidden');
      toggle.classList.add('is-open');
      toggle.setAttribute('aria-expanded', 'true');
    }

    function selectItem(value, label) {
      input.value = value;
      if (textEl) textEl.textContent = label || placeholder;
      if (onSelect) onSelect(value);
      closeMenu();
    }

    toggle.addEventListener('click', function (event) {
      event.stopPropagation();
      if (menu.classList.contains('hidden')) { openMenu(); } else { closeMenu(); }
    });

    document.addEventListener('click', function (event) {
      if (!wrap.contains(event.target)) closeMenu();
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') closeMenu();
    });

    menu.replaceChildren();
    // "不跳转" option
    var noneBtn = document.createElement('button');
    noneBtn.type = 'button';
    noneBtn.className = 'account-menu-item' + (!selectedValue ? ' is-active' : '');
    noneBtn.textContent = placeholder;
    noneBtn.addEventListener('click', function () { selectItem('', placeholder); });
    menu.append(noneBtn);

    // item options
    items.forEach(function (opt) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'account-menu-item' + (opt.value === selectedValue ? ' is-active' : '');
      btn.textContent = opt.label;
      btn.addEventListener('click', function () { selectItem(opt.value, opt.label); });
      menu.append(btn);
    });

    // set initial display text
    if (selectedValue) {
      var found = items.find(function (it) { return it.value === selectedValue; });
      if (found && textEl) textEl.textContent = found.label;
    }
  }

  function setupJumpSeasonDropdown(form, item) {
    var selected = item.jump_season_id || '';
    fetch('/api/lineup-seasons')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var items = (data.seasons || []).map(function (s) { return { value: s.id, label: s.name || s.id }; });
        setupJumpDropdown('noticeJumpSeasonWrap', 'noticeJumpSeasonToggle', 'noticeJumpSeasonMenu', 'noticeJumpSeasonInput', items, selected, '不跳转');
      })
      .catch(function () {});
  }

  function setupLineupBulkImportSeasonDropdown() {
    var selected = state.lineupBulkImport.season_id || state.lineupSeasons.default_season_id || '';
    var items = (state.lineupSeasons.seasons || []).map(function (season) {
      return { value: season.id, label: season.name || season.id };
    });
    setupJumpDropdown(
      'lineupBulkImportSeasonWrap',
      'lineupBulkImportSeasonToggle',
      'lineupBulkImportSeasonMenu',
      'lineupBulkImportSeasonInput',
      items,
      selected,
      '请选择赛季',
      function (value) {
        state.lineupBulkImport.raw_text = document.querySelector('#lineupBulkImportRawText')?.value || state.lineupBulkImport.raw_text;
        state.lineupBulkImport.season_id = value;
        state.lineupBulkImport.result = null;
        state.lineupBulkImport.preview_raw_text = '';
        state.lineupBulkImport.preview_season_id = '';
        render();
      },
    );
  }

  function setupJumpTabDropdown(form, item) {
    var selected = item.jump_tab || '';
    var items = [
      { value: 'live', label: '实时阵容排行' },
      { value: 'latest', label: '最新' },
      { value: 'hot', label: '最热' },
      { value: 'rising', label: '上升' },
      { value: 'recommended', label: '推荐' },
      { value: 'ss', label: 'SS' },
    ];
    setupJumpDropdown('noticeJumpTabWrap', 'noticeJumpTabToggle', 'noticeJumpTabMenu', 'noticeJumpTabInput', items, selected, '不跳转');
  }

  function renderSettingsWorkspace() {
    const panel = workbenchPanel('站点设置', '控制前台功能的开关状态');
    const body = panel.querySelector('.admin-workspace-body');

    const card = el('article', 'admin-row-card');
    const info = el('div');
    info.append(
      el('strong', '', '阵容模拟器'),
      el('p', 'admin-meta', '控制前台导航栏中阵容模拟器入口的显示与隐藏'),
    );

    const enabled = (state.settings.data || {}).simulator_enabled === 'true';

    const actions = el('div', 'card-actions');
    actions.append(
      button('开启', () => toggleSimulator(true), `small-button${enabled ? ' is-active' : ''}`),
      button('关闭', () => toggleSimulator(false), `small-button${!enabled ? ' is-active' : ''}`),
    );

    card.append(info, actions);
    body.append(card);

    const noticeData = state.noticeData.data || {};
    const noticeEnabled = noticeData.enabled ?? false;
    const notices = noticeData.items || [];

    const noticePanel = workbenchPanel('全站通知', '编辑首页通知横幅的内容和状态');
    const noticeBody = noticePanel.querySelector('.admin-workspace-body');

    const toggleRow = el('article', 'admin-row-card');
    const toggleInfo = el('div');
    toggleInfo.append(
      el('strong', '', '启用通知'),
      el('p', 'admin-meta', '开启后首页将展示通知横幅'),
    );
    const toggleActions = el('div', 'card-actions');
    toggleActions.append(
      button('开启', () => toggleNotice(true), `small-button${noticeEnabled ? ' is-active' : ''}`),
      button('关闭', () => toggleNotice(false), `small-button${!noticeEnabled ? ' is-active' : ''}`),
    );
    toggleRow.append(toggleInfo, toggleActions);
    noticeBody.append(toggleRow);

    const listHead = el('div', 'admin-section-head');
    listHead.append(
      el('div', '', ''),
      button('新增通知', saveNoticeContent, 'small-button is-active'),
    );
    noticeBody.append(listHead);

    const list = el('div', 'admin-list');
    if (!notices.length) {
      list.append(empty('暂无全站通知'));
    } else {
      notices.forEach((item) => {
        const card = el('article', 'admin-row-card');
        const info = el('div');
        const title = el('strong', '', item.title);
        const metaParts = [
          item.is_active ? '当前展示' : '未展示',
          item.marquee_enabled === false ? '静止' : '',
          item.updated_at ? `更新 ${item.updated_at}` : '',
        ].filter(Boolean);
        info.append(
          title,
          el('p', 'admin-meta', metaParts.join(' · ')),
          el('p', 'admin-reason', item.message),
        );
        if (item.jump_season_id && item.jump_tab) {
          var tabNames = { live: '实时阵容排行', latest: '最新', hot: '最热', rising: '上升', recommended: '推荐', ss: 'SS' };
          var tabName = tabNames[item.jump_tab] || item.jump_tab;
          info.append(el('p', 'admin-meta', '页内跳转: ' + item.jump_season_id + ' · ' + tabName));
        } else if (item.link_url && item.link_text) {
          info.append(el('p', 'admin-meta', `${item.link_text} · ${item.link_url}`));
        }
        const actions = el('div', 'card-actions');
        actions.append(
          button('设为展示', () => activateNotice(item.id), `small-button${item.is_active && noticeEnabled ? ' is-active' : ''}`, item.is_active && noticeEnabled),
          button('编辑', () => openNoticeDialog(item), 'small-button'),
          button('删除', () => deleteNotice(item.id), 'small-button danger-button'),
        );
        card.append(info, actions);
        list.append(card);
      });
    }
    noticeBody.append(list);
    body.append(noticePanel);
    return panel;
  }

  function renderGuestbookWorkspace() {
    const panel = workbenchPanel('留言管理', '');
    const body = panel.querySelector('.admin-workspace-body');
    const list = el('div', 'admin-list');
    if (!state.guestbook.items.length) {
      list.append(empty('暂无留言'));
    } else {
      state.guestbook.items.forEach((msg) => list.append(guestbookCard(msg)));
    }
    body.append(list, renderPagination('guestbook'));
    return panel;
  }

  function guestbookCard(msg) {
    const card = el('article', 'admin-card admin-card-tight');
    const head = el('div', 'admin-card-head');
    head.append(el('h3', '', msg.nickname));
    const meta = el('p', 'admin-meta', `${msg.created_at} · IP: ${msg.ip_address}`);
    const content = el('p', 'admin-reason', msg.content);
    const actions = el('div', 'card-actions');
    const delBtn = button('删除留言', async () => {
      if (!confirm('确定要删除这条留言吗？')) return;
      await api(`/api/guestbook/${msg.id}`, { method: 'DELETE' });
      await loadGuestbook({ force: true });
      render();
      setNotice('留言已删除');
    }, 'small-button danger-button');
    actions.append(delBtn);
    card.append(head, meta, content, actions);
    return card;
  }

  function renderPagination(kind) {
    const source = state[kind];
    if (!source || (source.total_pages || 1) <= 1) return el('div');
    const wrap = el('div', 'admin-pagination');
    wrap.append(
      button('上一页', async () => {
        if (source.page <= 1) return;
        state[kind].page -= 1;
        await reloadKind(kind);
        render();
      }, 'small-button', source.page <= 1),
    );
    wrap.append(el('span', 'admin-meta', `第 ${source.page} / ${source.total_pages} 页 · 共 ${source.total} 条`));
    wrap.append(
      button('下一页', async () => {
        if (source.page >= source.total_pages) return;
        state[kind].page += 1;
        await reloadKind(kind);
        render();
      }, 'small-button', source.page >= source.total_pages),
    );
    return wrap;
  }

  async function reloadKind(kind) {
    if (kind === 'reports') await loadReports({ force: true });
    if (kind === 'lineups') await loadLineups({ force: true });
    if (kind === 'liveComps') await loadAdminLiveComps({ force: true });
    if (kind === 'users') await loadUsers({ force: true });
    if (kind === 'audit') await loadAudit({ force: true });
    if (kind === 'guestbook') await loadGuestbook({ force: true });
  }

  function workbenchPanel(title, subtitle, controls = null) {
    const section = el('section', 'admin-workspace-panel');
    const header = el('div', 'admin-module-header');
    header.append(sectionTitle(title, subtitle));
    if (controls) header.append(controls);
    const body = el('div', 'admin-workspace-body');
    section.append(header, body);
    return section;
  }

  function trafficMetric(label, value, caption) {
    const card = el('article', 'traffic-metric');
    card.append(el('span', 'stat-label', label), el('strong', '', String(value)), el('small', '', caption));
    return card;
  }

  function sectionTitle(title, subtitle) {
    const wrap = el('div', 'admin-section-title');
    wrap.append(el('h2', '', title), el('p', '', subtitle));
    return wrap;
  }

  function pill(text) {
    return el('span', 'admin-pill', text);
  }

  function empty(text, className = '') {
    return el('div', ['empty-state', className].filter(Boolean).join(' '), text);
  }

  function openPasswordDialog(user) {
    state.passwordUser = user;
    state.passwordError = '';
    renderDialogs();
  }

  function closePasswordDialog() {
    state.passwordUser = null;
    state.passwordError = '';
    renderDialogs();
  }

  function openLiveCompManualCodeDialog(item) {
    state.liveCompManualCodeTarget = item;
    state.liveCompManualCodeError = '';
    renderDialogs();
  }

  function closeLiveCompManualCodeDialog() {
    state.liveCompManualCodeTarget = null;
    state.liveCompManualCodeError = '';
    renderDialogs();
  }

  function renderDialogs() {
    if (!dialogRoot) return;
    dialogRoot.replaceChildren();
    if (state.passwordUser) {
      renderPasswordDialog();
    } else if (state.liveCompManualCodeTarget) {
      renderLiveCompManualCodeDialog();
    } else if (state.liveSeasonCreating) {
      renderLiveSeasonCreateDialog();
    } else if (state.noticeEditing) {
      renderNoticeDialog();
    }
    refreshIcons();
  }

  function closeLiveSeasonCreateDialog() {
    state.liveSeasonCreating = null;
    state.liveSeasonCreateError = '';
    renderDialogs();
  }

  function renderLiveSeasonCreateDialog() {
    if (!dialogRoot || !state.liveSeasonCreating) return;
    const draft = state.liveSeasonCreating;
    const overlay = el('div', 'modal-backdrop');
    const card = el('section', 'modal-card admin-password-dialog');
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-modal', 'true');
    card.setAttribute('aria-labelledby', 'liveSeasonCreateTitle');

    const header = el('div', 'modal-header');
    const titleWrap = el('div');
    const title = el('h2', '', '新增实时阵容赛季');
    title.id = 'liveSeasonCreateTitle';
    titleWrap.append(title, el('p', 'admin-meta', '创建后即出现在赛季列表；建议先以"后台隐藏"创建，数据上传完成后再启用展示'));
    header.append(titleWrap, button('取消', async () => closeLiveSeasonCreateDialog()));

    const form = el('form', 'modal-form');
    form.innerHTML = `
      <label class="field">
        <span>赛季 ID（小写字母/数字/短横线，如 s18-preview）</span>
        <input id="liveSeasonIdInput" name="id" maxlength="40" placeholder="s18-preview" value="${escapeHtml(draft.id)}" />
      </label>
      <label class="field">
        <span>赛季名称</span>
        <input id="liveSeasonNameInput" name="name" maxlength="60" placeholder="S18 · 新赛季" value="${escapeHtml(draft.name)}" />
      </label>
      <label class="field">
        <span>说明（可选）</span>
        <input id="liveSeasonDescriptionInput" name="description" maxlength="200" placeholder="赛季说明" value="${escapeHtml(draft.description)}" />
      </label>
      <label class="field">
        <span>初始状态</span>
        <select id="liveSeasonStatusInput" name="status">
          <option value="hidden">后台隐藏（推荐，数据齐后再启用）</option>
          <option value="active">启用展示</option>
          <option value="archived">归档展示</option>
          <option value="disabled">停用</option>
        </select>
      </label>
      <div class="message" id="liveSeasonCreateMessage">${escapeHtml(state.liveSeasonCreateError || '')}</div>
      <div class="editor-actions">
        <button class="primary-button" type="submit">创建赛季</button>
        <button class="ghost-button" type="button" id="cancelLiveSeasonCreateButton">取消</button>
      </div>
    `;
    form.querySelector('#liveSeasonStatusInput').value = draft.status || 'hidden';
    form.addEventListener('submit', submitLiveSeasonCreate);
    form.querySelector('#cancelLiveSeasonCreateButton').addEventListener('click', closeLiveSeasonCreateDialog);
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closeLiveSeasonCreateDialog();
    });

    card.append(header, form);
    overlay.append(card);
    dialogRoot.append(overlay);
  }

  async function submitLiveSeasonCreate(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {
      id: form.querySelector('#liveSeasonIdInput').value.trim(),
      name: form.querySelector('#liveSeasonNameInput').value.trim(),
      description: form.querySelector('#liveSeasonDescriptionInput').value.trim(),
      status: form.querySelector('#liveSeasonStatusInput').value,
    };
    state.liveSeasonCreating = { ...payload };
    try {
      await api('/api/admin/live-comps/seasons', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    } catch (error) {
      state.liveSeasonCreateError = error.message || '创建失败';
      renderDialogs();
      return;
    }
    closeLiveSeasonCreateDialog();
    await loadAdminLiveCompsSeasons({ force: true });
    setNotice(`赛季「${payload.name}」已创建`);
    render();
  }

  function renderNoticeDialog() {
    if (!dialogRoot || !state.noticeEditing) return;
    const item = state.noticeEditing;
    const isEdit = Boolean(item.id);

    const overlay = el('div', 'modal-backdrop');
    const card = el('section', 'modal-card admin-password-dialog');
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-modal', 'true');
    card.setAttribute('aria-labelledby', 'noticeDialogTitle');

    const header = el('div', 'modal-header');
    const titleWrap = el('div');
    const title = el('h2', '', isEdit ? '编辑全站通知' : '新增全站通知');
    title.id = 'noticeDialogTitle';
    titleWrap.append(title, el('p', 'admin-meta', '保存后可在列表中选择哪一条展示到首页'));
    header.append(titleWrap, button('取消', async () => closeNoticeDialog()));

    const form = el('form', 'modal-form');
    form.innerHTML = `
      <label class="field">
        <span>通知标题</span>
        <input id="noticeTitleInput" name="title" type="text" placeholder="通知标题" value="${escapeAttribute(item.title || '')}" />
      </label>
      <label class="field">
        <span>通知内容</span>
        <textarea id="noticeMessageInput" name="message" rows="4" placeholder="通知内容">${escapeHtml(item.message || '')}</textarea>
      </label>
      <div class="field">
        <span>页内跳转（设置后将忽略下方的外部链接）</span>
      </div>
      <label class="field">
        <span>跳转赛季</span>
        <div class="season-menu-wrap" id="noticeJumpSeasonWrap">
          <button class="account-toggle season-toggle" id="noticeJumpSeasonToggle" type="button" aria-haspopup="menu" aria-expanded="false">
            <span id="noticeJumpSeasonText">不跳转</span>
            <i class="account-chevron" data-lucide="chevron-down" aria-hidden="true"></i>
          </button>
          <div class="account-menu hidden season-menu" id="noticeJumpSeasonMenu" role="menu"></div>
        </div>
        <input type="hidden" id="noticeJumpSeasonInput" name="jump_season_id" value="${escapeAttribute(item.jump_season_id || '')}" />
      </label>
      <label class="field">
        <span>跳转Tab</span>
        <div class="season-menu-wrap" id="noticeJumpTabWrap">
          <button class="account-toggle season-toggle" id="noticeJumpTabToggle" type="button" aria-haspopup="menu" aria-expanded="false">
            <span id="noticeJumpTabText">不跳转</span>
            <i class="account-chevron" data-lucide="chevron-down" aria-hidden="true"></i>
          </button>
          <div class="account-menu hidden season-menu" id="noticeJumpTabMenu" role="menu"></div>
        </div>
        <input type="hidden" id="noticeJumpTabInput" name="jump_tab" value="${escapeAttribute(item.jump_tab || '')}" />
      </label>
      <div class="field" style="border-top: 1px solid var(--line); padding-top: 12px;">
        <span>外部链接（页内跳转未设置时生效）</span>
      </div>
      <label class="field">
        <span>链接地址</span>
        <input id="noticeLinkUrlInput" name="link_url" type="text" placeholder="可选，例如 /patch-notes" value="${escapeAttribute(item.link_url || '')}" />
      </label>
      <label class="field">
        <span>链接文字</span>
        <input id="noticeLinkTextInput" name="link_text" type="text" placeholder="可选，例如 查看公告" value="${escapeAttribute(item.link_text || '')}" />
      </label>
      <div class="field visibility-toggle">
        <div class="visibility-copy">
          <span>滚动播放</span>
          <strong id="marqueeStatusSummary">${item.marquee_enabled !== false ? '滚动' : '静止'}</strong>
          <span class="field-hint">关闭后通知将静止显示，方便用户点击跳转链接</span>
        </div>
        <label class="visibility-switch" for="noticeMarqueeCheckbox">
          <span class="visibility-switch-label">滚动</span>
          <input id="noticeMarqueeCheckbox" name="marquee_enabled" type="checkbox"${item.marquee_enabled !== false ? ' checked' : ''} />
          <span class="visibility-slider" aria-hidden="true"></span>
          <span class="visibility-switch-label">静止</span>
        </label>
      </div>
      <div class="editor-actions">
        <button class="primary-button" type="submit">${isEdit ? '保存通知' : '创建通知'}</button>
        <button class="ghost-button" type="button" id="cancelNoticeButton">取消</button>
      </div>
    `;

    form.addEventListener('submit', submitNoticeDialog);
    form.querySelector('#cancelNoticeButton').addEventListener('click', closeNoticeDialog);
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closeNoticeDialog();
    });

    card.append(header, form);
    overlay.append(card);
    dialogRoot.append(overlay);

    // 设置自定义下拉框（必须在 form 挂载到 DOM 后再初始化，因为使用 document.getElementById）
    setupJumpSeasonDropdown(form, item);
    setupJumpTabDropdown(form, item);

    // 滚动开关状态同步
    var marqueeCheckbox = document.getElementById('noticeMarqueeCheckbox');
    if (marqueeCheckbox) {
      marqueeCheckbox.addEventListener('change', function () {
        var summary = document.getElementById('marqueeStatusSummary');
        if (summary) summary.textContent = this.checked ? '滚动' : '静止';
      });
    }
  }

  async function submitNoticeDialog(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const item = state.noticeEditing;
    const payload = {
      title: form.querySelector('#noticeTitleInput').value.trim(),
      message: form.querySelector('#noticeMessageInput').value.trim(),
      link_url: form.querySelector('#noticeLinkUrlInput').value.trim(),
      link_text: form.querySelector('#noticeLinkTextInput').value.trim(),
      jump_season_id: form.querySelector('#noticeJumpSeasonInput').value.trim(),
      jump_tab: form.querySelector('#noticeJumpTabInput').value.trim(),
      marquee_enabled: form.querySelector('#noticeMarqueeCheckbox').checked ? '1' : '0',
    };
    if (!payload.title) { alert('标题不能为空'); return; }
    if (!payload.message) { alert('内容不能为空'); return; }
    await api(item.id ? `/api/admin/notices/${item.id}` : '/api/admin/notices', {
      method: item.id ? 'PUT' : 'POST',
      body: JSON.stringify(payload),
    });
    closeNoticeDialog();
    await loadNotice({ force: true });
    setNotice(item.id ? '通知已保存' : '通知已创建');
    render();
  }

  function renderPasswordDialog() {
    if (!dialogRoot) return;
    if (!state.passwordUser) return;

    const overlay = el('div', 'modal-backdrop');
    const card = el('section', 'modal-card admin-password-dialog');
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-modal', 'true');
    card.setAttribute('aria-labelledby', 'passwordDialogTitle');

    const header = el('div', 'modal-header');
    const titleWrap = el('div');
    const title = el('h2', '', '修改用户密码');
    title.id = 'passwordDialogTitle';
    titleWrap.append(title, el('p', 'admin-meta', `正在修改 ${state.passwordUser.nickname}（${state.passwordUser.username}）的登录密码`));
    header.append(titleWrap, button('取消', async () => closePasswordDialog()));

    const form = el('form', 'modal-form');
    form.innerHTML = `
      <label class="field">
        <span>新密码</span>
        <input id="passwordInput" name="password" type="password" placeholder="大于 5 位，且包含字母和数字" autocomplete="new-password" />
      </label>
      <label class="field">
        <span>确认密码</span>
        <input id="confirmPasswordInput" name="confirmPassword" type="password" placeholder="再次输入新密码" autocomplete="new-password" />
      </label>
      <div class="message" id="passwordDialogMessage">${state.passwordError || ''}</div>
      <div class="editor-actions">
        <button class="primary-button" type="submit">保存新密码</button>
        <button class="ghost-button" type="button" id="cancelPasswordButton">取消</button>
      </div>
    `;
    form.addEventListener('submit', submitPasswordReset);
    form.querySelector('#cancelPasswordButton').addEventListener('click', closePasswordDialog);
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closePasswordDialog();
    });

    card.append(header, form);
    overlay.append(card);
    dialogRoot.append(overlay);
  }

  async function submitPasswordReset(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const password = form.querySelector('#passwordInput').value;
    const confirmPassword = form.querySelector('#confirmPasswordInput').value;
    if (!isValidPassword(password)) {
      state.passwordError = '密码需大于5位且包含字母和数字';
      renderDialogs();
      return;
    }
    if (password !== confirmPassword) {
      state.passwordError = '两次输入的密码不一致';
      renderDialogs();
      return;
    }
    await api(`/api/admin/users/${state.passwordUser.id}`, {
      method: 'PUT',
      body: JSON.stringify({ password }),
    });
    const passwordUser = state.passwordUser;
    closePasswordDialog();
    if (state.users.searched) await loadUsers({ force: true });
    setNotice(`已更新 ${passwordUser.nickname} 的密码`);
  }

  function renderLiveCompManualCodeDialog() {
    if (!dialogRoot || !state.liveCompManualCodeTarget) return;
    const target = state.liveCompManualCodeTarget;
    const overlay = el('div', 'modal-backdrop');
    const card = el('section', 'modal-card admin-live-code-dialog');
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-modal', 'true');
    card.setAttribute('aria-labelledby', 'liveCompManualCodeTitle');

    const header = el('div', 'modal-header');
    const titleWrap = el('div');
    const title = el('h2', '', '补录实时阵容码');
    title.id = 'liveCompManualCodeTitle';
    titleWrap.append(title, el('p', 'admin-meta', `${target.tier} · ${target.title} · ${target.id}`));
    header.append(titleWrap, button('取消', async () => closeLiveCompManualCodeDialog()));

    const form = el('form', 'modal-form');
    form.innerHTML = `
      <label class="field">
        <span>阵容码</span>
        <textarea id="liveCompManualCodeInput" name="code" rows="4" placeholder="粘贴阵容码"></textarea>
      </label>
      <div class="message" id="liveCompManualCodeMessage">${state.liveCompManualCodeError || ''}</div>
      <div class="editor-actions">
        <button class="primary-button" type="submit">保存</button>
        <button class="ghost-button" type="button" id="cancelLiveCompManualCodeButton">取消</button>
      </div>
    `;
    form.addEventListener('submit', submitLiveCompManualCode);
    form.querySelector('#cancelLiveCompManualCodeButton').addEventListener('click', closeLiveCompManualCodeDialog);
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closeLiveCompManualCodeDialog();
    });

    card.append(header, form);
    overlay.append(card);
    dialogRoot.append(overlay);
  }

  async function submitLiveCompManualCode(event) {
    event.preventDefault();
    const target = state.liveCompManualCodeTarget;
    const code = event.currentTarget.querySelector('#liveCompManualCodeInput').value;
    try {
      await api(`/api/admin/live-comps/${encodeURIComponent(state.liveComps.selectedSeasonId)}/${encodeURIComponent(target.id)}/manual-code`, {
        method: 'POST',
        body: JSON.stringify({ code }),
      });
    } catch (error) {
      state.liveCompManualCodeError = error.message || '保存失败';
      renderDialogs();
      return;
    }
    closeLiveCompManualCodeDialog();
    await loadAdminLiveComps({ force: true });
    setNotice('实时阵容补码已保存');
  }

  function isValidPassword(password) {
    const value = String(password || '');
    return value.length > 5 && /[A-Za-z]/.test(value) && /\d/.test(value);
  }

  async function disableUser(id) {
    if (!confirm('确定禁用这个用户吗？')) return;
    await api(`/api/admin/users/${id}`, { method: 'DELETE' });
    if (state.users.searched) await loadUsers({ force: true });
    await loadOverview({ force: true });
    setNotice('用户已禁用');
  }

  function setNotice(text) {
    state.notice = text;
    render();
    clearTimeout(setNotice.timer);
    setNotice.timer = setTimeout(() => {
      state.notice = '';
      render();
    }, 2600);
  }

  function initTheme() {
    setTheme(localStorage.getItem('theme') || 'light');
  }

  function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
    window.jccApplyThemeToggleState?.(theme, elements.themeToggle, elements.themeIcon, elements.themeText);
    if (!window.jccApplyThemeToggleState && elements.themeText) elements.themeText.textContent = theme === 'dark' ? '白天模式' : '夜间模式';
  }

})().catch((error) => {
  const root = document.querySelector('#adminApp');
  if (root) root.textContent = error.message || '后台加载失败';
});
