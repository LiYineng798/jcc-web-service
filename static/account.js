const reportStatusText = {
  pending: '待处理',
  resolved: '已处理',
  dismissed: '已驳回',
};

const lineupStatusText = {
  normal: '正常',
  hidden: '已隐藏',
  deleted: '已删除',
};

let accountCsrfToken = '';

(async function () {
  const root = document.querySelector('#accountApp');
  const themeToggle = document.querySelector('#themeToggle');
  const themeIcon = document.querySelector('#themeIcon');
  const themeText = document.querySelector('#themeText');
  if (!root) return;

  setAccountTheme(localStorage.getItem('theme') || 'light', themeIcon, themeText);
  themeToggle?.addEventListener('click', () => {
    setAccountTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark', themeIcon, themeText);
  });

  const [me, dashboard, views, copies, reports, minePayload] = await Promise.all([
    fetch('/api/me').then((response) => response.json()),
    fetch('/api/me/dashboard').then((response) => response.json()),
    fetch('/api/me/recent-views').then((response) => response.json()),
    fetch('/api/me/recent-copies').then((response) => response.json()),
    fetch('/api/me/reports').then((response) => response.json()),
    fetch('/api/lineups?view=mine&page=1&page_size=20').then((response) => response.json()),
  ]);

  accountCsrfToken = me.csrf_token || '';
  const lineups = minePayload.items || [];
  root.replaceChildren(
    renderSummaryCards(me.user, dashboard),
    renderHistorySection('最近浏览', views, '还没有最近浏览记录', '浏览时间'),
    renderHistorySection('最近复制', copies, '还没有最近复制记录', '复制时间'),
    renderReportsSection(reports),
    renderMineSection(lineups),
  );
})();

function setAccountTheme(theme, themeIcon, themeText) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  if (themeIcon) themeIcon.textContent = theme === 'dark' ? '☼' : '☾';
  if (themeText) themeText.textContent = theme === 'dark' ? '白天模式' : '夜间模式';
}

function renderSummaryCards(user, dashboard) {
  const section = document.createElement('section');
  section.className = 'account-section';

  const title = document.createElement('div');
  title.className = 'account-section-head';
  title.innerHTML = `
    <div>
      <p class="section-kicker">Dashboard</p>
      <h3>我的数据</h3>
      <p class="account-subtitle">${escapeAccountHtml(user?.nickname || '')} 的账号数据概览</p>
    </div>
  `;

  const grid = document.createElement('div');
  grid.className = 'account-summary-grid';
  [
    ['已发布阵容', dashboard.published_lineups || 0],
    ['隐藏阵容', dashboard.hidden_lineups || 0],
    ['收到点赞', dashboard.received_likes || 0],
    ['收到收藏', dashboard.received_favorites || 0],
    ['收到复制', dashboard.received_copies || 0],
    ['发起举报', dashboard.submitted_reports || 0],
    ['待处理举报', dashboard.pending_reports_on_my_lineups || 0],
  ].forEach(([label, value]) => {
    const card = document.createElement('article');
    card.className = 'account-stat-card';
    card.innerHTML = `<small>${label}</small><strong>${value}</strong>`;
    grid.append(card);
  });

  section.append(title, grid);
  return section;
}

