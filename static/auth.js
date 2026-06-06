const state = { user: null, csrfToken: '', captchaToken: '' };
const $ = (selector) => document.querySelector(selector);
const elements = {
  authStatus: $('#authStatus'), authForms: $('#authForms'), loginForm: $('#loginForm'), registerForm: $('#registerForm'), logoutButton: $('#logoutButton'), adminLink: $('#adminLink'),
  loginAccount: $('#loginAccount'), loginPassword: $('#loginPassword'), registerUsername: $('#registerUsername'), registerEmail: $('#registerEmail'), registerNickname: $('#registerNickname'), registerPassword: $('#registerPassword'), captchaImage: $('#captchaImage'), captchaAnswer: $('#captchaAnswer'), refreshCaptcha: $('#refreshCaptcha'), message: $('#message'),
  themeToggle: $('#themeToggle'), themeIcon: $('#themeIcon'), themeText: $('#themeText'),
};

setTheme(localStorage.getItem('theme') || 'light');
boot();

elements.themeToggle.addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
elements.refreshCaptcha.addEventListener('click', loadCaptcha);
elements.loginForm.addEventListener('submit', login);
elements.registerForm.addEventListener('submit', register);
elements.logoutButton.addEventListener('click', logout);

async function boot() {
  await loadMe();
  trackGrowth('open_auth_page', { source: document.referrer ? 'redirect' : 'direct' });
  if (!state.user) await loadCaptcha();
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
      page_key: 'auth',
      ref_lineup_id: null,
      payload,
    }),
  }).catch(() => {});
}

async function loadMe() {
  const data = await fetch('/api/me').then((response) => response.json());
  state.user = data.user;
  state.csrfToken = data.csrf_token;
  renderAuth();
}

async function loadCaptcha() {
  const data = await fetch('/api/captcha').then((response) => response.json());
  state.captchaToken = data.captcha_token;
  elements.captchaImage.src = data.image_url;
  elements.captchaAnswer.value = '';
}

function renderAuth() {
  const loggedIn = Boolean(state.user);
  elements.authForms.classList.toggle('hidden', loggedIn);
  elements.logoutButton.classList.toggle('hidden', !loggedIn);
  elements.adminLink.classList.toggle('hidden', !(state.user && state.user.role === 'admin'));
  elements.authStatus.textContent = loggedIn
    ? `已登录：${state.user.nickname}（${state.user.role === 'admin' ? '管理员' : '用户'}）`
    : '未登录：请选择登录或注册';
}

async function login(event) {
  event.preventDefault();
  try {
    const data = await api('/api/login', { method: 'POST', body: JSON.stringify({ account: elements.loginAccount.value.trim(), password: elements.loginPassword.value }) });
    state.user = data.user;
    state.csrfToken = data.csrf_token;
    await window.jccHistoryStore?.syncToAccount(state.csrfToken);
    showMessage('登录成功，正在返回阵容库...');
    window.setTimeout(() => { window.location.href = resolvePostLoginRedirect(); }, 500);
  } catch (error) {
    showMessage(error.message);
  }
}

async function register(event) {
  event.preventDefault();
  try {
    const data = await api('/api/register', { method: 'POST', body: JSON.stringify({ username: elements.registerUsername.value.trim(), email: elements.registerEmail.value.trim(), nickname: elements.registerNickname.value.trim(), password: elements.registerPassword.value, captcha_token: state.captchaToken, captcha_answer: elements.captchaAnswer.value.trim() }) });
    state.user = data.user;
    state.csrfToken = data.csrf_token;
    await window.jccHistoryStore?.syncToAccount(state.csrfToken);
    showMessage('注册成功，正在返回阵容库...');
    window.setTimeout(() => { window.location.href = resolvePostLoginRedirect(); }, 500);
  } catch (error) {
    showMessage(error.message);
    loadCaptcha();
  }
}

async function logout() {
  await api('/api/logout', { method: 'POST' });
  state.user = null;
  showMessage('已退出登录');
  renderAuth();
  loadCaptcha();
}

function showMessage(text) {
  elements.message.textContent = text;
  clearTimeout(showMessage.timer);
  showMessage.timer = setTimeout(() => { elements.message.textContent = ''; }, 2600);
}

function resolvePostLoginRedirect() {
  const nextPath = sanitizeNextPath(new URLSearchParams(window.location.search).get('next'));
  const intent = window.jccAuthIntent?.read();
  if (intent?.type === 'open_create_lineup') return '/lineup/new';
  if (nextPath) {
    const url = new URL(nextPath, window.location.origin);
    if (intent) url.searchParams.set('resume_intent', '1');
    return `${url.pathname}${url.search}${url.hash}`;
  }
  if (!intent) return '/';
  return '/?resume_intent=1';
}

function sanitizeNextPath(value) {
  const nextValue = String(value || '').trim();
  if (!nextValue) return '';
  try {
    const url = new URL(nextValue, window.location.origin);
    return url.origin === window.location.origin ? `${url.pathname}${url.search}${url.hash}` : '';
  } catch (_) {
    return '';
  }
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  elements.themeIcon.textContent = theme === 'dark' ? '☼' : '☾';
  elements.themeText.textContent = theme === 'dark' ? '白天模式' : '夜间模式';
}
