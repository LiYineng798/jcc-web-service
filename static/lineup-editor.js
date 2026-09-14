const root = document.querySelector('.editor-page-shell');
const mode = root?.dataset.pageMode || 'create';
const lineupId = root?.dataset.lineupId || '';
const $ = (selector) => document.querySelector(selector);
const elements = {
  form: $('#editorForm'),
  lineupId: $('#lineupId'),
  lineupVersion: $('#lineupVersion'),
  nameInput: $('#nameInput'),
  codeInput: $('#codeInput'),
  seasonSelect: $('#seasonSelect'),
  editorSeasonToggle: $('#editorSeasonToggle'),
  editorSeasonText: $('#editorSeasonText'),
  editorSeasonMenu: $('#editorSeasonMenu'),
  editorSeasonMenuWrap: $('#editorSeasonMenuWrap'),
  statusToggle: $('#statusToggle'),
  statusSummary: $('#statusSummary'),
  submitButton: $('#submitButton'),
  title: $('#editorTitle'),
  description: $('#editorDescription'),
  themeToggle: $('#themeToggle'),
  themeIcon: $('#themeIcon'),
  themeText: $('#themeText'),
};

const state = { user: null, csrfToken: '', seasons: [], defaultSeasonId: '', restricted: false, pending: false };

setTheme(localStorage.getItem('theme') || 'light');
boot();

elements.themeToggle.addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
elements.form.addEventListener('submit', saveLineup);
elements.statusToggle?.addEventListener('change', syncStatusSummary);
elements.editorSeasonToggle?.addEventListener('click', toggleEditorSeasonMenu);
document.addEventListener('click', closeEditorSeasonMenuOnOutsideClick);
document.addEventListener('keydown', closeEditorSeasonMenuOnEscape);

async function boot() {
  await loadMe();
  if (!state.user) {
    showMessage('请先登录后再新增或编辑阵容', 'warning');
    elements.submitButton.disabled = true;
    return;
  }
  await loadSeasons();
  if (mode === 'edit' && lineupId) await loadLineup();
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

async function loadMe() {
  const data = await fetch('/api/me').then((response) => response.json());
  state.user = data.user;
  state.csrfToken = data.csrf_token;
}

async function loadSeasons() {
  const payload = await fetch('/api/lineup-seasons').then((response) => response.json());
  state.seasons = payload.seasons || [];
  state.defaultSeasonId = payload.default_season_id || state.seasons[0]?.id || '';
  setEditorSeason(state.defaultSeasonId);
  renderEditorSeasonMenu();
}

function setEditorSeason(seasonId) {
  const selectedSeason = state.seasons.find((season) => season.id === seasonId) || state.seasons[0] || {};
  elements.seasonSelect.value = selectedSeason.id || '';
  elements.editorSeasonText.textContent = selectedSeason.name || selectedSeason.id || '请选择赛季';
}

function renderEditorSeasonMenu() {
  if (!elements.editorSeasonMenu) return;
  elements.editorSeasonMenu.replaceChildren();
  state.seasons.forEach((season) => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = `account-menu-item${season.id === elements.seasonSelect.value ? ' is-active' : ''}`;
    item.textContent = season.name || season.id;
    item.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      setEditorSeason(season.id);
      renderEditorSeasonMenu();
      closeEditorSeasonMenu();
    });
    elements.editorSeasonMenu.append(item);
  });
}

function toggleEditorSeasonMenu(event) {
  event.stopPropagation();
  const willOpen = elements.editorSeasonMenu.classList.contains('hidden');
  elements.editorSeasonMenu.classList.toggle('hidden', !willOpen);
  elements.editorSeasonToggle.classList.toggle('is-open', willOpen);
  elements.editorSeasonToggle.setAttribute('aria-expanded', String(willOpen));
}

function closeEditorSeasonMenu() {
  if (!elements.editorSeasonMenu || !elements.editorSeasonToggle) return;
  elements.editorSeasonMenu.classList.add('hidden');
  elements.editorSeasonToggle.classList.remove('is-open');
  elements.editorSeasonToggle.setAttribute('aria-expanded', 'false');
}

function closeEditorSeasonMenuOnOutsideClick(event) {
  if (event.target.closest('#editorSeasonMenuWrap')) return;
  closeEditorSeasonMenu();
}

function closeEditorSeasonMenuOnEscape(event) {
  if (event.key === 'Escape') closeEditorSeasonMenu();
}

