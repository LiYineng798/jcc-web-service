(() => {
  const root=document.querySelector('#lineupDetailApp');if(!root)return;
  const $=id=>document.getElementById(id), id=root.dataset.lineupId;
  let user=null,token='',lineup=null,controller=null,busy=false,reportBusy=false,booting=false,avatarKey='';
  const buttons=['ldCopy','ldLike','ldFavorite','ldReport','ldShare'];
  function message(text,error=false){$('ldActionStatus').textContent=text;$('ldActionStatus').classList.toggle('is-error',error);}
  async function api(path,options={}){const response=await fetch(path,{credentials:'same-origin',cache:'no-store',signal:controller?.signal,...options,headers:{'Content-Type':'application/json','X-CSRF-Token':token,...options.headers}});const data=await response.json();if(!response.ok)throw Object.assign(new Error(data.error||'请求失败，请稍后重试'),{status:response.status});return data;}
  function update(){if(!lineup)return;$('ldLikes').textContent=lineup.like_count;$('ldCopies').textContent=lineup.copy_count;$('ldRank').textContent=lineup.rank_level;$('ldUpdated').textContent=lineup.updated_at.slice(0,16);$('ldCode').textContent=lineup.code;root.querySelector('h1').textContent=lineup.name;
    const nextAvatar=JSON.stringify([lineup.owner_avatar_config,lineup.owner_avatar_color,lineup.owner_nickname]);if(nextAvatar!==avatarKey){avatarKey=nextAvatar;$('ldAvatar').replaceChildren(window.jccAvatar.image(lineup.owner_avatar_config||lineup.owner_avatar_color,44,lineup.owner_nickname+'的头像'));}
    for(const key of buttons)if($(key))$(key).disabled=busy||!lineup.can_interact;
    $('ldLike').setAttribute('aria-pressed',String(lineup.is_liked_today));$('ldLike').querySelector('span').textContent=lineup.is_liked_today?'今日已赞':'点赞';$('ldLike').disabled=busy||!lineup.can_interact||lineup.is_liked_today;
    $('ldFavorite').setAttribute('aria-pressed',String(lineup.is_favorited));$('ldFavorite').querySelector('span').textContent=lineup.is_favorited?'已收藏':'收藏';
    if($('ldShare'))$('ldShare').hidden=lineup.status!=='normal';root.querySelector('.ld-manage')?.toggleAttribute('hidden',!lineup.can_edit);
    const restriction=$('ldRestriction');restriction.hidden=lineup.status==='normal';
    if(lineup.status==='banned'){restriction.textContent='此阵容已封禁，暂不可复制或互动。';const m=lineup.moderation;if(m?.reason){const p=document.createElement('p');p.textContent=m.reason;restriction.append(p);}const a=document.createElement('a');a.textContent=lineup.can_moderate?'前往管理后台':'查看处理详情与申请重审';a.href=lineup.can_moderate?'/admin':`/me?notice=moderation:${id}#lineup-notifications`;restriction.append(a);}
    else if(lineup.status==='hidden')restriction.textContent='此阵容已隐藏，仅作者和管理员可查看。';
  }
  async function boot(record=true){if(booting)return;booting=true;controller?.abort();controller=new AbortController();$('ldRetry').hidden=true;
    try{const me=await api('/api/me');user=me.user;token=me.csrf_token;lineup=await api(`/api/lineups/${id}`);update();message(lineup.can_interact?'复制后即可前往游戏粘贴使用。':'此阵容当前不可互动。');
      if(record){if(user)api(`/api/lineups/${id}/view`,{method:'POST'}).catch(()=>{});else window.jccHistoryStore?.pushLocalView(lineup);}
    }catch(e){if(e.name==='AbortError')return;lineup=null;message(e.status===404?'阵容已不可用，请返回查看其他阵容。':'互动状态暂时无法同步，仍可选中阵容码手动复制。',true);$('ldRetry').hidden=false;$('ldSelectCode').hidden=false;for(const key of buttons)if($(key))$(key).disabled=true;}finally{booting=false;}
  }
  async function clipboard(text){try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);return true;}}catch{}
    const input=document.createElement('textarea'),focused=document.activeElement;input.value=text;input.readOnly=true;Object.assign(input.style,{position:'fixed',opacity:'0',pointerEvents:'none'});document.body.append(input);input.select();input.setSelectionRange(0,input.value.length);try{return document.execCommand('copy');}catch{return false;}finally{input.remove();focused?.focus({preventScroll:true});}
  }
  function loginHint(){message('登录后即可点赞、收藏和跟进反馈。');const a=document.createElement('a');a.textContent='登录后继续';a.href='/auth?next='+encodeURIComponent(location.pathname+location.search);$('ldActionStatus').append(a);return !user;}
  async function act(action){if(busy||!lineup?.can_interact)return;busy=true;update();try{await action();}catch(e){message(e.message,true);if(e.status===401)loginHint();if([404,409].includes(e.status))await boot(false);}finally{busy=false;update();}}
  $('ldCopy').onclick=()=>act(async()=>{
    if(!await clipboard(lineup.code)){$('ldSelectCode').hidden=false;throw new Error('浏览器未能复制，请点击“选中阵容码”后手动复制。');}
    message('阵容码已复制，去游戏里试试吧。');window.jccAvatar.feedback($('ldAvatar').firstElementChild,'copy');
    if(!user)window.jccHistoryStore?.pushLocalCopy(lineup);
    try{const result=await api(`/api/lineups/${id}/copy?source=detail`,{method:'POST'});if(result.counted)lineup.copy_count+=1;}catch{message('阵容码已复制，复制记录暂未同步。');}
  });
  $('ldShare')?.addEventListener('click',()=>act(async()=>{if(!await clipboard(location.origin+location.pathname))throw new Error('链接复制失败，请从地址栏复制。');message('分享链接已复制。');}));
  $('ldLike').onclick=()=>{if(!user){loginHint();return;}act(async()=>{const result=await api(`/api/lineups/${id}/like`,{method:'POST'});lineup=result.lineup;message('谢谢你的支持，作者会收到这份心意。');window.jccAvatar.feedback($('ldAvatar').firstElementChild,'like');});};
  $('ldFavorite').onclick=()=>{if(!user){loginHint();return;}act(async()=>{const removing=lineup.is_favorited;await api(`/api/lineups/${id}/favorite`,{method:removing?'DELETE':'POST'});lineup.is_favorited=!removing;message(removing?'已取消收藏。':'已收藏，可以在个人中心随时找到。');});};
  $('ldSelectCode').onclick=()=>{const selection=getSelection(),range=document.createRange();range.selectNodeContents($('ldCode'));selection.removeAllRanges();selection.addRange(range);$('ldCode').focus();};$('ldRetry').onclick=()=>boot(false);
  const dialog=$('ldReportDialog'),form=$('ldReportForm');
  $('ldReport').onclick=()=>{if(!user){loginHint();return;}$('ldReportError').textContent='';dialog.showModal();$('ldReportReason').focus();};
  function closeReport(){if(reportBusy)return;if($('ldReportReason').value.trim()&&!$('ldReportSubmit').hidden&&!confirm('反馈尚未提交，确定关闭吗？'))return;dialog.close();$('ldReport').focus();}
  $('ldReportClose').onclick=closeReport;dialog.addEventListener('cancel',event=>{event.preventDefault();closeReport();});
  form.onsubmit=async event=>{event.preventDefault();if(reportBusy)return;const reason=$('ldReportReason').value.trim();if(!reason){$('ldReportError').textContent='请先描述遇到的问题。';return;}reportBusy=true;$('ldReportSubmit').disabled=true;$('ldReportClose').disabled=true;
    try{const receipt=await api(`/api/lineups/${id}/report`,{method:'POST',body:JSON.stringify({reason})});$('ldReportResult').textContent='反馈已收到，后续处理进度会在通知中心更新。';const a=document.createElement('a');a.href=receipt.feedback_url;a.textContent='查看反馈进度 →';$('ldReportResult').append(document.createElement('br'),a);$('ldReportSubmit').hidden=true;$('ldReportReason').disabled=true;$('ldReportError').textContent='';}
    catch(e){$('ldReportError').textContent=e.message;}finally{reportBusy=false;$('ldReportSubmit').disabled=false;$('ldReportClose').disabled=false;}
  };
  window.addEventListener('pagehide',()=>controller?.abort());window.addEventListener('pageshow',event=>{if(event.persisted){booting=false;busy=false;boot(false);}});boot();
})();
