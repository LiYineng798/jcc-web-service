const authorRoot = document.querySelector('#authorApp');
const authorElements = {
  themeToggle: document.querySelector('#themeToggle'),
  themeIcon: document.querySelector('#themeIcon'),
  themeText: document.querySelector('#themeText'),
  authPromptRoot: document.querySelector('#authPromptRoot'),
  toast: document.querySelector('#toast'),
};
const authorState = {
  user: null,
  csrfToken: '',
  username: authorRoot?.dataset.username || '',
  payload: null,
};

(async function () {
  if (!authorRoot) return;
  setAuthorTheme(localStorage.getItem('theme') || 'light');
  authorElements.themeToggle?.addEventListener('click', () => {
    setAuthorTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  });

  try {
    await loadMe();
    if (authorState.user) await window.jccHistoryStore?.syncToAccount(authorState.csrfToken);
    await loadAuthor();
    await consumePendingIntent();
  } catch (error) {
    authorRoot.replaceChildren(buildAuthorEmpty(error.message || '加载作者主页失败'));
  }
})();

async function api(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  if (authorState.csrfToken && ['POST', 'PUT', 'DELETE'].includes(options.method)) headers['X-CSRF-Token'] = authorState.csrfToken;
  const response = await fetch(url, { ...options, headers });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.error || '操作失败');
  return data;
}

async function trackGrowth(eventName, payload = {}) {
  if (!authorState.csrfToken) return;
  await fetch('/api/growth-events', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': authorState.csrfToken },
    body: JSON.stringify({
      event_name: eventName,
      page_key: 'author',
      ref_lineup_id: payload.lineupId || null,
      payload,
    }),
  }).catch(() => {});
}

async function loadMe() {
  const data = await fetch('/api/me').then((response) => response.json());
  authorState.user = data.user;
  authorState.csrfToken = data.csrf_token;
}

async function loadAuthor() {
  const payload = await fetch(`/api/authors/${encodeURIComponent(authorState.username)}`).then(async (response) => {
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.error || '加载作者主页失败');
    return data;
  });
  authorState.payload = payload;
  renderAuthor(payload);
}

function renderAuthor(payload) {
  authorRoot.replaceChildren();

  const profile = document.createElement('section');
  profile.className = 'author-profile';
  profile.innerHTML = `
    <div>
      <p class="section-kicker">Creator</p>
      <h2>${escapeAuthorHtml(payload.profile.nickname)}</h2>
      <p class="account-row-meta">@${escapeAuthorHtml(payload.profile.username)} · 入驻时间：${escapeAuthorHtml(payload.profile.created_at || '')}</p>
    </div>
  `;

  const summary = document.createElement('div');
  summary.className = 'account-summary-grid';
  [
    ['公开阵容', payload.summary.published_lineups || 0],
    ['累计点赞', payload.summary.total_likes || 0],
    ['累计复制', payload.summary.total_copies || 0],
  ].forEach(([label, value]) => {
    const card = document.createElement('article');
    card.className = 'account-stat-card';
    card.innerHTML = `<small>${label}</small><strong>${value}</strong>`;
    summary.append(card);
  });

  const lineupSection = document.createElement('section');
  lineupSection.className = 'author-lineups';
  const title = document.createElement('h3');
  title.textContent = '公开阵容';
  lineupSection.append(title);

  if (!(payload.lineups || []).length) {
    lineupSection.append(buildAuthorEmpty('这个作者暂时还没有公开阵容。'));
  } else {
    const list = document.createElement('div');
    list.className = 'lineup-list';
    payload.lineups.forEach((lineup) => list.append(renderAuthorLineup(lineup)));
    lineupSection.append(list);
  }

  authorRoot.append(profile, summary, lineupSection);
}

