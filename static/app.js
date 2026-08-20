const HOME_VIEW_CACHE_TTL = 60000;

const state = {
  lineups: [],
  liveCompsSummary: null,
  liveCompsPage: null,
  homeStats: { total_public_lineups: 0 },
  lineupSeasons: [],
  liveCompSeasons: [],
  selectedLineupSeasonId: null,
  selectedLiveCompSeasonId: null,
  imageMode: localStorage.getItem('homeImageMode') || 'text',
  requestControllers: {
    lineups: null,
    liveComps: null,
  },
  homeViewCache: {
    lineups: new Map(),
    liveComps: new Map(),
  },
  query: '',
  sort: 'live',
  view: 'live-comps',
  user: null,
  csrfToken: '',
  page: 1,
  pageSize: 10,
  total: 0,
  totalPages: 1,
};

const LINEUP_PAGE_SIZE = 10;

const $ = (selector) => document.querySelector(selector);
const elements = {
  accountToggle: $('#accountToggle'),
  accountToggleText: $('#accountToggleText'),
  accountMenu: $('#accountMenu'),
  menuAuthLink: $('#menuAuthLink'),
  menuAccountLink: $('#menuAccountLink'),
  menuCreateLineupLink: $('#menuCreateLineupLink'),
  menuAdminLink: $('#menuAdminLink'),
  menuLogoutButton: $('#menuLogoutButton'),
  createLineupLink: $('#createLineupLink'),
  imageModeToggle: $('#imageModeToggle'),
  imageModeIcon: $('#imageModeIcon'),
  imageModeText: $('#imageModeText'),
  searchClear: $('#searchClear'),
  searchInput: $('#searchInput'),
  searchClearMirror: $('#searchClearMirror'),
  searchClearPlaceholder: $('#searchClearPlaceholder'),
  searchClearGlow: $('#searchClearGlow'),
  searchClearButton: $('#searchClearButton'),
  lineupList: $('#lineupList'),
  emptyState: $('#emptyState'),
  message: $('#message'),
  lineupCount: $('#lineupCount'),
  currentDisplayCount: $('#currentDisplayCount'),
  seasonFilterToggle: $('#seasonFilterToggle'),
  seasonFilterText: $('#seasonFilterText'),
  seasonFilterMenu: $('#seasonFilterMenu'),
  seasonMenuWrap: $('#seasonMenuWrap'),
  favoritesTab: $('#favoritesTab'),
  mineTab: $('#mineTab'),
  tabs: $('#tabs'),
  tabIndicator: $('#tabIndicator'),
  pagination: $('#pagination'),
  themeToggle: $('#themeToggle'),
  themeIcon: $('#themeIcon'),
  themeText: $('#themeText'),
  toast: $('#toast'),
  authPromptRoot: $('#authPromptRoot'),
  listTitle: $('#listTitle'),
  listHeading: $('#listHeading'),
  heroDescription: $('#heroDescription'),
  mobileResourceTrigger: $('#mobileResourceTrigger'),
  mobileResourceDialog: $('#mobileResourceDialog'),
  mobileResourceClose: $('#mobileResourceClose'),
};

const searchClear = window.JccHomeTransitions.createSearchClear({
  root: elements.searchClear,
  input: elements.searchInput,
  mirror: elements.searchClearMirror,
  placeholder: elements.searchClearPlaceholder,
  glow: elements.searchClearGlow,
  button: elements.searchClearButton,
  onClear: clearLineupSearch,
});
const lineupLoader = window.JccHomeTransitions.createLineupLoader({
  container: elements.lineupList,
  count: 3,
});
const paginationCompactQuery = globalThis.matchMedia('(max-width: 520px)');
const mobileResourceQuery = globalThis.matchMedia('(max-width: 520px)');
let pendingPaginationScroll = false;

setTheme(localStorage.getItem('theme') || 'light');
renderHomeImageModeToggle();
applyBorderGlowToStaticCards();
boot();

elements.imageModeToggle?.addEventListener('click', toggleHomeImageMode);
elements.themeToggle.addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
elements.accountToggle.addEventListener('click', handleAccountToggle);
elements.menuLogoutButton.addEventListener('click', logout);
elements.menuAuthLink.addEventListener('click', () => {
  trackGrowth('click_login_entry', { source: 'account_menu' });
});
document.addEventListener('click', closeAccountMenuOnOutsideClick);
document.addEventListener('keydown', closeAccountMenuOnEscape);
elements.searchInput.addEventListener('input', (event) => searchClear.sync(event.target.value));
elements.searchInput.addEventListener('input', debounce((event) => {
  if (state.view === 'live-comps') return;
  cancelPaginationNavigation();
  state.query = event.target.value.trim();
  state.page = 1;
  loadLineups();
}, 180));
elements.seasonFilterToggle?.addEventListener('click', toggleSeasonMenu);
document.addEventListener('click', closeSeasonMenuOnOutsideClick);
document.addEventListener('keydown', closeSeasonMenuOnEscape);
elements.tabs.addEventListener('click', (event) => {
  const tab = event.target.closest('.tab');
  if (!tab) return;
  if (!state.user && tab.dataset.view === 'favorites') {
    requireAuthIntent({ type: 'open_view_favorites' }, '登录后可收藏阵容并随时找回');
    return;
  }
  if (!state.user && tab.dataset.view === 'mine') {
    requireAuthIntent({ type: 'open_view_mine' }, '登录后可查看和管理你发布的阵容');
    return;
  }
  setActiveTab(tab.dataset.sort, tab.dataset.view);
  loadCurrentView();
});
window.addEventListener('resize', updateTabIndicator);
elements.pagination.addEventListener('click', (event) => {
  const button = event.target.closest('[data-page]');
  if (!button) return;
  const nextPage = Number(button.dataset.page);
  if (!nextPage || nextPage === state.page) return;
  state.page = nextPage;
  pendingPaginationScroll = true;
  loadCurrentView();
});
paginationCompactQuery.addEventListener('change', () => renderPagination());
elements.createLineupLink.addEventListener('click', (event) => {
  if (state.user) return;
  event.preventDefault();
  requireAuthIntent({ type: 'open_create_lineup' }, '登录后可发布和管理自己的阵容');
});
elements.mobileResourceTrigger?.addEventListener('click', openMobileResourceDialog);
elements.mobileResourceClose?.addEventListener('click', closeMobileResourceDialog);
elements.mobileResourceDialog?.addEventListener('close', handleMobileResourceDialogClosed);
elements.mobileResourceDialog?.addEventListener('cancel', (event) => {
  event.preventDefault();
  closeMobileResourceDialog();
});
elements.mobileResourceDialog?.addEventListener('click', (event) => {
  if (event.target === elements.mobileResourceDialog) closeMobileResourceDialog();
});
elements.mobileResourceDialog?.querySelectorAll('a').forEach((link) => {
  link.addEventListener('click', closeMobileResourceDialog);
});
mobileResourceQuery.addEventListener('change', (event) => {
  if (!event.matches) closeMobileResourceDialog({ restoreFocus: false });
});
document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape' || !elements.mobileResourceDialog?.open) return;
  event.preventDefault();
  closeMobileResourceDialog();
});

