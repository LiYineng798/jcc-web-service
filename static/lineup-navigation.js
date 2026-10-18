/* Explicit, same-tab return context for ordinary lineup details. Never redirect off-site. */
(() => {
  const KEY='jccLineupOrigin:v1',MAX_AGE=30*60*1000;
  function safe(value){
    if(typeof value!=='string'||!value.startsWith('/')||value.startsWith('//')||value.includes('\\')||value.length>1500)return null;
    try{const url=new URL(value,location.origin);if(url.origin!==location.origin||!/^\/(?:me|admin|author\/[^/]+)?\/?$/.test(url.pathname))return null;url.searchParams.delete('return_to');return url.pathname+url.search+url.hash;}catch{return null;}
  }
  function source(){
    const current=location.pathname+location.search+location.hash;
    if(location.pathname==='/'&&document.querySelector('.ln-panel')&&!document.querySelector('.ln-panel').hidden)return '/?notifications=open';
    if(location.pathname==='/me'&&document.querySelector('.pf-dialog[open]'))return '/me#lineup-notifications';
    if(location.pathname==='/')return '/?restore_list=1';
    return safe(current)||'/';
  }
  document.addEventListener('click',event=>{
    const link=event.target.closest('a[href]');if(!link)return;const url=new URL(link.href,location.href);
    if(url.origin!==location.origin||!/^\/lineup\/\d+$/.test(url.pathname))return;
    const fallback=source();url.searchParams.set('return_to',fallback);link.href=url.pathname+url.search+url.hash;
    const sameTab=event.button===0&&!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.altKey&&(!link.target||link.target==='_self');
    if(sameTab){try{sessionStorage.setItem(KEY,JSON.stringify({target:url.pathname,fallback,from:location.href,created:Date.now()}));}catch{}}
  },true);
  const back=document.getElementById('lineupDetailBack');if(!back)return;
  const requested=safe(new URLSearchParams(location.search).get('return_to'));
  let record=history.state?.jccLineupOrigin;
  if(!record||record.target!==location.pathname||Date.now()-record.created>MAX_AGE){
    record=null;try{const pending=JSON.parse(sessionStorage.getItem(KEY)||'null');sessionStorage.removeItem(KEY);if(pending?.target===location.pathname&&Date.now()-pending.created<15000&&Date.now()>=pending.created&&safe(pending.fallback)){record=pending;history.replaceState({...history.state,jccLineupOrigin:record},'');}}catch{}
  }
  const fallback=safe(record?.fallback)||requested||'/';back.href=fallback;
  const label=fallback.includes('notifications')?'返回通知':fallback.startsWith('/me')?'返回个人中心':fallback.startsWith('/author/')?'返回作者主页':fallback.startsWith('/admin')?'返回管理后台':'返回阵容库';
  back.querySelector('span').textContent=label;
  back.addEventListener('click',event=>{if(event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;if(record&&history.length>1){event.preventDefault();history.back();}});
})();
