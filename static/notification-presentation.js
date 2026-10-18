/* Shared notification visuals for the homepage, account workspace and private details. */
(() => {
  const el=(tag,cls='',text='')=>{const n=document.createElement(tag);n.className=cls;n.textContent=text;return n;};
  const labels={like:'收到点赞',favorite:'收到收藏',copy:'收到复制',feedback:'反馈进度',moderation:'阵容审核'};
  const states={pending:'已收到',in_progress:'核实中',resolved:'已解决',dismissed:'未采纳 / 无法复现'};
  const paths={like:['M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z'],favorite:['M5 3h14v18l-7-4-7 4V3Z'],copy:['M9 9h12v12H9z','M15 5V3H3v12h2'],feedback:['M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7A8.4 8.4 0 0 1 4 11.5a8.5 8.5 0 0 1 4.7-7.6A8.4 8.4 0 0 1 12.5 3H13a8.5 8.5 0 0 1 8 8v.5Z'],moderation:['M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z','m9 12 2 2 4-4']};
  function icon(kind){
    const wrap=el('span',`nc-icon nc-${kind}`);wrap.setAttribute('aria-hidden','true');
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    for(const [key,value] of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':'1.7','stroke-linecap':'round','stroke-linejoin':'round'}))svg.setAttribute(key,value);
    for(const d of paths[kind]||paths.moderation){const p=document.createElementNS(svg.namespaceURI,'path');p.setAttribute('d',d);svg.append(p);}wrap.append(svg);return wrap;
  }
  const date=value=>value?.replace('T',' ').slice(0,16)||'';
  function actors(summary, expanded=false){
    const group=el('span',expanded?'nc-people nc-people-expanded':'nc-people');
    const users=summary?.users||[];
    if(!users.length){if(expanded)group.append(el('span','nc-caption','这份支持已记下，游客和较早的互动不展示头像。'));return group;}
    const stack=el('span','nc-avatar-circles');stack.setAttribute('aria-label',`${summary.total} 位棋友的互动`);
    for(const user of users){const avatar=el('img','nc-avatar');avatar.src=window.jccAvatar.getAvatarDataUrl('',{config:user.avatar_config});avatar.width=40;avatar.height=40;avatar.alt=user.nickname+'的头像';avatar.title=user.nickname;stack.append(avatar);}
    const more=summary.total-users.length;if(more>0){const count=el('span','nc-avatar nc-avatar-more',`+${more}`);count.setAttribute('aria-label',`还有 ${more} 位棋友`);stack.append(count);}

    const names=users.slice(0,2).map(u=>u.nickname).join('、');
    group.append(stack,el('span','nc-people-caption',`${names}${summary.total>2?` 等 ${summary.total} 位棋友`:''}`));
    if(expanded){const roster=el('span','nc-roster');for(const user of users)roster.append(el('span','',user.nickname));group.append(roster);}
    return group;
  }
  function hero(kind,title,subtitle){const head=el('div',`nc-hero nc-${kind}`);head.append(icon(kind),el('p','nc-eyebrow',labels[kind]),el('h3','nc-title',title));if(subtitle)head.append(el('p','nc-caption',subtitle));return head;}
  function interaction(item,target){
    target.replaceChildren();const section=el('section','nc-detail');section.append(hero(item.kind,item.name,'每一份支持，都让好阵容被更多人看见。'));
    const metrics=el('div','nc-metrics');const total=el('div');total.append(el('strong','',String(item.event_count)),el('span','',({like:'累计点赞',favorite:'累计收藏',copy:'有效复制'})[item.kind]));metrics.append(total);
    if(item.new_count>0){const recent=el('div');recent.append(el('strong','',`+${item.new_count}`),el('span','','本次新增'));metrics.append(recent);}section.append(metrics,actors(item.actors,true));
    const note=el('p','nc-caption nc-footnote',item.kind==='favorite'?'记录你曾收到的收藏；取消后再收藏不会重复计入。':item.kind==='copy'?'同一玩家短时间内重复复制只计一次，游客复制也会计入。':'记录功能启用后收到的赞，不包含你自己的操作。');section.append(note);
    if(item.url){const link=el('a','nc-action','查看阵容 ↗');link.href=item.url;link.setAttribute('aria-label','查看阵容');section.append(link);}else section.append(el('p','nc-caption','阵容已删除，这些支持仍为你保留。'));
    target.append(section);
  }
  function feedback(data,target,admin=false){
    target.replaceChildren();const section=el('section','nc-detail nc-feedback-detail');
    const head=hero('feedback',data.title,'');head.append(el('span',`nc-status nc-status-${data.status}`,states[data.status]));section.append(head);
    const progress=el('ol','nc-progress');const steps=['pending','in_progress',data.status==='dismissed'?'dismissed':'resolved'];const current=steps.indexOf(data.status);
    steps.forEach((state,index)=>{const step=el('li',index<=current?'is-done':'',states[state]);if(index===current)step.setAttribute('aria-current','step');progress.append(step);});section.append(progress);
    const original=el('div','nc-original');original.append(el('span','nc-eyebrow',admin?'用户反馈':'我的反馈'),el('p','',data.content));section.append(original);
    const list=el('ol','nc-timeline');
    for(const event of data.events.filter(e=>e.actor_role!=='user')){
      const row=el('li');const head=el('div','nc-event-head');head.append(el('strong','',event.actor_role==='admin'?'管理员回复':'处理记录'),el('time','',date(event.created_at)));row.append(head,el('span','nc-event-state',states[event.status]),el('p','',event.body));list.append(row);
    }
    if(!list.children.length)list.append(el('li','nc-waiting','反馈已送达，后续进展会在这里告诉你。'));
    section.append(list);target.append(section);
  }
  function moderation(data,target){
    target.replaceChildren();const section=el('section','nc-detail');const m=data.moderation;
    const state={banned:'需要修改',pending:'等待审核',rejected:'请补充修改',approved:'审核通过',released:'已解除封禁'};
    section.append(hero('moderation',data.lineup.name,state[m?.state]||'处理记录'));
    const card=el('div','nc-original');card.append(el('span','nc-eyebrow','处理说明'),el('p','',m?.review_note||m?.reason||'暂无补充说明'));section.append(card);
    const list=el('ol','nc-timeline');for(const event of data.events){const row=el('li');const head=el('div','nc-event-head');head.append(el('strong','',({ban:'封禁阵容',submit:'提交修改',approve:'审核通过',reject:'退回修改',release:'解除封禁'})[event.action]||'处理记录'),el('time','',date(event.created_at)));row.append(head,el('p','',event.reason||'处理状态已更新'));list.append(row);}section.append(list);
    const link=el('a','nc-action','查看阵容与处理选项 ↗');link.href=`/me?notice=moderation:${data.lineup.id}#lineup-notifications`;link.target='_blank';link.rel='noopener';section.append(link);target.append(section);
  }
  window.JccNoticeView={icon,actors,interaction,feedback,moderation,labels,date};
})();