function openMobileResourceDialog() {
  if (!elements.mobileResourceDialog || elements.mobileResourceDialog.open) return;
  elements.mobileResourceTrigger?.setAttribute('aria-expanded', 'true');
  elements.mobileResourceDialog.showModal();
}

function closeMobileResourceDialog({ restoreFocus = true } = {}) {
  if (!elements.mobileResourceDialog?.open) return;
  elements.mobileResourceDialog.dataset.restoreFocus = String(restoreFocus);
  elements.mobileResourceDialog.close();
}

function handleMobileResourceDialogClosed() {
  elements.mobileResourceTrigger?.setAttribute('aria-expanded', 'false');
  const restoreFocus = elements.mobileResourceDialog?.dataset.restoreFocus !== 'false';
  if (elements.mobileResourceDialog) delete elements.mobileResourceDialog.dataset.restoreFocus;
  if (restoreFocus) elements.mobileResourceTrigger?.focus();
}

async function boot() {
  await loadMe();
  applySavedMessage();
  await consumePendingIntent();
  loadHomeStats();
  await loadCurrentView();
  renderGuestbookTrigger();
}

function renderHomeImageModeToggle() {
  if (!elements.imageModeToggle || !elements.imageModeText) return;
  const isImageMode = state.imageMode === 'image';
  if (elements.imageModeIcon) elements.imageModeIcon.textContent = isImageMode ? '有' : '无';
  elements.imageModeText.textContent = isImageMode ? '有图' : '无图';
  elements.imageModeToggle.setAttribute('aria-pressed', String(isImageMode));
  elements.imageModeToggle.setAttribute('aria-label', isImageMode ? '切换为首页无图片模式' : '切换为首页有图片模式');
}

function initBorderGlowCard(card, options = {}) {
  if (!card || card.dataset.borderGlowReady === 'true') return;
  if (window.matchMedia?.('(hover: none), (pointer: coarse)').matches) return;
  card.dataset.borderGlowReady = 'true';
  card.classList.add('border-glow-card');

  const {
    glowColor = 'rgba(245, 185, 92, 0.92)',
    glowColorSoft = 'rgba(201, 100, 66, 0.28)',
    glowColorFaint = 'rgba(245, 185, 92, 0.16)',
    fillOpacity = '0.18',
    edgeSensitivity = '34',
    coneSpread = '22',
    initialSweep = false,
  } = options;

  card.style.setProperty('--glow-color', glowColor);
  card.style.setProperty('--glow-color-soft', glowColorSoft);
  card.style.setProperty('--glow-color-faint', glowColorFaint);
  card.style.setProperty('--fill-opacity', fillOpacity);
  card.style.setProperty('--edge-sensitivity', edgeSensitivity);
  card.style.setProperty('--cone-spread', coneSpread);

  if (!card.querySelector(':scope > .edge-light')) {
    const edgeLight = document.createElement('span');
    edgeLight.className = 'edge-light';
    edgeLight.setAttribute('aria-hidden', 'true');
    card.prepend(edgeLight);
  }

  card.addEventListener('pointermove', handleBorderGlowPointerMove);
  card.addEventListener('pointerleave', handleBorderGlowPointerLeave);

  if (initialSweep && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    runBorderGlowSweep(card);
  }
}

function handleBorderGlowPointerMove(event) {
  const card = event.currentTarget;
  const rect = card.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const cx = rect.width / 2;
  const cy = rect.height / 2;
  const dx = x - cx;
  const dy = y - cy;
  const kx = dx === 0 ? Infinity : cx / Math.abs(dx);
  const ky = dy === 0 ? Infinity : cy / Math.abs(dy);
  const edge = Math.min(Math.max(1 / Math.min(kx, ky), 0), 1);
  let angle = Math.atan2(dy, dx) * (180 / Math.PI) + 90;
  if (angle < 0) angle += 360;
  card.style.setProperty('--edge-proximity', `${(edge * 100).toFixed(3)}`);
  card.style.setProperty('--cursor-angle', `${angle.toFixed(3)}deg`);
}

function handleBorderGlowPointerLeave(event) {
  event.currentTarget.style.setProperty('--edge-proximity', '0');
}

function runBorderGlowSweep(card) {
  card.classList.add('border-glow-sweep');
  card.style.setProperty('--cursor-angle', '115deg');
  window.setTimeout(() => {
    card.style.setProperty('--cursor-angle', '430deg');
  }, 80);
  window.setTimeout(() => {
    card.classList.remove('border-glow-sweep');
    card.style.setProperty('--edge-proximity', '0');
  }, 1200);
}

function applyBorderGlowToStaticCards() {
  const statCard = document.querySelector('[data-border-glow="stat"]');
  initBorderGlowCard(statCard, {
    fillOpacity: '0.14',
    edgeSensitivity: '38',
    coneSpread: '20',
    initialSweep: true,
  });
}

function toggleHomeImageMode() {
  state.imageMode = state.imageMode === 'image' ? 'text' : 'image';
  localStorage.setItem('homeImageMode', state.imageMode);
  renderHomeImageModeToggle();
  if (state.view === 'live-comps') {
    renderLiveComps();
  }
}

async function api(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  if (state.csrfToken && ['POST', 'PUT', 'DELETE'].includes(options.method)) headers['X-CSRF-Token'] = state.csrfToken;
  const response = await fetch(url, { ...options, headers });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.error || '操作失败');
  return data;
}

async function trackGrowth(eventName, payload = {}) {
  if (!state.csrfToken) return;
  await fetch('/api/growth-events', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': state.csrfToken },
    body: JSON.stringify({
      event_name: eventName,
      page_key: 'home',
      ref_lineup_id: payload.lineupId || null,
      payload,
    }),
  }).catch(() => {});
}

function abortHomeRequest(kind) {
  const controller = state.requestControllers[kind];
  if (controller) controller.abort();
}

function homeCacheKey(kind, keyParts) {
  return `${kind}:${keyParts.map((part) => String(part ?? '')).join('|')}`;
}

function readHomeCache(kind, key) {
  const cached = state.homeViewCache[kind].get(key);
  if (!cached) return null;
  if (Date.now() - cached.loadedAt > HOME_VIEW_CACHE_TTL) {
    state.homeViewCache[kind].delete(key);
    return null;
  }
  return cached.value;
}

function writeHomeCache(kind, key, value) {
  state.homeViewCache[kind].set(key, {
    loadedAt: Date.now(),
    value,
  });
}

function invalidateHomeViewCache(kind = null) {
  if (kind) {
    state.homeViewCache[kind]?.clear();
    return;
  }
  Object.values(state.homeViewCache).forEach((cache) => cache.clear());
}

async function fetchCachedJson(kind, key, url, signal) {
  const cached = readHomeCache(kind, key);
  if (cached) return cached;
  const data = await fetch(url, { signal }).then((response) => response.json());
  writeHomeCache(kind, key, data);
  return data;
}