function renderAuthorLineup(lineup) {
  const card = document.createElement('article');
  card.className = 'lineup-card';
  const title = document.createElement('h3');
  title.className = 'lineup-title';
  title.textContent = `${lineup.name} · ${lineup.rank_level}`;
  const meta = document.createElement('p');
  meta.className = 'card-time';
  meta.textContent = `赞 ${lineup.like_count} · 复制 ${lineup.copy_count} · 更新于 ${lineup.updated_at}`;
  const code = document.createElement('pre');
  code.className = 'code-preview';
  code.textContent = lineup.code;
  const actions = document.createElement('div');
  actions.className = 'card-actions';
  actions.append(actionButton('复制阵容码', () => copyLineup(lineup)));
  actions.append(actionButton('查看', () => openLineupDetail(lineup.id)));
  actions.append(actionButton(lineup.is_liked_today ? '今日已赞' : '点赞', () => likeLineup(lineup), '', Boolean(authorState.user && lineup.is_liked_today)));
  actions.append(actionButton(lineup.is_favorited ? '取消收藏' : '收藏', () => favoriteLineup(lineup)));
  actions.append(actionButton('举报', () => reportLineup(lineup)));
  card.append(title, meta, code, actions);
  return card;
}

function actionButton(label, handler, extraClass = '', disabled = false) {
  const element = document.createElement('button');
  element.type = 'button';
  element.className = `small-button ${extraClass}`.trim();
  element.textContent = label;
  element.disabled = disabled;
  element.addEventListener('click', async () => {
    try {
      await handler(element);
    } catch (error) {
      showToast(error.message || '操作失败，请稍后重试');
    }
  });
  return element;
}

function openLineupDetail(lineupId) {
  window.location.href = `/lineup/${lineupId}`;
}

async function copyLineup(lineup) {
  const copied = await writeClipboard(lineup.code);
  if (!copied) {
    showToast('复制失败，请长按阵容码手动复制');
    return;
  }
  await api(`/api/lineups/${lineup.id}/copy?source=author`, { method: 'POST' });
  if (!authorState.user) window.jccHistoryStore?.pushLocalCopy(lineup);
  showToast('复制成功！');
  await loadAuthor();
}

async function likeLineup(lineup) {
  if (!authorState.user) trackGrowth('guest_click_like', { source: 'author-lineup', lineupId: lineup.id });
  if (requireAuthIntent({ type: 'like_lineup', lineupId: lineup.id }, '登录后可点赞并保留个人记录')) return;
  await api(`/api/lineups/${lineup.id}/like`, { method: 'POST' });
  showToast('点赞成功');
  await loadAuthor();
}

async function favoriteLineup(lineup) {
  if (!authorState.user) trackGrowth('guest_click_favorite', { source: 'author-lineup', lineupId: lineup.id });
  if (requireAuthIntent({ type: 'favorite_lineup', lineupId: lineup.id }, '登录后可收藏阵容并跨设备同步')) return;
  if (lineup.is_favorited) {
    await api(`/api/lineups/${lineup.id}/favorite`, { method: 'DELETE' });
    showToast('已取消收藏');
  } else {
    await api(`/api/lineups/${lineup.id}/favorite`, { method: 'POST' });
    showToast('收藏成功');
  }
  await loadAuthor();
}

async function reportLineup(lineup) {
  if (!authorState.user) trackGrowth('guest_click_report', { source: 'author-lineup', lineupId: lineup.id });
  if (requireAuthIntent({ type: 'report_lineup', lineupId: lineup.id }, '登录后可举报问题阵容并保留处理记录')) return;
  showReportDialog(lineup);
}

function requireAuthIntent(intent, message) {
  if (authorState.user) return false;
  window.jccAuthIntent?.save(intent);
  showAuthPrompt(message);
  return true;
}

function showAuthPrompt(message) {
  closeAuthorDialog(false);
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) closeAuthorDialog(true);
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
  header.append(headerCopy, actionButton('关闭', () => closeAuthorDialog(true)));

  const hint = document.createElement('p');
  hint.className = 'field-hint';
  hint.textContent = '登录后可收藏阵容、查看我的收藏。';

  const actions = document.createElement('div');
  actions.className = 'auth-prompt-actions';
  actions.append(actionButton('稍后', () => closeAuthorDialog(true)));
  const loginButton = document.createElement('button');
  loginButton.type = 'button';
  loginButton.className = 'primary-button auth-prompt-confirm';
  loginButton.textContent = '去登录';
  loginButton.addEventListener('click', () => {
    const next = encodeURIComponent(window.location.pathname);
    window.location.href = `/auth?next=${next}`;
  });
  actions.append(loginButton);

  card.append(header, hint, actions);
  backdrop.append(card);
  authorElements.authPromptRoot?.append(backdrop);
}