async function loadLineup() {
  try {
    const lineup = await fetch(`/api/lineups/${lineupId}`).then(async (response) => {
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.error || '加载阵容失败');
      return data;
    });
    if (!lineup.can_edit) throw new Error('你无权编辑该阵容');
    elements.lineupId.value = lineup.id;
    elements.lineupVersion.value = lineup.version;
    elements.nameInput.value = lineup.name;
    elements.codeInput.value = lineup.code;
    setEditorSeason(lineup.season_id || state.defaultSeasonId);
    renderEditorSeasonMenu();
    elements.statusToggle.checked = lineup.status === 'hidden';
    syncStatusSummary();
    elements.title.textContent = '编辑阵容';
    elements.description.textContent = `正在修改「${lineup.name}」，保存后返回阵容列表。`;
    state.restricted = lineup.status === 'banned';
    if (state.restricted) {
      const moderation = lineup.moderation;
      state.pending = moderation?.state === 'pending';
      const proposal = moderation?.proposal;
      elements.nameInput.value = proposal?.name || lineup.name;
      elements.codeInput.value = proposal?.code || lineup.code;
      const selectedSeason = proposal?.season_id || lineup.season_id;
      if (state.seasons.some(season => season.id === selectedSeason)) setEditorSeason(selectedSeason);
      else { elements.seasonSelect.value = ''; elements.editorSeasonText.textContent = '原赛季不可用，请重新选择'; }
      renderEditorSeasonMenu();
      elements.statusToggle.closest('.visibility-toggle').hidden = true;
      document.querySelectorAll('a.ghost-link[href="/"]').forEach(link => { link.href = `/me/lineup-notifications/${lineup.id}`; link.textContent = '返回处理通知'; });
      elements.title.textContent = state.pending ? '修改已提交' : '修改并提交重审';
      elements.description.textContent = state.pending ? '管理员正在审核你的提交，审核期间不能再次修改。' : '修改名称、阵容码或赛季后提交；审核通过后才会替换原内容。';
      const notice = document.createElement('section'); notice.className = 'lm-callout lm-editor-notice';
      const title = document.createElement('strong'); title.textContent = '封禁原因';
      const reason = document.createElement('p'); reason.className = 'lm-reason'; reason.textContent = moderation?.reason || '';
      notice.append(title, reason);
      if (moderation?.review_note) { const review = document.createElement('p'); review.className = 'lm-reason'; review.textContent = '退回说明：' + moderation.review_note; notice.append(review); }
      elements.form.before(notice);
      elements.submitButton.textContent = state.pending ? '等待管理员审核' : '提交修改并申请重审';
      elements.submitButton.disabled = state.pending;
      elements.nameInput.disabled = elements.codeInput.disabled = elements.editorSeasonToggle.disabled = state.pending;
    }
  } catch (error) {
    elements.submitButton.disabled = true;
    showMessage(error.message, 'error');
  }
}

async function saveLineup(event) {
  event.preventDefault();
  if (!state.user || state.pending || elements.submitButton.disabled) return;
  const normalizedCode = extractLineupCode(elements.codeInput.value);
  if (!normalizedCode) {
    showMessage('阵容码无法解析，请改成以 # 开头的阵容码后再提交', 'warning');
    return;
  }
  if (!elements.seasonSelect.value) {
    showMessage('请选择所属赛季', 'warning');
    return;
  }
  elements.codeInput.value = normalizedCode;
  const body = {
    name: elements.nameInput.value.trim(),
    code: normalizedCode,
    season_id: elements.seasonSelect.value,
    status: elements.statusToggle.checked ? 'hidden' : 'normal',
  };
  const isEdit = mode === 'edit' && elements.lineupId.value;
  if (elements.lineupVersion.value) body.version = Number(elements.lineupVersion.value);
  if (state.restricted) delete body.status;
  elements.submitButton.disabled = true;
  try {
    await api(state.restricted ? `/api/lineups/${elements.lineupId.value}/revision` : isEdit ? `/api/lineups/${elements.lineupId.value}` : '/api/lineups', {
      method: state.restricted ? 'POST' : isEdit ? 'PUT' : 'POST',
      body: JSON.stringify(body),
    });
    window.location.href = state.restricted ? `/me/lineup-notifications/${elements.lineupId.value}` : `/?saved=${isEdit ? 'edit' : 'create'}`;
  } catch (error) {
    showMessage(error.message, 'error');
  } finally { elements.submitButton.disabled = false; }
}

function showMessage(text, variant = 'success') {
  window.jccNotify.show(text, { variant });
}

function syncStatusSummary() {
  if (!elements.statusSummary || !elements.statusToggle) return;
  elements.statusSummary.textContent = elements.statusToggle.checked ? '直接隐藏' : '直接展示';
}

function extractLineupCode(rawCode) {
  const matches = Array.from(String(rawCode || '').matchAll(/[#＃]([A-Za-z0-9]+)/g)).map((item) => item[1]);
  if (!matches.length) return '';
  return `#${matches.sort((left, right) => right.length - left.length)[0]}`;
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  window.jccApplyThemeToggleState?.(theme, elements.themeToggle, elements.themeIcon, elements.themeText);
  if (!window.jccApplyThemeToggleState && elements.themeText) elements.themeText.textContent = theme === 'dark' ? '白天模式' : '夜间模式';
}

syncStatusSummary();