function isAbortError(error) {
  return error?.name === 'AbortError';
}

async function loadMe() {
  const data = await fetch('/api/me').then((response) => response.json());
  state.user = data.user;
  state.csrfToken = data.csrf_token;
  renderAuth();
}

async function loadHomeStats() {
  try {
    const payload = await fetch('/api/home-stats').then((response) => response.json());
    state.homeStats = {
      total_public_lineups: Number(payload.total_public_lineups || 0),
    };
    renderHomeStats();
  } catch (_) {
    renderHomeStats();
  }
}

function renderHomeStats() {
  if (!elements.lineupCount) return;
  elements.lineupCount.textContent = state.homeStats.total_public_lineups;
}

async function loadLineupSeasons() {
  if (state.lineupSeasons.length) return;
  const payload = await fetch('/api/lineup-seasons').then((response) => response.json());
  state.lineupSeasons = payload.seasons || [];
  state.selectedLineupSeasonId = state.selectedLineupSeasonId || payload.default_season_id || state.lineupSeasons[0]?.id || '';
  renderLineupSeasonFilter();
}

async function loadLiveCompSeasons() {
  if (state.liveCompSeasons.length) return;
  const payload = await fetch('/api/live-comps/seasons').then((response) => response.json());
  state.liveCompSeasons = payload.seasons || [];
  state.selectedLiveCompSeasonId = state.selectedLiveCompSeasonId || payload.default_season_id || state.liveCompSeasons[0]?.id || '';
  renderLineupSeasonFilter();
}

function toggleSeasonMenu(event) {
  event.stopPropagation();
  const willOpen = elements.seasonFilterMenu.classList.contains('hidden');
  elements.seasonFilterMenu.classList.toggle('hidden', !willOpen);
  elements.seasonFilterToggle.classList.toggle('is-open', willOpen);
  elements.seasonFilterToggle.setAttribute('aria-expanded', String(willOpen));
}

function closeSeasonMenu() {
  if (!elements.seasonFilterMenu || !elements.seasonFilterToggle) return;
  elements.seasonFilterMenu.classList.add('hidden');
  elements.seasonFilterToggle.classList.remove('is-open');
  elements.seasonFilterToggle.setAttribute('aria-expanded', 'false');
}

function closeSeasonMenuOnOutsideClick(event) {
  if (event.target.closest('#seasonMenuWrap')) return;
  closeSeasonMenu();
}

function closeSeasonMenuOnEscape(event) {
  if (event.key === 'Escape') closeSeasonMenu();
}

function renderAuth() {
  const loggedIn = Boolean(state.user);
  const nickname = state.user?.nickname || state.user?.username || '';
  const isAdmin = Boolean(state.user && state.user.role === 'admin');
  elements.mineTab.classList.toggle('hidden', !loggedIn);
  elements.favoritesTab.classList.remove('hidden');
  elements.accountToggleText.textContent = loggedIn ? `${isAdmin ? '管理员' : '已登录'} · ${nickname}` : '登录 / 注册';
  elements.menuAuthLink.classList.add('hidden');
  elements.menuAccountLink.classList.toggle('hidden', !loggedIn);
  elements.menuCreateLineupLink.classList.toggle('hidden', !loggedIn);
  elements.menuAdminLink.classList.toggle('hidden', !isAdmin);
  elements.menuLogoutButton.classList.toggle('hidden', !loggedIn);
  if (elements.heroDescription) {
    elements.heroDescription.textContent = loggedIn
      ? '保存、搜索、点赞和复制阵容码。收藏、个人中心和跨设备同步已开启。'
      : '保存、搜索、点赞和复制阵容码。登录后可收藏阵容并跨设备同步，登录后可查看我的收藏和我的阵容。';
  }
  elements.createLineupLink.href = loggedIn ? '/lineup/new' : '/auth';
  elements.createLineupLink.textContent = loggedIn ? '新增阵容' : '登录后新增阵容';
  if (!loggedIn && (state.view === 'mine' || state.view === 'favorites')) {
    state.sort = 'live';
    state.view = 'live-comps';
    state.page = 1;
  }
  closeAccountMenu();
  syncActiveTab();
}

function handleAccountToggle(event) {
  if (!state.user) {
    trackGrowth('click_login_entry', { source: 'header' });
    window.location.href = '/auth';
    return;
  }
  toggleAccountMenu(event);
}

function toggleAccountMenu(event) {
  event.stopPropagation();
  const willOpen = elements.accountMenu.classList.contains('hidden');
  elements.accountMenu.classList.toggle('hidden', !willOpen);
  elements.accountToggle.classList.toggle('is-open', willOpen);
  elements.accountToggle.setAttribute('aria-expanded', String(willOpen));
}

function closeAccountMenu() {
  elements.accountMenu.classList.add('hidden');
  elements.accountToggle.classList.remove('is-open');
  elements.accountToggle.setAttribute('aria-expanded', 'false');
}

function closeAccountMenuOnOutsideClick(event) {
  if (event.target.closest('#accountMenuWrap')) return;
  closeAccountMenu();
}

function closeAccountMenuOnEscape(event) {
  if (event.key === 'Escape') closeAccountMenu();
}
async function logout() {
  await api('/api/logout', { method: 'POST' });
  invalidateHomeViewCache('lineups');
  state.user = null;
  state.sort = 'live';
  state.view = 'live-comps';
  state.page = 1;
  closeAuthPrompt(true);
  showMessage('已退出登录');
  renderAuth();
  await loadCurrentView();
}

async function loadLineups(options = {}) {
  await loadLineupSeasons();
  const params = new URLSearchParams({
    sort: state.sort,
    view: state.view,
    page: String(state.page),
    page_size: String(LINEUP_PAGE_SIZE),
  });
  if (state.query) params.set('q', state.query);
  if (state.selectedLineupSeasonId) params.set('season', state.selectedLineupSeasonId);
  const requestKey = homeCacheKey('lineups', [
    state.user?.id || 'guest',
    state.view,
    state.sort,
    state.query,
    state.selectedLineupSeasonId || '',
    state.page,
    LINEUP_PAGE_SIZE,
  ]);
  const cachedResponse = readHomeCache('lineups', requestKey);
  const shouldShowLoading = !cachedResponse && !options.preserveContent;
  if (shouldShowLoading) lineupLoader.showLoading();
  abortHomeRequest('lineups');
  const controller = new AbortController();
  state.requestControllers.lineups = controller;
  try {
    const response = cachedResponse || await fetchCachedJson('lineups', requestKey, `/api/lineups?${params}`, controller.signal);
    if (state.requestControllers.lineups !== controller) return;
    state.lineups = response.items || [];
    state.total = response.total ?? state.lineups.length;
    state.page = response.page ?? 1;
    state.pageSize = response.page_size ?? state.pageSize;
    state.totalPages = response.total_pages ?? 1;
    renderLineups({ animate: shouldShowLoading });
    renderPagination();
    completePaginationNavigation();
  } catch (error) {
    if (isAbortError(error)) return;
    if (state.requestControllers.lineups === controller) lineupLoader.fail();
    if (state.requestControllers.lineups === controller) cancelPaginationNavigation();
    throw error;
  } finally {
    if (state.requestControllers.lineups === controller) state.requestControllers.lineups = null;
  }
}

