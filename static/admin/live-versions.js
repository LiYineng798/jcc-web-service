(function (global) {
  const { el, button, revealListStart } = global.JccAdminCore;
  const labels = { active: '当前线上', draft: '预上线', history: '历史版本' };

  function create({ api, render, notify, getSeason }) {
    let items = [], detail = null, loading = false, error = '', busy = false;
    let filter = 'all', onlyMissing = false, query = '', page = 1, sequence = 0;
    const url = (id = '') => `/api/admin/live-comps/versions/${encodeURIComponent(getSeason())}${id ? '/' + encodeURIComponent(id) : ''}`;
    function reset() { sequence++; items = []; detail = null; error = ''; loading = false; filter = 'all'; query = ''; page = 1; }
    async function load(preferred) {
      const ticket = ++sequence;
      loading = true; error = ''; render();
      try {
        const result = await api(url());
        if (ticket !== sequence) return;
        items = result.items;
        const id = items.find(item => item.id === (preferred || detail?.id))?.id || result.active_id || items[0]?.id;
        const next = id ? await api(url(id)) : null;
        if (ticket !== sequence) return;
        detail = next;
      } catch (err) {
        if (ticket === sequence) error = err.message || '版本读取失败';
      } finally {
        if (ticket === sequence) { loading = false; render(); }
      }
    }
    async function select(id) {
      const ticket = ++sequence;
      loading = true; error = ''; detail = null; page = 1; render();
      try {
        const next = await api(url(id));
        if (ticket === sequence) detail = next;
      } catch (err) { if (ticket === sequence) error = err.message; }
      finally { if (ticket === sequence) { loading = false; render(); document.querySelector('#liveVersionPreviewTitle')?.focus({ preventScroll: true }); } }
    }
    function badge(status) { return el('span', `live-version-badge is-${status}`, labels[status]); }
    async function mutate(action, data, chosen = detail) {
      if (busy || !chosen) return;
      busy = true;
      try {
        await api(`${url(chosen.id)}/${action}`, { method: 'POST', body: JSON.stringify({
          revision: chosen.revision, active_revision: chosen.active_revision, ...data,
        }) });
        notify(action === 'publish' ? '线上版本已切换，首页现已展示此版本' : action === 'delete' ? '版本已删除' : '补码已保存');
      } finally { busy = false; }
      // A refresh failure must not misreport a successful write.
      await load(action === 'delete' ? undefined : chosen.id);
    }
    function confirmAction(action) {
      const chosen = detail;
      const opener = document.activeElement;
      const dialog = el('dialog', 'live-version-dialog');
      const title = el('h2', '', action === 'delete' ? '删除这个版本？' : chosen.status === 'history' ? '回滚到这个版本？' : '将这个版本上线？');
      title.id = 'liveVersionConfirmTitle'; dialog.setAttribute('aria-labelledby', title.id);
      dialog.append(title, el('p', '', chosen.filename), el('p', 'admin-meta', action === 'delete'
        ? '将删除此版本及其补码记录，此操作无法撤销。当前线上版本不会变化。'
        : `首页将展示这 ${chosen.total} 套阵容。当前线上版本会保留在历史中，随时可以切换回来。`));
      let acknowledgement = null;
      if (action === 'publish' && chosen.missing) {
        const label = el('label', 'live-version-ack');
        acknowledgement = el('input'); acknowledgement.type = 'checkbox';
        label.append(acknowledgement, el('span', '', `仍有 ${chosen.missing} 套阵容缺码，我确认先上线这些内容`));
        dialog.append(label);
      }
      const message = el('p', 'live-upload-error'); message.setAttribute('role', 'alert');
      const actions = el('div', 'card-actions');
      const cancel = button('取消', () => dialog.close());
      const submit = button(action === 'delete' ? '确认删除' : '确认切换线上版本', async () => {
        submit.disabled = true; cancel.disabled = true;
        try { await mutate(action, { allow_missing: Boolean(acknowledgement?.checked) }, chosen); dialog.close(); }
        catch (err) { message.textContent = err.message; submit.disabled = false; cancel.disabled = false; }
      }, action === 'delete' ? 'small-button danger' : 'primary-button', Boolean(acknowledgement));
      acknowledgement?.addEventListener('change', () => { submit.disabled = !acknowledgement.checked; });
      actions.append(cancel, submit); dialog.append(message, actions);
      dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
      dialog.addEventListener('close', () => { dialog.remove(); if (opener?.isConnected) opener.focus(); else document.querySelector('#liveVersionPreviewTitle')?.focus(); });
      document.body.append(dialog); dialog.showModal(); cancel.focus();
    }
    function codeDialog(item) {
      const chosen = detail;
      const dialog = el('dialog', 'live-version-dialog');
      dialog.setAttribute('aria-labelledby', 'liveVersionCodeTitle');
      const title = el('h2', '', item.hasCode ? '修改补码' : '补充阵容码'); title.id = 'liveVersionCodeTitle';
      dialog.append(title, el('p', 'admin-meta', `${chosen.filename} · ${item.title}`),
        el('p', 'admin-meta', chosen.status === 'active' ? '保存后立即更新当前线上版本。' : '仅保存到这个版本，上线前不会影响首页。'));
      const form = el('form'); const label = el('label', 'field');
      label.append(el('span', '', '金铲铲阵容码'));
      const input = el('textarea'); input.rows = 5; input.required = true; input.value = item.jccCode || '';
      input.placeholder = '粘贴游戏分享的完整阵容码'; label.append(input);
      const message = el('p', 'live-upload-error'); message.setAttribute('role', 'alert');
      const actions = el('div', 'card-actions'); const save = el('button', 'primary-button', '保存补码'); save.type = 'submit';
      const cancel = button('取消', () => dialog.close()); actions.append(cancel, save);
      form.append(label, message, actions);
      form.addEventListener('submit', async event => {
        event.preventDefault(); save.disabled = true; cancel.disabled = true;
        try { await mutate('code', { item_id: item.id, code: input.value }, chosen); dialog.close(); }
        catch (err) { message.textContent = err.message; save.disabled = false; cancel.disabled = false; }
      });
      dialog.append(form); dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
      dialog.addEventListener('close', () => { dialog.remove(); document.querySelector('#liveVersionPreviewTitle')?.focus({ preventScroll: true }); });
      document.body.append(dialog); dialog.showModal(); input.focus();
    }
    function preview() {
      const panel = el('section', 'live-version-preview');
      if (loading) { panel.append(el('p', 'admin-meta', '正在读取版本内容…')); return panel; }
      if (!detail) { panel.append(el('p', 'admin-meta', '选择左侧版本，预览阵容并完成补码。')); return panel; }
      const head = el('div', 'live-version-preview-head'); const titleWrap = el('div');
      const title = el('h3', '', detail.filename); title.id = 'liveVersionPreviewTitle'; title.tabIndex = -1;
      titleWrap.append(badge(detail.status), title, el('p', 'admin-meta', `上传时间 ${detail.created_at} · ${detail.id === 'legacy' ? '原线上数据' : detail.id.slice(0, 8)}`));
      const actions = el('div', 'card-actions');
      if (detail.status !== 'active') {
        actions.append(button(detail.status === 'history' ? '回滚到此版本' : '上线此版本', () => confirmAction('publish'), 'primary-button', busy));
        actions.append(button('删除版本', () => confirmAction('delete'), 'small-button danger', busy));
      }
      head.append(titleWrap, actions); panel.append(head);
      const stats = el('div', 'live-version-stats');
      [['阵容总数', detail.total], ['已具备阵容码', detail.ready], ['等待补码', detail.missing]].forEach(([name, count]) => {
        const stat = el('div'); stat.append(el('strong', '', String(count)), el('span', '', name)); stats.append(stat);
      }); panel.append(stats);
      if (detail.status !== 'active') {
        const diff = detail.diff;
        panel.append(el('p', 'live-version-diff', `相对线上：新增 ${diff.added_ids.length} · 移除 ${diff.removed_ids.length} · 内容变化 ${diff.changed_ids.length} · 阵容码变化 ${diff.code_changed_ids.length}`));
      }
      const toolbar = el('div', 'live-version-tools'); const search = el('input');
      search.type = 'search'; search.placeholder = '搜索阵容名称 / ID'; search.value = query; search.setAttribute('aria-label', '搜索版本内阵容');
      const missing = el('label'); const checkbox = el('input'); checkbox.type = 'checkbox'; checkbox.checked = onlyMissing;
      missing.append(checkbox, el('span', '', '只看缺码'));
      toolbar.append(search, missing); panel.append(toolbar);
      const results = el('div', 'live-version-comps');
      const pager = el('div', 'live-version-pager');
      function draw() {
        const all = ['S', 'A', 'B', 'C', 'D'].flatMap(tier => detail.payload.tiers[tier] || []).filter(item => (!onlyMissing || !item.hasCode) && `${item.title} ${item.id}`.toLowerCase().includes(query.toLowerCase()));
        const pages = Math.max(1, Math.ceil(all.length / 8)); page = Math.min(page, pages);
        results.replaceChildren(); pager.replaceChildren();
        if (!all.length) results.append(el('p', 'live-version-empty', onlyMissing ? '当前筛选下没有缺码阵容' : '没有匹配的阵容'));
        all.slice((page - 1) * 8, page * 8).forEach(item => {
          const card = el('article', 'live-version-comp'); const heading = el('div', 'live-version-comp-head');
          heading.append(el('span', 'live-version-tier', item.tier), el('strong', '', item.title), el('span', item.hasCode ? 'live-version-code-ok' : 'live-version-code-missing', item.hasCode ? (item.codeSource === 'manual' ? '已补码' : '原始码') : '待补码'));
          const heroes = el('div', 'live-version-heroes');
          (item.heroImages || []).forEach(src => {
            // Only cached site assets / site static resources are previewed.
            if (!String(src).startsWith('/api/live-comps/assets/') && !String(src).startsWith('/static/')) return;
            const img = el('img'); img.src = src; img.alt = ''; img.loading = 'lazy'; heroes.append(img);
          });
          card.append(heading, heroes, el('p', 'admin-meta', `ID ${item.id}${item.formationDetails?.units?.length ? ` · ${item.formationDetails.units.length} 个站位弈子` : ''}`));
          if (item.hasCode) card.append(el('pre', 'admin-code', item.jccCode));
          if (!item.originalJccCode) card.append(button(item.hasCode ? '修改补码' : '补充阵容码', () => codeDialog(item), 'small-button', busy));
          results.append(card);
        });
        pager.append(button('上一页', () => { page--; draw(); revealListStart(results); }, 'small-button', page <= 1), el('span', 'admin-meta', `${page} / ${pages} · 共 ${all.length} 套`), button('下一页', () => { page++; draw(); revealListStart(results); }, 'small-button', page >= pages));
      }
      let composing = false;
      const searchChanged = () => { if (!composing) { query = search.value; page = 1; draw(); } };
      search.addEventListener('compositionstart', () => { composing = true; });
      search.addEventListener('compositionend', () => { composing = false; searchChanged(); });
      search.addEventListener('input', searchChanged);
      checkbox.addEventListener('change', () => { onlyMissing = checkbox.checked; page = 1; draw(); });
      draw(); panel.append(results, pager); return panel;
    }
    function view() {
      const section = el('section', 'live-version-library');
      const head = el('div', 'live-version-library-head'); const title = el('div');
      title.append(el('span', 'live-version-eyebrow', 'RELEASE LIBRARY'), el('h2', '', '版本库'), el('p', 'admin-meta', '每个赛季独立管理 · 每个版本独立补码 · 同一时间仅展示一个版本'));
      head.append(title, button('刷新版本库', () => load(), 'small-button', loading || busy)); section.append(head);
      if (error) { const alert = el('p', 'live-upload-error', error + '，请刷新重试。'); alert.setAttribute('role', 'alert'); section.append(alert); }
      const layout = el('div', 'live-version-layout'); const sidebar = el('aside', 'live-version-list'); sidebar.setAttribute('aria-label', '上传版本');
      const filters = el('div', 'live-version-filters');
      [['all', '全部'], ['draft', '预上线'], ['history', '历史']].forEach(([key, label]) => {
        const node = button(label, () => { filter = key; render(); document.getElementById(`liveVersionFilter-${key}`)?.focus({ preventScroll: true }); }, `small-button ${filter === key ? 'is-active' : ''}`);
        node.id = `liveVersionFilter-${key}`;
        node.setAttribute('aria-pressed', String(filter === key)); filters.append(node);
      }); sidebar.append(filters);
      const filtered = items.filter(item => filter === 'all' || item.status === filter);
      if (!filtered.length) sidebar.append(el('p', 'live-version-empty', loading ? '正在读取版本…' : '暂无版本，上传 JSON 后保存为预上线版本即可在这里管理。'));
      filtered.forEach(item => {
        const row = button('', () => select(item.id), `live-version-row ${item.id === detail?.id ? 'is-selected' : ''}`, busy);
        row.setAttribute('aria-pressed', String(item.id === detail?.id));
        const top = el('div'); top.append(badge(item.status), el('span', 'admin-meta', item.id === 'legacy' ? '原始' : item.id.slice(0, 8)));
        const meter = el('div', 'live-version-meter'); const fill = el('span'); fill.style.width = `${item.total ? item.ready / item.total * 100 : 0}%`; meter.append(fill);
        row.append(top, el('strong', '', item.filename), el('small', '', item.created_at), meter, el('span', 'admin-meta', `${item.total} 套阵容 · ${item.missing ? item.missing + ' 套待补码' : '阵容码齐全'}`)); sidebar.append(row);
      }); layout.append(sidebar, preview()); section.append(layout); return section;
    }
    return { view, load, reset };
  }
  global.JccAdminLiveVersions = { create };
})(window);
