/* Admin toolbox lifecycle manager: grouped display, intra/cross-group & group drag-and-drop. */
(function (global) {
  const { el } = global.JccAdminCore;

  const FILTERS = [
    ['all', '全部'],
    ['visible', '公开'],
    ['unlisted', '仅直链'],
    ['disabled', '已下线'],
  ];

  const STATUSES = [
    ['visible', '公开'],
    ['unlisted', '仅直链'],
    ['disabled', '下线'],
  ];

  const PATHS = {
    grip: 'M9 6h.01M9 12h.01M9 18h.01M15 6h.01M15 12h.01M15 18h.01',
    up: 'm18 15-6-6-6 6',
    down: 'm6 9 6 6 6-6',
    edit: 'M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z',
    open: 'M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6',
    close: 'M18 6 6 18M6 6l12 12',
    check: 'M20 6 9 17l-5-5',
  };

  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', PATHS[name]);
    svg.append(path);
    return svg;
  }

  function create({ api, render, notify }) {
    let items = [];
    let counts = { all: 0, visible: 0, unlisted: 0, disabled: 0 };
    let emptyGroups = [];
    let filter = 'all';
    let query = '';
    let loading = false;
    let error = '';
    let editingId = null;
    let draft = null;
    let groupMenuOpen = false;
    let busyId = null;
    let reordering = false;
    let creatingGroup = false;
    let newGroupName = '';
    let dragState = null; // { kind: 'item', id } | { kind: 'group', name }

    document.addEventListener('click', (event) => {
      if (!groupMenuOpen) return;
      if (!event.target.closest?.('.tbx-select')) {
        groupMenuOpen = false;
        render();
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && groupMenuOpen) {
        groupMenuOpen = false;
        render();
      }
    });

    function recomputeCounts() {
      counts = {
        all: items.length,
        visible: items.filter((item) => item.status === 'visible').length,
        unlisted: items.filter((item) => item.status === 'unlisted').length,
        disabled: items.filter((item) => item.status === 'disabled').length,
      };
    }

    function syncEmptyGroups() {
      const populated = new Set(items.map((item) => item.group || ''));
      emptyGroups = emptyGroups.filter((name) => !populated.has(name));
    }

    async function load() {
      loading = true;
      error = '';
      render();
      try {
        const result = await api('/api/admin/toolbox');
        items = Array.isArray(result.items) ? result.items : [];
        recomputeCounts();
        syncEmptyGroups();
      } catch (err) {
        error = err.message || '加载失败';
      } finally {
        loading = false;
        render();
      }
    }

    function buildGroups(sourceItems, includeEmpty) {
      const order = [];
      const byName = new Map();
      for (const item of sourceItems) {
        const name = item.group || '';
        if (!byName.has(name)) {
          byName.set(name, []);
          order.push(name);
        }
        byName.get(name).push(item);
      }
      if (includeEmpty) {
        for (const name of emptyGroups) {
          if (!byName.has(name)) {
            byName.set(name, []);
            order.push(name);
          }
        }
      }
      return order.map((name) => ({ name, items: byName.get(name) }));
    }

    function selectableGroupNames() {
      const names = buildGroups(items, true).map((group) => group.name);
      const result = [''];
      for (const name of names) {
        if (name && !result.includes(name)) result.push(name);
      }
      if (draft && draft.group && !result.includes(draft.group)) {
        result.push(draft.group);
      }
      return result;
    }

    function filteredItems() {
      const term = query.trim().toLowerCase();
      return items.filter((item) => {
        if (filter !== 'all' && item.status !== filter) return false;
        if (!term) return true;
        return `${item.title} ${item.group} ${item.description} ${item.id}`.toLowerCase().includes(term);
      });
    }

    async function persistGroups(groups) {
      if (reordering) return;
      const flattened = [];
      const nextEmpty = [];
      for (const group of groups) {
        if (!group.items.length) {
          nextEmpty.push(group.name);
          continue;
        }
        for (const item of group.items) {
          flattened.push({ ...item, group: group.name });
        }
      }
      const prevItems = items;
      const prevEmpty = emptyGroups;
      items = flattened;
      emptyGroups = nextEmpty;
      recomputeCounts();
      reordering = true;
      render();
      try {
        const result = await api('/api/admin/toolbox/reorder', {
          method: 'POST',
          body: JSON.stringify({
            items: flattened.map((item) => ({ id: item.id, group: item.group })),
          }),
        });
        if (Array.isArray(result.items)) {
          items = result.items;
          recomputeCounts();
          syncEmptyGroups();
        }
      } catch (err) {
        items = prevItems;
        emptyGroups = prevEmpty;
        recomputeCounts();
        notify(err.message || '排序保存失败', 'error');
      } finally {
        reordering = false;
        render();
      }
    }

    function moveItem(sourceId, targetGroupName, targetItemId, position) {
      const groups = buildGroups(items, true).map((g) => ({ name: g.name, items: [...g.items] }));
      let moved = null;
      for (const group of groups) {
        const idx = group.items.findIndex((i) => i.id === sourceId);
        if (idx >= 0) {
          [moved] = group.items.splice(idx, 1);
          break;
        }
      }
      if (!moved) return;
      moved.group = targetGroupName;

      let targetGroup = groups.find((g) => g.name === targetGroupName);
      if (!targetGroup) {
        targetGroup = { name: targetGroupName, items: [] };
        groups.push(targetGroup);
      }

      if (targetItemId) {
        const targetIdx = targetGroup.items.findIndex((i) => i.id === targetItemId);
        if (targetIdx >= 0) {
          const insertAt = position === 'after' ? targetIdx + 1 : targetIdx;
          targetGroup.items.splice(insertAt, 0, moved);
        } else {
          targetGroup.items.push(moved);
        }
      } else {
        targetGroup.items.push(moved);
      }
      persistGroups(groups);
    }

    function moveItemStep(groupName, toolId, delta) {
      const groups = buildGroups(items, true).map((g) => ({ name: g.name, items: [...g.items] }));
      const group = groups.find((g) => g.name === groupName);
      if (!group) return;
      const idx = group.items.findIndex((i) => i.id === toolId);
      const nextIdx = idx + delta;
      if (idx < 0 || nextIdx < 0 || nextIdx >= group.items.length) return;
      const [moved] = group.items.splice(idx, 1);
      group.items.splice(nextIdx, 0, moved);
      persistGroups(groups);
    }

    function moveGroup(sourceName, targetName, position) {
      if (sourceName === targetName) return;
      const groups = buildGroups(items, true).map((g) => ({ name: g.name, items: [...g.items] }));
      const from = groups.findIndex((g) => g.name === sourceName);
      if (from < 0) return;
      const [moved] = groups.splice(from, 1);
      const to = groups.findIndex((g) => g.name === targetName);
      if (to < 0) return;
      const insertAt = position === 'after' ? to + 1 : to;
      groups.splice(insertAt, 0, moved);
      persistGroups(groups);
    }

    function moveGroupStep(groupName, delta) {
      const groups = buildGroups(items, true).map((g) => ({ name: g.name, items: [...g.items] }));
      const idx = groups.findIndex((g) => g.name === groupName);
      const nextIdx = idx + delta;
      if (idx < 0 || nextIdx < 0 || nextIdx >= groups.length) return;
      const [moved] = groups.splice(idx, 1);
      groups.splice(nextIdx, 0, moved);
      persistGroups(groups);
    }

    function createGroup(name) {
      const trimmed = name.trim();
      if (trimmed.length > 40) {
        notify('分组名不能超过 40 字', 'error');
        return;
      }
      const existing = buildGroups(items, true).map((group) => group.name);
      if (!existing.includes(trimmed)) {
        emptyGroups = [...emptyGroups, trimmed];
      }
      creatingGroup = false;
      newGroupName = '';
      filter = 'all';
      query = '';
      render();
    }

    function removeEmptyGroup(name) {
      emptyGroups = emptyGroups.filter((g) => g !== name);
      render();
    }

    async function setStatus(item, nextStatus) {
      if (busyId || item.status === nextStatus) return;
      const previous = item.status;
      item.status = nextStatus;
      recomputeCounts();
      busyId = item.id;
      render();
      try {
        const result = await api(`/api/admin/toolbox/${encodeURIComponent(item.id)}`, {
          method: 'PATCH',
          body: JSON.stringify({ status: nextStatus }),
        });
        if (result.item) {
          items = items.map((row) => (row.id === item.id ? result.item : row));
          recomputeCounts();
        }
      } catch (err) {
        item.status = previous;
        recomputeCounts();
        notify(err.message || '状态更新失败', 'error');
      } finally {
        busyId = null;
        render();
      }
    }

    async function saveDraft(item) {
      if (busyId || !draft) return;
      const title = draft.title.trim();
      if (!title) {
        notify('请输入标题', 'error');
        return;
      }
      busyId = item.id;
      groupMenuOpen = false;
      render();
      try {
        const result = await api(`/api/admin/toolbox/${encodeURIComponent(item.id)}`, {
          method: 'PATCH',
          body: JSON.stringify({
            title,
            group: draft.group.trim(),
            description: draft.description.trim(),
          }),
        });
        if (result.item) {
          items = items.map((row) => (row.id === item.id ? result.item : row));
          recomputeCounts();
          syncEmptyGroups();
        }
        editingId = null;
        draft = null;
        notify('已保存');
      } catch (err) {
        notify(err.message || '保存失败', 'error');
      } finally {
        busyId = null;
        render();
      }
    }

    async function resetItem(item) {
      if (busyId) return;
      busyId = item.id;
      groupMenuOpen = false;
      render();
      try {
        const result = await api(`/api/admin/toolbox/${encodeURIComponent(item.id)}/reset`, {
          method: 'POST',
        });
        if (result.item) {
          items = items.map((row) => (row.id === item.id ? result.item : row));
          items.sort((a, b) => a.sort_order - b.sort_order);
          recomputeCounts();
          syncEmptyGroups();
        }
        editingId = null;
        draft = null;
        notify('已恢复默认');
      } catch (err) {
        notify(err.message || '重置失败', 'error');
      } finally {
        busyId = null;
        render();
      }
    }

    function openEditor(item) {
      groupMenuOpen = false;
      if (editingId === item.id) {
        editingId = null;
        draft = null;
      } else {
        editingId = item.id;
        draft = {
          title: item.title,
          group: item.group || '',
          description: item.description || '',
        };
      }
      render();
    }

    function renderGroupSelect(item) {
      const box = el('div', 'tbx-select');
      const triggerId = `tbx-group-${item.id}`;
      const trigger = el('button', 'tbx-select-trigger');
      trigger.id = triggerId;
      trigger.type = 'button';
      trigger.setAttribute('aria-haspopup', 'listbox');
      trigger.setAttribute('aria-expanded', String(groupMenuOpen));

      const valueSpan = el('span', `tbx-select-value${draft.group ? '' : ' is-blank'}`, draft.group || '未分组');
      const chevron = icon('down');
      chevron.classList.add('tbx-select-chevron');
      trigger.append(valueSpan, chevron);
      trigger.addEventListener('click', (event) => {
        event.stopPropagation();
        groupMenuOpen = !groupMenuOpen;
        render();
      });
      box.append(trigger);

      if (groupMenuOpen) {
        const menu = el('div', 'tbx-select-menu');
        menu.setAttribute('role', 'listbox');
        menu.setAttribute('aria-labelledby', triggerId);
        for (const name of selectableGroupNames()) {
          const selected = draft.group === name;
          const option = el(
            'button',
            `tbx-select-option${selected ? ' is-selected' : ''}${name ? '' : ' is-blank'}`
          );
          option.type = 'button';
          option.setAttribute('role', 'option');
          option.setAttribute('aria-selected', String(selected));
          option.append(el('span', '', name || '未分组'));
          if (selected) option.append(icon('check'));
          option.addEventListener('click', (event) => {
            event.stopPropagation();
            draft.group = name;
            groupMenuOpen = false;
            render();
          });
          menu.append(option);
        }
        box.append(menu);
      }

      return box;
    }

    function renderEditor(item) {
      const form = el('form', 'tbx-editor');
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        saveDraft(item);
      });

      const grid = el('div', 'tbx-editor-grid');

      const titleField = el('div', 'tbx-field');
      const titleId = `tbx-title-${item.id}`;
      const titleLabel = el('label', '', '标题');
      titleLabel.htmlFor = titleId;
      const titleInput = el('input');
      titleInput.id = titleId;
      titleInput.maxLength = 80;
      titleInput.required = true;
      titleInput.value = draft.title;
      titleInput.addEventListener('input', (e) => { draft.title = e.target.value; });
      titleField.append(titleLabel, titleInput);

      const groupField = el('div', 'tbx-field');
      const groupLabel = el('label', '', '分组');
      groupLabel.htmlFor = `tbx-group-${item.id}`;
      groupField.append(groupLabel, renderGroupSelect(item));

      const descField = el('div', 'tbx-field is-full');
      const descId = `tbx-desc-${item.id}`;
      const descLabel = el('label', '', '简介');
      descLabel.htmlFor = descId;
      const descInput = el('input');
      descInput.id = descId;
      descInput.maxLength = 160;
      descInput.value = draft.description;
      descInput.addEventListener('input', (e) => { draft.description = e.target.value; });
      descField.append(descLabel, descInput);

      grid.append(titleField, groupField, descField);

      const foot = el('div', 'tbx-editor-foot');
      const resetBtn = el('button', 'tbx-btn is-ghost', '恢复默认');
      resetBtn.type = 'button';
      resetBtn.disabled = !item.customized || busyId === item.id;
      resetBtn.addEventListener('click', () => resetItem(item));

      const right = el('div', 'tbx-editor-foot-right');
      const cancelBtn = el('button', 'tbx-btn', '取消');
      cancelBtn.type = 'button';
      cancelBtn.addEventListener('click', () => {
        editingId = null;
        draft = null;
        groupMenuOpen = false;
        render();
      });

      const saveBtn = el('button', 'tbx-btn is-primary', busyId === item.id ? '保存中' : '保存');
      saveBtn.type = 'submit';
      saveBtn.disabled = busyId === item.id;

      right.append(cancelBtn, saveBtn);
      foot.append(resetBtn, right);
      form.append(grid, foot);
      return form;
    }

    function renderItem(item, index, groupItems, groupName, allowReorder) {
      const wrap = el('div', 'tbx-item');
      wrap.dataset.toolId = item.id;
      wrap.dataset.toolStatus = item.status;

      if (allowReorder) {
        wrap.draggable = editingId !== item.id;
        wrap.addEventListener('dragstart', (event) => {
          if (editingId === item.id) {
            event.preventDefault();
            return;
          }
          event.stopPropagation();
          dragState = { kind: 'item', id: item.id };
          wrap.classList.add('is-dragging');
          event.dataTransfer?.setData('text/plain', `item:${item.id}`);
        });
        wrap.addEventListener('dragend', () => {
          dragState = null;
          wrap.classList.remove('is-dragging', 'is-drop-before', 'is-drop-after');
        });
        wrap.addEventListener('dragover', (event) => {
          if (!dragState || dragState.kind !== 'item' || dragState.id === item.id) return;
          event.preventDefault();
          event.stopPropagation();
          const rect = wrap.getBoundingClientRect();
          const after = event.clientY > rect.top + rect.height / 2;
          wrap.classList.toggle('is-drop-before', !after);
          wrap.classList.toggle('is-drop-after', after);
        });
        wrap.addEventListener('dragleave', () => {
          wrap.classList.remove('is-drop-before', 'is-drop-after');
        });
        wrap.addEventListener('drop', (event) => {
          if (!dragState || dragState.kind !== 'item' || dragState.id === item.id) return;
          event.preventDefault();
          event.stopPropagation();
          const rect = wrap.getBoundingClientRect();
          const position = event.clientY > rect.top + rect.height / 2 ? 'after' : 'before';
          wrap.classList.remove('is-drop-before', 'is-drop-after');
          const sourceId = dragState.id;
          dragState = null;
          moveItem(sourceId, groupName, item.id, position);
        });
      }

      const row = el('div', 'tbx-row');

      const grip = el('span', `tbx-drag${allowReorder ? '' : ' is-hidden'}`);
      grip.title = '拖动排序或移至其他分组';
      grip.append(icon('grip'));

      const info = el('div', 'tbx-info');
      info.append(el('span', 'tbx-title', item.title));
      if (item.description) info.append(el('p', 'tbx-desc', item.description));

      const actions = el('div', 'tbx-actions');
      if (allowReorder && groupItems.length > 1) {
        const moves = el('div', 'tbx-row-moves');
        const upBtn = el('button', 'tbx-move');
        upBtn.type = 'button';
        upBtn.ariaLabel = `上移 ${item.title}`;
        upBtn.disabled = index === 0 || reordering;
        upBtn.append(icon('up'));
        upBtn.addEventListener('click', () => moveItemStep(groupName, item.id, -1));

        const downBtn = el('button', 'tbx-move');
        downBtn.type = 'button';
        downBtn.ariaLabel = `下移 ${item.title}`;
        downBtn.disabled = index === groupItems.length - 1 || reordering;
        downBtn.append(icon('down'));
        downBtn.addEventListener('click', () => moveItemStep(groupName, item.id, 1));

        moves.append(upBtn, downBtn);
        actions.append(moves);
      }

      const segment = el('div', 'tbx-segment');
      segment.setAttribute('role', 'radiogroup');
      segment.setAttribute('aria-label', `${item.title} 状态`);

      for (const [value, label] of STATUSES) {
        const btn = el('button', 'tbx-seg-btn');
        btn.type = 'button';
        btn.setAttribute('role', 'radio');
        btn.setAttribute('aria-checked', String(item.status === value));
        btn.disabled = busyId === item.id;
        if (item.status === value) btn.append(el('span', `tbx-dot is-${value}`));
        btn.append(document.createTextNode(label));
        btn.addEventListener('click', () => setStatus(item, value));
        segment.append(btn);
      }

      const editBtn = el('button', `tbx-icon-btn${editingId === item.id ? ' is-active' : ''}`);
      editBtn.type = 'button';
      editBtn.ariaLabel = `编辑 ${item.title}`;
      editBtn.title = '编辑';
      editBtn.append(icon('edit'));
      editBtn.addEventListener('click', () => openEditor(item));

      const openLink = el('a', 'tbx-icon-btn');
      openLink.href = item.status === 'disabled' ? `${item.url}?preview=1` : item.url;
      openLink.target = '_blank';
      openLink.rel = 'noopener';
      openLink.ariaLabel = `打开 ${item.title}`;
      openLink.title = item.status === 'disabled' ? '预览' : '打开';
      openLink.append(icon('open'));

      actions.append(segment, editBtn, openLink);
      row.append(grip, info, actions);
      wrap.append(row);

      if (editingId === item.id && draft) {
        wrap.append(renderEditor(item));
      }
      return wrap;
    }

    function renderGroupCard(group, index, allGroups, allowReorder) {
      const card = el('section', 'tbx-group-card');
      card.dataset.groupName = group.name;

      if (allowReorder) {
        card.addEventListener('dragover', (event) => {
          if (!dragState) return;
          if (dragState.kind === 'group' && dragState.name !== group.name) {
            event.preventDefault();
            const rect = card.getBoundingClientRect();
            const after = event.clientY > rect.top + rect.height / 2;
            card.classList.toggle('is-drop-before', !after);
            card.classList.toggle('is-drop-after', after);
          } else if (dragState.kind === 'item') {
            event.preventDefault();
            card.classList.add('is-item-drop-target');
          }
        });
        card.addEventListener('dragleave', (event) => {
          if (card.contains(event.relatedTarget)) return;
          card.classList.remove('is-drop-before', 'is-drop-after', 'is-item-drop-target');
        });
        card.addEventListener('drop', (event) => {
          if (!dragState) return;
          event.preventDefault();
          card.classList.remove('is-drop-before', 'is-drop-after', 'is-item-drop-target');
          if (dragState.kind === 'group' && dragState.name !== group.name) {
            const rect = card.getBoundingClientRect();
            const position = event.clientY > rect.top + rect.height / 2 ? 'after' : 'before';
            const sourceName = dragState.name;
            dragState = null;
            moveGroup(sourceName, group.name, position);
          } else if (dragState.kind === 'item') {
            const sourceId = dragState.id;
            dragState = null;
            moveItem(sourceId, group.name, null, 'after');
          }
        });
      }

      const head = el('header', 'tbx-group-head');
      if (allowReorder) {
        head.draggable = true;
        head.addEventListener('dragstart', (event) => {
          dragState = { kind: 'group', name: group.name };
          card.classList.add('is-dragging');
          event.dataTransfer?.setData('text/plain', `group:${group.name}`);
        });
        head.addEventListener('dragend', () => {
          dragState = null;
          card.classList.remove('is-dragging', 'is-drop-before', 'is-drop-after');
        });
      }

      const grip = el('span', `tbx-drag${allowReorder ? '' : ' is-hidden'}`);
      grip.title = '拖动调整分组顺序';
      grip.append(icon('grip'));

      const titleWrap = el('div', 'tbx-group-head-title');
      const titleText = group.name || '未分组';
      titleWrap.append(
        el('span', `tbx-group-title${group.name ? '' : ' is-blank'}`, titleText),
        el('span', 'tbx-group-count', String(group.items.length))
      );

      const headActions = el('div', 'tbx-group-head-actions');
      if (allowReorder) {
        const upBtn = el('button', 'tbx-move');
        upBtn.type = 'button';
        upBtn.ariaLabel = `上移分组 ${titleText}`;
        upBtn.disabled = index === 0 || reordering;
        upBtn.append(icon('up'));
        upBtn.addEventListener('click', () => moveGroupStep(group.name, -1));

        const downBtn = el('button', 'tbx-move');
        downBtn.type = 'button';
        downBtn.ariaLabel = `下移分组 ${titleText}`;
        downBtn.disabled = index === allGroups.length - 1 || reordering;
        downBtn.append(icon('down'));
        downBtn.addEventListener('click', () => moveGroupStep(group.name, 1));

        headActions.append(upBtn, downBtn);
      }
      if (!group.items.length) {
        const removeBtn = el('button', 'tbx-move');
        removeBtn.type = 'button';
        removeBtn.ariaLabel = `移除空分组 ${titleText}`;
        removeBtn.title = '移除空分组';
        removeBtn.append(icon('close'));
        removeBtn.addEventListener('click', () => removeEmptyGroup(group.name));
        headActions.append(removeBtn);
      }

      head.append(grip, titleWrap, headActions);

      const body = el('div', 'tbx-group-body');
      if (!group.items.length) {
        body.append(el('div', 'tbx-group-empty', '空分组'));
      } else {
        group.items.forEach((item, itemIdx) => {
          body.append(renderItem(item, itemIdx, group.items, group.name, allowReorder));
        });
      }

      card.append(head, body);
      return card;
    }

    function view() {
      const shell = el('section', 'tbx-shell');
      shell.setAttribute('aria-label', '工具箱管理');

      const bar = el('div', 'tbx-bar');
      const filterGroup = el('div', 'tbx-filters');
      filterGroup.setAttribute('role', 'tablist');
      for (const [key, label] of FILTERS) {
        const btn = el('button', `tbx-filter${filter === key ? ' is-active' : ''}`);
        btn.type = 'button';
        btn.setAttribute('role', 'tab');
        btn.setAttribute('aria-selected', String(filter === key));
        btn.append(document.createTextNode(label), el('span', 'tbx-filter-count', String(counts[key] ?? 0)));
        btn.addEventListener('click', () => {
          filter = key;
          render();
        });
        filterGroup.append(btn);
      }

      const barRight = el('div', 'tbx-bar-right');
      const search = el('input', 'tbx-search');
      search.type = 'search';
      search.placeholder = '筛选工具';
      search.setAttribute('aria-label', '筛选工具');
      search.value = query;
      search.addEventListener('input', (e) => {
        query = e.target.value;
        render();
        const nextInput = document.querySelector('.tbx-search');
        if (nextInput) {
          nextInput.focus();
          nextInput.setSelectionRange(query.length, query.length);
        }
      });
      barRight.append(search);

      if (creatingGroup) {
        const form = el('form', 'tbx-new-group-form');
        form.addEventListener('submit', (event) => {
          event.preventDefault();
          createGroup(newGroupName);
        });
        const input = el('input', 'tbx-new-group-input');
        input.maxLength = 40;
        input.placeholder = '分组名称';
        input.setAttribute('aria-label', '新分组名称');
        input.value = newGroupName;
        input.addEventListener('input', (e) => { newGroupName = e.target.value; });
        input.addEventListener('keydown', (e) => {
          if (e.key === 'Escape') {
            creatingGroup = false;
            newGroupName = '';
            render();
          }
        });
        const submitBtn = el('button', 'tbx-btn is-primary', '添加');
        submitBtn.type = 'submit';
        const cancelBtn = el('button', 'tbx-btn', '取消');
        cancelBtn.type = 'button';
        cancelBtn.addEventListener('click', () => {
          creatingGroup = false;
          newGroupName = '';
          render();
        });
        form.append(input, submitBtn, cancelBtn);
        barRight.append(form);
        queueMicrotask(() => input.focus());
      } else {
        const addBtn = el('button', 'tbx-btn', '+ 新建分组');
        addBtn.type = 'button';
        addBtn.addEventListener('click', () => {
          creatingGroup = true;
          newGroupName = '';
          render();
        });
        barRight.append(addBtn);
      }

      bar.append(filterGroup, barRight);
      shell.append(bar);

      if (loading && !items.length) {
        shell.append(el('div', 'tbx-empty', '加载中…'));
      } else if (error) {
        shell.append(el('div', 'tbx-empty', error));
      } else {
        const allowReorder = filter === 'all' && !query.trim();
        const visible = filteredItems();
        const groups = buildGroups(visible, allowReorder);
        if (!groups.length) {
          shell.append(el('div', 'tbx-empty', '无匹配工具'));
        } else {
          const list = el('div', 'tbx-groups');
          groups.forEach((group, idx) => {
            list.append(renderGroupCard(group, idx, groups, allowReorder));
          });
          shell.append(list);
        }
      }
      return shell;
    }

    return { load, view };
  }

  global.JccAdminToolbox = { create };
})(window);
