(function(global) {
  const {el} = global.JccAdminCore;
  function createRenderer({workbenchPanel,button,empty}) {
    return function render(state,helpers) {
      const controls=el('form','experience-range');
      const start=el('input'), end=el('input');
      start.type=end.type='date'; start.value=state.start; end.value=state.end;
      start.required=end.required=true; start.max=end.max=helpers.today;
      const labelStart=el('label','','开始日期'); labelStart.append(start);
      const labelEnd=el('label','','结束日期'); labelEnd.append(end);
      const submit=el('button','small-button','查询'); submit.type='submit'; submit.disabled=state.loading;
      controls.append(labelStart,labelEnd,submit,
        button('近 7 天',()=>helpers.range(7),'small-button',state.loading),
        button('近 30 天',()=>helpers.range(30),'small-button',state.loading),
        button('刷新',()=>helpers.query(state.start,state.end,true),'small-button',state.loading));
      controls.addEventListener('submit',event=>{event.preventDefault();helpers.query(start.value,end.value,true);});
      const panel=workbenchPanel('搜索与设备','普通阵容列表搜索 · 最多查询 90 天 · 不含管理员',controls);
      panel.classList.add('admin-experience-panel');
      const body=panel.querySelector('.admin-workspace-body');
      const message=el('p','admin-meta'); message.setAttribute('role','status');
      message.textContent=state.loading ? '正在加载统计…' : state.error || '';
      body.append(message);
      if (state.error) {body.append(button('重试',()=>helpers.query(state.start,state.end,true),'small-button'));return panel;}
      if (!state.data) {if(!state.loading) body.append(empty('所选日期尚无统计数据。'));return panel;}
      const data=state.data,s=data.summary,cards=el('div','experience-stats');
      [['搜索次数',s.searches],['搜索人数',s.search_visitors],['无结果次数',s.zero_results],['无结果比例',s.searches ? `${s.zero_result_pct}%`:'—']].forEach(([label,value])=>{
        const card=el('article','admin-row-card');card.append(el('span','admin-meta',label),el('strong','',String(value)));cards.append(card);
      });
      body.append(el('p','admin-meta',`${data.start} 至 ${data.end} · 统计更新 ${data.generated_at}`),cards);
      const deviceSection=el('section','experience-section');
      deviceSection.append(el('h3','','按设备查看'),el('p','admin-meta','设备由浏览器标识粗略识别；旧记录保留为未知设备。访问按每天、访客和页面类型去重，同日换设备可能只保留首次记录。各设备人数可能重叠。'));
      const deviceTable=table(['设备','访问人数','页面访问记录','成功复制动作','复制人数','搜索次数','无结果比例'],data.devices.map(d=>[d.label,d.uv,d.pv,d.copies,d.copy_visitors,d.searches,d.searches?`${d.zero_result_pct}%`:'—']));
      deviceTable.classList.add('experience-device-table');
      const deviceCards=el('div','experience-device-cards');
      data.devices.forEach(d=>{
        const card=el('article','admin-row-card');
        card.append(el('strong','',d.label),el('p','admin-meta',`访问 ${d.uv} 人 · ${d.pv} 条记录`),
          el('p','admin-meta',`复制 ${d.copies} 次 · ${d.copy_visitors} 人`),
          el('p','admin-meta',`搜索 ${d.searches} 次`),el('p','admin-meta',`无结果 ${d.searches?d.zero_result_pct+'%':'—'}`));
        deviceCards.append(card);
      });
      deviceSection.append(deviceTable,deviceCards);
      deviceSection.append(el('p','admin-meta','复制包含普通与实时阵容的成功动作；复制人数与访问人数口径不同，不能直接视为访问转化率。'));
      body.append(deviceSection);
      if (!s.searches) body.append(empty('所选日期没有普通阵容搜索记录。新统计从本次版本启用后开始采集；普通用户在“最新”等列表搜索并停留后会产生记录。'));
      const grids=el('div','experience-keywords');
      [['热门搜索',data.top_queries,false],['无结果关键词',data.zero_queries,true]].forEach(([title,items,zero])=>{
        const section=el('section','experience-section');
        section.append(el('h3','',title),el('p','admin-meta',zero?'结合赛季和筛选判断原因；SS 无结果不等于整个赛季没有该阵容。':'按关键词、赛季和筛选分组，展示前 20 项。'));
        if (!items.length) section.append(empty(zero?'所选日期没有无结果搜索。':'所选日期没有搜索记录。'));
        else section.append(table(['关键词 / 条件','次数','人数',zero?'结果':'无结果'],items.map(item=>{
          const query=el('div');query.append(el('strong','',item.query),el('p','admin-meta',`${item.season_label} · ${item.sort_label}`));
          return [query,item.searches,item.visitors,zero?'0':item.zero_results];
        })));
        grids.append(section);
      });
      body.append(grids,el('p','admin-meta','搜索按名称匹配，仅记录成功展示且停留的普通阵容列表搜索；空关键词、翻页、恢复列表、加载失败和机器人请求不计入。收藏与个人阵容搜索不采集。搜索有结果表示匹配成功，不代表用户已复制或采用。'));
      return panel;
    };
  }
  function table(headers,rows) {
    const scroll=el('div','experience-table-wrap');scroll.tabIndex=0;scroll.setAttribute('aria-label',headers.join('、'));
    const table=el('table','admin-table experience-table'),head=el('thead'),body=el('tbody'),hr=el('tr');
    headers.forEach(value=>{const th=el('th','',value);th.scope='col';hr.append(th);});head.append(hr);
    rows.forEach(values=>{const row=el('tr');values.forEach(value=>{const td=el('td');if(value instanceof Node)td.append(value);else td.textContent=String(value);row.append(td);});body.append(row);});
    table.append(head,body);scroll.append(table);return scroll;
  }
  global.JccAdminExperience={createRenderer};
})(window);
