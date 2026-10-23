(function(global) {
  'use strict';
  const {el} = global.JccAdminCore;
  let sequence = 0;
  const observers = new Set();
  function destroy() { observers.forEach(observer => observer.disconnect()); observers.clear(); }
  const number = value => Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0;
  const fmt = value => number(value).toLocaleString('zh-CN');
  function chart({title, description, rows, series, headline, headlineLabel}) {
    const card = el('section', 'analytics-chart');
    const heading = el('div', 'analytics-chart-heading');
    const text = el('div');
    text.append(el('h3', '', title));
    if (headline !== undefined) {
      const value = el('div', 'analytics-chart-value', fmt(headline));
      value.append(el('span', '', headlineLabel || ''));
      text.append(value);
    }
    text.append(el('p', 'admin-meta', description));
    const glyph = el('span', 'analytics-chart-glyph'); glyph.setAttribute('aria-hidden', 'true');
    glyph.innerHTML = '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M4 15V9m6 6V4m6 11V7"/></svg>';
    heading.append(text, glyph);
    const plot = el('div', 'analytics-chart-plot');
    const legend = el('div', 'analytics-chart-legend');
    const detail = el('p', 'analytics-chart-detail', '悬停、轻触或聚焦柱形，查看精确数值');
    detail.setAttribute('role', 'status');
    const hidden = new Set();
    const id = `analytics-${++sequence}`;
    const ns = 'http://www.w3.org/2000/svg';
    function svgNode(tag, attrs = {}, content) {
      const node = document.createElementNS(ns, tag);
      Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
      if (content !== undefined) node.textContent = content;
      return node;
    }
    let plotWidth = 520;
    function draw() {
      const visible = series.filter(s => !hidden.has(s.key));
      const maximum = Math.max(1, ...rows.flatMap(row => visible.map(s => number(row[s.key]))));
      const magnitude = 10 ** Math.floor(Math.log10(maximum / 4));
      const interval = Math.max(1, [1,2,5,10].find(step => step*magnitude >= maximum/4)*magnitude);
      const top = interval * 4;
      const width = plotWidth, height = 240, left = width < 380 ? 30 : 40, right = 6, bottom = 196;
      const svg = svgNode('svg', {viewBox: `0 0 ${width} ${height}`, role:'group', 'aria-label':title});
      const defs = svgNode('defs');
      const pattern = svgNode('pattern', {id, width:7, height:7, patternUnits:'userSpaceOnUse', patternTransform:'rotate(40)'});
      pattern.append(svgNode('rect', {width:7,height:7,fill:'var(--analytics-hatch-bg)'}), svgNode('line', {x1:0,y1:0,x2:0,y2:7,stroke:'var(--accent)', 'stroke-width':2}));
      defs.append(pattern); svg.append(defs);
      for (let index = 0; index <= 4; index++) {
        const y = bottom - index * 42;
        svg.append(svgNode('line', {x1:left,x2:width-right,y1:y,y2:y,stroke:'var(--admin-border)','stroke-dasharray':'3 5'}));
        svg.append(svgNode('text', {x:left-9,y:y+4,'text-anchor':'end',class:'analytics-axis'}, new Intl.NumberFormat('zh-CN',{notation:'compact',maximumFractionDigits:1}).format(top*index/4)));
      }
      const step = (width-left-right)/Math.max(1,rows.length);
      rows.forEach((row, index) => {
        const center = left + step*(index+.5);
        const group = svgNode('g', {tabindex:0,role:'img','aria-label':`${row.label}：${visible.map(s=>`${s.label} ${fmt(row[s.key])}`).join('，')}`,class:'analytics-bar-group'});
        group.append(svgNode('rect',{x:left+index*step+2,y:20,width:step-4,height:bottom-16,fill:'transparent',rx:6}));
        const barWidth = Math.min(38, (step*.64)/Math.max(1,visible.length)-4);
        visible.forEach((s, si) => {
          const h = number(row[s.key])/top*168;
          const x = center - visible.length*(barWidth+4)/2 + si*(barWidth+4)+2;
          group.append(svgNode('rect', {x,y:bottom-h,width:barWidth,height:h,rx:6,fill:s.texture==='hatch'?`url(#${id})`:'var(--accent)',stroke:s.texture==='hatch'?'var(--accent)':'none','stroke-width':.8,class:'analytics-bar'}));
        });
        const reveal = () => {
          detail.textContent = `${row.label} · ${visible.map(s=>`${s.label} ${fmt(row[s.key])}`).join(' / ')}`;
          svg.querySelectorAll('.analytics-bar-group').forEach(g=>g.classList.toggle('is-active',g===group));
        };
        group.addEventListener('pointerenter',reveal); group.addEventListener('click',reveal); group.addEventListener('focus',reveal);
        group.addEventListener('pointerleave',()=>group.classList.remove('is-active'));
        group.addEventListener('blur',()=>group.classList.remove('is-active'));
        group.addEventListener('keydown',event=>{
          const groups=[...svg.querySelectorAll('.analytics-bar-group')];
          const target=event.key==='ArrowRight'?groups[index+1]:event.key==='ArrowLeft'?groups[index-1]:event.key==='Home'?groups[0]:event.key==='End'?groups.at(-1):null;
          if(target){event.preventDefault();target.focus();}
        });
        const label = svgNode('text',{x:center,y:218,'text-anchor':'middle',class:'analytics-axis'});
        const characters = [...String(row.label)];
        const perLine = Math.max(2, Math.floor((step-4)/11));
        for (let start=0;start<characters.length;start+=perLine) {
          label.append(svgNode('tspan',{x:center,dy:start?13:0},characters.slice(start,start+perLine).join('')));
        }
        svg.append(group,label);
      });
      plot.replaceChildren(svg);
    }
    series.forEach(s=>{
      const toggle=el('button','analytics-legend-item');toggle.type='button';toggle.setAttribute('aria-pressed','true');
      const swatch=el('i',s.texture==='hatch'?'is-hatched':'');toggle.append(swatch,document.createTextNode(s.label));
      toggle.addEventListener('click',()=>{
        if(hidden.has(s.key)) hidden.delete(s.key);
        else if(hidden.size<series.length-1) hidden.add(s.key);
        toggle.setAttribute('aria-pressed',String(!hidden.has(s.key)));draw();
        detail.textContent='已更新显示指标，可聚焦柱形查看数值。';
      });legend.append(toggle);
    });
    const details=el('details','analytics-data');
    const disclosure=svgNode('svg',{viewBox:'0 0 16 16',class:'analytics-disclosure','aria-hidden':'true',focusable:'false'});
    disclosure.append(svgNode('path',{d:'M4 6l4 4 4-4',fill:'none',stroke:'currentColor','stroke-width':1.5,'stroke-linecap':'round','stroke-linejoin':'round'}));
    const summary=el('summary');summary.append(el('span','','数据明细'),el('small','',`${rows.length} 个项目`),disclosure);details.append(summary);
    const table=el('table','analytics-data-table');table.setAttribute('aria-label',`${title}数据明细`);
    const head=el('thead'),tr=el('tr'),body=el('tbody');
    ['项目',...series.map(s=>s.label)].forEach(label=>{const th=el('th','',label);th.scope='col';tr.append(th);});head.append(tr);
    rows.forEach(row=>{const tr=el('tr');const th=el('th','',row.label);th.scope='row';tr.append(th);series.forEach(s=>tr.append(el('td','',fmt(row[s.key]))));body.append(tr);});
    table.append(head,body);const tableShell=el('div','analytics-table-shell');tableShell.append(table);details.append(tableShell);
    card.append(heading,plot,legend,detail,details);draw();
    const observer = new ResizeObserver(entries => {
      const next = Math.floor(entries[0].contentRect.width);
      if (next > 0 && next !== plotWidth) { plotWidth = next; draw(); }
    });
    observers.add(observer);observer.observe(plot);
    return card;
  }
  global.JccAnalyticsCharts={chart,destroy};
})(window);
