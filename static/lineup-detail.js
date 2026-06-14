const detailState = { user: null, csrfToken: '', lineup: null };
const detailRoot = document.querySelector('#lineupDetailApp');
const detailThemeToggle = document.querySelector('#themeToggle');
const detailThemeIcon = document.querySelector('#themeIcon');
const detailThemeText = document.querySelector('#themeText');

setDetailTheme(localStorage.getItem('theme') || 'light');
detailThemeToggle?.addEventListener('click', () => setDetailTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
bootDetail();

async function bootDetail() {
  if (!detailRoot) return;
  const lineupId = detailRoot.dataset.lineupId;
  const me = await fetch('/api/me').then((response) => response.json());
  detailState.user = me.user;
  detailState.csrfToken = me.csrf_token;
  const lineup = await fetch(`/api/lineups/${lineupId}`).then((response) => response.json());
  detailState.lineup = lineup;
  renderDetail(lineup);
  if (detailState.user) {
    await fetch(`/api/lineups/${lineupId}/view`, {
      method: 'POST',
      headers: { 'X-CSRF-Token': detailState.csrfToken },
    });
  } else {
    window.jccHistoryStore?.pushLocalView(lineup);
  }
}

function renderDetail(lineup) {
  detailRoot.innerHTML = `
    <div class="detail-stack">
      <p class="section-kicker">Lineup Detail</p>
      <h1 class="detail-title">${escapeHtml(lineup.name)} · ${escapeHtml(lineup.rank_level || '')}</h1>
      <p class="hero-description">由 ${escapeHtml(lineup.owner_nickname)} 上传 · 赞 ${lineup.like_count} · 复制 ${lineup.copy_count}</p>
      <pre class="code-preview">${escapeHtml(lineup.code)}</pre>
    </div>
  `;
}

function setDetailTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  if (detailThemeIcon) detailThemeIcon.textContent = theme === 'dark' ? '☼' : '☾';
  if (detailThemeText) detailThemeText.textContent = theme === 'dark' ? '白天模式' : '夜间模式';
}

function escapeHtml(text) {
  return String(text ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