function syncSearchInputState(isLiveComps) {
  const placeholder = isLiveComps
    ? '实时阵容排行暂不支持搜索'
    : '搜索阵容名称，例如：九五、卡莎、斗士';
  elements.searchInput.value = isLiveComps ? '' : state.query;
  searchClear.setDisabled(isLiveComps, placeholder);
  searchClear.sync(elements.searchInput.value);
}

function clearLineupSearch() {
  cancelPaginationNavigation();
  state.query = '';
  state.page = 1;
  loadLineups();
}

async function loadCurrentView() {
  const isLiveComps = state.view === 'live-comps';
  abortHomeRequest(isLiveComps ? 'lineups' : 'liveComps');
  syncSearchInputState(isLiveComps);
  elements.listTitle.textContent = isLiveComps ? '实时阵容排行' : '阵容列表';
  if (isLiveComps) {
    await loadLiveComps();
    return;
  }
  await loadLineups();
}

async function loadLiveComps() {
  await loadLiveCompSeasons();
  const seasonQuery = state.selectedLiveCompSeasonId ? `&season=${encodeURIComponent(state.selectedLiveCompSeasonId)}` : '';
  const summarySeasonQuery = state.selectedLiveCompSeasonId ? `?season=${encodeURIComponent(state.selectedLiveCompSeasonId)}` : '';
  const seasonKey = state.selectedLiveCompSeasonId || 'default';
  abortHomeRequest('liveComps');
  const controller = new AbortController();
  state.requestControllers.liveComps = controller;
  try {
    const [summary, pagePayload] = await Promise.all([
      fetchCachedJson('liveComps', homeCacheKey('liveSummary', [seasonKey]), `/api/live-comps/summary${summarySeasonQuery}`, controller.signal),
      fetchCachedJson('liveComps', homeCacheKey('livePage', [seasonKey, state.page]), `/api/live-comps?page=${state.page}${seasonQuery}`, controller.signal),
    ]);
    state.liveCompsSummary = summary;
    state.liveCompsPage = pagePayload;
    state.total = pagePayload.total ?? 0;
    state.page = pagePayload.page ?? 1;
    state.pageSize = pagePayload.page_size ?? state.pageSize;
    state.totalPages = pagePayload.total_pages ?? 1;
    renderLiveComps();
    renderPagination();
    completePaginationNavigation();
  } catch (error) {
    if (isAbortError(error)) return;
    if (state.requestControllers.liveComps === controller) cancelPaginationNavigation();
    throw error;
  } finally {
    if (state.requestControllers.liveComps === controller) state.requestControllers.liveComps = null;
  }
}

function renderLineupSeasonFilter() {
  if (!elements.seasonFilterMenu || !elements.seasonFilterText) return;
  elements.seasonFilterMenu.replaceChildren();
  const isLiveComps = state.view === 'live-comps';
  const seasons = isLiveComps ? state.liveCompSeasons : state.lineupSeasons;
  const selectedSeasonId = isLiveComps ? state.selectedLiveCompSeasonId : state.selectedLineupSeasonId;
  const selectedSeason = seasons.find((season) => season.id === selectedSeasonId) || seasons[0] || {};
  elements.seasonFilterText.textContent = selectedSeason.name || selectedSeason.id || '赛季';
  seasons.forEach((season) => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = `account-menu-item${season.id === selectedSeasonId ? ' is-active' : ''}`;
    item.textContent = season.name || season.id;
    item.addEventListener('click', async () => {
      if (selectedSeasonId === season.id) {
        closeSeasonMenu();
        return;
      }
      if (isLiveComps) {
        state.selectedLiveCompSeasonId = season.id;
      } else {
        state.selectedLineupSeasonId = season.id;
      }
      state.page = 1;
      cancelPaginationNavigation();
      closeSeasonMenu();
      renderLineupSeasonFilter();
      await loadCurrentView();
    });
    elements.seasonFilterMenu.append(item);
  });
}

function renderLineups(options = {}) {
  renderCurrentDisplayCount();
  elements.emptyState.classList.toggle('hidden', state.total > 0);
  renderEmptyState();
  const cards = state.lineups.map(createLineupCard);
  lineupLoader.reveal(cards, options);
}

function createLineupCard(lineup) {
  const card = document.createElement('article');
  card.className = 'lineup-card';
  const title = document.createElement('h3');
  title.className = 'lineup-title';
  title.textContent = `${lineup.name} · ${lineup.rank_level}`;
  const meta = document.createElement('div');
  meta.className = 'card-time';
  meta.append('由 ');
  const authorLink = document.createElement('a');
  authorLink.className = 'author-link';
  authorLink.href = `/author/${encodeURIComponent(lineup.owner_username || '')}`;
  authorLink.textContent = lineup.owner_nickname;
  meta.append(authorLink, ` 上传 · 赞 ${lineup.like_count} · 复制 ${lineup.copy_count} · ${lineup.updated_at}`);
  const code = document.createElement('pre');
  code.className = 'code-preview';
  code.textContent = lineup.code;
  const actions = document.createElement('div');
  actions.className = 'card-actions';
  actions.append(button('复制阵容码', () => copyLineup(lineup)));
  actions.append(button('查看', () => openLineupDetail(lineup.id)));
  actions.append(button(lineup.is_liked_today ? '今日已赞' : '点赞', () => likeLineup(lineup), '', Boolean(state.user && lineup.is_liked_today)));
  actions.append(button(lineup.is_favorited ? '取消收藏' : '收藏', () => favoriteLineup(lineup)));
  actions.append(button('举报', () => reportLineup(lineup)));
  if (lineup.can_hide) actions.append(button('隐藏阵容', () => hideLineup(lineup), 'danger-button'));
  if (lineup.can_edit) actions.append(button('编辑', () => openEditor(lineup.id)));
  if (lineup.can_delete) actions.append(button('删除', () => deleteLineup(lineup), 'danger-button'));
  card.append(title, meta, code, actions);
  return card;
}

function renderEmptyState() {
  const title = elements.emptyState.querySelector('h3');
  const description = elements.emptyState.querySelector('p');
  if (state.total > 0 || !title || !description) return;
  if (state.view === 'live-comps') {
    title.textContent = '还没有实时阵容';
    description.textContent = '上传 `team_codes_by_tier.verify.json` 后，这里会直接展示实时阵容排行。';
    return;
  }
  if (state.view === 'favorites') {
    title.textContent = '还没有收藏阵容';
    description.textContent = state.user
      ? '你收藏的阵容会出现在这里，可随时回来查看和复制。'
      : '登录后可收藏阵容并随时找回，收藏内容会跟随账号同步。';
    return;
  }
  if (state.view === 'mine') {
    title.textContent = '还没有你的阵容';
    description.textContent = '登录后上传第一套阵容，管理和维护你自己的阵容库。';
    return;
  }
  title.textContent = '还没有阵容';
  description.textContent = '登录后上传第一套阵容，或切换到全部阵容查看公开内容。';
}

