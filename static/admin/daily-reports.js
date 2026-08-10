(function (global) {
  const { el } = global.JccAdminCore;

  const HOURS = Array.from({ length: 24 }, (_, hour) => hour);

  function createDailyReportsRenderer({ workbenchPanel, empty, button }) {
    return function renderDailyReportsWorkspace(state, helpers) {
      const { items, report } = state;
      const wrap = el('div', 'admin-daily-reports');
      wrap.append(renderToolbar(state, helpers));

      if (!items.length && !report) {
        wrap.append(empty('还没有每日报告。每天凌晨会自动生成昨日报告，也可以点击「生成昨日报告」立即生成。'));
        return wrap;
      }
      if (!report) {
        wrap.append(empty('正在加载报告数据...'));
        return wrap;
      }

      wrap.append(
        renderReportStats(report),
        renderHeatmapPanel(report),
        renderDetailPanels(report),
        renderReportFooter(report),
      );
      return wrap;
    };

    function renderToolbar(state, helpers) {
      const toolbar = el('div', 'daily-report-toolbar');
      const left = el('div', 'daily-report-toolbar-left');
      const label = el('label', 'daily-report-date-label', '报告日期');
      const select = el('select', 'daily-report-date-select');
      (state.items || []).forEach((item) => {
        const option = document.createElement('option');
        option.value = item.report_date;
        option.textContent = `${item.report_date} · UV ${item.unique_visitors} · 复制 ${item.successful_copies}`;
        option.selected = item.report_date === state.selectedDate;
        select.append(option);
      });
      select.disabled = !(state.items || []).length;
      select.addEventListener('change', () => {
        if (select.value) helpers.selectDate(select.value);
      });
      label.append(select);
      left.append(label);

      const actions = el('div', 'card-actions');
      actions.append(
        button('生成昨日报告', async () => helpers.generate(helpers.yesterdayDate()), 'small-button'),
        button('重新生成', async () => {
          if (!state.selectedDate) return;
          if (!window.confirm(`重新生成 ${state.selectedDate} 的报告？现有快照会被覆盖。`)) return;
          await helpers.generate(state.selectedDate);
        }, 'small-button'),
        button('刷新', async () => helpers.refresh(), 'small-button'),
      );
      toolbar.append(left, actions);
      return toolbar;
    }

    function renderReportStats(report) {
      const summary = report.summary || {};
      const deltas = report.deltas || {};
      const cards = el('div', 'daily-report-stat-grid');
      [
        ['独立访客 UV', summary.unique_visitors, 'unique_visitors', '全站按访客去重'],
        ['访问次数 PV', summary.page_visits, 'page_visits', '记录的页面访问'],
        ['成功复制', summary.total_copies, 'total_copies', `阵容 ${summary.lineup_copies || 0} · 实时 ${summary.live_comp_copies || 0}`],
        ['新增注册', summary.new_registrations, 'new_registrations', '不含管理员'],
        ['成功登录', summary.successful_logins, 'successful_logins', '去重登录用户'],
        ['新增阵容', summary.new_lineups, 'new_lineups', '当天发布'],
        ['公开留言', summary.guestbook_messages, 'guestbook_messages', '当天提交'],
        ['收到举报', summary.reports_submitted, 'reports_submitted', '当天提交'],
      ].forEach(([label, value, deltaKey, caption]) => {
        const card = el('article', 'daily-report-stat-card');
        card.append(
          el('span', 'stat-label', label),
          el('strong', '', String(value == null ? 0 : value)),
          deltaBadge(deltas, deltaKey),
          el('small', '', caption),
        );
        cards.append(card);
      });
      return cards;
    }

    function deltaBadge(deltas, key) {
      const value = deltas[key];
      if (value === undefined || value === null) return null;
      const className = value > 0 ? 'daily-delta up' : value < 0 ? 'daily-delta down' : 'daily-delta flat';
      const text = value > 0 ? `较上期 +${value}` : value < 0 ? `较上期 ${value}` : '与上期持平';
      return el('span', className, text);
    }

    function renderHeatmapPanel(report) {
      const panel = workbenchPanel(
        '昨日小时热度',
        '24 小时访问与复制分布，颜色越深人数越多',
      );
      const body = panel.querySelector('.admin-workspace-body');
      const hourly = report.hourly || { uv: [], visits: [], copies: [] };
      const peakVisit = report.peak_visit_hour;
      const peakCopy = report.peak_copy_hour;

      const chips = el('div', 'daily-peak-chips');
      if (peakVisit) {
        chips.append(el('span', 'daily-peak-chip', `访问高峰 ${String(peakVisit.hour).padStart(2, '0')}:00 · ${peakVisit.value} 人`));
      }
      if (peakCopy) {
        chips.append(el('span', 'daily-peak-chip', `复制高峰 ${String(peakCopy.hour).padStart(2, '0')}:00 · ${peakCopy.value} 次`));
      }
      if (chips.children.length) body.append(chips);
      body.append(
        renderHeatmapLegend(),
        renderHeatmapGrid([
          ['访问人数', hourly.uv, '人'],
          ['访问次数', hourly.visits, '次'],
          ['复制次数', hourly.copies, '次'],
        ]),
      );
      return panel;
    }

    function renderHeatmapLegend() {
      const legend = el('div', 'daily-heat-legend');
      legend.append(el('span', '', '少'));
      const bar = el('span', 'daily-heat-legend-bar');
      bar.append(el('i', '', ''));
      legend.append(bar, el('span', '', '多'));
      return legend;
    }

    function heatColor(ratio) {
      const alpha = ratio <= 0 ? 0.05 : 0.08 + 0.82 * Math.min(1, ratio);
      return `rgba(139, 92, 246, ${alpha.toFixed(3)})`;
    }

    function renderHeatmapGrid(rows) {
      const grid = el('div', 'daily-heatmap');
      const head = el('div', 'daily-heat-row is-head');
      head.append(el('span', 'daily-heat-label', '时段'));
      HOURS.forEach((hour) => head.append(el('span', 'daily-heat-hour', String(hour))));
      grid.append(head);

      rows.forEach(([label, series, unit]) => {
        const max = Math.max(1, ...series);
        const row = el('div', 'daily-heat-row');
        row.append(el('span', 'daily-heat-label', label));
        HOURS.forEach((hour) => {
          const value = Number(series[hour] || 0);
          const ratio = value / max;
          const cell = el('span', 'daily-heat-cell', value ? String(value) : '');
          cell.style.background = heatColor(ratio);
          cell.title = `${String(hour).padStart(2, '0')}:00 ${label} ${value}${unit}`;
          if (value > 0) cell.classList.add('has-value');
          row.append(cell);
        });
        grid.append(row);
      });
      return grid;
    }

    function renderDetailPanels(report) {
      const grid = el('div', 'daily-report-detail-grid');
      grid.append(
        renderTopPagesPanel(report),
        renderTopCopiedPanel(report),
      );
      return grid;
    }

    function renderTopPagesPanel(report) {
      const panel = workbenchPanel('热门页面', '昨日访问最多的页面');
      const body = panel.querySelector('.admin-workspace-body');
      const pages = report.top_pages || [];
      if (!pages.length) {
        body.append(empty('昨日没有可统计的访问记录'));
        return panel;
      }
      const maxVisits = Math.max(1, ...pages.map((page) => page.visits));
      const list = el('div', 'admin-list compact');
      pages.forEach((page) => {
        const card = el('article', 'admin-row-card');
        const info = el('div');
        info.append(el('strong', '', page.label || page.page_key));
        info.append(el('p', 'admin-meta', `页面 ${page.page_key} · ${page.visits} 次访问 · ${page.uv} 人`));
        const barWrap = el('div', 'daily-page-bar');
        const bar = el('i', '', '');
        bar.style.width = `${Math.round((page.visits / maxVisits) * 100)}%`;
        barWrap.append(bar);
        card.append(info, barWrap);
        list.append(card);
      });
      body.append(list);
      return panel;
    }

    function renderTopCopiedPanel(report) {
      const panel = workbenchPanel('复制排行', '昨日被复制最多的阵容码（普通阵容 + 实时阵容）');
      const body = panel.querySelector('.admin-workspace-body');
      const items = report.top_copied || [];
      if (!items.length) {
        body.append(empty('昨日没有复制记录'));
        return panel;
      }
      const list = el('div', 'admin-list compact');
      items.forEach((item) => {
        const card = el('article', 'admin-row-card');
        const info = el('div');
        const typeLabel = item.target_type === 'live_comp' ? '实时阵容' : '普通阵容';
        const titleRow = el('strong', '', `#${item.rank} ${item.title || item.target_id}`);
        if (item.target_type === 'lineup' && item.lineup_id) {
          const link = el('a', 'admin-inline-link', ' 查看');
          link.href = `/lineup/${item.lineup_id}`;
          link.target = '_blank';
          link.rel = 'noopener';
          titleRow.append(link);
        }
        const metaParts = [typeLabel];
        if (item.tier) metaParts.push(`${item.tier} 级`);
        if (item.season_name) metaParts.push(item.season_name);
        metaParts.push(`复制 ${item.copies} 次 · ${item.unique_visitors} 人`);
        info.append(titleRow, el('p', 'admin-meta', metaParts.join(' · ')));
        if (item.code) info.append(el('code', 'daily-copied-code', item.code));
        card.append(info);
        list.append(card);
      });
      body.append(list);
      return panel;
    }

    function renderReportFooter(report) {
      const footer = el('p', 'daily-report-footer',
        `快照时间 ${report.generated_at || '--'} · 每日 00:15 左右自动生成昨日报告 · 可在上方重新生成`);
      if (report.previous_date && report.deltas) {
        footer.textContent = `与 ${report.previous_date} 报告对比 · ${footer.textContent}`;
      }
      return footer;
    }
  }

  global.JccAdminDailyReports = Object.freeze({
    createDailyReportsRenderer,
  });
})(window);
