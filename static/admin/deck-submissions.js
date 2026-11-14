/* Admin deck submission workbench: a queue by status, one expanded submission at a time.
   Claim, release, reassign, ask for more, reject or mark duplicate here; completion and publishing use the deck editor.
   Every action sends the submission version; a conflict reloads the item instead of overwriting. */
(function (global) {
  const { el, button } = global.JccAdminCore;
  const FILTERS = [['pending', '待处理'], ['mine', '我处理的'], ['processing', '处理中'], ['needs_info', '待补充'], ['resolved', '已处理']];
  const STATUS = { pending: '待处理', processing: '处理中', needs_info: '待补充', published: '已发布', rejected: '未采纳', duplicate: '重复', withdrawn: '已撤回' };
  const NOTE_MAX = 1000;

  function shortTime(value) {
    const [date = '', time = ''] = String(value || '').split(' ');
    if (!date) return '—';
    return date.startsWith(String(new Date().getFullYear())) ? `${date.slice(5)} ${time.slice(0, 5)}`.trim() : date;
  }

  function waited(value) {
    const start = new Date(String(value || '').replace(' ', 'T'));
    const hours = (Date.now() - start.getTime()) / 36e5;
    if (!Number.isFinite(hours) || hours < 0) return '';
    return hours < 1 ? '不到 1 小时' : hours < 48 ? `${Math.floor(hours)} 小时` : `${Math.floor(hours / 24)} 天`;
  }

  function create({ api, render, notify, workbenchPanel, empty, onCounts }) {
    let status = 'pending', query = '', searchDraft = '', page = 1, data = null, loading = false, error = '', sequence = 0, timer = null;
    let openId = null, detail = null, detailError = '', acting = false, form = null, noteDraft = '', targetDraft = '';

    async function load() {
      const ticket = ++sequence;
      loading = true; error = ''; render();
      try {
        const params = new URLSearchParams({ status, page: String(page), page_size: '20' });
        if (query) params.set('q', query);
        const result = await api(`/api/admin/deck-submissions?${params}`);
        if (ticket === sequence) { data = result; onCounts?.(result.counts); }
      } catch (err) {
        if (ticket === sequence) error = err.message || '投稿读取失败';
      } finally {
        if (ticket === sequence) { loading = false; render(); }
      }
    }

    async function open(id) {
      if (openId === id) { openId = null; detail = null; form = null; render(); return; }
      openId = id; detail = null; detailError = ''; form = null; render();
      await refreshDetail();
    }

    async function refreshDetail() {
      const id = openId;
      try {
        const result = await api(`/api/admin/deck-submissions/${id}`);
        if (openId === id) detail = result;
      } catch (err) {
        if (openId === id) detailError = err.message || '读取失败';
      }
      render();
    }

    async function act(action, extra = {}, message = '') {
      if (acting || !detail) return;
      acting = true; render();
      try {
        detail = await api(`/api/admin/deck-submissions/${detail.id}/${action}`, { method: 'POST', body: JSON.stringify({ version: detail.version, ...extra }) });
        form = null; noteDraft = ''; targetDraft = '';
        notify(message);
      } catch (err) {
        acting = false;
        // A stale version or someone else's claim: show the latest state, keep the typed note.
        await refreshDetail();
        throw err;
      }
      acting = false;
      await load();
    }

    function statusTag(item) {
      const tag = el('span', 'admin-sub-status', STATUS[item.status]);
      tag.dataset.status = item.status;
      return tag;
    }

    function row(item) {
      const tr = el('tr', `admin-sub-row${openId === item.id ? ' is-open' : ''}`);
      const title = button('', () => open(item.id), 'admin-sub-title');
      title.setAttribute('aria-expanded', String(openId === item.id));
      title.setAttribute('aria-controls', `admin-sub-detail-${item.id}`);
      title.append(el('strong', '', item.title), el('span', 'admin-meta', `#${item.id}${item.note ? ` · ${item.note}` : ''}`));
      const who = el('span', 'admin-sub-person');
      who.append(global.jccAvatar.image(item.submitter.avatar_config, 24), el('span', '', item.submitter.nickname));
      const time = el('time', 'admin-meta', item.status === 'pending' || item.status === 'needs_info' ? `${shortTime(item.created_at)} · 等待 ${waited(item.updated_at)}` : shortTime(item.resolved_at || item.updated_at));
      const state = el('span', 'admin-sub-state');
      state.append(statusTag(item));
      if (item.assignee) state.append(el('span', 'admin-meta', item.mine ? '我' : item.assignee.nickname));
      const actions = [];
      if (item.status === 'pending') actions.push(button('认领', async () => { openId = item.id; detail = item; await act('claim', {}, '已认领，可以开始完善'); await refreshDetail(); }, 'small-button', acting));
      if (item.status === 'processing' && item.mine) {
        const edit = el('a', 'small-button is-primary-link', '完善卡组');
        edit.href = item.editor_url;
        actions.push(edit);
      }
      const cells = [[title, 'admin-sub-main'], [who, 'admin-sub-cell', '投稿人'], [time, 'admin-sub-cell', '时间'], [state, 'admin-sub-cell', '状态'], [actions, 'admin-sub-actions']];
      cells.forEach(([content, className, label]) => {
        const td = el('td', className);
        if (label) td.dataset.label = label;
        td.append(...[].concat(content));
        tr.append(td);
      });
      return tr;
    }

    function copyBlock(label, value) {
      const wrap = el('div', 'admin-sub-code');
      const head = el('div', 'admin-sub-code-head');
      head.append(el('span', '', label), button('复制', async (_, node) => {
        try { await navigator.clipboard.writeText(value); node.textContent = '已复制'; } catch { node.textContent = '请手动复制'; }
        setTimeout(() => { node.textContent = '复制'; }, 1500);
      }, 'small-button'));
      const code = el('code', '', value);
      wrap.append(head, code);
      return wrap;
    }

    function noteForm(kind) {
      const config = {
        request_info: ['需要补充的内容', '投稿人可见，例如：方案码无法导入，请重新复制', '发送补充请求', '已请投稿人补充'],
        reject: ['未采纳原因', '投稿人可见，2–1000 字', '确认不采纳', '已标记为未采纳'],
        duplicate: ['重复的卡组', '选择或输入同赛季公开卡组 ID；说明可选', '确认判重', '已判定为重复'],
        assign: ['转派给', '只有当前处理人可以继续完善', '确认转派', '已转派'],
      }[kind];
      const wrap = el('form', 'admin-sub-form');
      const label = el('label', 'admin-sub-form-label', config[0]);
      const hint = el('span', 'admin-meta', config[1]);
      const fields = el('div', 'admin-sub-form-fields');
      let submitDisabled = () => false;
      if (kind === 'assign') {
        const select = el('select');
        select.append(el('option', '', '选择管理员'));
        select.firstChild.value = '';
        detail.admins.filter((admin) => admin.id !== detail.assignee?.id).forEach((admin) => {
          const option = el('option', '', admin.nickname); option.value = String(admin.id); select.append(option);
        });
        select.value = targetDraft;
        select.addEventListener('change', () => { targetDraft = select.value; sync(); });
        fields.append(select);
        submitDisabled = () => !targetDraft;
      }
      if (kind === 'duplicate') {
        const select = el('select');
        select.append(el('option', '', '选择疑似重复的公开卡组'));
        select.firstChild.value = '';
        detail.possible_duplicates.decks.filter((deck) => deck.status === 'published').forEach((deck) => {
          const option = el('option', '', `#${deck.id} ${deck.name}`); option.value = String(deck.id); select.append(option);
        });
        const input = el('input');
        Object.assign(input, { type: 'number', min: '1', placeholder: '或输入卡组 ID', value: targetDraft });
        select.addEventListener('change', () => { targetDraft = select.value; input.value = select.value; sync(); });
        input.addEventListener('input', () => { targetDraft = input.value; sync(); });
        fields.append(select, input);
        submitDisabled = () => !(Number(targetDraft) > 0);
      }
      let textarea = null;
      if (kind !== 'assign') {
        textarea = el('textarea');
        Object.assign(textarea, { rows: 3, maxLength: NOTE_MAX, value: noteDraft, placeholder: kind === 'duplicate' ? '可选：告诉投稿人对应哪套卡组' : '' });
        textarea.setAttribute('aria-label', config[0]);
        textarea.addEventListener('input', () => { noteDraft = textarea.value; sync(); });
        fields.append(textarea);
        if (kind !== 'duplicate') { const required = submitDisabled; submitDisabled = () => required() || noteDraft.trim().length < 2; }
      }
      const cancel = button('取消', () => { form = null; noteDraft = ''; targetDraft = ''; render(); }, 'small-button');
      const confirmButton = button(config[2], () => act(kind, kind === 'assign' ? { admin_id: Number(targetDraft) }
        : kind === 'duplicate' ? { duplicate_of_deck_id: Number(targetDraft), note: noteDraft.trim() } : { note: noteDraft.trim() }, config[3]),
        `small-button${kind === 'reject' ? ' danger-button is-solid' : ' is-primary-button'}`);
      confirmButton.type = 'submit';
      const sync = () => { confirmButton.disabled = acting || submitDisabled(); };
      sync();
      wrap.addEventListener('submit', (event) => { event.preventDefault(); if (!confirmButton.disabled) confirmButton.click(); });
      wrap.addEventListener('keydown', (event) => { if (event.key === 'Escape') { event.preventDefault(); cancel.click(); } });
      const buttons = el('div', 'admin-sub-form-buttons');
      buttons.append(cancel, confirmButton);
      const heading = el('div', 'admin-sub-form-heading');
      heading.append(label, hint);
      wrap.append(heading, fields, buttons);
      queueMicrotask(() => { if (wrap.isConnected && !wrap.contains(document.activeElement)) (textarea || fields.querySelector('select'))?.focus({ preventScroll: true }); });
      return wrap;
    }

    function detailView() {
      const wrap = el('div', 'admin-sub-detail');
      if (detailError) { wrap.append(empty(detailError)); return wrap; }
      if (!detail) { wrap.append(el('p', 'admin-meta', '正在读取投稿…')); return wrap; }
      const left = el('div', 'admin-sub-detail-main');
      left.append(copyBlock('方案码', detail.plan_code), copyBlock('阵容码', detail.lineup_code));
      if (detail.note) { const note = el('div', 'admin-sub-note'); note.append(el('span', 'admin-meta', '投稿人备注'), el('p', '', detail.note)); left.append(note); }
      if (detail.review_note) { const note = el('div', 'admin-sub-note'); note.append(el('span', 'admin-meta', '处理说明'), el('p', '', detail.review_note)); left.append(note); }
      if (detail.season_id !== detail.current_season_id) left.append(el('p', 'admin-sub-warning', '投稿所属赛季已不是当前时间卡片赛季，无法完善发布。'));
      const dupes = detail.possible_duplicates;
      if (dupes.decks.length || dupes.submissions.length) {
        const box = el('div', 'admin-sub-dupes');
        box.append(el('span', 'admin-meta', '相同代码'));
        dupes.decks.forEach((deck) => { const link = el('a', '', `卡组 #${deck.id} ${deck.name}${deck.status === 'hidden' ? '（已隐藏）' : ''}`); link.href = deck.detail_url; link.target = '_blank'; link.rel = 'noopener'; box.append(link); });
        dupes.submissions.forEach((sub) => box.append(el('span', '', `投稿 #${sub.id} · ${sub.submitter}${sub.same_submitter ? '（同一人）' : ''} · ${sub.status_label}`)));
        left.append(box);
      }
      if (detail.deck_detail) {
        const draft = el('p', 'admin-meta', `完善草稿 #${detail.deck_detail.id} · ${detail.deck_detail.name} · ${detail.deck_detail.cards.filter(Boolean).length}/3 张卡 · 版本 ${detail.deck_detail.version}`);
        left.append(draft);
      }
      const side = el('div', 'admin-sub-detail-side');
      const actions = el('div', 'admin-sub-detail-actions');
      const processingMine = detail.status === 'processing' && detail.mine;
      if (detail.status === 'pending') actions.append(button('认领并开始处理', () => act('claim', {}, '已认领'), 'small-button is-primary-button', acting));
      if (processingMine) {
        const edit = el('a', 'small-button is-primary-link', detail.deck_detail ? '继续完善并发布' : '完善卡组');
        edit.href = detail.editor_url;
        actions.append(edit,
          button('请求补充', () => { form = 'request_info'; render(); }, 'small-button', acting),
          button('判重', () => { form = 'duplicate'; render(); }, 'small-button', acting),
          button('不采纳', () => { form = 'reject'; render(); }, 'small-button danger-button', acting),
          button('放回队列', () => act('release', {}, '已放回待处理队列'), 'small-button', acting));
      }
      if (['pending', 'processing'].includes(detail.status) && detail.admins.length > 1) {
        actions.append(button(detail.status === 'processing' && !detail.mine ? '转派给我或他人' : '转派', () => { form = 'assign'; render(); }, 'small-button', acting));
      }
      if (detail.status === 'processing' && !detail.mine) side.append(el('p', 'admin-meta', `正由 ${detail.assignee?.nickname || '其他管理员'} 处理`));
      if (detail.status === 'needs_info') side.append(el('p', 'admin-meta', '等待投稿人补充，补充后回到待处理。'));
      if (detail.deck?.detail_url) { const link = el('a', 'small-button', '查看发布的卡组'); link.href = detail.deck.detail_url; link.target = '_blank'; actions.append(link); }
      side.append(actions);
      if (form) side.append(noteForm(form));
      const history = el('ol', 'admin-sub-history');
      detail.events.slice().reverse().forEach((event) => {
        const item = el('li');
        item.append(el('strong', '', event.label), el('span', 'admin-meta', `${event.actor} · ${shortTime(event.created_at)}`));
        if (event.note) item.append(el('p', '', event.note));
        history.append(item);
      });
      const historyWrap = el('details', 'admin-sub-history-wrap');
      historyWrap.open = detail.events.length <= 4;
      historyWrap.append(el('summary', '', `处理记录 ${detail.events.length}`), history);
      side.append(historyWrap);
      wrap.append(left, side);
      return wrap;
    }

    function toolbar() {
      const bar = el('div', 'admin-deck-toolbar');
      const filters = el('div', 'admin-deck-filters');
      filters.setAttribute('role', 'group');
      filters.setAttribute('aria-label', '按状态筛选');
      const counts = data?.counts || {};
      FILTERS.forEach(([value, label]) => {
        const control = button('', async () => { if (status === value) return; status = value; page = 1; openId = null; detail = null; await load(); },
          `admin-deck-filter${status === value ? ' is-active' : ''}`);
        control.setAttribute('aria-pressed', String(status === value));
        control.append(el('span', '', label), el('span', 'admin-deck-filter-count', data ? String(counts[value] || 0) : ''));
        filters.append(control);
      });
      const search = el('label', 'admin-deck-search');
      search.dataset.searchKey = 'deck-submissions';
      const input = el('input');
      Object.assign(input, { type: 'search', placeholder: '搜索标题、投稿人或 #编号', value: searchDraft, maxLength: 40 });
      input.setAttribute('aria-label', '搜索投稿');
      let composing = false;
      const changed = () => {
        searchDraft = input.value;
        clearTimeout(timer);
        if (composing) return;
        timer = setTimeout(() => { if (!input.isConnected) return; query = searchDraft.trim(); page = 1; openId = null; load(); }, 350);
      };
      input.addEventListener('compositionstart', () => { composing = true; clearTimeout(timer); });
      input.addEventListener('compositionend', () => { composing = false; changed(); });
      input.addEventListener('input', changed);
      search.append(input);
      bar.append(filters, search);
      return bar;
    }

    function view() {
      const panel = workbenchPanel('卡组投稿', '认领后补全三张卡、传送门和站位，发布时署名由投稿人提供');
      const body = panel.querySelector('.admin-workspace-body');
      body.classList.add('admin-deck-workspace', 'admin-sub-workspace');
      body.append(toolbar());
      if (error) body.append(empty(error));
      else if (loading && !data) body.append(empty('正在读取投稿…'));
      else if (!data?.items.length) body.append(empty(query ? '没有匹配的投稿' : { pending: '没有待处理的投稿', mine: '你当前没有处理中的投稿', processing: '没有处理中的投稿', needs_info: '没有等待补充的投稿', resolved: '还没有已处理的投稿' }[status]));
      else {
        const table = el('table', 'admin-sub-table');
        table.setAttribute('aria-busy', String(loading));
        const rows = el('tbody');
        data.items.forEach((item) => {
          rows.append(row(item));
          if (openId === item.id) {
            const tr = el('tr', 'admin-sub-detail-row');
            tr.id = `admin-sub-detail-${item.id}`;
            const td = el('td');
            td.colSpan = 5;
            td.append(detailView());
            tr.append(td);
            rows.append(tr);
          }
        });
        table.append(rows);
        body.append(table);
      }
      if (data && (data.total_pages || 1) > 1) {
        const pager = el('div', 'admin-pagination');
        pager.append(button('上一页', async () => { page -= 1; openId = null; await load(); }, 'small-button', page <= 1),
          el('span', 'admin-meta', `第 ${page} / ${data.total_pages} 页`),
          button('下一页', async () => { page += 1; openId = null; await load(); }, 'small-button', page >= data.total_pages));
        body.append(pager);
      }
      return panel;
    }
    return { load, view };
  }

  global.JccAdminDeckSubmissions = { create };
})(window);
