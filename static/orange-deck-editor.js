/* Deck editor. Card rules mirror orange_fortune_service; the server repeats every check.
   The formation is edited in the creator simulator (deck mode, no browser storage) and kept
   as its structured payload plus the simulator's own trait result. */
(function () {
  'use strict';
  const D = window.JccOrangeDeck;
  const config = JSON.parse(document.getElementById('deckEditorConfig').textContent);
  const $ = (id) => document.getElementById(id);
  const deckId = $('deckEditor').dataset.deckId;
  const assistantSeason = $('deckEditor').dataset.assistantSeason || '';
  const cards = new Map(config.cards.map((card) => [card.id, card]));
  const portals = new Map(config.portals.map((portal) => [portal.id, portal]));
  const preview = new URLSearchParams(location.search).get('preview_release');
  let DRAFT_KEY = 'jcc-orange-deck-draft-v1' + (preview ? `:preview:${preview}` : '');
  const fields = { name: $('deckName'), plan_code: $('deckPlanCode'), note: $('deckNote'), key_rounds: $('deckRounds'), alternatives: $('deckAlternatives') };
  const state = { version: null, status: 'new', name: '', portal: config.portals[0].id, cards: [null, null, null], note: '', key_rounds: '',
    alternatives: '', plan_code: '', hiddenReason: '', formation: null, formationDirty: false, formationLocked: false, dirty: false, busy: false };
  let session = { csrf: '' }, activeSlot = 0;
  // On the shared publish page the lineup editor already owns the theme toggle.
  if (!document.getElementById('editorForm')) D.bindTheme();

  const notice = (lines) => {
    const box = $('deckEditorNotice');
    box.hidden = !lines.length;
    box.innerHTML = lines.map(D.esc).join('<br>');
  };
  const setError = (text) => { $('deckFormError').textContent = text || ''; };

  // ------------------------------------------------------------- deck rules
  function summary() {
    const selected = state.cards.map((id) => cards.get(id) || null);
    const portal = portals.get(state.portal);
    const energy = selected.reduce((sum, card) => sum + (card?.energy || 0), 0);
    const count = selected.filter(Boolean).length;
    return { selected, portal, energy, count, over: energy > portal.energy_limit };
  }

  function publishProblem() {
    const d = summary();
    if (!fields.name.value.trim()) return '请填写卡组名称';
    if (d.count < 3) return `还需选择 ${3 - d.count} 张时间卡片`;
    if (d.over) return `卡组能量 ${d.energy} 超出${d.portal.name}上限 ${d.portal.energy_limit}，请调整卡片或更换传送门`;
    return '';
  }

  function renderCards() {
    const d = summary();
    $('deckSlots').innerHTML = d.selected.map((card, index) => {
      const label = card ? `第 ${index + 1} 张：${card.name}，${card.tier_name}，能量 ${card.energy}。点击更换` : `选择第 ${index + 1} 张时间卡片`;
      return `<div class="deck-slot${card ? ' is-filled' : ''}"><button type="button" class="deck-thumb" data-slot="${index}" aria-haspopup="dialog" aria-label="${D.esc(label)}" data-tier="${card?.tier || ''}">${card ? D.art({ ...card, status: 'ok' }) : '<span class="deck-frame-empty">＋ 选卡</span>'}<span class="deck-thumb-name">${card ? D.esc(card.name) : `第 ${index + 1} 张`}</span><small>${card ? `${D.esc(card.tier_name)} · 能量 ${card.energy}` : '未选择'}</small></button>${card ? `<button type="button" class="deck-slot-remove" data-remove="${index}" aria-label="移除${D.esc(card.name)}">×</button>` : ''}</div>`;
    }).join('');
    const energy = $('deckEnergy');
    energy.classList.toggle('is-over', d.over);
    energy.innerHTML = `<span>卡组能量 <b>${d.energy}</b> / ${d.portal.energy_limit}（${D.esc(d.portal.name)}）</span><span>${d.over ? `超出 ${d.energy - d.portal.energy_limit} 点，公开发布前需要调整` : d.count === 3 ? '符合准入条件' : `已选 ${d.count} / 3 张，还可用 ${d.portal.energy_limit - d.energy} 点`}</span>`;
    document.querySelectorAll('#deckPortals label').forEach((label) => {
      const portal = portals.get(label.dataset.portal);
      const fit = d.count === 3 ? (d.energy > portal.energy_limit ? 'over' : 'fit') : '';
      label.dataset.fit = fit;
      label.querySelector('[data-fit]').textContent = fit === 'over' ? '当前卡组超限' : fit === 'fit' ? '当前卡组可进入' : '';
      label.querySelector('input').checked = label.dataset.portal === state.portal;
    });
  }

  function renderPicker() {
    const terms = $('pickerSearch').value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const tier = $('pickerTier').value, category = $('pickerCategory').value;
    const portal = portals.get(state.portal);
    const others = state.cards.reduce((sum, id, index) => sum + (index === activeSlot ? 0 : cards.get(id)?.energy || 0), 0);
    const budget = portal.energy_limit - others;
    const matches = config.cards.filter((card) => (!tier || String(card.tier) === tier) && (!category || card.category === category)
      && terms.every((term) => `${card.name} ${card.tier_name} ${card.description} ${card.rounds.join(' ')}`.toLowerCase().includes(term)));
    $('pickerTitle').textContent = `选择第 ${activeSlot + 1} 张时间卡片`;
    $('pickerBudget').textContent = budget > 0
      ? `${portal.name}上限 ${portal.energy_limit}，其他卡槽已用 ${others}：本槽选择能量 ≤ ${budget} 的卡片可满足准入条件。`
      : `${portal.name}上限 ${portal.energy_limit}，其他卡槽已用 ${others}：本槽任何卡片都会超限。`;
    $('pickerCount').textContent = `找到 ${matches.length} 张 · 已在其他卡槽的卡片不可重复选择`;
    $('pickerGrid').innerHTML = matches.length ? matches.map((card) => {
      const selected = state.cards[activeSlot] === card.id, occupied = !selected && state.cards.includes(card.id), over = card.energy > budget;
      return `<button type="button" class="deck-pick" data-card="${D.esc(card.id)}" data-tier="${card.tier}" aria-pressed="${selected}" ${occupied ? 'disabled' : ''} aria-label="${D.esc(`${card.name}，${card.tier_name}，能量 ${card.energy}${over ? '，会超出上限' : ''}${occupied ? '，已在其他卡槽' : ''}`)}">${D.art({ ...card, status: 'ok' })}<span class="deck-thumb-name">${D.esc(card.name)}</span><small class="deck-tier" data-tier="${card.tier}">${D.esc(card.tier_name)} · ${card.energy}${occupied ? ' · 已选' : ''}</small>${over ? '<span class="deck-pick-flag">超出上限</span>' : ''}<p>${D.esc(D.roundText(card))} · ${D.esc(card.description)}</p></button>`;
    }).join('') : '<p class="deck-boundary">没有匹配的卡片，试试其他关键词或品阶。</p>';
  }

  // ------------------------------------------------------------- formation
  const signature = (payload) => JSON.stringify([(payload?.board || []).map((slot) => slot && [slot.championId, slot.items]), payload?.augmentIds || []]);

  function viewFromMessage(message, payload) {
    return {
      available: true, issues: [], augments: [],
      unit_count: message.board.filter(Boolean).length,
      cells: message.board.map((slot, index) => slot && { name: slot.name, cost: slot.cost, icon: slot.icon, star: payload.board[index]?.star || 1,
        items: slot.items.map((item) => ({ name: item.name, icon: item.icon })) }),
      traits: message.traits.map((trait) => ({ name: trait.name, count: trait.count, icon: trait.icon, frame: trait.frame })),
    };
  }

  function mergeStars(previous, next) {
    // Keep a unit's star when it moves: match by champion and its nth appearance.
    const stars = new Map(), seen = new Map();
    (previous?.board || []).forEach((slot) => {
      if (!slot) return;
      const n = (seen.get(slot.championId) || 0) + 1;
      seen.set(slot.championId, n);
      stars.set(`${slot.championId}#${n}`, slot.star || 1);
    });
    seen.clear();
    next.board = (next.board || []).map((slot) => {
      if (!slot) return null;
      const n = (seen.get(slot.championId) || 0) + 1;
      seen.set(slot.championId, n);
      return { championId: slot.championId, items: [...slot.items], star: stars.get(`${slot.championId}#${n}`) || 1 };
    });
    return next;
  }

  function renderFormation() {
    const f = state.formation;
    $('formationPreview').innerHTML = f?.view ? D.board(f.view) : '';
    $('removeFormation').hidden = !f;
    $('openFormation').hidden = state.formationLocked;
    $('openFormation').textContent = f ? '修改阵容' : '配置阵容';
    const list = $('starList');
    const units = f && !state.formationLocked ? f.payload.board.map((slot, index) => slot && { slot, index, name: f.view?.cells[index]?.name || slot.championId }).filter(Boolean) : [];
    list.hidden = !units.length;
    list.innerHTML = units.map(({ slot, index, name }) => `<li><span>${D.esc(name)}</span><span role="radiogroup" aria-label="${D.esc(name)}的星级">${[1, 2, 3].map((star) => `<button type="button" role="radio" aria-checked="${slot.star === star}" data-star-slot="${index}" data-star="${star}" tabindex="${slot.star === star ? 0 : -1}">${star}★</button>`).join('')}</span></li>`).join('');
    if (!config.simulator_available && !f) $('formationStatus').textContent = '大橘大利阵容资料暂未开放，可以不配置阵容直接发布。';
    else if (state.formationLocked) $('formationStatus').textContent = '此阵容属于当前未开放或已更换的资料赛季，编辑器无法修改；保存时原样保留，也可以移除后重新配置。';
    else if (!f) $('formationStatus').textContent = '未配置阵容。不配置也可以发布。';
    else if (f.pending) $('formationStatus').textContent = '正在由阵容编辑器计算羁绊…';
    else $('formationStatus').textContent = `${f.view?.unit_count || 0} 个单位${state.formationDirty ? ' · 有未保存的阵容修改' : ''}`;
  }

  let frame = null, frameReady = false, frameTimer = null;
  function ensureFrame() {
    if (frame || !config.simulator_available) return;
    frame = document.createElement('iframe');
    frame.title = '大橘大利阵容编辑器';
    frame.src = '/tools/lineup-simulator?creator=orange-fortune&deck=1' + (preview ? `&preview_release=${encodeURIComponent(preview)}` : '');
    $('formationFrameSlot').append(frame);
    frameTimer = setTimeout(() => frameFailed('阵容编辑器加载超时'), 20000);
  }
  function frameFailed(message) {
    clearTimeout(frameTimer);
    frame?.remove();
    frame = null; frameReady = false;
    if (state.formation?.pending) state.formation.pending = false;
    $('formationStatus').textContent = `${message}，可以稍后点击“配置阵容”重试；不配置阵容也能发布。`;
  }
  function sendFormation() {
    if (frame && frameReady && state.formation?.payload) {
      frame.contentWindow.postMessage({ type: 'jcc:orange-formation-load', version: 1, payload: state.formation.payload }, location.origin);
    }
  }

  window.addEventListener('message', (event) => {
    if (!frame || event.origin !== location.origin || event.source !== frame.contentWindow) return;
    const data = event.data || {};
    if (data.type === 'jcc:orange-formation-error') { frameFailed('阵容资料暂时无法加载'); return; }
    if (data.type === 'jcc:orange-formation-ready' && data.version === 1) {
      clearTimeout(frameTimer);
      frameReady = true;
      sendFormation();
      return;
    }
    if (data.type === 'jcc:orange-formation-load-result') {
      if (!data.ok) notice([`阵容未能载入编辑器：${data.error}`]);
      else if (data.droppedUnits || data.droppedItems) notice([`当前资料中已不存在的 ${data.droppedUnits} 个弈子、${data.droppedItems} 件装备没有载入，保存后会从阵容中移除。`]);
      return;
    }
    if (data.type !== 'jcc:orange-formation' || data.version !== 1 || !frameReady || data.season !== config.season_id || !data.payload) return;
    const previous = state.formation;
    const payload = mergeStars(previous?.payload, structuredClone(data.payload));
    const changed = signature(previous?.payload) !== signature(payload) || Boolean(previous?.pending);
    if (!payload.board.some(Boolean)) {
      if (previous && changed) { state.formation = null; state.formationDirty = true; markDirty(); }
    } else {
      state.formation = { payload, traits: data.traits.map((trait) => ({ id: trait.id, count: trait.count, style: trait.style })), view: viewFromMessage(data, payload) };
      if (changed) { state.formationDirty = true; markDirty(); }
    }
    renderFormation();
  });

  $('openFormation').addEventListener('click', () => {
    ensureFrame();
    $('formationDialog').showModal();
  });
  $('closeFormation').addEventListener('click', () => $('formationDialog').close());
  $('formationDialog').addEventListener('close', () => $('openFormation').focus({ preventScroll: true }));
  $('removeFormation').addEventListener('click', () => {
    if (!confirm('移除此卡组的阵容站位？保存后生效。')) return;
    state.formation = null; state.formationLocked = false; state.formationDirty = true;
    frame?.remove(); frame = null; frameReady = false;
    markDirty(); renderFormation();
  });
  $('starList').addEventListener('click', (event) => {
    const button = event.target.closest('[data-star]');
    if (!button) return;
    const index = Number(button.dataset.starSlot), star = Number(button.dataset.star);
    state.formation.payload.board[index].star = star;
    if (state.formation.view?.cells[index]) state.formation.view.cells[index].star = star;
    state.formationDirty = true;
    markDirty(); renderFormation();
    $('starList').querySelector(`[data-star-slot="${index}"][data-star="${star}"]`)?.focus();
  });
  $('starList').addEventListener('keydown', (event) => {
    const button = event.target.closest('[data-star]');
    if (!button || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const star = Math.min(3, Math.max(1, Number(button.dataset.star) + (event.key === 'ArrowRight' ? 1 : -1)));
    $('starList').querySelector(`[data-star-slot="${button.dataset.starSlot}"][data-star="${star}"]`)?.click();
  });

  // Formation payloads from the poster tool still need the simulator's trait result.
  function adoptPayload(payload) {
    if (!payload?.board?.some(Boolean) || payload.season !== config.season_id || !config.simulator_available) return false;
    state.formation = { payload: mergeStars(null, structuredClone(payload)), traits: [], view: null, pending: true };
    state.formationLocked = false;
    state.formationDirty = true;
    ensureFrame();
    sendFormation();
    return true;
  }

  // ------------------------------------------------------------- persistence
  function collect() {
    Object.keys(fields).forEach((key) => { state[key] = fields[key].value; });
  }
  function markDirty() {
    state.dirty = true;
    setError('');
    if (state.status === 'new') {
      collect();
      try {
        localStorage.setItem(DRAFT_KEY, JSON.stringify({ version: 1, name: state.name, portal: state.portal, cards: state.cards, note: state.note,
          plan_code: state.plan_code, key_rounds: state.key_rounds, alternatives: state.alternatives, formation: state.formation && { payload: state.formation.payload, traits: state.formation.traits, view: state.formation.view } }));
        $('deckSaveState').textContent = '未提交的内容已暂存在当前浏览器';
      } catch { $('deckSaveState').textContent = '浏览器无法暂存，请在离开前保存'; }
    } else {
      $('deckSaveState').textContent = '有未保存的修改';
    }
  }

  function applyDeck(data) {
    Object.assign(state, { name: data.name || '', portal: portals.has(data.portal) ? data.portal : state.portal, note: data.note || '',
      plan_code: data.plan_code || '', key_rounds: data.key_rounds || '', alternatives: data.alternatives || '',
      // A card missing from current data leaves its slot empty; the notice names it, nothing is swapped in.
      cards: [0, 1, 2].map((index) => (cards.has(data.cards?.[index]) ? data.cards[index] : null)) });
    Object.keys(fields).forEach((key) => { fields[key].value = state[key]; });
  }

  function renderActions() {
    const status = state.status;
    const primary = $('savePrimary'), secondary = $('saveSecondary');
    secondary.hidden = status === 'hidden' || Boolean(assistantSeason);
    primary.textContent = status === 'hidden' ? '保存修改' : status === 'published' ? '保存并更新' : '发布';
    secondary.textContent = status === 'published' ? '撤回为草稿' : '保存草稿';
    $('deleteDeck').hidden = !deckId;
    primary.disabled = secondary.disabled = state.busy || Boolean(preview);
    if (preview) { primary.textContent = '预览中不可发布'; secondary.hidden = true; }
  }

  async function save(action) {
    if (state.busy || preview) return;
    collect();
    setError('');
    if (action !== 'draft') {
      const problem = publishProblem();
      if (problem) { setError(problem); return; }
    }
    if (state.formation?.pending) { setError('阵容还在计算羁绊，请稍候再保存。'); return; }
    const body = { action, name: state.name, plan_code: state.plan_code, portal: state.portal, cards: state.cards, note: state.note, key_rounds: state.key_rounds, alternatives: state.alternatives };
    if (assistantSeason) body.season_id = assistantSeason;
    if (state.formationDirty) body.formation = state.formation ? { payload: state.formation.payload, traits: state.formation.traits } : null;
    if (deckId) body.version = state.version;
    state.busy = true; renderActions();
    $('deckSaveState').textContent = '正在保存…';
    try {
      const data = await D.api(assistantSeason ? '/api/admin/assistant/decks' : deckId ? `/api/orange-decks/${deckId}` : '/api/orange-decks', { method: deckId ? 'PUT' : 'POST', body, csrf: session.csrf });
      state.dirty = false;
      if (!deckId) { try { localStorage.removeItem(DRAFT_KEY); } catch { /* Nothing stored. */ } }
      try { sessionStorage.setItem('jcc-orange-deck-notice', JSON.stringify([data.status === 'published' ? '卡组已发布。' : '已保存。'])); } catch { /* Optional. */ }
      location.href = data.status === 'draft' ? `/orange-decks/${data.id}/edit` : data.detail_url;
    } catch (error) {
      setError(error.message);
      $('deckSaveState').textContent = error.status === 409 ? '内容已在其他页面更新，请刷新后再编辑' : '保存未完成，修改仍保留在此页面';
      state.busy = false; renderActions();
    }
  }

  $('deckForm').addEventListener('submit', (event) => { event.preventDefault(); save(state.status === 'hidden' ? 'save' : 'publish'); });
  $('saveSecondary').addEventListener('click', () => save('draft'));
  $('deleteDeck').addEventListener('click', async () => {
    if (!confirm('确定删除这个卡组吗？删除后详情、搜索和分享链接都将失效。')) return;
    try {
      await D.api(`/api/orange-decks/${deckId}`, { method: 'DELETE', csrf: session.csrf });
      state.dirty = false;
      location.href = '/?library=decks&tab=mine';
    } catch (error) { setError(error.message); }
  });
  Object.values(fields).forEach((input) => input.addEventListener('input', markDirty));
  $('deckPortals').addEventListener('change', (event) => {
    if (event.target.name !== 'deckPortal') return;
    state.portal = event.target.value;
    renderCards(); markDirty();
  });
  $('deckSlots').addEventListener('click', (event) => {
    const remove = event.target.closest('[data-remove]');
    if (remove) { state.cards[Number(remove.dataset.remove)] = null; renderCards(); markDirty(); $('deckSlots').querySelector(`[data-slot="${remove.dataset.remove}"]`)?.focus(); return; }
    const slot = event.target.closest('[data-slot]');
    if (!slot) return;
    activeSlot = Number(slot.dataset.slot);
    renderPicker();
    $('cardPicker').showModal();
    $('pickerSearch').focus();
    $('pickerSearch').select();
  });
  ['pickerSearch', 'pickerTier', 'pickerCategory'].forEach((id) => $(id).addEventListener('input', renderPicker));
  $('pickerGrid').addEventListener('click', (event) => {
    const pick = event.target.closest('[data-card]');
    if (!pick || pick.disabled) return;
    state.cards[activeSlot] = pick.dataset.card;
    $('cardPicker').close();
    renderCards(); markDirty();
    $('deckSlots').querySelector(`[data-slot="${activeSlot}"]`)?.focus();
  });
  $('cardPicker').querySelector('[data-close]').addEventListener('click', () => $('cardPicker').close());
  // A search field would otherwise spend the first Escape on clearing its text.
  $('cardPicker').addEventListener('keydown', (event) => { if (event.key === 'Escape') { event.preventDefault(); $('cardPicker').close(); } });
  $('cardPicker').addEventListener('close', () => $('deckSlots').querySelector(`[data-slot="${activeSlot}"]`)?.focus({ preventScroll: true }));
  $('importCreator').addEventListener('click', () => importCreator(true));
  window.addEventListener('beforeunload', (event) => { if (state.dirty && !state.busy) { event.preventDefault(); event.returnValue = ''; } });

  function importCreator(confirmReplace) {
    let draft = null, formation = null;
    try {
      draft = JSON.parse(localStorage.getItem('jcc-orange-creator-v1' + (preview ? `:preview:${preview}` : '')) || 'null');
      const formationKey = preview ? `jcc-simulator-preview:${preview}:` : 'jcc-orange-formation-v1:';
      formation = config.season_id ? JSON.parse(localStorage.getItem(`${formationKey}${config.season_id}`) || 'null') : null;
    } catch { /* Read-only; unavailable storage simply means nothing to import. */ }
    if (!draft || draft.version !== 1) { notice(['没有找到海报创作者草稿。']); return; }
    const hasContent = state.cards.some(Boolean) || fields.name.value.trim() || state.formation;
    if (confirmReplace && hasContent && !confirm('用海报创作者草稿替换当前填写的卡片、名称和阵容？海报草稿本身不会改变。')) return;
    applyDeck({ name: String(draft.title || '').slice(0, 24), portal: draft.portal, cards: (draft.cards || []).filter((id) => cards.has(id)).concat([null, null, null]).slice(0, 3),
      note: String(draft.note || ''), key_rounds: String(draft.tempo || ''), alternatives: state.alternatives });
    const lines = ['已从海报创作者草稿导入；海报草稿本身没有改变。'];
    if (formation && !adoptPayload(formation)) lines.push('海报草稿中的阵容不属于当前资料赛季，未导入。');
    renderCards(); renderFormation(); markDirty(); notice(lines);
  }

  // ------------------------------------------------------------- boot
  async function boot() {
    const queued = (() => { try { const value = JSON.parse(sessionStorage.getItem('jcc-orange-deck-notice') || '[]'); sessionStorage.removeItem('jcc-orange-deck-notice'); return value; } catch { return []; } })();
    const me = await D.api('/api/me');
    if (assistantSeason) DRAFT_KEY = `jcc-assistant-deck-draft-v1:${me.user.id}:${assistantSeason}`;
    session = { csrf: me.csrf_token };
    if (deckId) {
      const deck = await D.api(`/api/orange-decks/${deckId}`);
      applyDeck({ ...deck, portal: deck.portal.id, cards: deck.cards.map((card) => card?.id || null) });
      Object.assign(state, { version: deck.version, status: deck.status, hiddenReason: deck.hidden_reason || '' });
      if (deck.formation_edit) {
        state.formationLocked = deck.formation_edit.season !== config.season_id || !config.simulator_available;
        state.formation = { payload: deck.formation_edit.payload, traits: deck.formation_edit.traits, view: null };
        D.api(`/api/orange-decks/${deckId}/formation`).then((data) => { if (state.formation && !state.formation.view) { state.formation.view = data.formation; renderFormation(); } })
          .catch(() => { $('formationStatus').textContent = '阵容预览加载失败；保存时会原样保留阵容。'; });
      }
      const hidden = deck.status === 'hidden' ? [`此卡组已被管理员隐藏${deck.hidden_reason ? `：${deck.hidden_reason}` : ''}。可以修改内容，恢复公开需要管理员处理。`] : [];
      const issues = deck.compat.issues.length ? ['资料变化：', ...deck.compat.issues] : [];
      notice([...queued, ...hidden, ...issues]);
    } else {
      const params = new URLSearchParams(location.search);
      let draft = null;
      try { draft = JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null'); } catch { /* No stored draft. */ }
      let fromCreator = params.get('from') === 'creator';
      if (fromCreator) {
        if (draft && !confirm('当前浏览器里还有一份未提交的卡组。用海报创作者草稿替换它吗？选择“取消”将继续编辑原来的内容。')) fromCreator = false;
        else { try { localStorage.removeItem(DRAFT_KEY); } catch { /* Nothing stored. */ } draft = null; }
      }
      params.delete('from');
      history.replaceState(history.state, '', `${location.pathname}${params.size ? `?${params}` : ''}`);
      if (fromCreator) importCreator(false);
      else if (draft?.version === 1) {
        applyDeck(draft);
        if (draft.formation?.payload?.season === config.season_id) state.formation = draft.formation;
        notice(['已恢复上次未提交的内容（仅保存在当前浏览器）。']);
      }
      state.status = 'new';
    }
    renderCards(); renderFormation(); renderActions();
    $('deckForm').removeAttribute('aria-busy');
    if (!state.dirty) $('deckSaveState').textContent = deckId ? `状态：${{ draft: '草稿', published: '已发布', hidden: '已隐藏' }[state.status]}` : assistantSeason ? '填写完成后发布到已授权赛季' : '填写完成后发布，或先保存为草稿';
  }
  boot().catch((error) => {
    setError(`编辑器加载失败：${error.message}`);
    const retry = document.createElement('button');
    retry.type = 'button'; retry.className = 'deck-button'; retry.textContent = '重新加载';
    retry.addEventListener('click', () => location.reload());
    $('deckSaveState').replaceChildren(retry);
  });
})();
