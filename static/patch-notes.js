const patchListRoot = document.querySelector('#patchNotesApp');
const patchDetailRoot = document.querySelector('#patchNoteDetailApp');
const patchThemeToggle = document.querySelector('#themeToggle');
const patchThemeIcon = document.querySelector('#themeIcon');
const patchThemeText = document.querySelector('#themeText');

setPatchTheme(localStorage.getItem('theme') || 'light');
patchThemeToggle?.addEventListener('click', () => setPatchTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));

if (patchListRoot) loadPatchNoteList();
if (patchDetailRoot) loadPatchNoteDetail();

async function loadPatchNoteList() {
  try {
    const data = await fetch('/api/patch-notes').then((response) => response.json());
    renderPatchNoteList(data.items || []);
  } catch (error) {
    patchListRoot.textContent = '公告加载失败，请稍后再试';
  }
}

async function loadPatchNoteDetail() {
  try {
    const id = patchDetailRoot.dataset.patchNoteId;
    const response = await fetch(`/api/patch-notes/${id}`);
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.error || '公告不存在');
    renderPatchNoteDetail(data);
  } catch (error) {
    patchDetailRoot.textContent = error.message || '公告加载失败';
  }
}

function renderPatchNoteList(items) {
  patchListRoot.replaceChildren();
  const list = document.createElement('div');
  list.className = 'patch-note-list';
  if (!items.length) {
    list.append(el('div', 'empty-state', '暂无更新公告'));
  } else {
    items.forEach((item) => {
      const card = el('article', 'patch-note-card');
      const title = el('h2', '', item.title);
      const meta = el('p', 'admin-meta', `${item.version || '版本公告'} · ${item.published_at}`);
      const link = el('a', 'primary-link patch-note-card-action', '查看公告');
      link.href = `/patch-notes/${item.id}`;
      card.append(title, meta, link);
      list.append(card);
    });
  }
  patchListRoot.append(list);
}

function renderPatchNoteDetail(item) {
  patchDetailRoot.replaceChildren();
  const stack = el('div', 'detail-stack patch-note-detail');
  stack.append(el('p', 'section-kicker', 'Patch Notes'));
  stack.append(el('h1', 'detail-title', item.title));
  stack.append(el('p', 'hero-description', `${item.version || '版本公告'} · ${item.published_at}`));
  if (item.source_url) {
    const source = el('a', 'ghost-link', '查看原公告');
    source.href = item.source_url;
    source.target = item.source_url.startsWith('/') ? '' : '_blank';
    source.rel = 'noopener';
    stack.append(source);
  }
  stack.append(renderSummary(item.summary_items || []));
  if (item.original_text) stack.append(renderOriginal(item.original_text));
  patchDetailRoot.append(stack);
}

function renderSummary(items) {
  const wrap = el('div', 'patch-note-summary');
  items.forEach((item) => {
    if (item.type === 'section') {
      wrap.append(el('h2', 'patch-note-section', item.title));
      return;
    }
    if (item.type === 'change') {
      const row = el('article', `patch-note-change patch-note-change-${item.kind}`);
      row.append(el('span', `change-tag change-tag-${item.kind}`, item.label));
      const body = el('div', 'patch-note-change-body');
      if (item.old_value || item.new_value) {
        body.append(el('span', 'change-old-value', item.old_value), el('span', 'change-arrow', '=>'), el('span', 'change-new-value', item.new_value));
      } else {
        body.append(el('span', '', item.text));
      }
      row.append(body);
      wrap.append(row);
      return;
    }
    wrap.append(el('p', 'patch-note-text', item.text));
  });
  return wrap;
}

function renderOriginal(text) {
  const details = document.createElement('details');
  details.className = 'patch-note-original';
  const summary = el('summary', '', '展开原文');
  const pre = el('pre', 'code-preview');
  pre.textContent = text;
  details.append(summary, pre);
  return details;
}

function setPatchTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  if (patchThemeIcon) patchThemeIcon.textContent = theme === 'dark' ? '☼' : '☾';
  if (patchThemeText) patchThemeText.textContent = theme === 'dark' ? '白天模式' : '夜间模式';
}

function el(tag, className = '', text = '') {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}
