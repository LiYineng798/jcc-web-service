(function () {
  'use strict';
  const { el, escapeAttribute: attr, escapeHtml: html } = window.JccAdminCore;
  const kinds = [
    ['none', '仅展示', '不设置跳转'], ['tool', '工具箱', '直接打开站内工具'],
    ['lineup', '阵容榜单', '指定赛季与榜单'], ['guestbook', '留言板', '打开首页反馈窗口'],
    ['custom', '自定义链接', '站内页面或外部网站'],
  ];
  const tabs = [['live', '实时阵容排行'], ['latest', '最新'], ['hot', '最热'], ['rising', '上升'], ['recommended', '推荐'], ['ss', 'SS']];

  function mount(root, { item, api, close, saved }) {
    const previousFocus = document.activeElement;
    const lifetime = new AbortController();
    const dialog = el('dialog', 'notice-editor');
    dialog.setAttribute('aria-labelledby', 'noticeDialogTitle');
    let kind = item.target?.kind || (item.link_url === '/#guestbook' ? 'guestbook' : item.jump_season_id && item.jump_tab ? 'lineup' : item.link_url ? 'custom' : 'none');
    let selectedTool = item.target?.tool_id || '';
    let catalog = { tools: [], seasons: [] };
    let loaded = false;
    let busy = false;
    let loading = false;
    let savedId = item.id;
    dialog.innerHTML = `
      <header class="notice-editor-header"><div><p class="notice-eyebrow">首页 · 全站通知</p>
        <h2 id="noticeDialogTitle">${item.id ? '编辑通知' : '创建一条通知'}</h2>
        <p class="admin-meta">写好消息，选择去处。发布前即可预览效果。</p></div>
        <button type="button" class="ghost-button" data-close aria-label="关闭通知编辑器">关闭</button></header>
      <form class="notice-editor-form">
        <div class="notice-editor-grid"><div class="notice-editor-fields">
          <section><h3><span>01</span> 通知内容</h3>
            <label class="field"><span>标题</span><input id="noticeTitleInput" name="title" required placeholder="例如：时间卡片图鉴已上线" value="${attr(item.title || '')}"></label>
            <label class="field"><span>内容</span><textarea id="noticeMessageInput" name="message" required rows="3" placeholder="用简短的一句话，告诉玩家这次更新的亮点。">${html(item.message || '')}</textarea></label>
          </section>
          <section><h3><span>02</span> 点击后前往</h3>
            <fieldset class="notice-target-types"><legend class="sr-only">跳转类型</legend>${kinds.map(([value, label, hint]) => `
              <label class="notice-type"><input type="radio" name="target_kind" value="${value}"${kind === value ? ' checked' : ''}><span><strong>${label}</strong><small>${hint}</small></span></label>`).join('')}
            </fieldset>
            <div data-panel="tool" class="notice-target-panel">
              <div class="notice-catalog-heading"><span class="admin-meta">与前台工具箱同步</span><button type="button" class="small-button" data-refresh>刷新选项</button></div>
              <label class="field"><span class="sr-only">搜索工具</span><input type="search" data-tool-search placeholder="搜索工具名称或赛季…"></label>
              <div class="notice-tool-list" role="group" aria-label="选择工具"></div>
              <p class="notice-tool-status" role="status"></p>
            </div>
            <div data-panel="lineup" class="notice-target-panel notice-lineup-fields">
              <label class="field"><span>赛季</span><select id="noticeJumpSeasonInput"><option value="">请选择赛季</option></select></label>
              <label class="field"><span>榜单</span><select id="noticeJumpTabInput"><option value="">请选择榜单</option>${tabs.map(([value, label]) => `<option value="${value}"${item.jump_tab === value ? ' selected' : ''}>${label}</option>`).join('')}</select></label>
              <button type="button" class="small-button" data-refresh>刷新赛季</button>
            </div>
            <p data-panel="guestbook" class="notice-target-panel admin-meta">玩家点击后，将直接打开首页留言窗口。</p>
            <label data-panel="custom" class="field notice-target-panel"><span>链接地址</span><input id="noticeLinkUrlInput" placeholder="/patch-notes 或 https://example.com" value="${attr(item.link_url || '')}"><small class="admin-meta">站内链接在当前页打开，外部网站在新标签页打开。</small></label>
            <label class="field" data-link-text><span>按钮文字 <small class="admin-meta">选填，留空使用默认文字</small></span><input id="noticeLinkTextInput" placeholder="例如：打开图鉴" value="${attr(item.link_text || '')}"></label>
            <p class="notice-catalog-error" role="status" hidden></p>
          </section>
          <section class="notice-display-option"><div><h3><span>03</span> 展示方式</h3><p class="admin-meta">桌面端滚动展示，手机端自动换行。</p></div>
            <label><input id="noticeMarqueeCheckbox" type="checkbox"${item.marquee_enabled !== false ? ' checked' : ''}> 滚动播放</label>
          </section>
        </div><aside class="notice-preview"><p class="notice-eyebrow">实时预览</p><h3>玩家将看到</h3>
          <div class="notice-preview-banner"><strong data-preview-title></strong><p data-preview-message></p><span data-preview-link></span></div>
          <div class="notice-destination"><span class="notice-eyebrow">跳转目标</span><strong data-preview-target></strong><code data-preview-url></code></div>
          <p class="admin-meta" data-preview-mode></p><p class="admin-meta">预览用于检查内容和去向，首页会按屏幕宽度自动排版。</p>
        </aside></div>
        <footer class="notice-editor-footer"><p class="notice-form-error" role="alert" hidden></p><p class="admin-meta">${item.is_active ? '此通知已被选中，保存会同步更新展示内容。' : '保存到通知库，或立即展示在首页。'}</p>
          <div><button type="button" class="ghost-button" data-close>取消</button><button type="submit" class="small-button" value="save">保存通知</button><button type="submit" class="primary-button" value="publish">保存并展示</button></div>
        </footer>
      </form>`;
    root.append(dialog);
    const form = dialog.querySelector('form');
    const $ = (selector) => dialog.querySelector(selector);
    const value = (selector) => $(selector).value.trim();
    const formError = $('.notice-form-error');
    function dismiss() {
      if (busy) return;
      lifetime.abort();
      dialog.close();
      close();
      if (previousFocus?.isConnected) previousFocus.focus();
    }
    dialog.querySelectorAll('[data-close]').forEach((node) => node.addEventListener('click', dismiss));
    dialog.addEventListener('cancel', (event) => { event.preventDefault(); dismiss(); });
    dialog.addEventListener('keydown', (event) => {
      if (event.key !== 'Tab') return;
      const nodes = [...dialog.querySelectorAll('button, input, textarea, select')]
        .filter((node) => !node.disabled && node.getClientRects().length);
      const first = nodes[0], last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    });

    function target() {
      if (kind === 'tool') {
        const tool = catalog.tools.find((entry) => entry.id === selectedTool);
        return { label: tool?.title || (selectedTool ? '原工具已隐藏或不可用，请重新选择' : '请选择一个工具'), url: tool?.url || '', text: tool ? `打开${tool.title}` : '' };
      }
      if (kind === 'lineup') {
        const season = $('#noticeJumpSeasonInput');
        const tab = $('#noticeJumpTabInput');
        return { label: season.value && tab.value ? `${season.selectedOptions[0].textContent} · ${tab.selectedOptions[0].textContent}` : '请选择赛季与榜单', url: '首页内切换', text: '查看阵容' };
      }
      if (kind === 'guestbook') return { label: '首页留言板', url: '/#guestbook', text: '去留言' };
      if (kind === 'custom') return { label: '自定义链接', url: value('#noticeLinkUrlInput'), text: '了解更多' };
      return { label: '仅展示通知', url: '不设置跳转', text: '' };
    }
    function update() {
      dialog.querySelectorAll('[data-panel]').forEach((node) => { node.hidden = node.dataset.panel !== kind; });
      $('[data-link-text]').hidden = kind === 'none';
      const destination = target();
      $('[data-preview-title]').textContent = value('#noticeTitleInput') || '通知标题';
      $('[data-preview-message]').textContent = value('#noticeMessageInput') || '通知内容会显示在这里。';
      $('[data-preview-link]').textContent = kind === 'none' ? '' : `${value('#noticeLinkTextInput') || destination.text || '查看详情'} →`;
      $('[data-preview-target]').textContent = destination.label;
      $('[data-preview-url]').textContent = destination.url;
      $('[data-preview-mode]').textContent = $('#noticeMarqueeCheckbox').checked ? '展示方式 · 桌面滚动 / 手机换行' : '展示方式 · 静止显示';
    }
    function changeTarget(change) {
      const text = $('#noticeLinkTextInput');
      const usedDefault = text.value.trim() === target().text;
      change();
      if (usedDefault) text.value = '';
      update();
    }
    function renderTools() {
      const list = $('.notice-tool-list');
      list.replaceChildren();
      const query = value('[data-tool-search]').toLocaleLowerCase();
      const tools = catalog.tools.filter((tool) => `${tool.title} ${tool.group} ${tool.description}`.toLocaleLowerCase().includes(query));
      let group;
      tools.forEach((tool) => {
        if (group !== tool.group) {
          group = tool.group;
          list.append(el('p', 'notice-tool-group', group || '通用工具'));
        }
        const label = el('label', 'notice-tool-option');
        const radio = document.createElement('input');
        radio.type = 'radio'; radio.name = 'tool_id'; radio.value = tool.id; radio.checked = selectedTool === tool.id;
        const copy = el('span');
        copy.append(el('strong', '', tool.title), el('small', '', tool.description));
        label.append(radio, copy);
        radio.addEventListener('change', () => changeTarget(() => { selectedTool = tool.id; }));
        list.append(label);
      });
      $('.notice-tool-status').textContent = !loaded ? '正在加载工具目录…' : !catalog.tools.length ? '暂无可用工具，请选择其他跳转方式。' : !tools.length ? '没有匹配的工具，试试其他关键词。' : `共 ${catalog.tools.length} 个可用工具${query ? ` · 匹配 ${tools.length} 个` : ''}`;
    }
    async function refresh() {
      if (loading || busy) return;
      loading = true;
      const error = $('.notice-catalog-error');
      error.hidden = true;
      dialog.querySelectorAll('[data-refresh]').forEach((node) => { node.disabled = true; });
      try {
        const data = await api('/api/admin/notice-targets', { signal: lifetime.signal });
        if (!dialog.isConnected || lifetime.signal.aborted) return;
        const season = $('#noticeJumpSeasonInput');
        const selected = loaded ? season.value : item.jump_season_id || '';
        catalog = data;
        loaded = true;
        season.replaceChildren(new Option('请选择赛季', ''));
        catalog.seasons.forEach((entry) => season.add(new Option(entry.name, entry.id)));
        if (selected && !catalog.seasons.some((entry) => entry.id === selected)) {
          const unavailable = new Option(`${selected}（已不可用）`, selected); unavailable.disabled = true; season.add(unavailable);
        }
        season.value = selected;
        renderTools(); update();
      } catch (cause) {
        if (cause.name === 'AbortError' || !dialog.isConnected) return;
        error.textContent = '选项目录加载失败，请点击“刷新选项”或“刷新赛季”重试；已填写的内容会保留。';
        error.hidden = false;
        $('.notice-tool-status').textContent = '暂时无法获取最新工具目录';
      } finally {
        loading = false;
        if (!busy) dialog.querySelectorAll('[data-refresh]').forEach((node) => { node.disabled = false; });
      }
    }
    dialog.querySelectorAll('[data-refresh]').forEach((node) => node.addEventListener('click', refresh));
    window.addEventListener('focus', refresh, { signal: lifetime.signal });
    $('[data-tool-search]').addEventListener('input', renderTools);
    form.addEventListener('input', update);
    form.addEventListener('change', (event) => {
      if (event.target.name === 'target_kind') changeTarget(() => { kind = event.target.value; });
      update();
    });
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (busy) return;
      formError.hidden = true;
      const payload = {
        title: value('#noticeTitleInput'), message: value('#noticeMessageInput'), target_kind: kind,
        tool_id: selectedTool, link_url: kind === 'custom' ? value('#noticeLinkUrlInput') : '',
        link_text: value('#noticeLinkTextInput'),
        jump_season_id: kind === 'lineup' ? value('#noticeJumpSeasonInput') : '',
        jump_tab: kind === 'lineup' ? value('#noticeJumpTabInput') : '',
        marquee_enabled: $('#noticeMarqueeCheckbox').checked ? '1' : '0',
      };
      const publish = event.submitter?.value === 'publish';
      let persisted = false;
      busy = true;
      const controls = [...dialog.querySelectorAll('button, input, textarea, select')];
      controls.forEach((node) => { node.disabled = true; });
      dialog.setAttribute('aria-busy', 'true');
      try {
        const result = await api(savedId ? `/api/admin/notices/${savedId}` : '/api/admin/notices', { method: savedId ? 'PUT' : 'POST', body: JSON.stringify(payload) });
        savedId = result.id;
        persisted = true;
        if (publish) await api(`/api/admin/notices/${savedId}/activate`, { method: 'POST' });
        lifetime.abort(); dialog.close();
        await saved(result, publish);
      } catch (cause) {
        formError.textContent = `${persisted ? '通知已保存，但展示未切换。可重试“保存并展示”。' : ''}${cause.message || '保存失败，请重试'}`;
        formError.hidden = false;
        formError.scrollIntoView({ block: 'nearest' });
      } finally {
        busy = false;
        controls.forEach((node) => { node.disabled = false; });
        dialog.removeAttribute('aria-busy');
      }
    });
    dialog.showModal();
    update(); renderTools(); refresh();
    return () => { lifetime.abort(); if (dialog.open) dialog.close(); };
  }
  window.JccNoticeEditor = Object.freeze({ mount });
})();
