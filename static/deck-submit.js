/* Two-code deck submission. The server validates everything; this keeps one request key per content so a
   double click or a network retry returns the same submission instead of creating another one. */
(function () {
  'use strict';
  const form = document.getElementById('deckSubmitForm');
  if (!form) return;
  const $ = (id) => document.getElementById(id);
  const fields = { plan_code: $('submitPlanCode'), lineup_code: $('submitLineupCode'), name: $('submitName'), note: $('submitNote') };
  const button = $('deckSubmitButton'), error = $('submitError'), state = $('submitState');
  const defaultState = state.textContent;
  const DRAFT_KEY = 'jcc-deck-submission-draft-v1';
  let session = null, pending = null, busy = false;

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID()
    : '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, (c) => (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)));
  const values = () => Object.fromEntries(Object.entries(fields).map(([key, input]) => [key, input.value.trim()]));
  const signature = (body) => JSON.stringify([body.plan_code, body.lineup_code, body.name, body.note]);

  function hint(input, statusId, ok, text) {
    const node = $(statusId);
    node.textContent = text;
    node.classList.toggle('is-ok', ok === true);
    node.classList.toggle('is-error', ok === false);
    input.setAttribute('aria-invalid', String(ok === false));
  }
  // Light, local feedback only; the full check (including decoding) happens on the server.
  function checkPlan() {
    const value = fields.plan_code.value.trim();
    if (!value) return hint(fields.plan_code, 'submitPlanStatus', null, '游戏内「大橘大利」方案分享，格式为 名称-大橘大利-编码');
    const [, name, code] = value.match(/^(.*)-大橘大利-([A-Za-z0-9+/=]+)$/) || [];
    hint(fields.plan_code, 'submitPlanStatus', Boolean(name && name.trim() && code), name && code ? `方案「${name.trim()}」格式正确` : '格式应为 名称-大橘大利-编码，请复制完整方案码');
  }
  function checkLineup() {
    const value = fields.lineup_code.value.trim();
    if (!value) return hint(fields.lineup_code, 'submitLineupStatus', null, '自动提取以 # 开头的阵容码');
    const match = value.match(/#[^\s#]*#[A-Za-z0-9+/=_-]{4,}/) || value.match(/#[A-Za-z0-9+/=_-]{6,}/);
    hint(fields.lineup_code, 'submitLineupStatus', Boolean(match), match ? '已识别阵容码' : '没有找到以 # 开头的阵容码，请粘贴游戏内的分享内容');
  }

  function saveDraft() {
    try { sessionStorage.setItem(DRAFT_KEY, JSON.stringify(values())); } catch { /* Optional. */ }
  }
  function restoreDraft() {
    try {
      const draft = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || 'null');
      if (!draft) return;
      Object.entries(fields).forEach(([key, input]) => { if (typeof draft[key] === 'string') input.value = draft[key]; });
      if (draft.name || draft.note) form.querySelector('details').open = true;
    } catch { /* Optional. */ }
  }

  function setBusy(value) {
    busy = value;
    button.disabled = value || !session?.user;
    button.textContent = value ? '正在提交…' : '提交投稿';
    form.setAttribute('aria-busy', String(value));
  }

  async function request(body) {
    const response = await fetch('/api/deck-submissions', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRF-Token': session.csrf_token },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const failure = new Error(data?.error || (response.status >= 500 ? '服务暂时不可用，请稍后重试' : '提交未完成'));
      failure.status = response.status; failure.data = data || {};
      throw failure;
    }
    return data;
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (busy || !session?.user) return;
    error.innerHTML = '';
    const body = values();
    if (!body.plan_code || !body.lineup_code) {
      error.textContent = !body.plan_code ? '请粘贴方案码' : '请粘贴阵容码';
      (!body.plan_code ? fields.plan_code : fields.lineup_code).focus();
      return;
    }
    // Same content keeps its key across retries; edited content is a new request.
    if (!pending || pending.signature !== signature(body)) pending = { key: uuid(), signature: signature(body) };
    setBusy(true);
    state.textContent = '正在提交…';
    let attempt = 0;
    while (true) {
      try {
        const data = await request({ ...body, request_key: pending.key });
        pending = null;
        try { sessionStorage.removeItem(DRAFT_KEY); } catch { /* Optional. */ }
        form.reset(); checkPlan(); checkLineup();
        state.innerHTML = `${data.replayed ? '这份投稿已经提交过' : '投稿已提交'}，管理员处理后会通过站内通知告诉你。<a href="${esc(data.url)}">查看进度</a>`;
        state.focus?.();
        break;
      } catch (failure) {
        // One automatic retry for a dropped connection, reusing the same request key.
        if (failure instanceof TypeError && attempt++ < 1) continue;
        const existing = failure.data?.submission_id;
        error.innerHTML = esc(failure instanceof TypeError ? '网络连接中断，内容仍在此页面，可以再次提交（不会重复投稿）' : failure.message)
          + (existing ? ` <a href="/me/deck-submissions/${Number(existing)}">查看已有投稿</a>` : '');
        state.textContent = defaultState;
        if (failure.status === 409 && existing) pending = null;
        break;
      }
    }
    setBusy(false);
  });

  fields.plan_code.addEventListener('input', () => { checkPlan(); saveDraft(); });
  fields.lineup_code.addEventListener('input', () => { checkLineup(); saveDraft(); });
  fields.name.addEventListener('input', saveDraft);
  fields.note.addEventListener('input', saveDraft);

  restoreDraft(); checkPlan(); checkLineup();
  setBusy(false);
  fetch('/api/me', { headers: { Accept: 'application/json' } }).then((response) => response.json()).then((data) => {
    session = data;
    if (!data.user) {
      state.innerHTML = '登录后即可投稿。<a href="/auth">登录 / 注册</a>';
    } else if (data.user.role === 'automation') {
      state.textContent = '协作账号不能投稿。';
      session = { ...data, user: null };
    }
    setBusy(false);
  }).catch(() => { error.textContent = '登录状态暂时无法确认，请刷新页面后再提交。'; });
})();
