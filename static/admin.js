(async function () {
  const {
    button,
    debounce,
    el,
    escapeAttribute,
    escapeHtml,
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
  let seasonDropdownCleanup = null;
  let noticeEditorCleanup = null;

  const state = {
    me: null,
    csrfToken: '',
    activeTab: 'overview',
    overview: null,
    growth: null,
    growthDate: todayInputValue(),
    analyticsWorkspace: 'growth',
    experience: {start: shiftExperienceDate(todayInputValue(),-6),end:todayInputValue(),data:null,loading:false,error:''},
    reports: { items: [], total: 0, page: 1, page_size: 20, total_pages: 1, status: 'pending', loadedAt: 0 },
    lineups: { status: 'all', season: '', order: 'newest', counts: {}, items: [], total: 0, page: 1, page_size: 10, total_pages: 1, query: '', loadedAt: 0 },
    lineupWorkspace: 'list',
    lineupSeasons: { seasons: [], default_season_id: '', loadedAt: 0 },
    lineupBulkImport: { season_id: '', raw_text: '', result: null, preview_raw_text: '', preview_season_id: '' },
    liveComps: { items: [], total: 0, page: 1, page_size: 10, total_pages: 1, query: '', updated_at: null, source_meta: null, selectedSeasonId: '', loadedAt: 0 },
    liveCompsWorkspace: 'codes',
    liveUpload: { seasonId: '', selectedFile: null, selectedFileName: '', uploadPercent: 0, job: null, pollTimer: null, publish: false, busy: false },
    navExpanded: { lineups: false, 'live-comps': false },
    liveCompsSeasons: { seasons: [], default_season_id: '', loadedAt: 0 },
    liveSeasonUi: { expanded: false, error: '' },
    liveSeasonBusy: false,
    liveSeasonCreateBusy: false,
    seasonDisplays: {
      simulator: { items: [], default_season_id: '', loadedAt: 0 },
      library: { items: [], default_season_id: '', loadedAt: 0 },
    },
    seasonDisplayUi: { library: { expanded: false, error: '' }, simulator: { expanded: false, error: '' } },
    seasonDisplayBusy: false,
    copyRank: { date: '', items: [], loadedAt: 0 },
    dailyReports: { items: [], selectedDate: '', report: null, loadedAt: 0 },
    liveSeasonCreating: null,
    liveSeasonCreateError: '',
    patchNotes: { items: [], loadedAt: 0 },
    users: { items: [], total: 0, page: 1, page_size: 10, total_pages: 1, query: '', loadedAt: 0 },
    settings: { data: {}, loadedAt: 0 },
    noticeData: { data: null, loadedAt: 0 },
    guestbook: { items: [], total: 0, unread_total: 0, status: 'active', page: 1, page_size: 20, total_pages: 1, loadedAt: 0 },
    passwordResetEmails: { date: '', items: [], total: 0, loadedAt: 0 },
    controllers: {},
    cacheTtlMs: 30000,
    passwordUser: null,
    passwordError: '',
    liveCompManualCodeTarget: null,
    liveCompManualCodeError: '',
    patchNoteEditing: null,
    noticeEditing: null,
  };
  const liveVersions = window.JccAdminLiveVersions.create({
    api, render, notify: setNotice, getSeason: () => liveUploadSeasonOptions().selected,
  });
  const statusText = {
    pending: '待处理',
    in_progress: '核实中',
    resolved: '已处理',
    dismissed: '已驳回',
    normal: '正常',
    hidden: '已隐藏',
    deleted: '已删除',
    active: '正常',
    archived: '已归档',
    unread: '未读',
    read: '已读',
    disabled: '已禁用',
  };
  const tabMeta = {
    overview: ['运营概览', '今日关键指标与待处理事项'],
    reports: ['失效反馈处理', '核查用户反馈并记录处理结果'],
    lineups: ['阵容管理', '搜索、审核与维护普通阵容'],
    'live-comps': ['实时阵容', '维护赛季状态与阵容码'],
    'season-display': ['资料赛季', '统一管理资料库与模拟器的赛季展示'],
    'season-packages': ['赛季版本更新', '上传资料包，检查差异并发布版本'],
    'patch-notes': ['更新公告', '编辑版本内容与发布状态'],
    users: ['用户管理', '查询账号、权限和可用状态'],
    analytics: ['增长分析', '查看访问、注册与转化数据'],
    audit: ['审计日志', '追溯操作来源，查看每一次关键变更'],
    'daily-reports': ['每日报告', '昨日运营快照与历史数据'],
    guestbook: ['留言管理', '处理访客提交的站点反馈'],
    'password-reset-emails': ['找回邮件', '查看今日密码找回验证码发送记录'],
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
  const renderDailyReportsWorkspaceFromModule = window.JccAdminDailyReports.createDailyReportsRenderer({
    workbenchPanel,
    empty,
    button,
  });
  const renderExperienceFromModule = window.JccAdminExperience.createRenderer({workbenchPanel,empty,button});
  const renderSeasonDisplayHub = window.JccAdminSeasonDisplay.createRenderer({
    getDisplay: (kind) => state.seasonDisplays[kind],
    getUi: (kind) => state.seasonDisplayUi[kind],
    isBusy: () => state.seasonDisplayBusy || !state.csrfToken,
    mutate: mutateSeasonDisplay,
    refresh: async (kind) => { await loadSeasonDisplay(kind, { force: true }); render(); },
    openVersions: () => activateTab('season-packages'),
  });
  const renderLiveSeasonSurface = window.JccAdminSeasonDisplay.createSurfaceRenderer({
    getDisplay: () => ({ ...state.liveCompsSeasons, items: (state.liveCompsSeasons.seasons || []).map(season => ({ ...season, season_id: season.id, display_name: season.name })) }),
    getUi: () => state.liveSeasonUi,
    isBusy: () => state.liveSeasonBusy || !state.csrfToken,
    mutate: (_kind, season, payload) => mutateLiveSeason(season, payload),
    refresh: refreshLiveSeasons,
  });

  const renderModeratedLineups = window.JccAdminLineups.createRenderer({
    getState: () => state.lineups,
    getSeasons: () => state.lineupSeasons.seasons,
    api,
    changeFilters: async (values) => {
      Object.assign(state.lineups, values, { page: 1, loadedAt: 0 });
      await loadLineups({ force: true }); render();
    },
    refresh: async () => { await loadLineups({ force: true }); render(); },
    searchControls: lineupSearchControls,
    pagination: () => renderPagination('lineups'),
    updateStatus: async (lineup, status) => { await updateLineupStatus(lineup, status); render(); },
    adjustScore: async (lineup) => { await adjustScore(lineup); render(); },
  });


  initTheme();
  elements.themeToggle?.addEventListener('click', () => {
    setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  });
  document.addEventListener('click', async (event) => {
    const toggle = event.target.closest('[data-admin-nav-toggle]');
    if (toggle) {
      const group = toggle.dataset.adminNavToggle;
      const nextExpanded = !state.navExpanded[group];
      Object.keys(state.navExpanded).forEach((key) => { state.navExpanded[key] = false; });
      state.navExpanded[group] = nextExpanded;
      syncTabs();
      return;
    }
    const button = event.target.closest('[data-admin-tab]');
    if (!button) return;
    try {
      await activateTab(button.dataset.adminTab, button.dataset.adminWorkspace || '');
    } catch (error) {
      if (error?.name !== 'AbortError') window.jccNotify.show(error.message || '加载失败，请重试', { variant: 'error' });
    }
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
      loadModerationSummary(),
    ]);
    await loadGuestbook({ force: true });
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

  window.addEventListener('beforeunload', event => {
    if (state.patchNoteEditing?.dirty) { event.preventDefault(); event.returnValue = ''; }
  });

  async function activateTab(tabKey, workspaceKey = '') {
    if (!tabKey) return;
    if (state.patchNoteEditing?.dirty && tabKey !== 'patch-notes' && !confirm('公告有未保存的修改，确定离开？草稿会保留到本次页面关闭。')) return;
    elements.moreDialog?.close();
    if (tabKey === 'lineups' && workspaceKey === 'list') { state.lineups.status = 'all'; state.lineups.order = 'newest'; state.lineups.page = 1; state.lineups.loadedAt = 0; }
    if (tabKey === 'lineups' && workspaceKey === 'review') {
      workspaceKey = 'list'; state.lineups.status = 'pending'; state.lineups.order = 'oldest'; state.lineups.page = 1; state.lineups.loadedAt = 0;
    }
    if (tabKey === 'lineups' && ['list', 'import'].includes(workspaceKey)) {
      state.lineupWorkspace = workspaceKey;
    }
    if (tabKey === 'live-comps' && ['codes', 'upload', 'seasons'].includes(workspaceKey)) {
      state.liveCompsWorkspace = workspaceKey;
    }
    Object.keys(state.navExpanded).forEach((key) => { state.navExpanded[key] = false; });
    if (tabKey in state.navExpanded) state.navExpanded[tabKey] = true;
    state.activeTab = tabKey;
    render();
    if (tabKey === 'overview') await Promise.all([loadOverview(), loadCopyRank()]);
    if (tabKey === 'reports') await loadReports();
    if (tabKey === 'lineups' && state.lineupWorkspace === 'list') await Promise.all([loadLineups(), loadLineupSeasons()]);
    if (tabKey === 'lineups' && state.lineupWorkspace === 'import') await loadLineupSeasons();
    if (tabKey === 'live-comps' && state.liveCompsWorkspace === 'codes') await loadAdminLiveComps();
    if (tabKey === 'live-comps' && state.liveCompsWorkspace === 'upload') {
      await loadAdminLiveCompsSeasons();
      await liveVersions.load();
    }
    if (tabKey === 'live-comps' && state.liveCompsWorkspace === 'seasons') await refreshLiveSeasons();
    if (tabKey === 'season-display') await Promise.all([loadSeasonDisplay('library'), loadSeasonDisplay('simulator')]);
    if (tabKey === 'patch-notes') await loadPatchNotes();
    if (tabKey === 'users') await loadUsers();
    if (tabKey === 'analytics') {
      if(state.analyticsWorkspace==='experience') await queryExperience(state.experience.start,state.experience.end);
      else await loadGrowth();
    }
    if (tabKey === 'daily-reports') await loadDailyReports();
    if (tabKey === 'guestbook') await loadGuestbook();
    if (tabKey === 'password-reset-emails') await loadPasswordResetEmails();
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

  function showPendingModeration(count) {
    document.querySelectorAll('[data-lineup-pending-count]').forEach(node => { node.textContent = count; node.hidden = !count; });
  }
  async function loadModerationSummary() {
    const summary = await api('/api/admin/lineup-moderation-summary');
    showPendingModeration(summary.pending);
  }

  async function loadLineups({ force = false } = {}) {
    if (!force && isFresh(state.lineups.loadedAt)) return;
    abortRequest('lineups');
    const controller = new AbortController();
    state.controllers.lineups = controller;
    const query = new URLSearchParams({
      q: state.lineups.query,
      status: state.lineups.status,
      season: state.lineups.season,
      order: state.lineups.order,
      page: String(state.lineups.page),
      page_size: String(state.lineups.page_size),
    });
    const payload = await api(`/api/admin/lineups?${query.toString()}`, { signal: controller.signal });
    if (state.controllers.lineups !== controller) return;
    state.lineups = { ...state.lineups, ...payload, loadedAt: Date.now() };
    showPendingModeration(payload.counts?.pending || 0);
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
    const controller = new AbortController();
    state.controllers.liveComps = controller;
    const query = new URLSearchParams({
      season: state.liveComps.selectedSeasonId,
      page: String(state.liveComps.page),
      page_size: String(state.liveComps.page_size),
    });
    const payload = await api(`/api/admin/live-comps?${query.toString()}`, { signal: controller.signal });
    if (state.controllers.liveComps !== controller) return;
    state.liveComps = { ...state.liveComps, ...payload, loadedAt: Date.now() };
  }

  async function loadAdminLiveCompsSeasons({ force = false } = {}) {
    if (!force && isFresh(state.liveCompsSeasons.loadedAt)) return;
    const payload = await api('/api/admin/live-comps/seasons');
    state.liveCompsSeasons = { ...payload, loadedAt: Date.now() };
    state.liveSeasonUi.error = '';
  }

  async function loadSeasonDisplay(kind, { force = false } = {}) {
    const current = state.seasonDisplays[kind];
    if (!force && isFresh(current.loadedAt)) return;
    try {
      const payload = await api(`/api/admin/season-display/${kind}`);
      state.seasonDisplays[kind] = { ...payload, loadedAt: Date.now() };
      state.seasonDisplayUi[kind].error = '';
    } catch (error) {
      state.seasonDisplayUi[kind].error = error.message || '赛季加载失败';
    }
  }

  async function loadPatchNotes({ force = false } = {}) {
    if (!force && isFresh(state.patchNotes.loadedAt)) return;
    const payload = await api('/api/admin/patch-notes');
    state.patchNotes = { items: payload.items || [], loadedAt: Date.now() };
  }

  async function loadUsers({ force = false } = {}) {
    if (!force && isFresh(state.users.loadedAt)) return;
    abortRequest('users');
    const controller = new AbortController();
    state.controllers.users = controller;
    const query = new URLSearchParams({
      q: state.users.query,
      page: String(state.users.page),
      page_size: String(state.users.page_size),
    });
    const payload = await api(`/api/admin/users?${query.toString()}`, { signal: controller.signal });
    if (state.controllers.users !== controller) return;
    state.users = { ...state.users, ...payload, loadedAt: Date.now() };
  }


  async function loadGrowth({ force = false } = {}) {
    if (!force && state.growth && state.growth.date === state.growthDate && isFresh(state.growth.loadedAt)) return;
    const payload = await api(`/api/admin/growth?date=${encodeURIComponent(state.growthDate)}`);
    state.growth = { ...payload, loadedAt: Date.now() };
  }

  function shiftExperienceDate(value,offset) {
    const [y,m,d]=value.split('-').map(Number);const date=new Date(y,m-1,d+offset);
    return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
  }
  async function queryExperience(start,end,force=false) {
    abortRequest('experience');
    const controller=new AbortController();state.controllers.experience=controller;
    Object.assign(state.experience,{start,end,loading:true,error:'',data:null});render();
    try {
      const data=await api(`/api/admin/experience?${new URLSearchParams({start,end,...(force?{refresh:'1'}:{})})}`,{signal:controller.signal});
      if(state.controllers.experience!==controller)return;
      state.experience.data=data;
    } catch(error) {
      if(error.name==='AbortError'||state.controllers.experience!==controller)return;
      state.experience.error=error.message;
    } finally {
      if(state.controllers.experience===controller){delete state.controllers.experience;state.experience.loading=false;render();}
    }
  }

  async function loadDailyReports({ force = false } = {}) {
    if (!force && isFresh(state.dailyReports.loadedAt)) return;
    const payload = await api('/api/admin/daily-reports?page_size=12');
    state.dailyReports = {
      ...state.dailyReports,
      items: payload.items || [],
      loadedAt: Date.now(),
    };
    if (!state.dailyReports.selectedDate && state.dailyReports.items.length) {
      state.dailyReports.selectedDate = state.dailyReports.items[0].report_date;
    }
    if (state.dailyReports.selectedDate) {
      await loadDailyReportDetail({ force });
    } else {
      state.dailyReports.report = null;
    }
  }

  async function loadDailyReportDetail({ force = false } = {}) {
    if (!state.dailyReports.selectedDate) {
      state.dailyReports.report = null;
      return;
    }
    const report = await api(`/api/admin/daily-reports/${encodeURIComponent(state.dailyReports.selectedDate)}`);
    state.dailyReports.report = { ...report, loadedAt: Date.now() };
  }

  function yesterdayDate() {
    const now = new Date();
    const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${date.getFullYear()}-${month}-${day}`;
  }

  async function generateDailyReport(date) {
    const report = await api(`/api/admin/daily-reports/${encodeURIComponent(date)}/generate`, { method: 'POST' });
    state.dailyReports.selectedDate = report.report_date;
    state.dailyReports.report = { ...report, loadedAt: Date.now() };
    await loadDailyReports({ force: true });
    render();
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
      status: state.guestbook.status,
    });
    const payload = await api(`/api/guestbook?${query.toString()}`);
    state.guestbook = { ...state.guestbook, ...payload, loadedAt: Date.now() };
  }

  async function loadPasswordResetEmails({ force = false } = {}) {
    if (!force && isFresh(state.passwordResetEmails.loadedAt)) return;
    const payload = await api('/api/admin/password-reset-emails');
    state.passwordResetEmails = { ...payload, loadedAt: Date.now() };
  }

  function render() {
    window.JccAnalyticsCharts?.destroy();
    seasonDropdownCleanup?.();
    seasonDropdownCleanup = null;
    syncHeader();
    syncTabs();
    if (state.activeTab === 'audit') {
      if (!state.me) return;
      window.JccSeasonPackages?.unmount();
      if (!document.getElementById('auditLogRoot')) {
        root.classList.remove('admin-app-loading');
        const auditRoot = document.createElement('div');
        auditRoot.id = 'auditLogRoot';
        root.replaceChildren(auditRoot);
        window.JccAuditLogs.mount(auditRoot);
      }
      refreshIcons();
      return;
    }
    window.JccAuditLogs?.unmount();
    if (state.activeTab === 'season-packages') {
      // Navigation is available while boot() is still loading the session.
      // Mount once the token exists so the React island cannot retain an empty token.
      if (!state.csrfToken) return;
      if (!document.getElementById('seasonPackageRoot')) {
        root.classList.remove('admin-app-loading');
        const packageRoot = document.createElement('div');
        packageRoot.id = 'seasonPackageRoot';
        root.replaceChildren(packageRoot);
        window.JccSeasonPackages.mount(packageRoot, { csrfToken: state.csrfToken });
      }
      return;
    }
    window.JccSeasonPackages?.unmount();
    root.classList.remove('admin-app-loading');
    const nextRoot = el('div');
    if (state.activeTab === 'overview') nextRoot.append(renderOverviewDashboardFromModule());
    if (state.activeTab === 'reports') nextRoot.append(renderReportsWorkspace());
    if (state.activeTab === 'lineups') nextRoot.append(renderLineupsWorkspace());
    if (state.activeTab === 'live-comps') nextRoot.append(renderLiveCompsWorkspace());
    if (state.activeTab === 'season-display') nextRoot.append(renderSeasonDisplayHub());
    if (state.activeTab === 'patch-notes') nextRoot.append(renderPatchNotesWorkspace());
    if (state.activeTab === 'users') nextRoot.append(renderUsersWorkspace());
    if (state.activeTab === 'analytics') nextRoot.append(renderAnalyticsWorkspace());
    if (state.activeTab === 'daily-reports') {
      nextRoot.append(renderDailyReportsWorkspaceFromModule(state.dailyReports, {
        selectDate: async (date) => {
          state.dailyReports.selectedDate = date;
          state.dailyReports.report = null;
          try {
            await loadDailyReportDetail({ force: true });
          } catch (error) {
            state.dailyReports.report = null;
            setNotice(error.message || '该日期还没有每日报告', 'error');
          }
          render();
        },
        generate: generateDailyReport,
        refresh: async () => {
          await loadDailyReports({ force: true });
          render();
        },
        yesterdayDate,
      }));
    }
    if (state.activeTab === 'guestbook') nextRoot.append(renderGuestbookWorkspace());
    if (state.activeTab === 'password-reset-emails') nextRoot.append(renderPasswordResetEmailsWorkspace());
    if (state.activeTab === 'settings') nextRoot.append(renderSettingsWorkspace());
    window.JccAdminSearch.replaceResults(root, nextRoot);
    // Bind the mounted controls synchronously. Deferred ID lookups can bind the
    // same final node twice when navigation/cache hits render twice in one tick.
    setupLineupBulkImportSeasonDropdown();
    setupLiveUploadSeasonDropdown();
    renderDialogs();
    refreshIcons();
  }

  function syncHeader() {
    if (elements.adminIdentityName) {
      elements.adminIdentityName.textContent = state.me?.nickname || '后台账号';
    }
    let [title, subtitle] = tabMeta[state.activeTab] || tabMeta.overview;
    if (state.activeTab === 'lineups') {
      [title, subtitle] = state.lineupWorkspace === 'import'
        ? ['阵容管理 · 批量导入', '批量解析、预览并导入普通阵容码']
        : state.lineups.status === 'pending' ? ['阵容管理 · 修改审核', '按提交先后核对用户修改，记录审核结果'] : ['阵容管理 · 阵容查找', '搜索、审核与维护普通阵容'];
    }
    if (state.activeTab === 'live-comps') {
      [title, subtitle] = state.liveCompsWorkspace === 'seasons'
        ? ['实时阵容 · 赛季管理', '调整赛季状态、顺序与默认赛季']
        : state.liveCompsWorkspace === 'upload'
          ? ['实时阵容 · 数据上传', '上传预上线、独立补码与版本切换']
        : ['实时阵容 · 阵容码维护', '按赛季检查并补充实时阵容码'];
    }
    if (elements.pageTitle) elements.pageTitle.textContent = title;
    if (elements.pageSubtitle) elements.pageSubtitle.textContent = subtitle;
    if (elements.pendingReportCount) {
      elements.pendingReportCount.textContent = String(state.overview?.stats?.pending_reports_count || 0);
    }
    const unread = String(state.guestbook?.unread_total || 0);
    document.querySelectorAll('#guestbookUnreadCount, #guestbookUnreadCountMobile').forEach((node) => {
      node.textContent = unread;
      node.hidden = unread === '0';
    });
  }

  function syncTabs() {
    document.querySelectorAll('[data-admin-tab]').forEach((node) => {
      const workspace = node.dataset.adminWorkspace || '';
      const activeWorkspace = node.dataset.adminTab === 'lineups' ? (state.lineupWorkspace === 'list' && state.lineups.status === 'pending' ? 'review' : state.lineupWorkspace)
        : node.dataset.adminTab === 'live-comps' ? state.liveCompsWorkspace : '';
      const isActive = node.dataset.adminTab === state.activeTab && (!workspace || workspace === activeWorkspace);
      node.classList.toggle('is-active', isActive);
      if (node.matches('.admin-nav-subitem, .admin-mobile-nav-item')) {
        node.setAttribute('aria-current', isActive ? 'page' : 'false');
      }
    });
    document.querySelectorAll('[data-admin-nav-tree]').forEach((tree) => {
      const group = tree.dataset.adminNavTree;
      const expanded = Boolean(state.navExpanded[group]);
      const parent = tree.querySelector('[data-admin-nav-toggle]');
      const submenu = tree.querySelector('.admin-nav-submenu');
      tree.classList.toggle('is-current', state.activeTab === group);
      tree.classList.toggle('is-expanded', expanded);
      parent?.setAttribute('aria-expanded', String(expanded));
      if (submenu) submenu.hidden = !expanded;
    });
    const isPrimaryMobileView = ['overview', 'reports', 'analytics'].includes(state.activeTab)
      || (state.activeTab === 'lineups' && state.lineupWorkspace === 'list');
    elements.moreButton?.classList.toggle('is-active', !isPrimaryMobileView);
  }

  function refreshIcons() {
    window.lucide?.createIcons({ attrs: { 'aria-hidden': 'true' } });
  }

  function renderReportsWorkspace() {
    const panel = workbenchPanel('用户失效反馈', '进入该工作台后再加载数据；支持分页切换');
    const body = panel.querySelector('.admin-workspace-body');
    body.append(renderReportStatusTabs());

    const list = el('div', 'admin-list');
    if (!state.reports.items.length) {
      list.append(empty(state.reports.status === 'pending' ? '暂无待处理失效反馈' : '该状态下没有失效反馈记录'));
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
    head.append(el('h3', '', `#${report.id} ${report.lineup_name || '阵容已删除'}`), pill(statusText[report.feedback_status || report.status] || report.status));
    const meta = el('p', 'admin-meta', `反馈用户：${report.reporter_nickname || '-'} · 作者：${report.owner_nickname || '-'} · 提交：${report.created_at}`);
    const reason = el('p', 'admin-reason', report.reason);
    const code = el('pre', 'admin-code', report.lineup_code || '无阵容码');
    card.append(head, meta, reason, code);
    const actions = el('div', 'card-actions');
    actions.append(button('查看进度 / 回复用户', () => window.JccFeedback.openAdmin('report', report.id, api, async () => {
      await Promise.all([loadReports({ force: true }), loadOverview({ force: true })]); render();
    })));
    card.append(actions);
    return card;
  }

  async function handleReport(id, status, hideLineup) {
    const actionText = hideLineup ? '处理失效反馈并隐藏阵容' : (status === 'dismissed' ? '驳回失效反馈' : '标记失效反馈为已处理');
    if (!confirm(`确定要${actionText}吗？`)) return;
    await api(`/api/admin/reports/${id}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ status, hide_lineup: hideLineup }),
    });
    await Promise.all([loadReports({ force: true }), loadOverview({ force: true })]);
    setNotice(hideLineup ? '失效反馈已处理，阵容已隐藏' : '失效反馈状态已更新');
  }


  function renderLineupsWorkspace() {
    const isImport = state.lineupWorkspace === 'import';
    const panel = workbenchPanel(isImport ? '批量导入' : '阵容管理',
      isImport ? '解析、预览并批量写入普通阵容' : '查看阵容状态，处理封禁与用户修改审核');
    panel.querySelector('.admin-workspace-body').append(isImport ? renderLineupBulkImportPanel() : renderModeratedLineups());
    return panel;
  }

  function renderLineupBulkImportPanel() {
    const panel = el('div', 'admin-subpanel lineup-bulk-import');
    const head = el('div', 'admin-subpanel-head');
    const title = el('div');
    title.append(el('h3', '', '批量导入阵容码'), el('p', 'admin-meta', '先解析预览，确认名称、赛季和重复项后再写入普通阵容库'));
    head.append(title);

    const form = el('form', 'lineup-bulk-import-form');
    const seasonField = el('div', 'lineup-bulk-import-field');
    const seasonLabel = el('label', '', '导入赛季');
    seasonLabel.htmlFor = 'lineupBulkImportSeasonToggle';
    seasonField.append(seasonLabel);
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

  function liveUploadSeasonOptions() {
    const seasons = state.liveCompsSeasons.seasons || [];
    const selected = state.liveUpload.seasonId || state.liveCompsSeasons.default_season_id || seasons[0]?.id || '';
    state.liveUpload.seasonId = selected;
    return { seasons, selected };
  }

  function renderLiveUploadProgressNode(job = state.liveUpload.job) {
    const wrap = el('div', 'live-upload-progress');
    wrap.hidden = !job && !state.liveUpload.selectedFile && !state.liveUpload.busy;
    const isPreview = job?.status === 'preview';
    const percent = isPreview ? Number(state.liveUpload.uploadPercent || 0) : job ? Number(job.percent || 0) : Number(state.liveUpload.uploadPercent || 0);
    const label = job
      ? `${job.status === 'completed' ? (job.message || '处理完成') : job.status === 'failed' ? '处理失败' : isPreview ? '文件已上传，等待确认' : (job.message || job.stage || '处理中')} · ${percent}%`
      : `上传文件 · ${percent}%`;
    const track = el('div', 'live-upload-progress-track');
    const fill = el('div', 'live-upload-progress-fill');
    fill.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    track.append(fill);
    wrap.append(track, el('p', 'live-upload-progress-label', label));
    if (job) {
      wrap.append(el('p', 'admin-meta', `阵容 ${job.item_done || 0}/${job.item_total || 0} · 图片 ${job.image_done || 0}/${job.image_total || 0}${job.current_item ? ` · 当前：${job.current_item}` : ''}`));
      if (job.error) wrap.append(el('p', 'live-upload-error', job.error));
      if (job.result?.backup_file) wrap.append(el('p', 'live-upload-success', `旧版本备份：${job.result.backup_file}`));
    }
    return wrap;
  }

  function renderLiveCompUploadPreview(preview) {
    const wrap = el('div', 'live-upload-preview');
    if (!preview) return wrap;
    const metrics = el('div', 'traffic-grid');
    metrics.append(
      trafficMetric('新阵容总数', preview.total || 0, '本次文件将发布的阵容数量'),
      trafficMetric('新增 ID', (preview.added_ids || []).length, '线上没有、本次新增'),
      trafficMetric('移除 ID', (preview.removed_ids || []).length, '线上存在、本次移除'),
      trafficMetric('复制受影响', Object.values(preview.copy_counts || {}).reduce((sum, value) => sum + Number(value || 0), 0), '历史复制记录仍会保留'),
    );
    wrap.append(metrics);
    const lists = [
      ['新增阵容 ID', preview.added_ids],
      ['移除阵容 ID', preview.removed_ids],
      ['阵容码变化 ID', preview.code_changed_ids],
      ['缺少阵容码 ID', preview.missing_code_ids],
    ];
    lists.forEach(([title, items]) => {
      if (!(items || []).length) return;
      const section = el('div', 'live-upload-change-list');
      section.append(el('strong', '', `${title}（${items.length}）`), el('p', 'admin-meta', items.join('、')));
      wrap.append(section);
    });
    (preview.warnings || []).forEach((warning) => wrap.append(el('p', 'live-upload-warning', `提示：${warning}`)));
    return wrap;
  }

  function updateLiveUploadProgressDom() {
    const node = document.querySelector('#liveUploadProgress');
    if (!node) return;
    const next = renderLiveUploadProgressNode(state.liveUpload.job);
    node.replaceWith(Object.assign(next, { id: 'liveUploadProgress' }));
  }

  function renderLiveCompUploadWorkspace() {
    const panel = el('div', 'live-upload-workspace');
    const uploadSurface = el('section', 'live-upload-surface');
    const uploadHeading = el('div', 'live-upload-section-head');
    uploadHeading.append(el('span', 'live-upload-eyebrow', '01 / 上传新版本'));
    const intro = el('p', 'admin-meta', '先上传，再安心补码。新文件默认保存为预上线版本；确认内容后，随时选择一个版本展示给用户。');
    uploadHeading.append(intro);
    const form = el('form', 'live-upload-form');
    const seasonLabel = el('div', 'live-upload-field');
    const caption = el('label', '', '目标赛季');
    caption.htmlFor = 'liveUploadSeasonToggle';
    seasonLabel.append(caption);
    const seasonData = liveUploadSeasonOptions();
    const seasonWrap = el('div', 'season-menu-wrap live-upload-season-wrap');
    seasonWrap.id = 'liveUploadSeasonWrap';
    seasonWrap.innerHTML = `
      <button class="account-toggle season-toggle" id="liveUploadSeasonToggle" type="button" aria-haspopup="menu" aria-expanded="false">
        <span id="liveUploadSeasonText">${escapeHtml((seasonData.seasons.find((season) => season.id === seasonData.selected)?.name) || seasonData.selected || '请选择赛季')}</span>
        <i class="account-chevron" data-lucide="chevron-down" aria-hidden="true"></i>
      </button>
      <div class="account-menu hidden season-menu" id="liveUploadSeasonMenu" role="menu"></div>
      <input type="hidden" id="liveUploadSeasonInput" value="${escapeAttribute(seasonData.selected)}" />
    `;
    seasonLabel.append(seasonWrap);
    const fileZone = el('div', 'live-upload-dropzone');
    fileZone.setAttribute('role', 'button');
    fileZone.setAttribute('tabindex', '0');
    fileZone.setAttribute('aria-label', '选择实时阵容 JSON 文件');
    const fileIcon = el('span', 'live-upload-drop-icon');
    fileIcon.setAttribute('aria-hidden', 'true');
    fileIcon.innerHTML = '<i data-lucide="file-json"></i>';
    fileZone.append(fileIcon);
    fileZone.append(el('strong', 'live-upload-file-name', state.liveUpload.selectedFileName || '选择实时阵容 JSON 文件'), el('span', 'live-upload-file-hint', '点击选择，或将 JSON 文件拖到这里 · UTF-8 · 最大 5 MB'));
    const fileInput = el('input');
    fileInput.className = 'live-upload-file-input';
    fileInput.type = 'file';
    fileInput.accept = 'application/json,.json';
    const setSelectedFile = (file) => {
      if (!file || state.liveUpload.busy) return;
      clearTimeout(state.liveUpload.pollTimer);
      state.liveUpload.selectedFile = file;
      state.liveUpload.selectedFileName = file.name || '';
      state.liveUpload.job = null;
      state.liveUpload.uploadPercent = 0;
      render();
    };
    fileInput.addEventListener('change', () => setSelectedFile(fileInput.files?.[0] || null));
    fileZone.addEventListener('click', (event) => {
      if (event.target !== fileInput) fileInput.click();
    });
    fileZone.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        fileInput.click();
      }
    });
    fileZone.addEventListener('dragover', (event) => {
      event.preventDefault();
      fileZone.classList.add('is-dragging');
    });
    fileZone.addEventListener('dragleave', () => fileZone.classList.remove('is-dragging'));
    fileZone.addEventListener('drop', (event) => {
      event.preventDefault();
      fileZone.classList.remove('is-dragging');
      setSelectedFile(event.dataTransfer?.files?.[0] || null);
    });
    fileZone.append(fileInput);
    const actions = el('div', 'card-actions');
    const previewButton = el('button', 'small-button is-active', '解析并预览');
    previewButton.type = 'submit';
    previewButton.disabled = state.liveUpload.busy || !state.liveUpload.selectedFile || !state.liveUpload.seasonId;
    actions.append(previewButton);
    if (state.liveUpload.job?.status === 'preview') {
      actions.append(button(state.liveUpload.publish ? '缓存图片并直接上线' : '保存为预上线版本', async (event, node) => startLiveCompUpload(node), 'small-button is-active', state.liveUpload.busy));
    }
    const mode = el('label', 'live-version-upload-mode');
    const direct = el('input');
    direct.id = 'liveUploadPublishMode';
    direct.type = 'checkbox';
    direct.checked = state.liveUpload.publish;
    direct.disabled = state.liveUpload.busy;
    direct.addEventListener('change', () => {
      state.liveUpload.publish = direct.checked;
      render();
      document.getElementById('liveUploadPublishMode')?.focus({ preventScroll: true });
    });
    const modeText = el('span');
    modeText.append(el('strong', '', '处理完成后直接上线'), el('small', '', '默认关闭 · 缺码时建议先保存为预上线版本'));
    mode.append(direct, modeText);
    form.append(seasonLabel, fileZone, mode, actions);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      await previewLiveCompUpload(previewButton);
    });
    uploadSurface.append(uploadHeading, form, Object.assign(renderLiveUploadProgressNode(), { id: 'liveUploadProgress' }));
    if (state.liveUpload.job?.preview) uploadSurface.append(renderLiveCompUploadPreview(state.liveUpload.job.preview));
    panel.append(uploadSurface);
    panel.append(liveVersions.view());
    return panel;
  }

  async function previewLiveCompUpload(buttonNode) {
    const file = state.liveUpload.selectedFile;
    if (!file) return setNotice('请先选择 JSON 文件', 'warning');
    state.liveUpload.busy = true;
    buttonNode.disabled = true;
    state.liveUpload.uploadPercent = 0;
    updateLiveUploadProgressDom();
    const formData = new FormData();
    formData.append('season_id', state.liveUpload.seasonId);
    formData.append('file', file, file.name);
    try {
      const result = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/admin/live-comps/uploads/preview');
        xhr.setRequestHeader('X-CSRF-Token', state.csrfToken);
        xhr.upload.onprogress = (event) => {
          if (!event.lengthComputable) return;
          state.liveUpload.uploadPercent = Math.round(event.loaded * 100 / event.total);
          updateLiveUploadProgressDom();
        };
        xhr.onload = () => {
          let data = {};
          try { data = JSON.parse(xhr.responseText || '{}'); } catch (_) { /* handled below */ }
          if (xhr.status >= 200 && xhr.status < 300) resolve(data);
          else reject(new Error(data.error || '上传预览失败'));
        };
        xhr.onerror = () => reject(new Error('上传网络错误'));
        xhr.send(formData);
      });
      state.liveUpload.uploadPercent = 100;
      state.liveUpload.job = result;
      setNotice('文件解析完成，请检查差异并选择保存方式');
    } catch (error) {
      setNotice(error.message || '上传预览失败', 'error');
    } finally {
      state.liveUpload.busy = false;
      render();
    }
  }

  async function startLiveCompUpload(buttonNode) {
    const job = state.liveUpload.job;
    if (!job?.job_id || state.liveUpload.busy) return;
    if (state.liveUpload.publish && !confirm(`确认直接上线此文件？${job.preview?.missing_code_ids?.length || 0} 套阵容仍缺码，完成后将替换首页当前版本。`)) return;
    state.liveUpload.busy = true;
    buttonNode.disabled = true;
    try {
      state.liveUpload.job = await api(`/api/admin/live-comps/uploads/${encodeURIComponent(job.job_id)}/start`, { method: 'POST', body: JSON.stringify({ publish: state.liveUpload.publish }) });
      setNotice('已进入后台处理队列');
      pollLiveCompUpload();
    } catch (error) {
      setNotice(error.message || '无法启动上传任务', 'error');
      state.liveUpload.busy = false;
      buttonNode.disabled = false;
    }
    render();
  }

  function pollLiveCompUpload() {
    const jobId = state.liveUpload.job?.job_id;
    if (!jobId) return;
    clearTimeout(state.liveUpload.pollTimer);
    state.liveUpload.pollTimer = setTimeout(async () => {
      try {
        const job = await api(`/api/admin/live-comps/uploads/${encodeURIComponent(jobId)}`);
        if (state.liveUpload.job?.job_id !== jobId) return;
        state.liveUpload.job = job;
        updateLiveUploadProgressDom();
        if (!['completed', 'failed'].includes(job.status)) pollLiveCompUpload();
        else { state.liveUpload.busy = false; await liveVersions.load(job.result?.version_id); render(); }
      } catch (error) {
        setNotice(error.message || '读取上传进度失败，将自动重试', 'error');
        if (state.liveUpload.job?.job_id === jobId) pollLiveCompUpload();
      }
    }, 1000);
  }

  function renderLiveCompsWorkspace() {
    if (state.liveCompsWorkspace === 'seasons') return renderLiveCompSeasonManager();
    const isUpload = state.liveCompsWorkspace === 'upload';
    const panel = workbenchPanel(
      isUpload ? '数据上传' : '阵容码维护',
      isUpload ? '上传 · 预览补码 · 选择上线 · 历史回滚' : '按赛季查看实时阵容并为缺码条目补码',
    );
    const body = panel.querySelector('.admin-workspace-body');
    if (isUpload) {
      panel.classList.add('admin-live-upload-page');
      body.append(renderLiveCompUploadWorkspace());
      return panel;
    }
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
    return panel;
  }

  async function mutateSeasonDisplay(kind, season, payload) {
    if (state.seasonDisplayBusy || !state.csrfToken) return;
    const focusId = document.activeElement?.id;
    state.seasonDisplayBusy = true;
    render();
    try {
      const result = await api(`/api/admin/season-display/${kind}/${encodeURIComponent(season.season_id)}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      state.seasonDisplays[kind] = { ...result, loadedAt: Date.now() };
      state.seasonDisplayUi[kind].error = '';
      const label = kind === 'library' ? '资料库' : '模拟器';
      setNotice(`已更新${label}中的「${season.display_name || season.season_id}」`);
    } catch (error) {
      setNotice(error.message || '操作失败', 'error');
    } finally {
      state.seasonDisplayBusy = false;
    }
    render();
    if (state.activeTab === 'season-display') {
      const previous = focusId && document.getElementById(focusId);
      const target = previous && previous.getClientRects().length && !previous.disabled
        ? previous : document.getElementById(`season-${kind}-title`);
      target?.focus({ preventScroll: true });
    }
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
    const panel = el('div', 'admin-season-hub live-season-manager');
    panel.setAttribute('aria-busy', String(state.liveSeasonBusy || !state.csrfToken));
    const intro = el('div', 'season-display-intro');
    const copy = el('div');
    copy.append(el('h2', '', '阵容赛季展示'), el('p', '', '这里的分类和顺序也用于普通阵容筛选、创建与批量导入。'));
    const actions = el('div', 'live-season-toolbar');
    actions.append(button('刷新赛季', refreshLiveSeasons, 'small-button', state.liveSeasonBusy));
    actions.append(button('新增赛季', () => {
      state.liveSeasonCreating = { id: '', name: '', description: '', status: 'hidden' };
      state.liveSeasonCreateError = '';
      renderDialogs();
    }, 'primary-button', state.liveSeasonBusy || !state.csrfToken));
    intro.append(copy, actions);
    panel.append(intro, el('p', 'season-display-guide', '启用和归档赛季参与排序；隐藏、停用赛季收在下方，重新展示后排在末尾。'), renderLiveSeasonSurface('live'));
    return panel;
  }

  function applyLiveSeasonManifest(payload) {
    state.liveCompsSeasons = { ...payload, loadedAt: Date.now() };
    state.liveSeasonUi.error = '';
    state.lineupSeasons.loadedAt = 0;
    state.liveComps.loadedAt = 0;
    if (!payload.seasons.some(season => season.id === state.lineupBulkImport.season_id && ['active', 'archived'].includes(season.status))) {
      state.lineupBulkImport.season_id = '';
      state.lineupBulkImport.result = null;
    }
  }

  async function refreshLiveSeasons() {
    if (state.liveSeasonBusy) return;
    state.liveSeasonBusy = true;
    render();
    try {
      const payload = await api('/api/admin/live-comps/seasons');
      applyLiveSeasonManifest(payload);
    } catch (error) {
      state.liveSeasonUi.error = error.message || '赛季加载失败';
    } finally {
      state.liveSeasonBusy = false;
      render();
    }
  }

  async function mutateLiveSeason(season, payload) {
    if (state.liveSeasonBusy || !state.csrfToken) return;
    const focusId = document.activeElement?.id;
    state.liveSeasonBusy = true;
    render();
    try {
      const body = payload.is_default ? { default_season_id: season.id } : payload;
      const result = await api(`/api/admin/live-comps/seasons/${encodeURIComponent(season.id)}`, { method: 'PUT', body: JSON.stringify(body) });
      applyLiveSeasonManifest(result);
      setNotice(`已更新实时阵容中的「${season.name || season.id}」`);
    } catch (error) {
      setNotice(error.message || '操作失败', 'error');
    } finally {
      state.liveSeasonBusy = false;
    }
    render();
    if (state.activeTab === 'live-comps' && state.liveCompsWorkspace === 'seasons') {
      const previous = focusId && document.getElementById(focusId);
      const target = previous && previous.getClientRects().length && !previous.disabled ? previous : document.getElementById('season-live-title');
      target?.focus({ preventScroll: true });
    }
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
      setNotice(error.message || '操作失败', 'error');
    }
    render();
  }

  function lineupSearchControls() {
    return window.JccAdminSearch.create({
      key: 'lineups', value: state.lineups.query, placeholder: '搜索阵容名、阵容码、作者',
      invalidate: () => abortRequest('lineups'),
      search: async query => {
        state.lineups = { ...state.lineups, query, page: 1, loadedAt: 0 };
        await loadLineups({ force: true });
        render();
      },
    });
  }

  function liveCompSearchControls() {
    return window.JccAdminSearch.create({
      key: 'liveComps', value: state.liveComps.query, placeholder: '搜索阵容名或 ID',
      invalidate: () => abortRequest('liveComps'),
      search: async query => {
        state.liveComps = { ...state.liveComps, query, page: 1, loadedAt: 0 };
        await loadAdminLiveComps({ force: true });
        render();
      },
    });
  }

  async function previewLineupBulkImport(buttonNode) {
    const rawText = state.lineupBulkImport.raw_text.trim();
    if (!rawText) {
      setNotice('请粘贴阵容码', 'warning');
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
      window.jccNotify.show(error.message || '解析失败，请检查内容后重试', { variant: 'error' });
      if (buttonNode) buttonNode.disabled = false;
    }
  }

  async function confirmLineupBulkImport(buttonNode) {
    const rawText = document.querySelector('#lineupBulkImportRawText')?.value?.trim() || '';
    const seasonId = document.querySelector('#lineupBulkImportSeasonInput')?.value || '';
    if (!state.lineupBulkImport.result || !state.lineupBulkImport.preview_raw_text) {
      setNotice('请先解析阵容码', 'warning');
      return;
    }
    if (rawText !== state.lineupBulkImport.preview_raw_text || seasonId !== state.lineupBulkImport.preview_season_id) {
      setNotice('阵容码文本或赛季已变化，请重新解析', 'warning');
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
      await loadLineups({ force: true });
      await loadOverview({ force: true });
      setNotice(`导入完成：新增 ${result.created_count || 0} 条，跳过 ${Number(result.duplicate_existing_count || 0) + Number(result.duplicate_in_upload_count || 0)} 条`);
      render();
    } catch (error) {
      window.jccNotify.show(error.message || '导入失败，请检查内容后重试', { variant: 'error' });
      if (buttonNode) buttonNode.disabled = false;
    }
  }

  async function updateLineupStatus(lineup, status) {
    await api(`/api/admin/lineups/${lineup.id}`, { method: 'PUT', body: JSON.stringify({ status, version: lineup.version }) });
    await Promise.all([loadLineups({ force: true }), loadOverview({ force: true })]);
    setNotice(status === 'hidden' ? '阵容已隐藏' : '阵容已恢复');
  }

  async function adjustScore(lineup) {
    window.JccAdminLineups.openScore({ api, lineup, afterChange: async () => { await loadLineups({ force: true }); render(); } });
  }

  function openAutomationAccounts() {
    window.JccAutomationAccounts.open({ api, afterChange: async () => {
      try { await loadUsers({ force: true }); if (state.activeTab === 'users') render(); } catch (_) { setNotice('账号操作已完成，请刷新用户列表', 'warning'); }
    } });
  }

  function renderUsersWorkspace() {
    const panel = workbenchPanel('用户管理', '管理账号与访问权限 · 按注册顺序展示最近用户');
    panel.classList.add('admin-users-workspace');
    const body = panel.querySelector('.admin-workspace-body');
    const toolbar = el('div', 'admin-users-toolbar');
    toolbar.append(button('AI 自动化账号', openAutomationAccounts), userSearchControls(), el('span', 'admin-meta', `共 ${state.users.total} 位用户`));
    body.append(toolbar);
    if (!state.users.items.length) {
      body.append(empty('没有找到用户，请尝试其他用户名、昵称或邮箱'), renderPagination('users'));
      return panel;
    }
    const table = el('table', 'admin-users-table');
    table.setAttribute('aria-label', '用户账号与权限');
    const head = el('thead');
    const headings = el('tr');
    ['用户', '状态', '角色', '注册时间', '操作'].forEach(label => {
      const th = el('th', '', label);
      th.scope = 'col';
      headings.append(th);
    });
    head.append(headings);
    const rows = el('tbody');
    state.users.items.forEach(user => {
      const row = el('tr');
      const identity = el('td', 'admin-user-identity');
      const person = el('div', 'admin-user-person');
      const avatar = window.jccAvatar.image(user.avatar_config || user.avatar_color, 38, '');
      const avatarImage = avatar.querySelector('img');
      if (avatarImage) avatarImage.decoding = 'async';
      const info = el('div', 'admin-user-info');
      info.append(el('strong', '', user.nickname || user.username),
        el('span', 'admin-user-handle', `@${user.username}`), el('span', 'admin-user-email', user.role === 'automation' ? '受限后台账号 · 用户名密码登录' : user.email || '未设置邮箱'));
      person.append(avatar, info);
      identity.append(person);
      const status = el('td');
      status.dataset.label = '状态';
      status.append(el('span', `admin-user-status ${user.status === 'disabled' ? 'is-disabled' : 'is-active'}`, statusText[user.status] || user.status));
      const role = el('td', 'admin-user-role', user.role === 'admin' ? '管理员' : user.role === 'automation' ? 'AI 自动化账号' : '普通用户');
      role.dataset.label = '角色';
      const joined = el('td', 'admin-user-date');
      joined.dataset.label = '注册时间';
      const time = el('time', '', String(user.created_at || '').replace('T', ' ').slice(0, 19) || '—');
      time.title = user.created_at || '';
      joined.append(time);
      const actions = el('td', 'admin-user-actions');
      if (user.role === 'automation') actions.append(button('管理自动化账号', openAutomationAccounts));
      else actions.append(button('修改密码', () => openPasswordDialog(user)));
      if (user.status !== 'disabled') {
        actions.append(button('禁用', () => disableUser(user.id), 'small-button danger-button'));
      }
      row.append(identity, status, role, joined, actions);
      rows.append(row);
    });
    table.append(head, rows);
    body.append(table, renderPagination('users'));
    return panel;
  }

  function userSearchControls() {
    return window.JccAdminSearch.create({
      key: 'users', value: state.users.query, placeholder: '搜索用户名、邮箱或昵称',
      invalidate: () => abortRequest('users'),
      search: async query => {
        state.users = { ...state.users, query, page: 1, loadedAt: 0 };
        await loadUsers({ force: true });
        render();
      },
    });
  }

  function renderAnalyticsWorkspace() {
    const wrap=el('div');const tabs=el('div','card-actions experience-switch');
    [['growth','注册与活跃'],['experience','搜索与设备']].forEach(([key,label])=>{
      tabs.append(button(label,async()=>{
        state.analyticsWorkspace=key;render();
        if(key==='experience'&&!state.experience.data&&!state.experience.loading) await queryExperience(state.experience.start,state.experience.end);
      },`small-button ${state.analyticsWorkspace===key?'is-active':''}`));
    });
    wrap.append(tabs);
    if(state.analyticsWorkspace==='experience') {
      wrap.append(renderExperienceFromModule(state.experience,{
        today:todayInputValue(),query:queryExperience,
        range:days=>queryExperience(shiftExperienceDate(todayInputValue(),1-days),todayInputValue()),
      }));return wrap;
    }
    const panel = workbenchPanel('增长分析', '按自然日查询，不在首页默认加载', growthDateControl());
    const body = panel.querySelector('.admin-workspace-body');
    const growth = state.growth || {};
    const charts = el('div', 'analytics-growth-charts');
    charts.append(window.JccAnalyticsCharts.chart({
      title:'访问与认证', headline:growth.home_uv || 0, headlineLabel:'首页访客',
      description:`${state.growthDate} · 各环节独立去重人数，不代表同一批访客的漏斗。`,
      rows:[{label:'首页',people:growth.home_uv},{label:'登录入口',people:growth.login_entry_visitors},{label:'登录页面',people:growth.auth_page_visitors},{label:'注册成功',people:growth.successful_registrations},{label:'登录成功',people:growth.successful_logins}],
      series:[{key:'people',label:'人数'}],
    }),window.JccAnalyticsCharts.chart({
      title:'互动意向与登录后行动', headline:growth.post_login_like_users || 0, headlineLabel:'登录后点赞人数',
      description:'登录后行动限定在认证成功后 10 分钟内；游客意向与登录用户分别统计。',
      rows:[{label:'点赞',guest:growth.guest_like_visitors,member:growth.post_login_like_users},{label:'收藏',guest:growth.guest_favorite_visitors,member:growth.post_login_favorite_users}],
      series:[{key:'guest',label:'游客尝试'},{key:'member',label:'登录后完成',texture:'hatch'}],
    }));
    const list = el('div', 'analytics-metrics');
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

    const rates = el('section', 'analytics-rates');
    const rateHeading = el('div', 'analytics-rates-heading');
    rateHeading.append(el('h3', '', '转化表现'), el('p', '', '从认证到行动 · 登录后的互动统计窗口为 10 分钟'));
    rates.append(rateHeading);
    const rateGrid = el('div', 'analytics-rates-grid');
    [
      ['进入登录页', '登录入口 → 登录页面', growth.conversion_rates?.entry_to_auth_page_pct],
      ['完成认证', '登录页面 → 注册 / 登录成功', growth.conversion_rates?.auth_page_to_auth_success_pct],
      ['完成点赞', '认证成功 → 点赞', growth.conversion_rates?.auth_success_to_like_pct],
      ['完成收藏', '认证成功 → 收藏', growth.conversion_rates?.auth_success_to_favorite_pct],
      ['发布阵容', '认证成功 → 上传阵容', growth.conversion_rates?.auth_success_to_create_lineup_pct],
    ].forEach(([label, description, value], index) => {
      const item = el('article', 'analytics-rate');
      const top = el('div','analytics-rate-label');top.append(el('span','',label),el('small','',String(index+1).padStart(2,'0')));
      const amount=el('strong','analytics-rate-value',Number(value || 0).toLocaleString('zh-CN',{maximumFractionDigits:2}));amount.append(el('span','','%'));
      const track=el('div','analytics-rate-track');track.setAttribute('aria-hidden','true');
      const fill=el('i');fill.style.width=`${Math.max(0,Math.min(100,Number(value)||0))}%`;track.append(fill);
      item.append(top,amount,track,el('p','',description));rateGrid.append(item);
    });
    rates.append(rateGrid);
    body.append(charts, list, rates);
    wrap.append(panel);return wrap;
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


  function renderPatchNotesWorkspace() {
    const panel = workbenchPanel('更新公告', '同步官方更新公告，维护版本重点与官方原文链接');
    const body = panel.querySelector('.admin-workspace-body');
    const actions = el('div', 'card-actions');
    actions.append(button('新增公告', () => {
      state.patchNoteEditing = emptyPatchNoteDraft();
      render();
    }, 'small-button'));
    if (state.patchNoteEditing) {
      body.append(renderPatchNoteForm(state.patchNoteEditing));
      return panel;
    }
    body.append(actions);

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
    head.append(el('h3', '', item.title), el('span', 'admin-pill', window.JccPatchEditor.labels[item.status] || item.status));
    const meta = el('p', 'admin-meta', `${item.version || '版本公告'} · ${item.published_at} · 更新 ${item.updated_at}`);
    const actions = el('div', 'card-actions');
    actions.append(
      button('编辑', () => {
        state.patchNoteEditing = { ...item };
        render();
      }, 'small-button'),
      button(item.status === 'published' ? '下线' : '发布', async () => {
        if (!confirm(item.status === 'published' ? '确认下线这条公告？' : '确认将这条公告发布到前台？')) return;
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
    return window.JccPatchEditor.create({ item, template: PATCH_NOTE_TEMPLATE,
      save: savePatchNote, cancel: () => { state.patchNoteEditing = null; render(); } });
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

  async function savePatchNote(payload) {
    const url = payload.id ? `/api/admin/patch-notes/${payload.id}` : '/api/admin/patch-notes';
    const method = payload.id ? 'PUT' : 'POST';
    await api(url, { method, body: JSON.stringify(payload) });
    state.patchNoteEditing = null;
    setNotice(payload.status === 'published' ? '公告已发布' : '公告已保存');
    try { await loadPatchNotes({ force: true }); } catch (_) { setNotice('公告已保存，列表刷新失败，请刷新列表', 'warning'); }
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
      window.jccNotify.show(error.message || '保存失败', { variant: 'error' });
    }
  }

  async function refreshNoticeAfterWrite(message) {
    setNotice(message);
    try {
      await loadNotice({ force: true });
      render();
    } catch (error) {
      state.noticeData.loadedAt = 0;
      window.jccNotify.show(`${message}，列表刷新失败，请刷新页面查看`, { variant: 'warning' });
    }
  }

  async function toggleNotice(enabled) {
    await api('/api/admin/notice', {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    });
    await refreshNoticeAfterWrite(enabled ? '通知已开启' : '通知已关闭');
  }

  async function saveNoticeContent(event, node) {
    openNoticeDialog(null, node);
  }

  async function activateNotice(noticeId) {
    await api(`/api/admin/notices/${noticeId}/activate`, { method: 'POST' });
    await refreshNoticeAfterWrite('已切换展示公告');
  }

  async function deleteNotice(noticeId) {
    if (!confirm('确定删除这条通知吗？')) return;
    await api(`/api/admin/notices/${noticeId}`, { method: 'DELETE' });
    await refreshNoticeAfterWrite('通知已删除');
  }

  function openNoticeDialog(notice, trigger) {
    trigger?.focus();
    state.noticeEditing = notice || { title: '', message: '', link_url: '', link_text: '', jump_season_id: '', jump_tab: '', marquee_enabled: true };
    renderDialogs();
  }

  function closeNoticeDialog() {
    state.noticeEditing = null;
    renderDialogs();
  }

  function setupLineupBulkImportSeasonDropdown() {
    const wrap = document.getElementById('lineupBulkImportSeasonWrap');
    if (!wrap) return;
    seasonDropdownCleanup = window.JccAdminSeasonPicker.mount(wrap, {
      seasons: state.lineupSeasons.seasons || [],
      selected: state.lineupBulkImport.season_id || state.lineupSeasons.default_season_id || '',
      onSelect(value) {
        state.lineupBulkImport.raw_text = document.querySelector('#lineupBulkImportRawText')?.value || state.lineupBulkImport.raw_text;
        state.lineupBulkImport.season_id = value;
        state.lineupBulkImport.result = null;
        state.lineupBulkImport.preview_raw_text = '';
        state.lineupBulkImport.preview_season_id = '';
        render();
      },
    });
  }

  function setupLiveUploadSeasonDropdown() {
    const wrap = document.getElementById('liveUploadSeasonWrap');
    if (!wrap) return;
    seasonDropdownCleanup = window.JccAdminSeasonPicker.mount(wrap, {
      seasons: state.liveCompsSeasons.seasons || [],
      selected: state.liveUpload.seasonId,
      onSelect(value) {
        if (state.liveUpload.busy) { setNotice('当前上传正在处理，请完成后切换赛季', 'warning'); render(); return; }
        clearTimeout(state.liveUpload.pollTimer);
        state.liveUpload.seasonId = value;
        state.liveUpload.job = null;
        state.liveUpload.uploadPercent = 0;
        liveVersions.reset();
        render();
        liveVersions.load();
      },
    });
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
          item.is_active ? (noticeEnabled ? '当前展示' : '已选中 · 展示已关闭') : '未展示',
          item.marquee_enabled === false ? '静止' : '',
          item.updated_at ? `更新 ${item.updated_at}` : '',
        ].filter(Boolean);
        info.append(
          title,
          el('p', 'admin-meta', metaParts.join(' · ')),
          el('p', 'admin-reason', item.message),
        );
        if (item.target) {
          info.append(el('p', 'admin-meta', `跳转至：${item.target.label}${item.target.available ? '' : ' · 已不可用，首页暂停显示链接'}`));
        }
        const actions = el('div', 'card-actions');
        actions.append(
          button('设为展示', () => activateNotice(item.id), `small-button${item.is_active && noticeEnabled ? ' is-active' : ''}`, item.is_active && noticeEnabled),
          button('编辑', (event, node) => openNoticeDialog(item, node), 'small-button'),
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

  function renderPasswordResetEmailsWorkspace() {
    const panel = workbenchPanel('今日密码找回邮件', '仅展示当天由系统发出的密码找回验证码邮件');
    const body = panel.querySelector('.admin-workspace-body');
    const emailData = state.passwordResetEmails;
    body.append(el('p', 'admin-meta', `${emailData.date || '今天'} · 共 ${emailData.total || 0} 封`));
    const list = el('div', 'admin-list');
    if (!emailData.items?.length) {
      list.append(empty('今天暂无密码找回邮件'));
    } else {
      emailData.items.forEach((item) => {
        const row = el('article', 'admin-row-card');
        const info = el('div');
        info.append(el('strong', '', item.email), el('p', 'admin-meta', `${item.created_at} · ${item.purpose} · ${item.status === 'sent' ? '已发送' : item.status}`));
        row.append(info);
        list.append(row);
      });
    }
    body.append(list);
    return panel;
  }

  function renderGuestbookWorkspace() {
    const panel = workbenchPanel('留言管理', '先标记已读，再归档已处理留言');
    const body = panel.querySelector('.admin-workspace-body');
    const filters = el('div', 'admin-segmented guestbook-filters');
    [['active', '待处理'], ['unread', '未读'], ['read', '已读'], ['archived', '已归档'], ['all', '全部']].forEach(([value, label]) => {
      filters.append(button(label, async () => {
        if (state.guestbook.status === value) return;
        state.guestbook.status = value;
        state.guestbook.page = 1;
        await loadGuestbook({ force: true });
        render();
      }, `small-button${state.guestbook.status === value ? ' is-active' : ''}`));
    });
    body.append(filters);
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
    const heading = el('div', 'guestbook-admin-heading');
    heading.append(el('h3', '', msg.nickname), pill(statusText[msg.status] || msg.status || '未读'));
    if(msg.feedback_status)heading.append(pill('处理进度：'+(statusText[msg.feedback_status]||msg.feedback_status)));
    else heading.append(el('span','admin-meta','游客留言 · 无站内回复'));
    head.append(heading);
    const meta = el('p', 'admin-meta', `${msg.created_at} · IP: ${msg.ip_address}`);
    const content = el('p', 'admin-reason', msg.content);
    const actions = el('div', 'card-actions');
    const statusActions = [];
    if (msg.status === 'unread') statusActions.push(button('标记已读', () => updateGuestbookStatus(msg, 'read'), 'small-button is-active'));
    if (msg.status === 'read') statusActions.push(button('归档', () => updateGuestbookStatus(msg, 'archived'), 'small-button'));
    if (msg.status === 'archived') statusActions.push(button('恢复待处理', () => updateGuestbookStatus(msg, 'read'), 'small-button'));
    const delBtn = button('删除留言', async () => {
      if (!confirm('确定要删除这条留言吗？')) return;
      await api(`/api/guestbook/${msg.id}`, { method: 'DELETE' });
      await loadGuestbook({ force: true });
      render();
      setNotice('留言已删除');
    }, 'small-button danger-button');
    if (msg.user_id) actions.append(button('查看进度 / 回复用户', () => window.JccFeedback.openAdmin('guestbook', msg.id, api, async () => { await loadGuestbook({ force: true }); render(); })));
    actions.append(...statusActions, delBtn);
    card.append(head, meta, content, actions);
    return card;
  }

  async function updateGuestbookStatus(msg, status) {
    await api(`/api/guestbook/${msg.id}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status }),
    });
    await loadGuestbook({ force: true });
    render();
    setNotice(status === 'archived' ? '留言已归档' : status === 'read' ? '留言已标记为已读' : '留言已恢复');
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
    if (noticeEditorCleanup) { noticeEditorCleanup(); noticeEditorCleanup = null; }
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
    if (state.liveSeasonCreateBusy) return;
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
    titleWrap.append(title, el('p', 'admin-meta', '后台隐藏的赛季收在「未展示赛季」；上传阵容数据后再启用展示。此处创建的分类也用于普通阵容。'));
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
    overlay.querySelectorAll('input, select, button').forEach(node => { node.disabled = state.liveSeasonCreateBusy; });
    dialogRoot.append(overlay);
  }

  async function submitLiveSeasonCreate(event) {
    event.preventDefault();
    if (state.liveSeasonCreateBusy) return;
    const form = event.currentTarget;
    const payload = {
      id: form.querySelector('#liveSeasonIdInput').value.trim(),
      name: form.querySelector('#liveSeasonNameInput').value.trim(),
      description: form.querySelector('#liveSeasonDescriptionInput').value.trim(),
      status: form.querySelector('#liveSeasonStatusInput').value,
    };
    state.liveSeasonCreating = { ...payload };
    state.liveSeasonCreateBusy = true;
    renderDialogs();
    try {
      const result = await api('/api/admin/live-comps/seasons', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      applyLiveSeasonManifest(result);
    } catch (error) {
      state.liveSeasonCreateBusy = false;
      state.liveSeasonCreateError = error.message || '创建失败';
      window.jccNotify.show(state.liveSeasonCreateError, { variant: 'error' });
      renderDialogs();
      return;
    }
    state.liveSeasonCreateBusy = false;
    if (['hidden', 'disabled'].includes(payload.status)) state.liveSeasonUi.expanded = true;
    closeLiveSeasonCreateDialog();
    setNotice(`赛季「${payload.name}」已创建`);
    render();
  }

  function renderNoticeDialog() {
    if (!dialogRoot || !state.noticeEditing) return;
    noticeEditorCleanup = window.JccNoticeEditor.mount(dialogRoot, {
      item: state.noticeEditing,
      api,
      close: closeNoticeDialog,
      async saved(item, publish) {
        closeNoticeDialog();
        await refreshNoticeAfterWrite(publish ? '通知已保存并展示' : '通知已保存');
      },
    });
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
      window.jccNotify.show(state.passwordError, { variant: 'error' });
      renderDialogs();
      return;
    }
    if (password !== confirmPassword) {
      state.passwordError = '两次输入的密码不一致';
      window.jccNotify.show(state.passwordError, { variant: 'error' });
      renderDialogs();
      return;
    }
    try {
      await api(`/api/admin/users/${state.passwordUser.id}`, {
        method: 'PUT', body: JSON.stringify({ password }),
      });
    } catch (error) {
      state.passwordError = error.message || '密码修改失败';
      window.jccNotify.show(state.passwordError, { variant: 'error' });
      renderDialogs();
      return;
    }
    const passwordUser = state.passwordUser;
    closePasswordDialog();
    await loadUsers({ force: true });
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
      window.jccNotify.show(state.liveCompManualCodeError, { variant: 'error' });
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
    await loadUsers({ force: true });
    await loadOverview({ force: true });
    setNotice('用户已禁用');
  }

  function setNotice(text, variant = 'success') {
    window.jccNotify.show(text, { variant });
    render();
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
