/* Deck figures shared by the admin overview and the daily report.
   Copy actions, effective copies and unique copiers stay separate; uncollected figures read "未采集". */
(function (global) {
  const { el } = global.JccAdminCore;
  const NOT_COLLECTED = '未采集';

  function value(summary, key, suffix = '') {
    const raw = summary?.[key];
    if (raw === undefined || raw === null) return NOT_COLLECTED;
    return `${Number(raw).toLocaleString('zh-CN')}${suffix}`;
  }

  function coverageText(coverage) {
    if (!coverage) return '历史快照未包含卡组数据';
    if (coverage.status === 'not_collected') return '卡组行为数据尚未开始采集；投稿与有效复制不受影响';
    if (coverage.status === 'partial') return `卡组行为数据从 ${String(coverage.from).slice(11, 16)} 起采集，不是全天`;
    return '';
  }

  function groups(summary, snapshot) {
    return [
      ['投稿', [
        ['新投稿', value(summary, 'deck_submissions_new')],
        ['补充重提', value(summary, 'deck_submissions_resubmitted')],
        ['投稿人', value(summary, 'deck_submitters')],
        ['待处理 / 处理中 / 待补充', `${value(summary, 'deck_submissions_pending')} / ${value(summary, 'deck_submissions_processing')} / ${value(summary, 'deck_submissions_needs_info')}`, '时段结束时'],
      ]],
      ['处理结果', [
        ['采纳 / 未采纳 / 重复', `${value(summary, 'deck_submissions_published')} / ${value(summary, 'deck_submissions_rejected')} / ${value(summary, 'deck_submissions_duplicate')}`],
        ['采纳率', summary?.deck_adoption_rate == null ? '—' : `${summary.deck_adoption_rate}%`, `本时段作出的 ${value(summary, 'deck_submissions_decided')} 个决定`],
        ['请求补充 / 撤回', `${value(summary, 'deck_submissions_info_requested')} / ${value(summary, 'deck_submissions_withdrawn')}`],
        ['处理耗时', summary?.deck_review_hours_median == null ? '—' : `中位 ${summary.deck_review_hours_median} 小时`, summary?.deck_review_hours_avg == null ? '' : `平均 ${summary.deck_review_hours_avg} 小时`],
      ]],
      ['卡组', [
        ['首次发布', value(summary, 'deck_published')],
        ['恢复 / 隐藏 / 删除', `${value(summary, 'deck_restored')} / ${value(summary, 'deck_hidden')} / ${value(summary, 'deck_deleted')}`],
        ['当前公开', snapshot ? Number(snapshot.public_decks || 0).toLocaleString('zh-CN') : '—', snapshot ? `其中投稿 ${snapshot.public_submitted_decks || 0} · 生成时` : ''],
      ]],
      ['复制', [
        ['复制动作', value(summary, 'deck_copy_actions'), `方案码 ${value(summary, 'deck_plan_copy_actions')} · 阵容码 ${value(summary, 'deck_lineup_copy_actions')}`],
        ['有效复制', value(summary, 'deck_effective_copies'), '同一人 5 分钟内只计一次，两种代码共用'],
        ['复制人数', value(summary, 'deck_copiers'), `方案码 ${value(summary, 'deck_plan_copiers')} · 阵容码 ${value(summary, 'deck_lineup_copiers')}`],
      ]],
      ['互动与访问', [
        ['点赞', value(summary, 'deck_likes')],
        ['收藏新增 / 取消', `${value(summary, 'deck_favorite_adds')} / ${value(summary, 'deck_favorite_removes')}`],
        ['卡组库访客', value(summary, 'deck_library_visitors'), '实际打开卡组库标签，按日去重'],
        ['详情访客', value(summary, 'deck_detail_visitors'), `按日、访客、卡组去重 ${value(summary, 'deck_detail_visits')} 次`],
      ]],
    ];
  }

  function render({ summary, coverage, top, contributors, snapshot, compact = false }) {
    const wrap = el('div', 'admin-deck-metrics');
    const note = coverageText(coverage);
    if (note) wrap.append(el('p', 'admin-deck-metrics-note', note));
    const grid = el('div', 'admin-deck-metric-groups');
    groups(summary, snapshot).forEach(([title, items]) => {
      const group = el('section', 'admin-deck-metric-group');
      group.append(el('h4', '', title));
      const list = el('dl');
      items.forEach(([label, text, caption]) => {
        const row = el('div');
        const dd = el('dd', text === NOT_COLLECTED ? 'is-missing' : '', text);
        row.append(el('dt', '', label), dd);
        if (caption) row.append(el('small', '', caption));
        list.append(row);
      });
      group.append(list);
      grid.append(group);
    });
    wrap.append(grid);
    if (top?.length) {
      const section = el('section', 'admin-deck-metric-rank');
      section.append(el('h4', '', '复制最多的卡组'));
      const list = el('ol');
      top.slice(0, compact ? 5 : 10).forEach((item) => {
        const row = el('li');
        const link = el('a', '', item.title || `卡组 #${item.deck_id}`);
        link.href = `/orange-decks/${item.deck_id}`; link.target = '_blank'; link.rel = 'noopener';
        row.append(link, el('span', 'admin-meta', `${item.credit === 'provided' ? '提供' : '作者'}：${item.uploader} · ${item.copiers} 人 · 动作 ${item.copy_actions}（方案 ${item.plan_copy_actions} / 阵容 ${item.lineup_copy_actions}）· 有效 ${item.effective_copies}`));
        list.append(row);
      });
      section.append(list);
      wrap.append(section);
    }
    if (!compact && contributors?.length) {
      const section = el('section', 'admin-deck-metric-rank');
      section.append(el('h4', '', '供稿人'));
      const list = el('ol');
      contributors.forEach((item) => list.append(el('li', '', `${item.user} · 投稿 ${item.submitted} · 采纳 ${item.published}`)));
      section.append(list);
      wrap.append(section);
    }
    return wrap;
  }

  global.JccAdminDeckMetrics = Object.freeze({ render, NOT_COLLECTED });
})(window);
