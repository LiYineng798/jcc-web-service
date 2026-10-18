(() => {
  const labels = {pending:'已收到',in_progress:'核实中',resolved:'已解决',dismissed:'未采纳 / 无法复现'};
  const node = (tag, cls='', text='') => { const n=document.createElement(tag); n.className=cls; n.textContent=text; return n; };
  async function request(url, options={}) {
    const response = await fetch(url, {credentials:'same-origin', ...options});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || '请求失败，请稍后重试');
    return payload;
  }
  function timeline(data, target, adminView=false) {
    window.JccNoticeView.feedback(data,target,adminView);
  }
  async function openAdmin(source, sourceId, api, onChanged) {
    const dialog=node('dialog','fb-dialog');
    const head=node('header','fb-head');
    const title=node('h2','','反馈处理与站内回复'); title.id='feedbackAdminTitle'; dialog.setAttribute('aria-labelledby',title.id);
    const close=node('button','small-button','关闭'); close.type='button';
    const body=node('div','fb-body'); head.append(title,close); dialog.append(head,body); document.body.append(dialog);
    const opener=document.activeElement;
    let busy=false, changed=false, disposed=false;
    let hasDraft=()=>false;
    const leave=()=>{if(busy)return;if(hasDraft()&&!confirm('回复尚未发送，确定放弃并关闭吗？'))return; disposed=true;dialog.close();dialog.remove();opener?.focus();if(changed)Promise.resolve(onChanged?.()).catch(()=>{window.jccNotify?.show('回复已保存，列表刷新失败，请重新打开工作区。',{variant:'error'});});};
    close.onclick=leave; dialog.addEventListener('cancel',e=>{e.preventDefault();leave();}); dialog.showModal();
    async function load() {
      body.textContent='正在读取反馈…';
      try { const data=await api(`/api/admin/feedback/${source}/${sourceId}`); if(!disposed)render(data); }
      catch(error) { if(disposed)return;body.replaceChildren(node('p','fb-error',error.message));const retry=node('button','small-button','重新加载');retry.onclick=load;body.append(retry); }
    }
    function render(data) {
      timeline(data,body,true);body.scrollTop=0;
      const form=node('form','fb-reply');
      const statusLabel=node('label','','处理进度'), select=node('select');select.setAttribute('aria-label','处理进度');
      for(const [key,label] of Object.entries(labels)){const option=node('option','',label);option.value=key;select.append(option);} select.value=data.status;statusLabel.append(select);
      const replyLabel=node('label','','站内回复'), textarea=node('textarea'); textarea.setAttribute('aria-label','站内回复');textarea.maxLength=1000;textarea.rows=4;textarea.placeholder='说明核实进展、解决办法或无法复现的原因（最多 1000 字）';replyLabel.append(textarea);
      const hideLabel=node('label','fb-hide'), hide=node('input');hide.type='checkbox';hideLabel.append(hide,node('span','','同时隐藏该阵容'));const hideHint=node('small','','仅在标记已解决时生效，已封禁阵容不受影响。');hideLabel.append(hideHint);
      const error=node('p','fb-error');error.setAttribute('role','status');
      const save=node('button','primary-button','发送回复 / 更新进度');save.type='submit';
      hasDraft=()=>Boolean(textarea.value.trim() || select.value!==data.status || hide.checked);
      form.append(statusLabel,replyLabel);if(source==='report')form.append(hideLabel);form.append(error,save);body.append(form);
      form.onsubmit=async event=>{
        event.preventDefault();if(busy)return;
        if(['resolved','dismissed'].includes(select.value)&&!textarea.value.trim()){error.textContent='请填写处理结果，让用户知道原因。';textarea.focus();return;}
        busy=true;save.disabled=true;close.disabled=true;error.textContent='';
        try {
          const updated=await api(`/api/admin/feedback/${data.id}/reply`,{method:'POST',body:JSON.stringify({status:select.value,body:textarea.value,revision:data.revision,hide_lineup:hide.checked})});
          changed=true;render(updated);body.append(node('p','','已保存，用户可查看最新进度和回复。'));
        } catch(failure) {
          error.textContent=failure.message;
          const reload=node('button','small-button','重新读取最新进度');reload.type='button';reload.onclick=()=>{if(!textarea.value.trim()||confirm('重新读取会放弃当前未发送的回复，是否继续？'))load();};error.append(reload);
        } finally {busy=false;save.disabled=false;close.disabled=false;}
      };
    }
    await load();
  }
  window.JccFeedback={openAdmin};
  const target=document.querySelector('#feedbackDetail');
  if(target) {
    const id=target.dataset.feedbackId;
    const load=async()=>{
      try {
        const data=await request(`/api/me/feedback/${id}`);timeline(data,target);
        if(data.notification?.notice_state==='unread') {
          const me=await request('/api/me');
          await request(`/api/me/notifications/${data.notification.id}`,{method:'PUT',headers:{'Content-Type':'application/json','X-CSRF-Token':me.csrf_token},body:JSON.stringify({status:'read',revision:data.notification.revision})}).catch(()=>{});
        }
      }catch(error){target.replaceChildren(node('p','fb-error',error.message));const retry=node('button','small-button','重试');retry.onclick=load;const login=node('a','ghost-link','登录后查看');login.href='/auth';target.append(retry,login);}
    };load();
  }
})();
