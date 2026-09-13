(function (global) {
  const { el, button } = global.JccAdminCore;
  const statuses = [['active', '启用展示'], ['archived', '归档展示'], ['hidden', '后台隐藏'], ['disabled', '停用']];
  const isPublic = (season) => ['active', 'archived'].includes(season.status);
  const surfaces = {
    library: { name: '资料库', icon: 'library', description: '控制首页资料菜单、赛季资料页与弈子详情。' },
    simulator: { name: '模拟器', icon: 'layout-grid', description: '控制模拟器的赛季菜单与首次打开的默认赛季。', defaultLabel: '模拟器' },
    live: { name: '实时阵容', icon: 'radio', description: '公开赛季按此顺序展示；默认标记表示首页优先打开的赛季。', defaultLabel: '实时阵容' },
  };

  function createSurfaceRenderer({ getDisplay, getUi, isBusy, mutate, refresh }) {
    function renderRow(kind, season, index, total, defaultId) {
      const visible = isPublic(season);
      const name = season.display_name || season.season_id;
      const key = `season-${kind}-${season.season_id}`;
      const row = el('li', `season-display-row${visible ? '' : ' is-inactive'}`);
      row.dataset.seasonId = season.season_id;
      const info = el('div', 'season-display-info');
      const nameLine = el('div', 'season-display-name');
      nameLine.append(el('strong', '', name));
      if (visible && season.season_id === defaultId) nameLine.append(el('span', 'season-display-badge', '默认'));
      info.append(nameLine, el('p', 'admin-meta', `${season.season_id}${season.game_version ? ` · ${season.game_version}` : ''}`));
      if (season.description) info.append(el('p', 'admin-meta', season.description));
      if (visible) row.append(el('span', 'season-display-rank', String(index + 1)));
      row.append(info);

      const actions = el('div', 'season-display-actions');
      const select = el('select', 'season-display-status');
      select.id = `${key}-status`;
      select.setAttribute('aria-label', `${name}展示状态`);
      statuses.forEach(([value, label]) => {
        const option = el('option', '', label);
        option.value = value;
        select.append(option);
      });
      select.value = season.status;
      select.disabled = isBusy();
      select.addEventListener('change', () => mutate(kind, season, { status: select.value }));
      actions.append(select);
      if (visible) {
        const move = el('div', 'season-display-move');
        [['上移', 'arrow-up', index, index === 0], ['下移', 'arrow-down', index + 2, index === total - 1]].forEach(([label, icon, order, disabled]) => {
          const control = button('', () => mutate(kind, season, { order }), 'small-button season-display-arrow', disabled || isBusy());
          control.id = `${key}-${icon}`;
          control.title = `${label}${name}`;
          control.setAttribute('aria-label', control.title);
          const glyph = el('i');
          glyph.dataset.lucide = icon;
          control.append(glyph);
          move.append(control);
        });
        actions.append(move);
        if (surfaces[kind].defaultLabel && season.season_id !== defaultId) {
          const control = button('设为默认', () => mutate(kind, season, { is_default: true }), 'small-button', isBusy());
          control.id = `${key}-default`;
          control.setAttribute('aria-label', `将${name}设为${surfaces[kind].defaultLabel}默认赛季`);
          actions.append(control);
        }
      } else {
        const restore = button('重新展示', () => mutate(kind, season, { status: 'active' }), 'small-button', isBusy());
        restore.id = `${key}-restore`;
        restore.setAttribute('aria-label', `重新展示${name}`);
        actions.append(restore);
      }
      row.append(actions);
      return row;
    }

    function renderSurface(kind) {
      const config = surfaces[kind];
      const { items = [], default_season_id: defaultId, loadedAt } = getDisplay(kind);
      const ui = getUi(kind);
      const panel = el('section', 'season-display-panel');
      panel.dataset.seasonSurface = kind;
      panel.setAttribute('aria-labelledby', `season-${kind}-title`);
      const header = el('div', 'season-display-panel-head');
      const title = el('h2', '', config.name);
      title.id = `season-${kind}-title`;
      title.tabIndex = -1;
      const glyph = el('i');
      glyph.dataset.lucide = config.icon;
      title.prepend(glyph);
      header.append(title);
      const visible = items.filter(isPublic);
      const inactive = items.filter((season) => !isPublic(season));
      if (loadedAt) header.append(el('span', 'season-display-count', `${visible.length} 个展示中`));
      panel.append(header, el('p', 'season-display-description', config.description));
      if (ui.error) {
        const error = el('div', 'season-display-empty');
        error.setAttribute('role', 'alert');
        error.append(el('p', '', ui.error), button('重新加载', () => refresh(kind), 'small-button', isBusy()));
        panel.append(error);
        return panel;
      }
      if (!loadedAt) {
        panel.append(el('p', 'season-display-empty', '正在加载赛季…'));
        return panel;
      }
      if (!items.length) {
        panel.append(el('p', 'season-display-empty', '暂无已登记的赛季'));
        return panel;
      }
      const list = el('ol', 'season-display-public');
      list.setAttribute('aria-label', `${config.name}展示顺序`);
      visible.forEach((season, index) => list.append(renderRow(kind, season, index, visible.length, defaultId)));
      panel.append(list);
      if (!visible.length) panel.append(el('p', 'season-display-empty', '暂无展示中的赛季，可从下方重新展示。'));

      if (inactive.length) {
        const details = el('details', 'season-display-inactive');
        details.open = ui.expanded;
        const summary = el('summary');
        const hidden = inactive.filter((season) => season.status === 'hidden').length;
        summary.append(el('strong', '', '未展示赛季'), el('span', '', `${inactive.length} 个 · ${hidden} 隐藏 / ${inactive.length - hidden} 停用`));
        const chevron = el('i');
        chevron.dataset.lucide = 'chevron-down';
        summary.append(chevron);
        const list = el('ul', 'season-display-inactive-list');
        list.setAttribute('aria-label', `${config.name}未展示赛季`);
        inactive.forEach((season) => list.append(renderRow(kind, season, 0, 0, defaultId)));
        details.append(summary, el('p', 'season-display-inactive-hint', '不参与展示排序；重新展示后排在末尾。'), list);
        // A detached details element may queue an initial toggle. Only persist
        // user-visible toggles, so a late event cannot overwrite a new render.
        details.addEventListener('toggle', () => { if (details.isConnected) ui.expanded = details.open; });
        panel.append(details);
      }
      return panel;
    }
    return renderSurface;
  }

  function createRenderer(options) {
    const { isBusy, openVersions } = options;
    const renderSurface = createSurfaceRenderer(options);
    return function render() {
      const hub = el('div', 'admin-season-hub');
      hub.setAttribute('aria-busy', String(isBusy()));
      const intro = el('div', 'season-display-intro');
      const copy = el('div');
      copy.append(el('h2', '', '一份赛季资料，两个展示入口'), el('p', '', '资料库与模拟器共用资料版本，展示状态和顺序分别设置。修改后立即保存。'));
      intro.append(copy, button('管理资料版本', openVersions, 'small-button'));
      hub.append(intro, el('p', 'season-display-guide', '展示区仅排列启用与归档赛季。隐藏、停用赛季统一收纳，可随时重新展示。'));
      const grid = el('div', 'season-display-grid');
      grid.append(renderSurface('library'), renderSurface('simulator'));
      hub.append(grid);
      return hub;
    };
  }
  global.JccAdminSeasonDisplay = Object.freeze({ createRenderer, createSurfaceRenderer });
})(window);