function showReportDialog(lineup) {
  closeAuthorDialog(false);
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) closeAuthorDialog(false);
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
  header.append(headerCopy, actionButton('关闭', () => closeAuthorDialog(false)));

  const form = document.createElement('form');
  form.className = 'modal-form';
  const field = document.createElement('label');
  field.className = 'field';
  const fieldLabel = document.createElement('span');
  fieldLabel.textContent = '举报原因';
  const textarea = document.createElement('textarea');
  textarea.rows = 5;
  textarea.maxLength = 300;
  textarea.placeholder = '请简要说明问题，例如：阵容码无效、内容不实、违规信息等';
  field.append(fieldLabel, textarea);

  const inlineMessage = document.createElement('div');
  inlineMessage.className = 'message';

  const actions = document.createElement('div');
  actions.className = 'auth-prompt-actions';
  actions.append(actionButton('取消', () => closeAuthorDialog(false)));
  const submitButton = document.createElement('button');
  submitButton.type = 'submit';
  submitButton.className = 'primary-button auth-prompt-confirm';
  submitButton.textContent = '提交举报';
  actions.append(submitButton);

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
      await api(`/api/lineups/${lineup.id}/report`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      closeAuthorDialog(false);
      showToast('举报已提交');
    } catch (error) {
      inlineMessage.textContent = error.message || '提交失败';
    } finally {
      submitButton.disabled = false;
    }
  });

  card.append(header, form);
  backdrop.append(card);
  authorElements.authPromptRoot?.append(backdrop);
  textarea.focus();
}

async function consumePendingIntent() {
  stripResumeIntentFlag();
  if (!authorState.user) return;
  const intent = window.jccAuthIntent?.read();
  if (!intent) return;
  window.jccAuthIntent.clear();
  const lineup = findLineupById(intent.lineupId);
  if (intent.type === 'like_lineup' && lineup) {
    await api(`/api/lineups/${lineup.id}/like`, { method: 'POST' }).catch((error) => showToast(error.message));
    await loadAuthor();
    return;
  }
  if (intent.type === 'favorite_lineup' && lineup) {
    await api(`/api/lineups/${lineup.id}/favorite`, { method: 'POST' }).catch((error) => showToast(error.message));
    await loadAuthor();
    return;
  }
  if (intent.type === 'report_lineup' && lineup) {
    showReportDialog(lineup);
  }
}

function findLineupById(lineupId) {
  return (authorState.payload?.lineups || []).find((item) => item.id === Number(lineupId)) || null;
}

function closeAuthorDialog(clearIntent = false) {
  authorElements.authPromptRoot?.replaceChildren();
  if (clearIntent) window.jccAuthIntent?.clear();
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

function buildAuthorEmpty(text) {
  const empty = document.createElement('div');
  empty.className = 'empty-state';
  empty.textContent = text;
  return empty;
}

function showToast(text) {
  if (!authorElements.toast) return;
  authorElements.toast.textContent = text;
  authorElements.toast.classList.add('is-visible');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    authorElements.toast.classList.remove('is-visible');
  }, 2200);
}

function stripResumeIntentFlag() {
  const params = new URLSearchParams(window.location.search);
  if (!params.has('resume_intent')) return;
  params.delete('resume_intent');
  const nextQuery = params.toString();
  history.replaceState({}, '', `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}`);
}

function setAuthorTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  if (authorElements.themeIcon) authorElements.themeIcon.textContent = theme === 'dark' ? '☼' : '☾';
  if (authorElements.themeText) authorElements.themeText.textContent = theme === 'dark' ? '白天模式' : '夜间模式';
}

function escapeAuthorHtml(text) {
  return String(text || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
