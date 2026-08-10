(function (global) {
  const { buildDeltaText, el, formatDay } = global.JccAdminCore;

  function createOverviewRenderer({ activateTab, button, empty, getOverview, getCopyRank, refreshCopyRank, trafficMetric, workbenchPanel }) {
    function renderOverviewDashboard() {
      const wrap = el('div', 'admin-dashboard');
      wrap.append(renderOverviewStats());

      const grid = el('div', 'admin-dashboard-grid');
      grid.append(renderTrafficOverview(), renderTodoPanel(), renderQuickLinks());
      wrap.append(grid);
      wrap.append(renderCopyRankPanel());
      return wrap;
    }

    function renderCopyRankPanel() {
      const rank = getCopyRank?.() || {};
      const panel = workbenchPanel('今日复制排行', `${rank.date || '今天'} 被复制最多的阵容码（普通阵容 + 实时阵容）`);
      const body = panel.querySelector('.admin-workspace-body');
      if (refreshCopyRank) {
        const actions = el('div', 'card-actions');
        actions.append(button('刷新', async () => refreshCopyRank(), 'small-button'));
        body.append(actions);
      }
      const items = rank.items || [];
      if (!items.length) {
        body.append(empty('今天还没有复制记录'));
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
        if (item.status && item.status !== 'normal') metaParts.push(`状态：${item.status}`);
        info.append(
          titleRow,
          el('p', 'admin-meta', `${metaParts.join(' · ')} · 复制 ${item.copies} 次 · ${item.unique_visitors} 人`),
        );
        const details = document.createElement('details');
        details.className = 'copy-rank-details';
        const summary = document.createElement('summary');
        summary.textContent = `查看明细（${(item.details || []).length} 条）`;
        details.append(summary);
        const eventList = el('div', 'copy-rank-event-list');
        (item.details || []).forEach((event) => {
          const row = el('div', 'copy-rank-event');
          const copiedCode = event.code ? el('code', 'copy-rank-code', event.code) : el('span', 'admin-meta', '阵容码已不可用');
          row.append(
            el('strong', '', event.actor || '游客'),
            el('span', 'copy-rank-event-time', event.copied_at || ''),
            el('span', 'copy-rank-event-owner', `上传者：${event.uploader || '未知用户'}`),
            el('span', 'copy-rank-event-ip', `复制 IP：${event.ip_address || '未记录'}`),
            el('span', 'copy-rank-event-source', event.source_page ? `来源：${event.source_page}` : '来源：未记录'),
            copiedCode,
          );
          eventList.append(row);
        });
        if (!eventList.children.length) eventList.append(el('p', 'admin-meta', '暂无可展示的明细'));
        details.append(eventList);
        card.append(info, details);
        list.append(card);
      });
      body.append(list);
      return panel;
    }

    function renderOverviewStats() {
      const stats = getOverview()?.stats || {};
      const cards = el('div', 'admin-stat-grid');
      [
        ['今日全站 UV', stats.today_uv || 0, '全站页面按自然日去重'],
        ['今日总复制', stats.today_total_copy_count || 0, `普通阵容 ${stats.today_lineup_copy_count || 0} · 实时阵容 ${stats.today_live_comp_copy_count || 0}`],
        ['今日注册', stats.today_users || 0, '新增用户数'],
        ['今日登录', stats.today_logins || 0, '去重登录用户'],
        ['待处理举报', stats.pending_reports_count || 0, '优先处理'],
        ['总用户', stats.total_users || 0, '不含管理员'],
      ].forEach(([label, value, caption]) => {
        const card = el('article', 'admin-stat-card');
        card.append(el('span', 'stat-label', label), el('strong', '', String(value)), el('small', '', caption));
        cards.append(card);
      });
      return cards;
    }

    function renderTrafficOverview() {
      const panel = workbenchPanel('7 日访问趋势', '只展示轻量趋势，不在首页加载完整增长漏斗');
      const body = panel.querySelector('.admin-workspace-body');
      const stats = getOverview()?.stats || {};
      const trend = getOverview()?.traffic_7d || [];
      const totalUv = trend.reduce((sum, item) => sum + Number(item.uv || 0), 0);

      const overview = el('div', 'traffic-overview');
      overview.append(
        trafficMetric('今日全站 UV', stats.today_uv || 0, buildDeltaText(stats.today_uv || 0, stats.yesterday_uv || 0)),
        trafficMetric('昨日全站 UV', stats.yesterday_uv || 0, '上一自然日全站去重'),
        trafficMetric('7 日累计全站 UV', totalUv, '最近 7 天全站访问人数'),
        trafficMetric('今日新访客', stats.today_new_visitors || 0, '首次访问日期为今天'),
        trafficMetric('今日老访客', stats.today_returning_visitors || 0, '今天之前已访问过'),
      );

      body.append(overview, renderTrafficLineChart(trend));
      return panel;
    }

    function renderTrafficLineChart(trend) {
      const wrap = el('div', 'traffic-line-chart');
      if (!trend.length) {
        wrap.append(empty('暂无访问数据'));
        return wrap;
      }

      const latest = trend[trend.length - 1];
      const previous = trend[trend.length - 2] || latest;
      const delta = Number(latest.uv || 0) - Number(previous.uv || 0);
      const summary = el('div', 'traffic-line-summary');
      summary.append(
        el('strong', '', '每日 UV 折线'),
        el('span', '', `最新 ${latest.uv} UV · ${delta >= 0 ? '+' : ''}${delta} 较前日`),
      );

      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('role', 'img');
      svg.setAttribute('aria-label', '最近 7 天每日 UV 折线图');
      wrap.append(summary, svg);

      // Render at the measured container width so the chart fills the panel
      // on phones instead of being clipped by a fixed 640px viewBox.
      let lastWidth = 0;
      let rafId = null;
      const draw = (width) => {
        const capped = Math.max(260, Math.min(760, Math.round(width)));
        if (Math.abs(capped - lastWidth) < 8) return;
        lastWidth = capped;
        svg.setAttribute('width', String(capped));
        svg.setAttribute('height', '220');
        svg.setAttribute('viewBox', `0 0 ${capped} 220`);
        svg.replaceChildren(buildTrafficChartContent(trend, capped));
      };
      requestAnimationFrame(() => draw(wrap.clientWidth || 640));
      if (typeof ResizeObserver !== 'undefined') {
        const observer = new ResizeObserver(() => {
          if (rafId) return;
          rafId = requestAnimationFrame(() => {
            rafId = null;
            draw(wrap.clientWidth || 640);
          });
        });
        observer.observe(wrap);
      }
      return wrap;
    }

    function buildTrafficChartContent(trend, width) {
      const SVG_NS = 'http://www.w3.org/2000/svg';
      const values = trend.map((item) => Number(item.uv || 0));
      const maxUv = Math.max(1, ...values);
      const minUv = Math.min(...values);
      const compact = width < 480;
      const height = 220;
      const padding = compact
        ? { top: 18, right: 10, bottom: 34, left: 32 }
        : { top: 24, right: 24, bottom: 42, left: 44 };
      const plotWidth = width - padding.left - padding.right;
      const plotHeight = height - padding.top - padding.bottom;
      const pointX = (index) => padding.left + (trend.length === 1 ? plotWidth / 2 : (plotWidth / (trend.length - 1)) * index);
      const pointY = (uv) => padding.top + plotHeight - (uv / maxUv) * plotHeight;
      const points = trend.map((item, index) => ({
        date: item.date,
        label: formatDay(item.date),
        uv: Number(item.uv || 0),
        x: pointX(index),
        y: pointY(Number(item.uv || 0)),
      }));
      const pathData = points.map((point, index) => `${index ? 'L' : 'M'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' ');

      const fragment = document.createDocumentFragment();
      const gridGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      gridGroup.setAttribute('class', 'traffic-line-grid');
      [0, 0.5, 1].forEach((ratio) => {
        const y = padding.top + plotHeight * ratio;
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', String(padding.left));
        line.setAttribute('x2', String(width - padding.right));
        line.setAttribute('y1', y.toFixed(1));
        line.setAttribute('y2', y.toFixed(1));
        gridGroup.append(line);
      });

      const area = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      area.setAttribute('class', 'traffic-line-area');
      area.setAttribute('d', `${pathData} L ${points[points.length - 1].x.toFixed(1)} ${height - padding.bottom} L ${points[0].x.toFixed(1)} ${height - padding.bottom} Z`);

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('class', 'traffic-line-path');
      path.setAttribute('d', pathData);

      const pointGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      pointGroup.setAttribute('role', 'list');
      points.forEach((point, index) => {
        const pointWrap = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        pointWrap.setAttribute('class', 'traffic-line-point-wrap');
        pointWrap.setAttribute('role', 'listitem');
        pointWrap.setAttribute('tabindex', '0');
        pointWrap.setAttribute('aria-label', `${point.date}，${point.uv} UV`);

        const hitStart = index === 0 ? padding.left : (points[index - 1].x + point.x) / 2;
        const hitEnd = index === points.length - 1 ? width - padding.right : (point.x + points[index + 1].x) / 2;
        const hitArea = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        hitArea.setAttribute('class', 'traffic-line-hit-area');
        hitArea.setAttribute('x', hitStart.toFixed(1));
        hitArea.setAttribute('y', String(padding.top));
        hitArea.setAttribute('width', (hitEnd - hitStart).toFixed(1));
        hitArea.setAttribute('height', String(plotHeight));

        const guide = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        guide.setAttribute('class', 'traffic-line-guide');
        guide.setAttribute('x1', point.x.toFixed(1));
        guide.setAttribute('x2', point.x.toFixed(1));
        guide.setAttribute('y1', String(padding.top));
        guide.setAttribute('y2', String(height - padding.bottom));

        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('class', 'traffic-line-point');
        circle.setAttribute('cx', point.x.toFixed(1));
        circle.setAttribute('cy', point.y.toFixed(1));
        circle.setAttribute('r', compact ? '3' : point.uv === maxUv ? '5' : '4');
        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent = `${point.label}：${point.uv} UV`;
        circle.append(title);

        const tooltipWidth = compact ? 96 : 104;
        const tooltipHeight = 46;
        const tooltipX = Math.max(6, Math.min(width - tooltipWidth - 6, point.x - tooltipWidth / 2));
        const tooltipY = Math.max(6, point.y - tooltipHeight - 14);
        const tooltip = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        tooltip.setAttribute('class', 'traffic-line-tooltip');
        tooltip.setAttribute('aria-hidden', 'true');
        tooltip.setAttribute('transform', `translate(${tooltipX.toFixed(1)} ${tooltipY.toFixed(1)})`);

        const tooltipBox = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        tooltipBox.setAttribute('width', String(tooltipWidth));
        tooltipBox.setAttribute('height', String(tooltipHeight));
        tooltipBox.setAttribute('rx', '10');

        const tooltipDate = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        tooltipDate.setAttribute('class', 'traffic-line-tooltip-date');
        tooltipDate.setAttribute('x', '12');
        tooltipDate.setAttribute('y', '18');
        tooltipDate.setAttribute('font-size', compact ? '11' : '12');
        tooltipDate.textContent = point.date;

        const tooltipValue = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        tooltipValue.setAttribute('class', 'traffic-line-tooltip-value');
        tooltipValue.setAttribute('x', '12');
        tooltipValue.setAttribute('y', '35');
        tooltipValue.setAttribute('font-size', compact ? '11' : '12');
        tooltipValue.textContent = `${point.uv} UV`;

        tooltip.append(tooltipBox, tooltipDate, tooltipValue);
        pointWrap.append(hitArea, guide, circle, tooltip);
        pointGroup.append(pointWrap);
      });

      const labelGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      labelGroup.setAttribute('class', 'traffic-line-labels');
      points.forEach((point) => {
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', point.x.toFixed(1));
        text.setAttribute('y', String(height - 12));
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('font-size', compact ? '10' : '12');
        text.textContent = point.label;
        labelGroup.append(text);
      });
      [maxUv, minUv].forEach((uv, index) => {
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', compact ? '4' : '8');
        text.setAttribute('y', (index === 0 ? padding.top + 4 : height - padding.bottom).toFixed(1));
        text.setAttribute('font-size', compact ? '10' : '12');
        text.textContent = String(uv);
        labelGroup.append(text);
      });

      fragment.append(gridGroup, area, path, pointGroup, labelGroup);
      return fragment;
    }

    function renderTodoPanel() {
      const panel = workbenchPanel('待办事项', '优先完成有风险和有反馈压力的任务');
      const body = panel.querySelector('.admin-workspace-body');
      const todos = getOverview()?.todos || {};
      const list = el('div', 'admin-list compact');
      [
        ['待处理举报', `${todos.pending_reports_count || 0} 条`, '需要人工判断与处理'],
        ['已隐藏阵容', `${todos.hidden_lineups_count || 0} 条`, '可去阵容管理复核'],
        ['今日后台操作', `${todos.recent_audit_count || 0} 次`, '建议关注异常频繁操作'],
      ].forEach(([label, value, caption]) => {
        const card = el('article', 'admin-row-card');
        const info = el('div');
        info.append(el('strong', '', label), el('p', 'admin-meta', caption));
        card.append(info, el('span', 'admin-meta', value));
        list.append(card);
      });
      body.append(list);
      return panel;
    }

    function renderQuickLinks() {
      const panel = workbenchPanel('快捷入口', '按任务进入对应工作台');
      const body = panel.querySelector('.admin-workspace-body');
      const links = el('div', 'admin-quick-links');
      [
        ['去处理举报', '优先清理待处理问题', 'reports'],
        ['去查找阵容', '按阵容名、阵容码、作者查找', 'lineups'],
        ['去管理用户', '查找用户、改密、禁用', 'users'],
        ['查看增长分析', '查看转化漏斗与日期数据', 'analytics'],
        ['查看审计日志', '查看最近后台操作记录', 'audit'],
      ].forEach(([title, desc, tabKey]) => {
        const card = button(title, async () => activateTab(tabKey), 'admin-quick-link');
        card.append(el('span', 'admin-meta', desc));
        links.append(card);
      });
      body.append(links);
      return panel;
    }

    return renderOverviewDashboard;
  }

  global.JccAdminOverview = Object.freeze({ createOverviewRenderer });
})(window);