function renderHistorySection(title, items, emptyText, timeLabel) {
  const section = document.createElement('section');
  section.className = 'account-section';
  const head = document.createElement('div');
  head.className = 'account-section-head';
  head.innerHTML = `<div><p class="section-kicker">History</p><h3>${title}</h3></div>`;
  section.append(head);

  if (!items.length) {
    section.append(buildEmptyLine(emptyText));
    return section;
  }

  const list = document.createElement('div');
  list.className = 'account-list is-scrollable-history';
  items.forEach((item) => {
    const card = document.createElement('article');
    card.className = 'history-card';
    card.innerHTML = `
      <div class="account-row-main">
        <a class="account-row-link" href="/lineup/${item.id}">${escapeAccountHtml(item.name)}</a>
        <span class="status-pill">${escapeAccountHtml(item.rank_level || '')}</span>
      </div>
      <p class="account-row-meta">作者：${escapeAccountHtml(item.owner_nickname)} · ${timeLabel}：${escapeAccountHtml(item.history_at || '')}</p>
      <p class="account-row-meta">赞 ${item.like_count} · 复制 ${item.copy_count}</p>
    `;
    const actions = document.createElement('div');
    actions.className = 'card-actions';
    const copyButton = document.createElement('button');
    copyButton.type = 'button';
    copyButton.className = 'small-button';
    copyButton.textContent = '复制阵容码';
    copyButton.addEventListener('click', async () => {
      const copied = await copyLineupCode(item.code);
      if (!copied) return;
      await recordLineupCopy(item.id, 'account');
      const originalText = copyButton.textContent;
      copyButton.textContent = '已复制';
      copyButton.disabled = true;
      window.setTimeout(() => {
        copyButton.textContent = originalText;
        copyButton.disabled = false;
      }, 1400);
    });
    actions.append(copyButton);
    card.append(actions);
    list.append(card);
  });
  section.append(list);
  return section;
}

function renderReportsSection(reports) {
  const section = document.createElement('section');
  section.className = 'account-section';
  const head = document.createElement('div');
  head.className = 'account-section-head';
  head.innerHTML = `<div><p class="section-kicker">Reports</p><h3>我的举报</h3></div>`;
  section.append(head);

  if (!reports.length) {
    section.append(buildEmptyLine('你还没有提交过举报。'));
    return section;
  }

  const list = document.createElement('div');
  list.className = 'account-list';
  reports.forEach((report) => {
    const card = document.createElement('article');
    card.className = 'report-card';
    card.innerHTML = `
      <div class="account-row-main">
        <a class="account-row-link" href="/lineup/${report.lineup_id}">${escapeAccountHtml(report.lineup_name)}</a>
        <span class="status-pill ${report.status}">${reportStatusText[report.status] || report.status}</span>
      </div>
      <p class="account-row-meta">阵容状态：${lineupStatusText[report.lineup_status] || report.lineup_status}</p>
      <p class="account-row-meta">举报原因：${escapeAccountHtml(report.reason)}</p>
      <p class="account-row-meta">提交时间：${escapeAccountHtml(report.created_at || '')}${report.handled_at ? ` · 处理时间：${escapeAccountHtml(report.handled_at)}` : ''}</p>
    `;
    list.append(card);
  });
  section.append(list);
  return section;
}

function renderMineSection(lineups) {
  const section = document.createElement('section');
  section.className = 'account-section';
  const head = document.createElement('div');
  head.className = 'account-section-head';
  head.innerHTML = `<div><p class="section-kicker">Mine</p><h3>我的阵容</h3></div>`;
  section.append(head);

  if (!lineups.length) {
    section.append(buildEmptyLine('你还没有发布过阵容。'));
    return section;
  }

  const list = document.createElement('div');
  list.className = 'account-list';
  lineups.forEach((lineup) => {
    const card = document.createElement('article');
    card.className = 'history-card';
    card.innerHTML = `
      <div class="account-row-main">
        <a class="account-row-link" href="/lineup/${lineup.id}">${escapeAccountHtml(lineup.name)}</a>
        <span class="status-pill ${lineup.status}">${lineupStatusText[lineup.status] || lineup.status}</span>
      </div>
      <p class="account-row-meta">更新时间：${escapeAccountHtml(lineup.updated_at || '')}</p>
      <p class="account-row-meta">赞 ${lineup.like_count} · 复制 ${lineup.copy_count}</p>
    `;
    list.append(card);
  });
  section.append(list);
  return section;
}

function buildEmptyLine(text) {
  const empty = document.createElement('p');
  empty.className = 'account-empty';
  empty.textContent = text;
  return empty;
}

async function copyLineupCode(text) {
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

async function recordLineupCopy(lineupId, source) {
  if (!accountCsrfToken) return;
  await fetch(`/api/lineups/${lineupId}/copy?source=${encodeURIComponent(source)}`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': accountCsrfToken },
  }).catch(() => {});
}

function escapeAccountHtml(text) {
  return String(text ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
