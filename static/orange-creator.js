(() => {
  'use strict';
  const config = JSON.parse(document.querySelector('#creator-config').textContent);
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const cards = new Map(config.cards.map((card) => [card.id, card]));
  const storageKey = 'jcc-orange-creator-v1';
  const defaults = {title:'我的大橘大利卡组', author:'', target:'不标注', portal:'unspecified', customPortal:'', energy:'', note:'', background:'gilded', cards:[null,null,null]};
  let state = {...defaults, cards:[...defaults.cards]}, formation = null, activeSlot = 0, exporting = false;
  const notify = (message, variant = 'info') => window.jccNotify?.show(message, {variant});
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
    if (saved && saved.version === 1) {
      for (const [key, max] of Object.entries({title:24,author:16,customPortal:12,note:100})) state[key] = typeof saved[key] === 'string' ? saved[key].slice(0,max) : defaults[key];
      for (const [key, options] of Object.entries({target:config.targets, portal:config.portals.map(p=>p.id), background:config.backgrounds.map(b=>b.id)})) if (options.includes(saved[key])) state[key] = saved[key];
      if (/^\d{1,3}$/.test(saved.energy)) state.energy = saved.energy;
      if (Array.isArray(saved.cards)) { const seen = new Set(); state.cards = Array.from({length:3}, (_,i) => { const id = saved.cards[i]; if (!cards.has(id) || seen.has(id)) return null; seen.add(id); return id; }); }
    }
  } catch { $('save-status').textContent = '浏览器存储不可用；本次仍可编辑与导出'; }
  function save() {
    try { localStorage.setItem(storageKey, JSON.stringify({...state,version:1})); $('save-status').textContent = '草稿已自动保存 · 仅当前浏览器'; }
    catch { $('save-status').textContent = '草稿未能保存；请在离开前导出海报'; }
  }
  const image = (url, alt = '', cls = '') => `<img src="${esc(url)}" alt="${esc(alt)}" class="${cls}" decoding="async">`;
  function art(card) {
    return `<span class="fortune-card-frame"><span class="fortune-card-surface fortune-art-${esc(card.layout)}">${card.image ? image(card.image_url, '', 'fortune-card-image') : '<span class="fortune-missing"><i>◇</i>卡图暂缺</span>'}<span class="fortune-card-shade"></span><span class="fortune-card-stars" aria-label="${card.tier}星">${'•'.repeat(card.tier)}</span><span class="fortune-card-category">${esc(card.category)}</span></span>${$(`bezel-${card.tier}`).innerHTML}</span>`;
  }
  function renderSlots() {
    $('card-count').textContent = `${state.cards.filter(Boolean).length} / 3`;
    $('card-slots').innerHTML = state.cards.map((id,i) => {
      const card = cards.get(id);
      return `<div class="creator-slot-row"><button class="creator-slot ${card?'selected':''}" type="button" data-slot="${i}" aria-haspopup="dialog" aria-label="选择第${i+1}张卡片${card?`：${esc(card.name)}`:''}">${card?.image?image(card.image_url):`<span>${String(i+1).padStart(2,'0')}</span>`}<span><strong>${card?esc(card.name):'选择一张时间卡片'}</strong><small>${card?`${card.tier} 星 · ${esc(card.category)} · ${esc(card.rounds.join(' / ') || '条件触发')}`:'从时间卡片图鉴中挑选'}</small></span></button>${card?`<button type="button" class="creator-remove" data-remove="${i}" aria-label="移除${esc(card.name)}">×</button>`:''}</div>`;
    }).join('');
  }
  function picker() {
    const query = $('card-search').value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const tier = $('card-tier').value, category = $('card-category').value;
    const matches = config.cards.filter(c => (!tier || String(c.tier)===tier) && (!category || c.category===category) && query.every(term=>`${c.name} ${c.description} ${c.rounds.join(' ')}`.toLowerCase().includes(term)));
    $('picker-title').textContent = `选择第 ${activeSlot+1} 张时间卡片`;
    $('picker-count').textContent = `找到 ${matches.length} 张卡片 · 已在其他卡槽中的卡片不可重复选择`;
    $('picker-results').innerHTML = matches.length ? matches.map(card => {
      const selected = state.cards[activeSlot]===card.id, occupied = state.cards.includes(card.id) && !selected;
      return `<button type="button" class="creator-pick" data-card="${esc(card.id)}" data-tier="${card.tier}" aria-pressed="${selected}" ${occupied?'disabled':''} aria-label="选择${esc(card.name)}" title="${esc(card.description)}">${art(card)}<strong>${esc(card.name)}</strong><small>${card.tier} 星 · ${esc(card.rounds.join(' / ') || '条件触发')}${occupied?' · 已选择':''}</small><small class="pick-effect">${esc(card.description)}</small></button>`;
    }).join('') : '<p class="creator-help">没有匹配卡片，试试其他关键词或星级。</p>';
  }
  function portalName() {
    if (state.portal==='unspecified') return '';
    return state.portal==='custom' ? (state.customPortal.trim() || '其他传送门') : config.portals.find(p=>p.id===state.portal)?.name || '';
  }
  function energyError() {
    const energy = deckEnergy();
    if (state.energy && !/^\d{1,3}$/.test(state.energy)) return '总能量请输入 0–999 的整数，或留空不标注。';
    const limit = config.portals.find(p=>p.id===state.portal)?.energy_limit;
    return energy.value !== null && limit != null && energy.value>limit ? `${energy.automatic?'卡组':'手填'}能量超过${portalName()}的 ${limit} 点上限，请调整卡组或传送门。` : '';
  }
  function deckEnergy() {
    const selected = state.cards.map(id=>cards.get(id));
    const automatic = selected.every(card=>Number.isInteger(card?.energy) && card.energy>=0);
    return {automatic, value:automatic ? selected.reduce((sum,card)=>sum+card.energy,0) : state.energy!=='' ? Number(state.energy) : null};
  }
  function renderBoard() {
    const board = formation?.board || Array(28).fill(null);
    return Array.from({length:4},(_,row)=>`<div class="fp-board-row">${board.slice(row*7,row*7+7).map(unit=>`<div class="fp-cell"><span class="fp-hex"></span>${unit?`<span class="fp-unit">${image(unit.icon)}</span><span class="fp-unit-name">${esc(unit.name)}</span><span class="fp-items">${unit.items.map(item=>image(item.icon,item.name)).join('')}</span>`:''}</div>`).join('')}</div>`).join('') + (!board.some(Boolean)?'<div class="fp-board-empty"><strong>你的下一步，即是灵感</strong><span>配置阵容，点亮棋盘</span></div>':'');
  }
  function renderPoster() {
    const selected = state.cards.map(id=>cards.get(id));
    const energy = deckEnergy();
    $('deck-energy').disabled=energy.automatic;
    $('deck-energy').value=energy.automatic ? String(energy.value) : state.energy;
    const meta = [portalName(),state.target!=='不标注'?`计划目标 · ${state.target}`:'',energy.value!==null && Number.isFinite(energy.value)?`总能量 ${energy.value}${energy.automatic?'':'（手填）'}`:''].filter(Boolean);
    const title = state.title.trim() || defaults.title;
    $('poster-preview').innerHTML = `<article class="fortune-poster theme-${state.background}" aria-label="${esc(title)}海报"><header class="fp-header"><div><p class="fp-overline">英雄联盟传奇 / 时间卡组构筑</p><h1 class="${title.length>18?'fp-long-title':''}">${esc(title)}</h1><div class="fp-meta">${meta.map(m=>`<span>${esc(m)}</span>`).join('')}</div></div><div class="fp-brand"><b>大橘大利</b><small>FORTUNE ATELIER</small></div></header><div class="fp-content"><section><div class="fp-label">01 / 时间卡组 <small>THREE CARDS. ONE STRATEGY.</small></div><div class="fp-cards">${selected.map((card,i)=>`<section class="fp-card" ${card?`data-tier="${card.tier}"`:''}>${card?`<div class="fp-card-art">${art(card)}</div><p class="fp-card-number">TIME CARD / 0${i+1}</p><h2>${esc(card.name)}</h2><p class="fp-card-round">${card.tier} 星 · ${esc(card.rounds.join(' / ') || '条件触发')}</p><p class="fp-card-effect">${esc(card.description)}</p>`:`<div class="fp-card-empty">0${i+1}<span>等待你的王牌</span></div>`}</section>`).join('')}</div></section><section class="fp-right"><div class="fp-label">02 / 阵容蓝图 <small>${formation?.board.some(Boolean)?`${formation.population} 人口 · ${formation.board.filter(Boolean).length} 个单位`:'POSITION & SYNERGY'}</small></div><div class="fp-board">${renderBoard()}</div><div class="fp-traits">${formation?.traits.length ? formation.traits.slice(0,8).map(t=>`<span class="fp-trait">${t.icon?image(t.icon):''}<b>${t.count}</b>${esc(t.name)}</span>`).join('') + (formation.traits.length>8?`<span class="fp-trait">+ ${formation.traits.length-8} 个羁绊</span>`:'') : '<p class="fp-muted">上阵弈子后展示激活羁绊</p>'}</div><section class="fp-notebook"><div class="fp-label">03 / 运营手记 <small>THE GAME PLAN</small></div><p>${esc(state.note.trim() || '把握卡片生效的时刻，让每一步都通向你的目标。')}</p></section></section></div><footer class="fp-footer"><b>金铲铲阵容库</b><span>${state.author.trim()?`创作 / ${esc(state.author.trim())}`:'三张卡片，无限可能。'}</span><small>大橘大利 / 4:3 CREATOR SERIES</small></footer></article>`;
    fitPoster();
    fitText();
    const error = energyError();
    $('portal-help').textContent = error || (state.portal==='stable' ? '稳定传送门能量上限 8。卡片能量以游戏内为准；目标在局内逐步提升。' : '目标是创作计划；局内可随阶段选择更高挑战。');
    $('portal-help').classList.toggle('is-error',Boolean(error));
    const count = state.cards.filter(Boolean).length;
    const ready = count===3 && formation?.board.some(Boolean) && !error;
    $('export-poster').disabled = !ready || exporting;
    $('export-status').textContent = error || (count<3 ? `还需选择 ${3-count} 张时间卡片。` : !formation?.board.some(Boolean) ? '配置阵容后即可导出完整海报。' : '已就绪 · 导出 1600 × 1200 高清 PNG');
  }
  function fitPoster() {
    const poster = $('poster-preview').firstElementChild;
    if (poster) poster.style.transform = `scale(${$('poster-preview').clientWidth/config.export.width})`;
  }
  function fitText() {
    document.querySelectorAll('#poster-preview .fp-card-effect').forEach(el=>{
      let size=17;
      while(el.scrollHeight>el.clientHeight+1 && size>12) { size-=.5; el.style.fontSize=`${size}px`; }
    });
    const notebook = document.querySelector('#poster-preview .fp-notebook p');
    let size=20;
    while(notebook.scrollHeight>notebook.clientHeight+1 && size>15) {size-=.5;notebook.style.fontSize=`${size}px`;}
  }
  function update() { renderSlots(); renderPoster(); save(); }
  const fields = {'deck-name':'title','deck-author':'author','deck-target':'target','deck-portal':'portal','custom-portal':'customPortal','deck-energy':'energy','deck-note':'note'};
  for (const [id,key] of Object.entries(fields)) {
    $(id).value = state[key];
    $(id).addEventListener('input',()=>{
      state[key]=$(id).value;
      $('custom-portal-field').hidden=state.portal!=='custom';
      renderPoster(); save();
    });
  }
  $('custom-portal-field').hidden=state.portal!=='custom';
  document.querySelectorAll('[data-background]').forEach(button=>{
    button.setAttribute('aria-pressed',String(button.dataset.background===state.background));
    button.addEventListener('click',()=>{
      state.background=button.dataset.background;
      document.querySelectorAll('[data-background]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
      renderPoster();save();
    });
  });
  $('card-slots').addEventListener('click',event=>{
    const remove = event.target.closest('[data-remove]');
    if (remove) {state.cards[Number(remove.dataset.remove)]=null;update();return;}
    const slot=event.target.closest('[data-slot]'); if (!slot) return;
    activeSlot=Number(slot.dataset.slot);picker();$('card-picker').showModal();$('card-search').focus();
  });
  ['card-search','card-tier','card-category'].forEach(id=>$(id).addEventListener('input',picker));
  $('picker-results').addEventListener('click',event=>{
    const button=event.target.closest('[data-card]');if(!button || button.disabled) return;
    state.cards[activeSlot]=button.dataset.card;$('card-picker').close();update();
    document.querySelector(`[data-slot="${activeSlot}"]`).focus();
  });
  document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>$(button.dataset.close).close()));
  $('edit-formation').addEventListener('click',()=>$('formation-dialog').showModal());
  const frame=$('formation-frame');
  let formationTimer=frame?setTimeout(formationFailed,20000):null;
  function formationFailed() {
    clearTimeout(formationTimer);
    formation=null;
    $('formation-status').textContent='阵容资料暂时无法加载，请重试。';
    $('retry-formation').hidden=false;
    renderPoster();
  }
  $('retry-formation').addEventListener('click',()=>{
    if(!frame) return;
    $('retry-formation').hidden=true;
    $('formation-status').textContent='正在重新加载阵容资料…';
    formationTimer=setTimeout(formationFailed,20000);
    frame.src=frame.src;
  });
  window.addEventListener('message',event=>{
    if (event.origin!==location.origin || !frame || event.source!==frame.contentWindow) return;
    if(event.data?.type==='jcc:orange-formation-error') {formationFailed();return;}
    if(event.data?.type!=='jcc:orange-formation' || event.data.version!==1 || event.data.season!==config.season_id) return;
    formation=event.data;
    clearTimeout(formationTimer);
    $('retry-formation').hidden=true;
    $('formation-count').textContent=`${formation.board.filter(Boolean).length} 个单位`;
    $('formation-status').textContent=formation.storageSaved ? '已连接阵容编辑器 · 独立保存，不覆盖模拟器原有草稿' : '已连接阵容编辑器 · 阵容未能保存，请在离开前导出海报';
    renderPoster();
  });
  // An unavailable child document must leave a useful retry action, never a false ready state.
  frame?.addEventListener('load',()=>{
    try {if(!frame.contentDocument.querySelector('#simulatorRoot')) throw new Error();}
    catch {formationFailed();}
  });
  new ResizeObserver(fitPoster).observe($('poster-preview'));
  document.fonts?.ready.then(()=>{fitPoster();fitText();});
  async function prepareImages(root) {
    await Promise.all([...root.querySelectorAll('img')].map(async img=>{
      try {await img.decode();} catch {throw new Error('有图片尚未加载，请稍后重试。');}
      if(!img.naturalWidth) throw new Error('有图片加载失败，请刷新页面后重试。');
      // Inline decoded pixels before SVG capture, including local SVG trait icons.
      const canvas=document.createElement('canvas');
      canvas.width=img.naturalWidth;canvas.height=img.naturalHeight;
      canvas.getContext('2d').drawImage(img,0,0);
      img.src=canvas.toDataURL('image/png');
      await img.decode();
    }));
  }
  $('export-poster').addEventListener('click',async()=>{
    if(exporting || $('export-poster').disabled) return;
    exporting=true; const button=$('export-poster');button.disabled=true;button.textContent='正在生成…';
    let copy;
    try {
      await document.fonts.ready; fitText();
      copy=$('poster-preview').firstElementChild.cloneNode(true);
      copy.style.transform='none';copy.style.position='fixed';copy.style.left='-10000px';copy.style.top='0';
      copy.prepend(document.querySelector('.fortune-frame-materials').cloneNode(true));
      document.body.append(copy);await prepareImages(copy);
      const options={width:config.export.width,height:config.export.height,pixelRatio:1,skipFonts:true,cacheBust:false,style:{position:'static',left:'auto',top:'auto',zIndex:'auto',transform:'none'}};
      // WebKit's first foreignObject paint can omit decoded nested images.
      // Prime that paint before capturing the downloadable frame.
      await window.htmlToImage.toCanvas(copy,options);
      const data=await window.htmlToImage.toPng(copy,options);
      const link=document.createElement('a');link.href=data;link.download=`${(state.title.trim()||defaults.title).replace(/[\\/:*?"<>|\x00-\x1f]/g,'-')}-大橘大利.png`;link.click();
      notify('海报已生成，下载已开始','success');
    } catch(error) {notify(error.message || '海报生成失败，请重试','error');$('export-status').textContent=error.message || '导出失败，请重试';}
    finally {copy?.remove();exporting=false;button.textContent='导出海报 ↓';button.disabled=state.cards.filter(Boolean).length!==3 || !formation?.board.some(Boolean) || Boolean(energyError());}
  });
  renderSlots();renderPoster();
})();
