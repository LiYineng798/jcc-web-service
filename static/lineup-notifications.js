(() => {
  const root=document.querySelector('#lineupNotificationRoot'); if(!root)return;
  const view=window.JccNoticeView;
  const toggle=root.querySelector('.ln-bell'),count=root.querySelector('.ln-count'),panel=root.querySelector('.ln-panel');
  const filters=panel.querySelector('.ln-filters'),list=panel.querySelector('.ln-list'),pagination=panel.querySelector('.ln-pagination');
  const title=panel.querySelector('h2');title.textContent='通知';
  const toolbar=document.createElement('div');toolbar.className='ln-toolbar';filters.before(toolbar);toolbar.append(filters);
  const stateFilter=document.createElement('select');stateFilter.className='ln-state-select';stateFilter.setAttribute('aria-label','通知状态');
  for(const [value,label] of [['all','全部状态'],['unread','仅未读'],['read','已读']]){const o=document.createElement('option');o.value=value;o.textContent=label;stateFilter.append(o);}toolbar.append(stateFilter);
  const back=document.createElement('button');back.type='button';back.className='ln-back';back.textContent='← 返回通知';back.hidden=true;toolbar.before(back);
  let session=null,category='all',status='all',page=1,requestId=0,detail=null,snapshot=null,scroll=0,focusKey=null,pendingClose=false;
  const el=(tag,cls='',text='')=>{const n=document.createElement(tag);n.className=cls;n.textContent=text;return n;};
  function button(text,action,cls){const b=el('button',cls,text);b.type='button';b.onclick=async()=>{b.disabled=true;try{await action();}catch(e){window.jccNotify.show(e.message,{variant:'error'});}finally{b.disabled=false;}};return b;}
  function setCount(n){count.textContent=n>99?'99+':String(n);count.hidden=!n;toggle.setAttribute('aria-label',n?`通知，${n} 条未读`:'通知，无未读');}
  function renderFilters(){filters.replaceChildren();for(const [key,label] of [['all','全部'],['interaction','互动'],['feedback','反馈'],['moderation','审核']]){const b=button(label,()=>{category=key;page=1;return load();},'ln-filter');b.setAttribute('aria-pressed',String(category===key));filters.append(b);}stateFilter.value=status;}
  async function mark(item){if(item.notice_state!=='unread')return;try{await session.api(`/api/me/notifications/${item.id}`,{method:'PUT',body:JSON.stringify({status:'read',revision:item.revision})});item.notice_state='read';if(snapshot){snapshot.unread_total=Math.max(0,snapshot.unread_total-1);setCount(snapshot.unread_total);}}catch{/* A newer revision stays unread. */}}
  function render(data){
    snapshot=data;setCount(data.unread_total);renderFilters();list.replaceChildren();pagination.replaceChildren();
    for(const item of data.items){
      const row=el('article',`ln-item ${item.notice_state==='unread'?'is-unread':''}`);row.dataset.noticeId=item.id;
      const open=button('',()=>openDetail(item),'ln-item-link');open.setAttribute('aria-label',`${view.labels[item.kind]}：${item.name}`);
      const content=el('span','ln-item-content'),meta=el('span','ln-item-meta');meta.append(el('span','ln-item-status',view.labels[item.kind]),el('time','ln-time',view.date(item.updated_at)));
      content.append(meta,el('strong','ln-item-name',item.name),el('span','ln-preview',item.body));if(item.category==='interaction')content.append(view.actors(item.actors));
      open.append(view.icon(item.kind),content);row.append(open);
      const next=item.notice_state==='unread'?'read':'unread';const read=button('',async()=>{await session.api(`/api/me/notifications/${item.id}`,{method:'PUT',body:JSON.stringify({status:next,revision:item.revision})});await load();},'ln-read-toggle');read.setAttribute('aria-label',next==='read'?'标记已读':'标记未读');read.title=read.getAttribute('aria-label');read.append(el('span','ln-read-dot'));row.append(read);list.append(row);
    }
    if(!data.items.length)list.append(el('p','ln-empty',status==='unread'?'都看过啦，新的消息会在这里等你。':'这里暂时没有消息。'));
    if(data.total_pages>1){const prev=button('上一页',()=>{page--;return load();},'ln-page-button');prev.disabled=page<=1;const next=button('下一页',()=>{page++;return load();},'ln-page-button');next.disabled=page>=data.total_pages;pagination.append(prev,el('span','',`${page} / ${data.total_pages}`),next);}pagination.hidden=data.total_pages<=1;
  }
  async function load(restore=false){
    if(!session||detail)return;const request=++requestId;const focused=document.activeElement;const filterFocus=filters.contains(focused);const rowFocus=focused?.closest('[data-notice-id]')?.dataset.noticeId;list.setAttribute('aria-busy','true');
    try{const data=await session.api(`/api/me/notifications?category=${category}&status=${status}&page=${page}&page_size=6`);if(request!==requestId||detail)return;page=data.page;render(data);if(filterFocus)filters.querySelector('[aria-pressed="true"]')?.focus({preventScroll:true});else if(rowFocus)list.querySelector(`[data-notice-id="${rowFocus}"] .ln-read-toggle`)?.focus({preventScroll:true});if(restore){list.scrollTop=scroll;list.querySelector(`[data-notice-id="${focusKey}"] .ln-item-link`)?.focus({preventScroll:true});}}
    catch(e){if(request!==requestId||detail)return;list.replaceChildren(el('p','ln-empty','消息暂时未送达'),button('重新加载',()=>load(restore),'ln-retry'));}finally{if(request===requestId)list.removeAttribute('aria-busy');}
  }
  async function openDetail(item,push=true){
    if(!detail){scroll=list.scrollTop;focusKey=item.id;}detail=item;++requestId;const request=requestId;
    if(push)history.pushState({...history.state,jccNotice:item.id},'');
    toolbar.hidden=true;pagination.hidden=true;back.hidden=false;title.textContent=view.labels[item.kind];list.classList.add('ln-detail');list.replaceChildren(el('p','ln-empty','正在展开…'));list.scrollTop=0;back.focus({preventScroll:true});
    try{
      if(item.category==='interaction'){view.interaction(item,list);await mark(item);}
      else if(item.kind==='feedback'){const data=await session.api(`/api/me/feedback/${item.feedback_id}`);if(request!==requestId)return;view.feedback(data,list);if(data.notification)await mark(data.notification);}
      else{const data=await session.api(`/api/lineups/${item.lineup_id}/moderation`);if(request!==requestId)return;view.moderation(data,list);if(data.moderation)await mark({id:item.id,...data.moderation});}
    }catch(e){if(request!==requestId)return;list.replaceChildren(el('p','ln-empty',e.message),button('重试',()=>openDetail(item,false),'ln-retry'));}
  }
  function showList(){detail=null;++requestId;toolbar.hidden=false;back.hidden=true;title.textContent='通知';list.classList.remove('ln-detail');if(snapshot)render(snapshot);list.scrollTop=scroll;load(true);}
  back.onclick=()=>{if(history.state?.jccNotice)history.back();else showList();};
  window.addEventListener('popstate',()=>{if(pendingClose){pendingClose=false;showList();hide(true);}else if(!history.state?.jccNotice&&detail)showList();else if(history.state?.jccNotice){const item=snapshot?.items.find(n=>n.id===history.state.jccNotice);if(item){panel.hidden=false;toggle.setAttribute('aria-expanded','true');position();openDetail(item,false);}}});
  function position(){if(panel.hidden)return;const edge=root.parentElement.getBoundingClientRect(),rect=toggle.getBoundingClientRect();const bottom=(visualViewport?.height||innerHeight)+(visualViewport?.offsetTop||0),top=Math.max(12,Math.min(rect.bottom+12,bottom-220));panel.style.top=`${top}px`;panel.style.right=`${Math.max(12,innerWidth-edge.right)}px`;panel.style.maxHeight=`${Math.max(160,bottom-top-12)}px`;}
  function hide(focus=false){panel.hidden=true;toggle.setAttribute('aria-expanded','false');if(focus)toggle.focus();}
  function close(focus=false){if(pendingClose)return;if(detail&&history.state?.jccNotice){pendingClose=true;history.back();}else hide(focus);}
  async function open(){if(!session)return;session.onOpen();panel.hidden=false;toggle.setAttribute('aria-expanded','true');position();panel.querySelector('.ln-close').focus({preventScroll:true});await load();}
  function setSession(value){const changed=session?.user?.id!==value.user?.id;session=value.user?value:null;root.hidden=!session;root.parentElement.classList.toggle('has-notifications',Boolean(session));if(!session){++requestId;detail=null;snapshot=null;toolbar.hidden=false;back.hidden=true;list.classList.remove('ln-detail');title.textContent='通知';hide();setCount(0);list.replaceChildren();return;}if(changed){
      const saved=history.state?.jccNoticeReturn;
      const returning=['back_forward','reload'].includes(performance.getEntriesByType('navigation')[0]?.type);
      if(returning&&saved?.owner===session.user.id&&saved.open){category=saved.category;status=saved.status;page=saved.page;open().then(()=>{if(saved.detail){openDetail(saved.detail,false);scroll=saved.listScroll||0;focusKey=saved.focusKey;}else list.scrollTop=saved.scroll;});return;}
      category='all';status='all';page=1;load();}
if(new URLSearchParams(location.search).get('notifications')==='open')open();}
  stateFilter.onchange=()=>{status=stateFilter.value;page=1;load();};toggle.onclick=()=>panel.hidden?open():close(true);panel.querySelector('.ln-close').onclick=()=>close(true);
  document.addEventListener('pointerdown',e=>{if(!root.contains(e.target)&&!panel.hidden)close();},true);
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden){e.preventDefault();if(detail)back.click();else close(true);}});
  window.addEventListener('resize',position);window.visualViewport?.addEventListener('resize',position);
  window.addEventListener('focus',()=>{if(session&&!detail)load();});window.addEventListener('pageshow',e=>{if(e.persisted&&session&&!detail)load();});
  window.addEventListener('pagehide',()=>{if(session)history.replaceState({...history.state,jccNoticeReturn:{owner:session.user.id,category,status,page,scroll:list.scrollTop,listScroll:scroll,focusKey,detail,open:!panel.hidden}},'');});
  window.JccLineupNotifications={setSession,close};
})();