function renderPagination() {
  elements.pagination.replaceChildren();
  elements.pagination.classList.toggle('hidden', state.totalPages <= 1);
  if (state.totalPages <= 1) return;

  const content = document.createElement('ul');
  content.className = 'pagination-content';
  const prevButton = button('', () => {}, 'pagination-direction pagination-previous', state.page <= 1);
  prevButton.dataset.page = String(state.page - 1);
  prevButton.setAttribute('aria-label', '上一页');
  prevButton.append(paginationIcon('left'), paginationDirectionLabel('上一页'));
  content.append(paginationItem(prevButton));

  const compact = paginationCompactQuery.matches;
  buildPaginationItems(state.page, state.totalPages, compact).forEach((item) => {
    if (item.type === 'ellipsis') {
      const ellipsis = document.createElement('span');
      ellipsis.className = 'pagination-ellipsis';
      ellipsis.setAttribute('aria-hidden', 'true');
      ellipsis.append(paginationIcon('more'));
      const label = document.createElement('span');
      label.className = 'sr-only';
      label.textContent = '更多页面';
      ellipsis.append(label);
      content.append(paginationItem(ellipsis));
      return;
    }
    const pageNumber = item.page;
    const isActive = pageNumber === state.page;
    const pageButton = button(String(pageNumber), () => {}, `pagination-page${isActive ? ' is-active' : ''}`, isActive);
    pageButton.dataset.page = String(pageNumber);
    pageButton.setAttribute('aria-label', `前往第 ${pageNumber} 页`);
    if (isActive) pageButton.setAttribute('aria-current', 'page');
    content.append(paginationItem(pageButton));
  });

  const nextButton = button('', () => {}, 'pagination-direction pagination-next', state.page >= state.totalPages);
  nextButton.dataset.page = String(state.page + 1);
  nextButton.setAttribute('aria-label', '下一页');
  nextButton.append(paginationDirectionLabel('下一页'), paginationIcon('right'));
  content.append(paginationItem(nextButton));
  elements.pagination.append(content);
}

function paginationItem(child) {
  const item = document.createElement('li');
  item.className = 'pagination-item';
  item.append(child);
  return item;
}

function paginationDirectionLabel(text) {
  const label = document.createElement('span');
  label.className = 'pagination-direction-label';
  label.textContent = text;
  return label;
}

function paginationIcon(kind) {
  const icon = document.createElement('span');
  icon.className = `pagination-icon pagination-icon-${kind}`;
  if (kind === 'more') {
    for (let index = 0; index < 3; index += 1) {
      const dot = document.createElement('span');
      icon.append(dot);
    }
  }
  return icon;
}

function paginationPage(page) {
  return { type: 'page', page };
}

function paginationEllipsis(key) {
  return { type: 'ellipsis', key };
}

function buildPaginationItems(currentPage, totalPages, compact = false) {
  const desktopLimit = 7;
  const compactLimit = 5;
  const visibleLimit = compact ? compactLimit : desktopLimit;
  if (totalPages <= visibleLimit) {
    return Array.from({ length: totalPages }, (_, index) => paginationPage(index + 1));
  }
  if (compact) {
    if (currentPage <= 3) {
      return [paginationPage(1), paginationPage(2), paginationPage(3), paginationEllipsis('end'), paginationPage(totalPages)];
    }
    if (currentPage >= totalPages - 2) {
      return [paginationPage(1), paginationEllipsis('start'), paginationPage(totalPages - 2), paginationPage(totalPages - 1), paginationPage(totalPages)];
    }
    return [paginationPage(1), paginationEllipsis('start'), paginationPage(currentPage), paginationEllipsis('end'), paginationPage(totalPages)];
  }
  if (currentPage <= 4) {
    return [1, 2, 3, 4, 5].map(paginationPage).concat(paginationEllipsis('end'), paginationPage(totalPages));
  }
  if (currentPage >= totalPages - 3) {
    return [paginationPage(1), paginationEllipsis('start')].concat(
      [totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages].map(paginationPage)
    );
  }
  return [
    paginationPage(1),
    paginationEllipsis('start'),
    paginationPage(currentPage - 1),
    paginationPage(currentPage),
    paginationPage(currentPage + 1),
    paginationEllipsis('end'),
    paginationPage(totalPages),
  ];
}

function scrollToLineupList() {
  if (!elements.listHeading) return;
  const reduceMotion = globalThis.matchMedia('(prefers-reduced-motion: reduce)');
  elements.listHeading.scrollIntoView({
    behavior: reduceMotion.matches ? 'auto' : 'smooth',
    block: 'start',
  });
}

function completePaginationNavigation() {
  if (!pendingPaginationScroll) return;
  pendingPaginationScroll = false;
  scrollToLineupList();
}

function cancelPaginationNavigation() {
  pendingPaginationScroll = false;
}

function renderLiveComps() {
  elements.lineupList.replaceChildren();
  renderCurrentDisplayCount();
  elements.emptyState.classList.toggle('hidden', state.total > 0);
  renderEmptyState();
  if (!state.total) return;

  const shell = document.createElement('div');
  shell.className = 'live-comps-shell';
  shell.append(renderLiveCompsSummaryHeader());
  shell.append(renderLiveCompsGrid());
  elements.lineupList.append(shell);
}

function renderCurrentDisplayCount() {
  if (!elements.currentDisplayCount) return;
  const unit = state.view === 'live-comps' ? '套实时阵容' : '套阵容';
  elements.currentDisplayCount.textContent = `当前展示 ${state.total} ${unit}`;
}

function renderLiveCompsSummaryHeader() {
  const header = document.createElement('section');
  header.className = 'live-comps-summary';

  const title = document.createElement('h3');
  title.className = 'live-comps-summary-title';
  title.textContent = '实时阵容排行';

  const meta = document.createElement('p');
  meta.className = 'live-comps-summary-meta';
  meta.textContent = state.liveCompsSummary?.updated_at
    ? `共 ${state.total} 套 · 最近更新：${state.liveCompsSummary.updated_at}`
    : '最近更新：暂无数据';
  header.append(title, meta);
  return header;
}

function renderLiveCompsGrid() {
  const grid = document.createElement('div');
  grid.className = 'live-comps-grid';
  (state.liveCompsPage?.items || []).forEach((item) => {
    grid.append(renderLiveCompCard(item));
  });
  return grid;
}

