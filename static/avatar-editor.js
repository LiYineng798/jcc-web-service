(() => {
  let activeCleanup = null;

  function mount(user, csrfToken, options = {}) {
    activeCleanup?.();
    const avatar = window.jccAvatar;
    let saved = avatar.normalize(user.avatar_config || user.avatar_color);
    let draft = { ...saved };
    let busy = false;
    let disposed = false;
    const request = new AbortController();
    const sameConfig = (a, b) => a.preset === b.preset && a.expression === b.expression && a.color === b.color;
    const section = document.createElement('section');
    section.className = 'avatar-account panel';
    section.id = 'avatar';
    section.innerHTML = `<div class="avatar-account-identity"><div class="avatar-saved"></div><div><p class="section-kicker">我的形象</p><h2 class="avatar-nickname"></h2><p class="avatar-caption">选一个形象，配上你的心情色彩</p></div></div><button type="button" class="small-button avatar-edit">调整头像</button>`;
    section.querySelector('.avatar-nickname').textContent = user.nickname || user.username;
    const savedPreview = section.querySelector('.avatar-saved');
    savedPreview.append(avatar.image(saved, 80, '我的头像'));
    if (!options.trigger) {
      const shell = document.querySelector('.account-page-shell');
      const panel = shell?.querySelector(':scope > .panel');
      if (panel) panel.before(section);
      else shell?.prepend(section);
    }

    const dialog = document.createElement('dialog');
    dialog.className = 'avatar-dialog';
    dialog.setAttribute('aria-labelledby', 'avatarEditorTitle');
    dialog.innerHTML = `<form class="avatar-editor" novalidate>
      <header class="avatar-editor-head"><h2 id="avatarEditorTitle">调整头像</h2><div><button type="button" class="avatar-random small-button">随机组合</button><button type="button" class="avatar-close" aria-label="关闭头像编辑">×</button></div></header>
      <div class="avatar-editor-body">
        <div class="avatar-preview-stage"><div id="avatarLargePreview"></div><div class="avatar-preview-summary"><p class="avatar-preview-name"></p><div class="avatar-preview-actions" role="group" aria-label="体验头像互动"><button type="button" class="small-button" data-avatar-feedback="copy">试试复制</button><button type="button" class="small-button" data-avatar-feedback="like">试试点赞</button><button type="button" class="small-button" data-avatar-feedback="favorite">试试收藏</button></div><span class="avatar-preview-hint">仅预览动效，不会执行操作</span></div><div class="avatar-size-preview" aria-label="首页实际尺寸预览"><span class="avatar-card-sample"></span><span class="avatar-card-sample-name"></span><span class="avatar-card-sample-label">首页显示</span></div></div>
        <div class="avatar-controls">
          <div class="avatar-tabs" role="tablist" aria-label="头像设置">
            <button type="button" role="tab" id="avatarTabShape" aria-controls="avatarPanelShape" aria-selected="true" data-avatar-tab="shape">形象</button>
            <button type="button" role="tab" id="avatarTabExpression" aria-controls="avatarPanelExpression" aria-selected="false" tabindex="-1" data-avatar-tab="expression">表情</button>
            <button type="button" role="tab" id="avatarTabColor" aria-controls="avatarPanelColor" aria-selected="false" tabindex="-1" data-avatar-tab="color">配色</button>
          </div>
          <div class="avatar-panel-scroll">
            <section id="avatarPanelShape" role="tabpanel" aria-labelledby="avatarTabShape" data-avatar-panel="shape"><h3 id="avatarPresetLabel">选择喜欢的形象</h3><div class="avatar-choices avatar-presets" role="group" aria-labelledby="avatarPresetLabel"></div></section>
            <section id="avatarPanelExpression" role="tabpanel" aria-labelledby="avatarTabExpression" data-avatar-panel="expression" hidden><h3 id="avatarExpressionLabel">选择日常表情</h3><div class="avatar-choices avatar-expressions" role="group" aria-labelledby="avatarExpressionLabel"></div></section>
            <section id="avatarPanelColor" role="tabpanel" aria-labelledby="avatarTabColor" data-avatar-panel="color" hidden><h3 id="avatarRecommendedLabel">适合这个形象</h3><div class="avatar-recommendations" role="group" aria-labelledby="avatarRecommendedLabel"></div><h3>全部配色</h3><div class="avatar-swatches" role="group" aria-label="全部配色"></div>
              <label class="avatar-color-label" for="avatarHex">自定义颜色</label><div class="avatar-color-inputs"><input id="avatarColor" type="color" aria-label="选择头像颜色"><input id="avatarHex" type="text" aria-label="头像十六进制颜色" maxlength="7" pattern="#[0-9a-fA-F]{6}" required spellcheck="false" autocapitalize="off" autocomplete="off" aria-describedby="avatarFeedback"></div><p class="avatar-caption">也可以输入你喜欢的六位 HEX 颜色。</p></section>
          </div>
        </div>
      </div>
      <footer class="avatar-editor-footer"><p id="avatarFeedback" role="status" aria-live="polite"></p><div><button type="button" class="small-button avatar-cancel">取消</button><button type="submit" class="small-button avatar-save">保存头像</button></div></footer>
    </form>`;
    document.body.append(dialog);
    const form = dialog.querySelector('form');
    const picker = dialog.querySelector('#avatarColor');
    const hex = dialog.querySelector('#avatarHex');
    const feedback = dialog.querySelector('#avatarFeedback');
    const save = dialog.querySelector('.avatar-save');
    const largePreview = dialog.querySelector('#avatarLargePreview');
    const cardPreview = dialog.querySelector('.avatar-card-sample');
    dialog.querySelector('.avatar-card-sample-name').textContent = user.nickname || user.username;
    const palettes = Object.values(avatar.palettes);
    const presets = Object.entries(avatar.presets);
    const expressions = Object.entries(avatar.expressions);
    const tabs = [...dialog.querySelectorAll('[data-avatar-tab]')];
    const panelScroll = dialog.querySelector('.avatar-panel-scroll');
    function selectTab(name, focus = false) {
      if (busy) return;
      tabs.forEach(tab => {
        const selected = tab.dataset.avatarTab === name;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        if (selected && focus) tab.focus();
      });
      dialog.querySelectorAll('[data-avatar-panel]').forEach(panel => { panel.hidden = panel.dataset.avatarPanel !== name; });
      panelScroll.scrollTop = 0;
    }
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => selectTab(tab.dataset.avatarTab));
      tab.addEventListener('keydown', event => {
        const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
        if (next < 0) return;
        event.preventDefault();
        selectTab(tabs[next].dataset.avatarTab, true);
      });
    });
    const fitViewport = () => {
      const viewport = window.visualViewport;
      const height = viewport?.height || window.innerHeight;
      dialog.style.setProperty('--avatar-available-height', `${Math.max(160, height - 16)}px`);
      dialog.style.setProperty('--avatar-viewport-top', `${(viewport?.offsetTop || 0) + 8}px`);
      dialog.classList.toggle('avatar-compact', height < 560);
    };
    window.visualViewport?.addEventListener('resize', fitViewport);
    window.visualViewport?.addEventListener('scroll', fitViewport);
    window.addEventListener('resize', fitViewport);

    function choices(entries, field, selector) {
      return entries.map(([value, definition]) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'avatar-choice';
        button.setAttribute('aria-label', definition.name);
        const thumbnail = document.createElement('span');
        thumbnail.className = 'avatar-choice-thumbnail';
        thumbnail.setAttribute('aria-hidden', 'true');
        const label = document.createElement('span');
        label.textContent = definition.name.split(' · ')[0];
        button.title = definition.name;
        button.append(thumbnail, label);
        button.addEventListener('click', () => update({ ...draft, [field]: value }));
        dialog.querySelector(selector).append(button);
        return { button, thumbnail, value };
      });
    }
    const presetChoices = choices(presets, 'preset', '.avatar-presets');
    const expressionChoices = choices(expressions, 'expression', '.avatar-expressions');
    const recommendations = Array.from({ length: 3 }, () => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'avatar-choice avatar-recommendation';
      const thumbnail = document.createElement('span');
      thumbnail.className = 'avatar-choice-thumbnail';
      thumbnail.setAttribute('aria-hidden', 'true');
      const label = document.createElement('span');
      button.append(thumbnail, label);
      button.addEventListener('click', () => update({ ...draft, color: button.dataset.color }));
      dialog.querySelector('.avatar-recommendations').append(button);
      return { button, thumbnail, label };
    });
    const swatches = palettes.map(palette => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'avatar-swatch';
      button.style.setProperty('--swatch', palette.mid);
      button.setAttribute('aria-label', palette.name);
      button.title = palette.name;
      button.addEventListener('click', () => update({ ...draft, color: palette.mid }));
      dialog.querySelector('.avatar-swatches').append(button);
      return button;
    });

    function update(config) {
      draft = avatar.normalize(config);
      picker.value = draft.color;
      hex.value = draft.color;
      hex.setCustomValidity('');
      hex.removeAttribute('aria-invalid');
      feedback.textContent = sameConfig(draft, saved) ? '当前头像' : '预览中 · 尚未保存';
      avatar.dispose(largePreview);
      avatar.dispose(cardPreview);
      largePreview.replaceChildren(avatar.image(draft, 176, '头像实时预览'));
      dialog.querySelector('.avatar-preview-name').textContent = `${avatar.presets[draft.preset].name} · ${avatar.expressions[draft.expression].name}`;
      cardPreview.replaceChildren(avatar.image(draft, 28));
      recommendations.forEach(({ button, thumbnail, label }, index) => {
        const palette = avatar.palettes[avatar.presets[draft.preset].recommended[index]];
        button.dataset.color = palette.mid;
        button.setAttribute('aria-label', `推荐配色：${palette.name}`);
        button.setAttribute('aria-pressed', String(palette.mid === draft.color));
        label.textContent = palette.name;
        thumbnail.replaceChildren(avatar.image({ ...draft, color: palette.mid }, 32));
      });
      presetChoices.forEach(({ button, thumbnail, value }) => {
        button.setAttribute('aria-pressed', String(value === draft.preset));
        thumbnail.replaceChildren(avatar.image({ ...draft, preset: value }, 40));
      });
      expressionChoices.forEach(({ button, thumbnail, value }) => {
        button.setAttribute('aria-pressed', String(value === draft.expression));
        thumbnail.replaceChildren(avatar.image({ ...draft, expression: value }, 36));
      });
      swatches.forEach((button, index) => button.setAttribute('aria-pressed', String(palettes[index].mid.toLowerCase() === draft.color)));
      save.disabled = busy || sameConfig(draft, saved);
    }
    picker.addEventListener('input', () => update({ ...draft, color: picker.value }));
    hex.addEventListener('input', () => {
      if (/^#[0-9a-f]{6}$/i.test(hex.value)) update({ ...draft, color: hex.value });
      else {
        hex.setCustomValidity('请输入 # 加六位十六进制颜色');
        hex.setAttribute('aria-invalid', 'true');
        save.disabled = true;
        feedback.textContent = '请输入完整颜色，例如 #7c3aed';
      }
    });
    dialog.querySelector('.avatar-random').addEventListener('click', () => {
      const pick = values => values[Math.floor(Math.random() * values.length)];
      const preset = pick(presets)[0];
      const color = avatar.palettes[pick(avatar.presets[preset].recommended)].mid;
      let next = { ...draft, preset, expression: pick(expressions)[0], color };
      if (sameConfig(next, draft)) next = { ...next, expression: expressions[(expressions.findIndex(([key]) => key === draft.expression) + 1) % expressions.length][0] };
      update(next);
    });
    dialog.querySelectorAll('[data-avatar-feedback]').forEach(button => {
      button.addEventListener('click', () => {
        avatar.feedback(largePreview.querySelector('.user-avatar'), button.dataset.avatarFeedback);
        avatar.feedback(cardPreview.querySelector('.user-avatar'), button.dataset.avatarFeedback);
      });
    });
    function close() { if (!busy) dialog.close(); }
    dialog.querySelector('.avatar-close').addEventListener('click', close);
    dialog.querySelector('.avatar-cancel').addEventListener('click', close);
    dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
    dialog.addEventListener('close', () => { if (!disposed) update(saved); });
    const trigger = options.trigger || section.querySelector('.avatar-edit');
    const openEditor = () => {
      if (busy || dialog.open) return;
      update(saved);
      selectTab('shape');
      fitViewport();
      dialog.showModal();
    };
    trigger.addEventListener('click', openEditor);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (busy || sameConfig(draft, saved)) return;
      if (!hex.validity.valid) selectTab('color');
      if (!form.reportValidity()) return;
      busy = true;
      const controls = [...form.querySelectorAll('button, input')];
      controls.forEach(control => { control.disabled = true; });
      form.setAttribute('aria-busy', 'true');
      feedback.textContent = '正在保存…';
      let savedUser;
      try {
        const response = await fetch(options.endpoint || '/api/me/avatar', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
          body: JSON.stringify({ color: draft.color, preset: draft.preset, expression: draft.expression }),
          signal: request.signal,
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || '保存失败，请重试');
        if (disposed) return;
        savedUser = payload.user;
        saved = avatar.normalize(savedUser.avatar_config || savedUser.avatar_color);
        savedPreview.replaceChildren(avatar.image(saved, 80, '我的头像'));
        section.querySelector('.avatar-caption').textContent = '头像已更新，新的形象已同步';
        dialog.close();
      } catch (error) {
        if (!disposed && error.name !== 'AbortError') window.jccNotify.inline(feedback, error.message || '网络异常，请重试');
      } finally {
        busy = false;
        controls.forEach(control => { control.disabled = false; });
        form.removeAttribute('aria-busy');
        save.disabled = sameConfig(draft, saved) || !hex.validity.valid;
      }
      if (savedUser && !disposed) {
        options.onSave?.(savedUser);
        window.jccNotify.show('头像已更新，新的形象已同步', { variant: 'success' });
      }
    });
    const cleanup = () => {
      disposed = true;
      request.abort();
      trigger.removeEventListener('click', openEditor);
      window.visualViewport?.removeEventListener('resize', fitViewport);
      window.visualViewport?.removeEventListener('scroll', fitViewport);
      window.removeEventListener('resize', fitViewport);
      avatar.dispose(dialog);
      dialog.remove();
      section.remove();
      if (activeCleanup === cleanup) activeCleanup = null;
    };
    activeCleanup = cleanup;
    if (location.hash === '#avatar') openEditor();
    return cleanup;
  }
  window.jccAvatarEditor = { mount };
})();
