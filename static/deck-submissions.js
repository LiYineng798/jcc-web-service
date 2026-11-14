/* My deck submissions: list, private detail, edits while waiting, resubmission and withdrawal.
   Status and permissions come from the server; a stale version is reported, never overwritten. */
(function () {
  'use strict';
  const app = document.getElementById('submissionsApp');
  const body = document.getElementById('submissionsBody');
  const submissionId = app.dataset.submissionId;
  const limits = JSON.parse(app.dataset.limits);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const date = (value) => String(value || '').slice(0, 16);
  const FILTERS = [['all', '全部'], ['active', '进行中'], ['resolved', '已结束']];
  const STEPS = ['pending', 'processing', 'published'];
  let session = null, filter = 'all', page = 1, detail = null, editing = false, busy = false;

  async function api(url, options = {}) {
    const response = await fetch(url, { method: options.method || 'GET', headers: { Accept: 'application/json', 'Content-Type': 'application/json',
      'X-CSRF-Token': session?.csrf_token || '' }, body: options.body ? JSON.stringify(options.body) : undefined });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const error = new Error(data?.error || (response.status >= 500 ? '服务暂时不可用，请稍后重试' : '操作未完成'));
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function status(item) {
    return `<span class="sub-status" data-status="${esc(item.status)}">${esc(item.status_label)}</span>`;
  }

  function outcome(item) {
    if (item.deck) {
      return item.deck.detail_url ? `<a class="deck-button is-primary" href="${esc(item.deck.detail_url)}">查看发布的卡组</a>`
        : '<span class="sub-muted">已发布的卡组当前未公开展示</span>';
    }
    if (item.duplicate_of) {
      return item.duplicate_of.detail_url ? `<a class="deck-button" href="${esc(item.duplicate_of.detail_url)}">查看相同卡组：${esc(item.duplicate_of.name)}</a>` : '';
    }
    return '';
  }

  // ------------------------------------------------------------- list
  async function loadList() {
    body.setAttribute('aria-busy', 'true');
    try {
      const data = await api(`/api/me/deck-submissions?status=${filter}&page=${page}`);
      renderList(data);
    } catch (error) { renderError(error, loadList); }
  }

  function renderList(data) {
    body.setAttribute('aria-busy', 'false');
    const counts = data.counts || {};
    const active = ['pending', 'processing', 'needs_info'].reduce((sum, key) => sum + (counts[key] || 0), 0);
    const filters = FILTERS.map(([key, label]) => `<button type="button" class="sub-filter" data-filter="${key}" aria-pressed="${filter === key}">${label}${key === 'active' && active ? ` <b>${active}</b>` : ''}</button>`).join('');
    const rows = data.items.map((item) => `<li><a class="sub-row" href="${esc(item.url)}">
        <span class="sub-row-main"><strong>${esc(item.title)}</strong><span class="sub-muted">提交于 ${esc(date(item.created_at))}${item.status === 'needs_info' ? ' · 需要你补充' : ''}</span></span>
        ${status(item)}</a></li>`).join('');
    body.innerHTML = `<div class="sub-toolbar" role="group" aria-label="按状态筛选">${filters}</div>
      ${data.items.length ? `<ul class="sub-list">${rows}</ul>` : `<div class="deck-empty"><h3>${filter === 'all' ? '还没有投稿' : '这里暂时没有投稿'}</h3><p>只需粘贴游戏内的方案码和阵容码，管理员补全卡片与站位后会公开展示，并署名由你提供。</p><div class="deck-actions"><a class="deck-button is-primary" href="/lineup/new">去投稿</a></div></div>`}
      ${data.total_pages > 1 ? `<div class="sub-pager"><button type="button" class="deck-button" data-page="${data.page - 1}" ${data.page <= 1 ? 'disabled' : ''}>上一页</button><span>第 ${data.page} / ${data.total_pages} 页</span><button type="button" class="deck-button" data-page="${data.page + 1}" ${data.page >= data.total_pages ? 'disabled' : ''}>下一页</button></div>` : ''}`;
  }

  // ------------------------------------------------------------- detail
  async function loadDetail(message = '') {
    body.setAttribute('aria-busy', 'true');
    try {
      detail = await api(`/api/me/deck-submissions/${submissionId}`);
      editing = editing && detail.can_edit;
      renderDetail(message);
      markRead();
    } catch (error) { renderError(error, () => loadDetail()); }
  }

  async function markRead() {
    const notice = detail?.notification;
    if (!notice || notice.notice_state !== 'unread') return;
    try {
      await api(`/api/me/notifications/${encodeURIComponent(notice.id)}`, { method: 'PUT', body: { status: 'read', revision: notice.revision } });
      notice.notice_state = 'read';
    } catch { /* A newer event keeps the notice unread; it is shown on the next load. */ }
  }

  function progress(item) {
    const terminal = { rejected: '未采纳', duplicate: '已有相同卡组', withdrawn: '已撤回' }[item.status];
    const steps = terminal ? ['pending', 'processing', item.status] : STEPS;
    const labels = { pending: '已提交', processing: item.status === 'needs_info' ? '待你补充' : '管理员完善', published: '公开发布', rejected: terminal, duplicate: terminal, withdrawn: terminal };
    const reached = { pending: 0, needs_info: 1, processing: 1, published: 2, rejected: 2, duplicate: 2, withdrawn: 2 }[item.status];
    return `<ol class="sub-progress" aria-label="处理进度">${steps.map((step, index) => `<li class="${index <= reached ? 'is-done' : ''}${index === reached ? ' is-current' : ''}"${index === reached ? ' aria-current="step"' : ''}>${esc(labels[step])}</li>`).join('')}</ol>`;
  }

  function codeBlock(label, value) {
    return `<div class="sub-code"><div class="sub-code-head"><span>${label}</span><button type="button" class="deck-button is-quiet" data-copy="${esc(value)}">复制</button></div><code>${esc(value)}</code></div>`;
  }

  function editor(item) {
    const field = (key, label, tag, extra = '') => `<label class="field" for="sub-${key}">${label} <small class="deck-hint">${limits[key]} 字内</small>
      ${tag === 'input' ? `<input id="sub-${key}" maxlength="${limits[key]}" value="${esc(item[key])}" ${extra} />` : `<textarea id="sub-${key}" maxlength="${limits[key]}" rows="${key === 'note' ? 3 : 2}" spellcheck="false" ${extra}>${esc(item[key])}</textarea>`}</label>`;
    return `<form class="deck-form sub-edit" id="subEdit" novalidate>
      ${field('plan_code', '方案码', 'textarea', 'class="deck-code-input" required')}
      ${field('lineup_code', '阵容码', 'textarea', 'class="deck-code-input" required')}
      ${field('name', '标题', 'input')}
      ${field('note', item.status === 'needs_info' ? '补充说明' : '备注', 'textarea')}
      <p class="deck-error" id="subEditError" role="alert"></p>
      <div class="sub-actions"><button type="button" class="deck-button" data-action="cancel">取消</button><button type="submit" class="deck-button is-primary">${item.status === 'needs_info' ? '补充并重新提交' : '保存修改'}</button></div>
    </form>`;
  }

  function renderDetail(message) {
    body.setAttribute('aria-busy', 'false');
    const item = detail;
    document.getElementById('submissionsTitle').textContent = item.title;
    document.title = `${item.title} · 投稿进度`;
    const note = item.review_note ? `<div class="sub-review" data-status="${esc(item.status)}"><span>${item.status === 'needs_info' ? '管理员需要你补充' : '处理说明'}</span><p>${esc(item.review_note)}</p></div>` : '';
    const actions = item.can_edit && !editing ? `<div class="sub-actions">
        <button type="button" class="deck-button is-quiet is-danger" data-action="withdraw">撤回投稿</button>
        <button type="button" class="deck-button${item.status === 'needs_info' ? ' is-primary' : ''}" data-action="edit">${item.status === 'needs_info' ? '补充信息' : '修改投稿'}</button></div>`
      : item.status === 'processing' ? '<p class="sub-muted">管理员正在完善，处理期间不能修改；需要补充时会通知你。</p>' : '';
    const events = item.events.map((event) => `<li><div><strong>${esc(event.label)}</strong><time>${esc(date(event.created_at))}</time></div>${event.note ? `<p>${esc(event.note)}</p>` : ''}<span class="sub-muted">${esc(event.actor)}</span></li>`).join('');
    body.innerHTML = `${message ? `<p class="deck-notice" role="status">${esc(message)}</p>` : ''}
      <section class="sub-card">
        <div class="sub-card-head">${status(item)}<span class="sub-muted">提交于 ${esc(date(item.created_at))}</span></div>
        ${progress(item)}
        ${note}
        ${outcome(item) ? `<div class="sub-outcome">${outcome(item)}</div>` : ''}
        ${editing ? editor(item) : `${codeBlock('方案码', item.plan_code)}${codeBlock('阵容码', item.lineup_code)}${item.note ? `<div class="sub-note"><span>备注</span><p>${esc(item.note)}</p></div>` : ''}${actions}`}
      </section>
      <section class="sub-history" aria-labelledby="subHistoryTitle"><h2 id="subHistoryTitle">处理记录</h2><ol>${events}</ol></section>`;
    if (editing) document.getElementById('sub-plan_code')?.focus();
  }

  async function saveEdit(form) {
    if (busy) return;
    const value = (key) => form.querySelector(`#sub-${key}`).value.trim();
    const payload = { version: detail.version, plan_code: value('plan_code'), lineup_code: value('lineup_code'), name: value('name'), note: value('note') };
    const error = document.getElementById('subEditError');
    busy = true; form.querySelector('[type="submit"]').disabled = true;
    try {
      const resubmit = detail.status === 'needs_info';
      await api(`/api/me/deck-submissions/${detail.id}`, { method: 'PUT', body: payload });
      editing = false;
      await loadDetail(resubmit ? '已重新提交，管理员会继续处理。' : '修改已保存。');
    } catch (failure) {
      error.textContent = failure.status === 409 ? `${failure.message}。你的修改仍保留在表单中，请刷新查看最新状态。` : failure.message;
      form.querySelector('[type="submit"]').disabled = false;
    } finally { busy = false; }
  }

  async function withdrawSubmission() {
    if (busy || !confirm('撤回后这份投稿不会再被处理，确定撤回吗？')) return;
    busy = true;
    try {
      await api(`/api/me/deck-submissions/${detail.id}/withdraw`, { method: 'POST', body: { version: detail.version } });
      await loadDetail('投稿已撤回。');
    } catch (failure) { await loadDetail(failure.message); } finally { busy = false; }
  }

  function renderError(error, retry) {
    body.setAttribute('aria-busy', 'false');
    body.innerHTML = `<div class="deck-empty" role="alert"><h3>${error.status === 404 ? '投稿不存在' : '读取失败'}</h3><p>${esc(error.message)}</p><div class="deck-actions"><button type="button" class="deck-button" data-action="retry">重新加载</button></div></div>`;
    body.querySelector('[data-action="retry"]').addEventListener('click', retry);
  }

  body.addEventListener('click', async (event) => {
    const target = event.target.closest('[data-filter], [data-page], [data-action], [data-copy]');
    if (!target || target.disabled) return;
    if (target.dataset.filter) { filter = target.dataset.filter; page = 1; loadList(); }
    else if (target.dataset.page) { page = Number(target.dataset.page); loadList(); }
    else if (target.dataset.copy !== undefined) {
      try { await navigator.clipboard.writeText(target.dataset.copy); target.textContent = '已复制'; }
      catch { target.textContent = '请手动选择复制'; }
      setTimeout(() => { target.textContent = '复制'; }, 1600);
    } else if (target.dataset.action === 'edit') { editing = true; renderDetail(); }
    else if (target.dataset.action === 'cancel') { editing = false; renderDetail(); }
    else if (target.dataset.action === 'withdraw') withdrawSubmission();
  });
  body.addEventListener('submit', (event) => { if (event.target.id === 'subEdit') { event.preventDefault(); saveEdit(event.target); } });
  body.addEventListener('keydown', (event) => { if (event.key === 'Escape' && editing) { editing = false; renderDetail(); } });

  fetch('/api/me', { headers: { Accept: 'application/json' } }).then((response) => response.json()).then((data) => {
    session = data;
    if (submissionId) loadDetail(); else loadList();
  }).catch((error) => renderError(error, () => location.reload()));
})();