function renderLiveCompCard(item) {
  const card = document.createElement('article');
  card.className = state.imageMode === 'image'
    ? `live-comp-card tier-${String(item.tier || '').toLowerCase()}`
    : `live-comp-card live-comp-card-text-only tier-${String(item.tier || '').toLowerCase()}`;
  card.dataset.borderGlow = 'live-comp';
  initBorderGlowCard(card, {
    fillOpacity: state.imageMode === 'image' ? '0.16' : '0.1',
    edgeSensitivity: '36',
    coneSpread: '21',
  });

  const actions = document.createElement('div');
  actions.className = 'live-comp-actions';
  actions.append(item.jccCode
    ? button('复制阵容码', () => copyLiveCompCode(item))
    : button('暂无阵容码', () => {}, '', true));
  if (item.hasFormationDetails) {
    const detail = document.createElement('a');
    detail.className = 'live-comp-detail-link';
    detail.href = `/live-comps/${encodeURIComponent(state.selectedLiveCompSeasonId)}/${encodeURIComponent(item.id)}`;
    detail.textContent = '→';
    detail.title = '查看阵容站位';
    detail.setAttribute('aria-label', `查看${item.title}的阵容站位`);
    actions.append(detail);
  }

  if (state.imageMode === 'image') {
    const header = document.createElement('div');
    header.className = 'live-comp-header';

    const avatarWrap = document.createElement('div');
    avatarWrap.className = 'live-comp-avatar-wrap';
    const avatar = document.createElement('img');
    avatar.className = 'live-comp-avatar';
    avatar.src = item.mainAvatar;
    avatar.alt = item.title;
    avatar.loading = 'lazy';
    avatar.decoding = 'async';
    const badge = document.createElement('span');
    badge.className = 'live-comp-avatar-badge';
    badge.textContent = item.tier;
    avatarWrap.append(avatar, badge);

    const body = document.createElement('div');
    body.className = 'live-comp-body';

    const name = document.createElement('h3');
    name.className = 'live-comp-name';
    name.textContent = item.title;

    const heroes = document.createElement('div');
    heroes.className = 'live-comp-hero-strip';
    (item.heroImages || []).forEach((src, index) => {
      const hero = document.createElement('img');
      hero.className = 'live-comp-hero';
      hero.src = src;
      hero.alt = `${item.title}-${index + 1}`;
      hero.loading = 'lazy';
      hero.decoding = 'async';
      heroes.append(hero);
    });

    body.append(name, heroes);
    header.append(avatarWrap, body);
    card.append(header, actions);
    return card;
  }

  const header = document.createElement('div');
  header.className = 'live-comp-text-header';

  const tierBadge = document.createElement('span');
  tierBadge.className = 'live-comp-tier-badge';
  tierBadge.textContent = item.tier || '—';

  const name = document.createElement('h3');
  name.className = 'live-comp-name';
  name.textContent = item.title;

  const caption = document.createElement('p');
  caption.className = 'live-comp-text-caption';
  caption.textContent = item.jccCode ? '实时阵容 · 可复制' : '实时阵容 · 暂无阵容码';

  header.append(tierBadge, name, caption);
  card.append(header, actions);
  return card;
}

async function copyLiveCompCode(item) {
  if (!item.jccCode) {
    showMessage('当前阵容暂无可复制的阵容码');
    return;
  }
  const copied = await writeClipboard(item.jccCode);
  if (!copied) {
    showMessage('复制失败，请长按阵容码手动复制');
    return;
  }
  try {
    const seasonQuery = state.selectedLiveCompSeasonId ? `?season=${encodeURIComponent(state.selectedLiveCompSeasonId)}` : '';
    const separator = seasonQuery ? '&' : '?';
    await api(`/api/live-comps/${encodeURIComponent(item.id)}/copy${seasonQuery}${separator}source=home`, { method: 'POST' });
  } catch (_) {
    showMessage('阵容码已复制，但次数统计失败');
    return;
  }
  showToast('阵容码已复制');
}

function button(label, handler, extraClass = '', disabled = false) {
  const element = document.createElement('button');
  element.type = 'button';
  element.className = `small-button ${extraClass}`.trim();
  element.textContent = label;
  element.disabled = disabled;
  element.addEventListener('click', () => handler(element));
  return element;
}

function setActiveTab(sort, view) {
  const previousView = state.view;
  cancelPaginationNavigation();
  syncSeasonSelectionForViewChange(previousView, view);
  state.sort = sort;
  state.view = view;
  state.page = 1;
  syncActiveTab();
  renderLineupSeasonFilter();
}

function syncSeasonSelectionForViewChange(previousView, nextView) {
  if (previousView === 'live-comps' && nextView !== 'live-comps' && state.selectedLiveCompSeasonId) {
    state.selectedLineupSeasonId = state.selectedLiveCompSeasonId;
  }
  if (previousView !== 'live-comps' && nextView === 'live-comps' && state.selectedLineupSeasonId) {
    state.selectedLiveCompSeasonId = state.selectedLineupSeasonId;
  }
}

function syncActiveTab() {
  document.querySelectorAll('.tab').forEach((item) => {
    const isActive = item.dataset.sort === state.sort && item.dataset.view === state.view;
    item.classList.toggle('active', isActive);
    item.setAttribute('aria-selected', String(isActive));
  });
  updateTabIndicator();
}

function updateTabIndicator() {
  if (!elements.tabs || !elements.tabIndicator) return;
  const activeTab = elements.tabs.querySelector('.tab.active:not(.hidden)');
  if (!activeTab) return;
  const tabRect = activeTab.getBoundingClientRect();
  const listRect = elements.tabs.getBoundingClientRect();
  elements.tabs.style.setProperty('--active-tab-width', `${tabRect.width}px`);
  elements.tabs.style.setProperty('--active-tab-left', `${tabRect.left - listRect.left + elements.tabs.scrollLeft}px`);
}

function openEditor(lineupId) {
  window.location.href = `/lineup/${lineupId}/edit`;
}

function openLineupDetail(lineupId) {
  window.location.href = `/lineup/${lineupId}`;
}

async function copyLineup(lineup) {
  const copied = await writeClipboard(lineup.code);
  if (!copied) {
    showMessage('复制失败，请长按阵容码手动复制');
    return;
  }
  await api(`/api/lineups/${lineup.id}/copy?source=home`, { method: 'POST' });
  if (!state.user) {
    window.jccHistoryStore?.pushLocalCopy(lineup);
  }
  invalidateHomeViewCache('lineups');
  showToast('复制成功！祝你把把吃鸡！');
  loadLineups({ preserveContent: true });
}

async function writeClipboard(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (_) {
  }
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', 'readonly');
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  textarea.style.pointerEvents = 'none';
  document.body.append(textarea);
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);
  const copied = document.execCommand('copy');
  textarea.remove();
  return copied;
}

function requireAuthIntent(intent, message) {
  if (state.user) return false;
  window.jccAuthIntent?.save(intent);
  showAuthPrompt(message);
  return true;
}

