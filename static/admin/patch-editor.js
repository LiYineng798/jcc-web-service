(function (global) {
  const { el, button } = global.JccAdminCore;
  const labels = { draft: '草稿', published: '已发布', hidden: '已下线' };
  function create({ item, template, save, cancel }) {
    const form = el('form', 'patch-editor');
    const header = el('header', 'patch-editor-heading');
    header.append(el('h3', '', item.id ? '编辑公告' : '新建公告'), el('span', 'admin-pill', labels[item.status]));
    const error = el('p', 'patch-editor-error'); error.setAttribute('role', 'alert');
    const grid = el('div', 'patch-editor-grid');
    const editor = el('section', 'patch-editor-fields');
    const preview = el('section', 'patch-editor-preview');
    preview.setAttribute('aria-label', '公告内容预览');
    let busy = false;
    const controls = [];
    const field = (key, title, type = 'text', required = false) => {
      const label = el('label', 'patch-editor-field');
      label.append(el('span', '', title));
      const input = el(type === 'textarea' ? 'textarea' : 'input');
      if (type !== 'textarea') input.type = type;
      else input.rows = key === 'summary_markdown' ? 14 : 8;
      input.name = key; input.value = item[key] || ''; input.required = required;
      input.addEventListener('input', () => { item[key] = input.value; item.dirty = true; updatePreview(); });
      controls.push(input); label.append(input);
      return label;
    };
    const basics = el('div', 'patch-editor-basics');
    basics.append(field('title', '公告标题 *', 'text', true), field('version', '版本号'),
      field('published_at', '发布日期 *', 'date', true), field('source_url', '官方来源链接（可选）'));
    editor.append(basics, el('p', 'admin-meta', '先填写重点内容并检查右侧预览，再保存草稿或发布。草稿和已下线公告不会出现在前台。'));
    const tools = el('div', 'card-actions');
    tools.append(button('追加内容模板', () => {
      item.summary_markdown = (item.summary_markdown || '').trim() + '\n\n' + template;
      item.dirty = true; form.elements.summary_markdown.value = item.summary_markdown; updatePreview();
    }));
    editor.append(tools, field('summary_markdown', '版本重点 *', 'textarea', true),
      el('p', 'admin-meta', '支持：## 分组标题、- [buff] 加强、- [nerf] 削弱、- [adjust] 调整；数值变化用 =>。'));
    const original = el('details', 'patch-editor-original');
    original.append(el('summary', '', '保留官方原文（可选）'), field('original_text', '原文纯文本', 'textarea'));
    editor.append(original); grid.append(editor, preview);
    const actions = el('footer', 'card-actions patch-editor-actions');
    const exit = button('返回列表', () => { if (!busy && (!item.dirty || confirm('有未保存的修改，确定放弃并返回列表？'))) cancel(); });
    const submit = async status => {
      if (busy || !form.reportValidity()) return;
      if (status === 'published' && !confirm('确认发布？保存后所有访客都能看到这条公告。')) return;
      busy = true; error.textContent = '';
      for (const control of [...controls, ...actions.querySelectorAll('button'), ...tools.querySelectorAll('button')]) control.disabled = true;
      try {
        const payload = {};
        for (const key of ['id', 'title', 'version', 'published_at', 'source_url', 'summary_markdown', 'original_text']) payload[key] = item[key];
        await save({ ...payload, status });
      } catch (err) { error.textContent = err.message || '保存失败，内容仍保留，请重试。'; }
      finally {
        busy = false;
        for (const control of [...controls, ...actions.querySelectorAll('button'), ...tools.querySelectorAll('button')]) control.disabled = false;
      }
    };
    actions.append(exit, button('保存草稿', () => submit('draft')),
      button(item.status === 'published' ? '保存并更新发布' : '发布公告', () => submit('published'), 'small-button is-active'));
    if (item.status === 'hidden') actions.append(button('保存并保持下线', () => submit('hidden')));
    form.addEventListener('submit', event => { event.preventDefault(); submit('draft'); });
    form.append(header, grid, error, actions);
    function updatePreview() {
      preview.replaceChildren(el('span', 'admin-meta', '内容预览'), el('h3', '', item.title || '公告标题'),
        el('p', 'admin-meta', `${item.version || '未填写版本'} · ${item.published_at || '未填写日期'}`));
      for (const raw of (item.summary_markdown || '').split('\n')) {
        const line = raw.trim(); if (!line) continue;
        if (line.startsWith('## ')) preview.append(el('h4', '', line.slice(3)));
        else {
          const match = line.match(/^-\s*\[(buff|nerf|adjust)\]\s*(.+)$/);
          const p = el('p');
          if (match) {
            p.append(el('strong', `patch-change-${match[1]}`, { buff: '加强 · ', nerf: '削弱 · ', adjust: '调整 · ' }[match[1]]),
              document.createTextNode(match[2].replace(/\s*=>\s*/, ' → ')));
          } else p.textContent = line;
          preview.append(p);
        }
      }
    }
    updatePreview(); return form;
  }
  global.JccPatchEditor = { create, labels };
})(window);
