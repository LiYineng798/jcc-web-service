/* Deck figures shared by the admin overview and the daily report.
   Headline figures first, then how submissions were handled, how copies split between the two codes, and what changed in the library.
   Copy actions, effective copies and unique copiers stay separate; uncollected figures read "未采集", never zero. */
(function (global) {
  const { el } = global.JccAdminCore;
  const NOT_COLLECTED = '未采集';

  const raw = (summary, key) => (summary?.[key] === undefined || summary?.[key] === null ? null : Number(summary[key]));
  const num = (value) => Number(value).toLocaleString('zh-CN');

  function value(summary, key, suffix = '') {
    const figure = raw(summary, key);
    return figure === null ? NOT_COLLECTED : `${num(figure)}${suffix}`;
  }

  function coverageText(coverage) {
    if (!coverage) return '历史快照未包含卡组数据';
    if (coverage.status === 'not_collected') return '卡组行为数据尚未开始采集；投稿与有效复制不受影响';
    if (coverage.status === 'partial') return `卡组行为数据从 ${String(coverage.from).slice(11, 16)} 起采集，不是全天`;
    return '';
  }

  function figure(text, className = '') {
    return el('strong', `${className}${text === NOT_COLLECTED ? ' is-missing' : ''}`.trim(), text);
  }

  function kpi(label, text, caption, tone = '') {
    const tile = el('article', `admin-dm-kpi${tone ? ` is-${tone}` : ''}`);
    tile.append(el('span', 'admin-dm-label', label), figure(text), el('small', '', caption));
    return tile;
  }

  function kpis(summary, snapshot) {
    const row = el('div', 'admin-dm-kpis');
    const rate = summary?.deck_adoption_rate;
    const decided = raw(summary, 'deck_submissions_decided');
    row.append(
      kpi('新投稿', value(summary, 'deck_submissions_new'), `投稿人 ${value(summary, 'deck_submitters')} · 补充重提 ${value(summary, 'deck_submissions_resubmitted')}`),
      kpi('采纳率', rate == null ? '—' : `${rate}%`, decided ? `本时段作出的 ${num(decided)} 个决定` : '本时段还没有处理决定', rate == null ? '' : 'good'),
      kpi('有效复制', value(summary, 'deck_effective_copies'), `复制动作 ${value(summary, 'deck_copy_actions')} · 同一人 5 分钟内计一次`, 'accent'),
      kpi('复制人数', value(summary, 'deck_copiers'), `方案码 ${value(summary, 'deck_plan_copiers')} · 阵容码 ${value(summary, 'deck_lineup_copiers')}`),
      kpi('公开卡组', snapshot ? num(snapshot.public_decks || 0) : '—', snapshot ? `其中投稿采纳 ${num(snapshot.public_submitted_decks || 0)} · 生成时` : '生成时的总数'),
    );
    return row;
  }

  // One proportional bar with its legend; missing data says so instead of drawing an empty bar.
  function split(title, caption, parts) {
    const block = el('div', 'admin-dm-split');
    const head = el('div', 'admin-dm-split-head');
    head.append(el('span', '', title));
    if (caption) head.append(el('small', '', caption));
    block.append(head);
    if (parts.some(([, amount]) => amount === null)) {
      block.append(el('p', 'admin-dm-missing', NOT_COLLECTED));
      return block;
    }
    const total = parts.reduce((sum, [, amount]) => sum + amount, 0);
    const bar = el('div', `admin-dm-bar${total ? '' : ' is-empty'}`);
    bar.setAttribute('role', 'img');
    bar.setAttribute('aria-label', `${title}：${parts.map(([label, amount]) => `${label} ${amount}`).join('，')}`);
    parts.forEach(([, amount, tone]) => {
      if (!amount) return;
      const segment = el('i', `is-${tone}`);
      segment.style.flexGrow = String(amount);
      bar.append(segment);
    });
    const legend = el('ul', 'admin-dm-legend');
    parts.forEach(([label, amount, tone]) => {
      const item = el('li', `is-${tone}`);
      item.append(el('span', '', label), el('b', '', num(amount)));
      legend.append(item);
    });
    block.append(bar, legend);
    return block;
  }

  function facts(rows) {
    const list = el('dl', 'admin-dm-facts');
    rows.forEach(([label, text, caption]) => {
      const row = el('div');
      row.append(el('dt', '', label), el('dd', text === NOT_COLLECTED ? 'is-missing' : '', text));
      if (caption) row.append(el('small', '', caption));
      list.append(row);
    });
    return list;
  }

  function card(title, ...children) {
    const section = el('section', 'admin-dm-card');
    section.append(el('h4', '', title), ...children);
    return section;
  }

  function panels(summary) {
    const grid = el('div', 'admin-dm-cards');
    const median = summary?.deck_review_hours_median;
    grid.append(
      card('投稿处理',
        split('时段结束时的队列', '', [['待处理', raw(summary, 'deck_submissions_pending'), 'neutral'], ['处理中', raw(summary, 'deck_submissions_processing'), 'accent'], ['待补充', raw(summary, 'deck_submissions_needs_info'), 'warn']]),
        split('处理决定', '', [['采纳', raw(summary, 'deck_submissions_published'), 'good'], ['未采纳', raw(summary, 'deck_submissions_rejected'), 'bad'], ['重复', raw(summary, 'deck_submissions_duplicate'), 'neutral']]),
        facts([
          ['请求补充 / 撤回', `${value(summary, 'deck_submissions_info_requested')} / ${value(summary, 'deck_submissions_withdrawn')}`],
          ['处理耗时', median == null ? '—' : `中位 ${median} 小时`, summary?.deck_review_hours_avg == null ? '' : `平均 ${summary.deck_review_hours_avg} 小时`],
        ])),
      card('复制构成',
        split('复制动作', `共 ${value(summary, 'deck_copy_actions')}`, [['方案码', raw(summary, 'deck_plan_copy_actions'), 'accent'], ['阵容码', raw(summary, 'deck_lineup_copy_actions'), 'blue']]),
        split('复制人数', '同一人两种代码都复制会各计一次', [['方案码', raw(summary, 'deck_plan_copiers'), 'accent'], ['阵容码', raw(summary, 'deck_lineup_copiers'), 'blue']]),
        facts([['有效复制', value(summary, 'deck_effective_copies'), '同一人 5 分钟内只计一次，两种代码共用']])),
      card('卡组与互动', facts([
        ['首次发布', value(summary, 'deck_published')],
        ['恢复 / 隐藏 / 删除', `${value(summary, 'deck_restored')} / ${value(summary, 'deck_hidden')} / ${value(summary, 'deck_deleted')}`],
        ['点赞', value(summary, 'deck_likes')],
        ['收藏新增 / 取消', `${value(summary, 'deck_favorite_adds')} / ${value(summary, 'deck_favorite_removes')}`],
        ['卡组库访客', value(summary, 'deck_library_visitors'), '实际打开卡组库，按日去重'],
        ['详情访客', value(summary, 'deck_detail_visitors'), `按日、访客、卡组去重共 ${value(summary, 'deck_detail_visits')} 次`],
      ])),
    );
    return grid;
  }

  function table(title, columns, rows) {
    const section = el('section', 'admin-dm-card admin-dm-rank');
    section.append(el('h4', '', title));
    const scroller = el('div', 'admin-dm-table-wrap');
    const tableNode = el('table', 'admin-dm-table');
    const head = el('tr');
    columns.forEach(([label, align]) => head.append(el('th', align ? `is-${align}` : '', label)));
    const thead = el('thead');
    thead.append(head);
    const tbody = el('tbody');
    rows.forEach((cells) => {
      const tr = el('tr');
      cells.forEach((content, index) => {
        const td = el('td', columns[index][1] ? `is-${columns[index][1]}` : '');
        td.append(...[].concat(content));
        tr.append(td);
      });
      tbody.append(tr);
    });
    tableNode.append(thead, tbody);
    scroller.append(tableNode);
    section.append(scroller);
    return section;
  }

  function topTable(top, compact) {
    const items = top.slice(0, compact ? 5 : 10);
    const most = Math.max(1, ...items.map((item) => item.effective_copies));
    return table('复制最多的卡组', [['#', 'num'], ['卡组'], ['有效复制', 'bar'], ['人数', 'num'], ['动作（方案 / 阵容）', 'num']], items.map((item, index) => {
      const name = el('div', 'admin-dm-deck');
      const link = el('a', '', item.title || `卡组 #${item.deck_id}`);
      link.href = `/orange-decks/${item.deck_id}`; link.target = '_blank'; link.rel = 'noopener';
      name.append(link, el('small', '', `${item.credit === 'provided' ? '由' : '作者'} ${item.uploader}${item.credit === 'provided' ? ' 提供' : ''}`));
      const bar = el('div', 'admin-dm-inline-bar');
      const fill = el('i');
      fill.style.width = `${Math.round((item.effective_copies / most) * 100)}%`;
      bar.append(fill, el('b', '', num(item.effective_copies)));
      return [el('span', `admin-dm-rank-no${index < 3 ? ' is-top' : ''}`, String(index + 1)), name, bar, num(item.copiers),
        `${num(item.copy_actions)}（${num(item.plan_copy_actions)} / ${num(item.lineup_copy_actions)}）`];
    }));
  }

  function contributorTable(contributors) {
    return table('供稿人', [['供稿人'], ['投稿', 'num'], ['采纳', 'num']], contributors.map((item) => [item.user, num(item.submitted), num(item.published)]));
  }

  function render({ summary, coverage, top, contributors, snapshot, compact = false }) {
    const wrap = el('div', `admin-deck-metrics${compact ? ' is-compact' : ''}`);
    const note = coverageText(coverage);
    if (note) wrap.append(el('p', 'admin-deck-metrics-note', note));
    wrap.append(kpis(summary, snapshot), panels(summary));
    const ranks = el('div', 'admin-dm-ranks');
    if (top?.length) ranks.append(topTable(top, compact));
    if (!compact && contributors?.length) ranks.append(contributorTable(contributors));
    if (!ranks.children.length) ranks.append(el('p', 'admin-dm-empty', '这一时段还没有卡组被复制'));
    wrap.append(ranks);
    return wrap;
  }

  global.JccAdminDeckMetrics = Object.freeze({ render, NOT_COLLECTED });
})(window);