function showAuthPrompt(message) {
  closeAuthPrompt(false);
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) closeAuthPrompt(true);
  });

  const card = document.createElement('section');
  card.className = 'modal-card';

  const header = document.createElement('div');
  header.className = 'modal-header';
  const headerCopy = document.createElement('div');
  const title = document.createElement('h2');
  title.textContent = '登录后继续';
  const desc = document.createElement('p');
  desc.className = 'auth-prompt-copy';
  desc.textContent = message;
  headerCopy.append(title, desc);
  const closeButton = button('关闭', () => closeAuthPrompt(true));
  header.append(headerCopy, closeButton);

  const hint = document.createElement('p');
  hint.className = 'field-hint';
  hint.textContent = '登录后可收藏阵容、查看我的收藏。';

  const actions = document.createElement('div');
  actions.className = 'auth-prompt-actions';
  const cancelButton = button('稍后', () => closeAuthPrompt(true));
  const loginButton = document.createElement('button');
  loginButton.type = 'button';
  loginButton.className = 'primary-button auth-prompt-confirm';
  loginButton.textContent = '去登录';
  loginButton.addEventListener('click', () => {
    closeAuthPrompt(false);
    window.location.href = '/auth';
  });
  actions.append(cancelButton, loginButton);

  card.append(header, hint, actions);
  backdrop.append(card);
  elements.authPromptRoot.append(backdrop);
}

function closeAuthPrompt(clearIntent = false) {
  elements.authPromptRoot.replaceChildren();
  if (clearIntent) window.jccAuthIntent?.clear();
}

function closeReportDialog() {
  elements.authPromptRoot.replaceChildren();
}

async function likeLineup(lineup) {
  if (!state.user) trackGrowth('guest_click_like', { source: 'lineup-card', lineupId: lineup.id });
  if (requireAuthIntent({ type: 'like_lineup', lineupId: lineup.id }, '登录后可点赞并保留个人记录')) return;
  try {
    await api(`/api/lineups/${lineup.id}/like`, { method: 'POST' });
    invalidateHomeViewCache('lineups');
    showMessage('点赞成功');
    await loadLineups({ preserveContent: true });
  } catch (error) {
    showMessage(error.message);
  }
}

async function favoriteLineup(lineup) {
  if (!state.user) trackGrowth('guest_click_favorite', { source: 'lineup-card', lineupId: lineup.id });
  if (requireAuthIntent({ type: 'favorite_lineup', lineupId: lineup.id }, '登录后可收藏阵容并跨设备同步')) return;
  try {
    if (lineup.is_favorited) {
      await api(`/api/lineups/${lineup.id}/favorite`, { method: 'DELETE' });
      showMessage('已取消收藏');
    } else {
      await api(`/api/lineups/${lineup.id}/favorite`, { method: 'POST' });
      showMessage('收藏成功');
    }
    invalidateHomeViewCache('lineups');
    await loadLineups({ preserveContent: true });
  } catch (error) {
    showMessage(error.message);
  }
}

async function reportLineup(lineup) {
  if (!state.user) trackGrowth('guest_click_report', { source: 'lineup-card', lineupId: lineup.id });
  if (requireAuthIntent({ type: 'report_lineup', lineupId: lineup.id }, '登录后可举报问题阵容并保留处理记录')) return;
  showReportDialog(lineup);
}

function showReportDialog(lineup) {
  closeReportDialog();
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) closeReportDialog();
  });

  const card = document.createElement('section');
  card.className = 'modal-card';

  const header = document.createElement('div');
  header.className = 'modal-header';
  const headerCopy = document.createElement('div');
  const title = document.createElement('h2');
  title.textContent = '举报阵容';
  const desc = document.createElement('p');
  desc.className = 'auth-prompt-copy';
  desc.textContent = `请填写举报原因，管理员会处理「${lineup.name}」。`;
  headerCopy.append(title, desc);
  const closeButton = button('关闭', () => closeReportDialog());
  header.append(headerCopy, closeButton);

  const form = document.createElement('form');
  form.className = 'modal-form';
  const field = document.createElement('label');
  field.className = 'field';
  const label = document.createElement('span');
  label.textContent = '举报原因';
  const textarea = document.createElement('textarea');
  textarea.rows = 5;
  textarea.maxLength = 300;
  textarea.placeholder = '请简要说明问题，例如：阵容码无效、内容不实、违规信息等';
  field.append(label, textarea);

  const inlineMessage = document.createElement('div');
  inlineMessage.className = 'message';

  const actions = document.createElement('div');
  actions.className = 'auth-prompt-actions';
  const cancelButton = button('取消', () => closeReportDialog());
  const submitButton = document.createElement('button');
  submitButton.type = 'submit';
  submitButton.className = 'primary-button auth-prompt-confirm';
  submitButton.textContent = '提交举报';
  actions.append(cancelButton, submitButton);
  form.append(field, inlineMessage, actions);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const reason = textarea.value.trim();
    if (!reason) {
      inlineMessage.textContent = '请输入举报原因';
      return;
    }
    submitButton.disabled = true;
    inlineMessage.textContent = '';
    try {
      await api(`/api/lineups/${lineup.id}/report`, { method: 'POST', body: JSON.stringify({ reason }) });
      closeReportDialog();
      showMessage('举报已提交');
    } catch (error) {
      inlineMessage.textContent = error.message;
    } finally {
      submitButton.disabled = false;
    }
  });

  card.append(header, form);
  backdrop.append(card);
  elements.authPromptRoot.append(backdrop);
  textarea.focus();
}

async function hideLineup(lineup) {
  if (!confirm(`确定隐藏“${lineup.name}”吗？`)) return;
  await api(`/api/lineups/${lineup.id}/hide`, { method: 'POST' });
  invalidateHomeViewCache('lineups');
  showMessage('阵容已隐藏');
  await loadLineups();
}

async function consumePendingIntent() {
  stripResumeIntentFlag();
  if (!state.user) return;
  const intent = window.jccAuthIntent?.read();
  if (!intent) return;
  window.jccAuthIntent.clear();
  if (intent.type === 'open_view_favorites') {
    setActiveTab('latest', 'favorites');
    showMessage('已进入我的收藏');
    return;
  }
  if (intent.type === 'open_view_mine') {
    setActiveTab('latest', 'mine');
    showMessage('已进入我的阵容');
    return;
  }
  if (intent.type === 'favorite_lineup') {
    try {
      await api(`/api/lineups/${intent.lineupId}/favorite`, { method: 'POST' });
      invalidateHomeViewCache('lineups');
      showMessage('已自动完成收藏');
    } catch (error) {
      showMessage(error.message);
    }
    return;
  }
  if (intent.type === 'like_lineup') {
    try {
      await api(`/api/lineups/${intent.lineupId}/like`, { method: 'POST' });
      invalidateHomeViewCache('lineups');
      showMessage('已自动完成点赞');
    } catch (error) {
      showMessage(error.message);
    }
    return;
  }
  if (intent.type === 'report_lineup') {
    try {
      const response = await fetch(`/api/lineups/${intent.lineupId}`);
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.error || '阵容不存在');
      showReportDialog(data);
    } catch (error) {
      showMessage(error.message);
    }
  }
}

async function deleteLineup(lineup) {
  if (!confirm('确定删除这个阵容吗？')) return;
  await api(`/api/lineups/${lineup.id}`, { method: 'DELETE' });
  invalidateHomeViewCache('lineups');
  showMessage('删除成功');
  if (state.page > 1 && state.lineups.length === 1) state.page -= 1;
  loadLineups();
}

function applySavedMessage() {
  const params = new URLSearchParams(window.location.search);
  const saved = params.get('saved');
  if (!saved) return;
  showMessage(saved === 'edit' ? '阵容已更新' : '阵容已新增');
  params.delete('saved');
  const nextQuery = params.toString();
  history.replaceState({}, '', `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}`);
}

function stripResumeIntentFlag() {
  const params = new URLSearchParams(window.location.search);
  if (!params.has('resume_intent')) return;
  params.delete('resume_intent');
  const nextQuery = params.toString();
  history.replaceState({}, '', `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}`);
}

function showMessage(text) {
  elements.message.textContent = text;
  clearTimeout(showMessage.timer);
  showMessage.timer = setTimeout(() => {
    elements.message.textContent = '';
  }, 2600);
}

function showToast(text) {
  if (!elements.toast) {
    showMessage(text);
    return;
  }
  elements.toast.textContent = text;
  elements.toast.classList.add('is-visible');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    elements.toast.classList.remove('is-visible');
  }, 2200);
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  window.jccApplyThemeToggleState?.(theme, elements.themeToggle, elements.themeIcon, elements.themeText);
  if (!window.jccApplyThemeToggleState && elements.themeText) elements.themeText.textContent = theme === 'dark' ? '白天模式' : '夜间模式';
}

function debounce(callback, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => callback(...args), delay);
  };
}

(function initSiteNotice() {
  const banner = document.querySelector('#siteNotice');
  const closeButton = document.querySelector('#siteNoticeClose');
  if (!banner || !closeButton) return;

  if (document.cookie.split(';').some(function (item) { return item.trim().indexOf('notice_dismissed=1') === 0; })) {
    banner.remove();
    return;
  }

  closeButton.addEventListener('click', function () {
    var expires = new Date(Date.now() + 86400000).toUTCString();
    document.cookie = 'notice_dismissed=1; expires=' + expires + '; path=/; SameSite=Lax';
    banner.remove();
  });

  var jumpLink = banner.querySelector('.site-notice-jump');
  if (jumpLink) {
    jumpLink.addEventListener('click', function (event) {
      event.preventDefault();
      var seasonId = jumpLink.getAttribute('data-jump-season');
      var tabValue = jumpLink.getAttribute('data-jump-tab');
      if (!seasonId || !tabValue) return;

      var tabMap = {
        'live':        { sort: 'live',        view: 'live-comps' },
        'latest':      { sort: 'latest',      view: 'all' },
        'hot':         { sort: 'hot',         view: 'all' },
        'rising':      { sort: 'rising',      view: 'all' },
        'recommended': { sort: 'recommended', view: 'all' },
        'ss':          { sort: 'ss',          view: 'all' },
      };
      var target = tabMap[tabValue];
      if (!target) return;

      state.sort = target.sort;
      state.view = target.view;
      state.page = 1;
      if (target.view === 'live-comps') {
        state.selectedLiveCompSeasonId = seasonId;
      } else {
        state.selectedLineupSeasonId = seasonId;
      }

      renderLineupSeasonFilter();

      syncActiveTab();

      loadCurrentView().then(function () {
        var lineupList = document.getElementById('lineupList');
        if (lineupList) {
          lineupList.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });
  }
})();

function el(tag, className = '', text = '') {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function renderGuestbookTrigger() {
  const trigger = document.getElementById('guestbookTrigger');
  if (!trigger) return;
  trigger.querySelector('button').addEventListener('click', showGuestbookDialog);
}

function showGuestbookDialog() {
  closeGuestbookDialog();

  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) closeGuestbookDialog();
  });

  const card = document.createElement('section');
  card.className = 'modal-card guestbook-dialog';

  const header = document.createElement('div');
  header.className = 'modal-header';
  const headerCopy = document.createElement('div');
  const title = document.createElement('h2');
  title.textContent = '给站长留言';
  const desc = document.createElement('p');
  desc.className = 'auth-prompt-copy';
  desc.textContent = '有任何建议或想法？欢迎留言，站长会尽快查看。';
  headerCopy.append(title, desc);
  const closeBtn = button('关闭', closeGuestbookDialog);
  header.append(headerCopy, closeBtn);

  const form = document.createElement('form');
  form.className = 'modal-form';

  const nicknameField = el('div', 'field');
  const nicknameLabel = el('label', '', '昵称');
  const nicknameInput = el('input');
  nicknameInput.type = 'text';
  nicknameInput.maxLength = 20;
  nicknameInput.placeholder = '如何称呼你';
  nicknameInput.required = true;
  if (state.user) {
    nicknameInput.value = state.user.nickname || '';
    nicknameInput.readOnly = true;
    nicknameLabel.textContent = '昵称（已登录）';
  }
  nicknameField.append(nicknameLabel, nicknameInput);

  const contentField = el('div', 'field');
  const contentLabel = el('label', '', '留言内容');
  const contentInput = el('textarea');
  contentInput.placeholder = '写下你想对站长说的话...';
  contentInput.maxLength = 500;
  contentInput.required = true;
  contentInput.rows = 4;
  contentField.append(contentLabel, contentInput);

  const inlineMessage = document.createElement('div');
  inlineMessage.className = 'message';

  const actions = document.createElement('div');
  actions.className = 'auth-prompt-actions';
  const cancelBtn = button('取消', closeGuestbookDialog);
  const submitBtn = document.createElement('button');
  submitBtn.type = 'submit';
  submitBtn.className = 'primary-button auth-prompt-confirm';
  submitBtn.textContent = '提交留言';
  actions.append(cancelBtn, submitBtn);

  form.append(nicknameField, contentField, inlineMessage, actions);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const nickname = nicknameInput.value.trim();
    const content = contentInput.value.trim();
    if (!nickname) { inlineMessage.textContent = '请填写昵称'; return; }
    if (!content) { inlineMessage.textContent = '请填写留言内容'; return; }
    submitBtn.disabled = true;
    inlineMessage.textContent = '';
    try {
      const body = { content };
      if (!state.user) body.nickname = nickname;
      await api('/api/guestbook', { method: 'POST', body: JSON.stringify(body) });
      closeGuestbookDialog();
      showToast('感谢留言，站长会尽快查看');
    } catch (err) {
      inlineMessage.textContent = err.message || '留言失败，请稍后再试';
    } finally {
      submitBtn.disabled = false;
    }
  });

  card.append(header, form);
  backdrop.append(card);
  document.getElementById('authPromptRoot').append(backdrop);
}

function closeGuestbookDialog() {
  const root = document.getElementById('authPromptRoot');
  if (!root) return;
  const existing = root.querySelector('.modal-backdrop');
  if (existing) existing.remove();
}
