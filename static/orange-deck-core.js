/* Shared rendering and requests for the Orange Fortune deck library (home list, detail, editor). */
(function (global) {
  'use strict';
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const roundText = (card) => (card.rounds?.length ? `生效 ${card.rounds.join(' / ')}` : '条件触发');

  async function api(url, options = {}) {
    const preview = new URLSearchParams(location.search).get('preview_release');
    if (preview) {
      const target = new URL(url, location.origin);
      target.searchParams.set('preview_release', preview);
      url = target.pathname + target.search;
    }
    const headers = { Accept: 'application/json', ...(options.headers || {}) };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (options.csrf) headers['X-CSRF-Token'] = options.csrf;
    const response = await fetch(url, { method: options.method || 'GET', headers, signal: options.signal,
      body: options.body === undefined ? undefined : JSON.stringify(options.body) });
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      const error = new Error(data?.error || (response.status >= 500 ? '服务暂时不可用，请稍后重试' : '操作未完成'));
      error.status = response.status;
      throw error;
    }
    return data;
  }

  async function recordCopy(deckId, csrf, codeType = 'plan') {
    if (!csrf) csrf = (await api('/api/me')).csrf_token;
    return api(`/api/orange-decks/${deckId}/copy?code_type=${encodeURIComponent(codeType)}`, { method: 'POST', csrf });
  }

  const art = card => global.FortuneCardArt.render(card);

  // Same portal glyphs as the gallery rules and the poster (orange_fortune.html, orange-creator.js).
  const PORTAL_MARKS = {
    stable: '<circle cx="32" cy="32" r="27"/><circle cx="32" cy="32" r="19"/><circle cx="32" cy="32" r="11"/><circle class="is-core" cx="32" cy="32" r="4"/>',
    volatile: '<path d="M32 5c9 3 14 0 20 7s2 13 7 20-1 14-7 20-13 3-20 7-14-2-20-7-2-13-7-20 3-14 7-20 11-4 20-7Z"/><path d="M32 14c6 2 9 0 13 5s1 9 5 13-1 9-5 13-9 2-13 5-9-1-13-5-1-9-5-13 2-9 5-13 7-3 13-5Z"/><circle class="is-core" cx="32" cy="32" r="5"/>',
    unknown: '<circle cx="32" cy="32" r="27" stroke-dasharray="3 5"/><circle cx="32" cy="32" r="18" stroke-dasharray="11 6"/><path class="is-core" d="M32 22l2.6 7.4L42 32l-7.4 2.6L32 42l-2.6-7.4L22 32l7.4-2.6Z"/>',
  };
  const portalMark = (id) => `<svg class="deck-portal-mark" viewBox="0 0 64 64" aria-hidden="true" focusable="false">${PORTAL_MARKS[id] || ''}</svg>`;

  function tierText(card) {
    return card.status === 'missing' ? '当前资料中不存在' : `${card.tier_name} · 能量 ${card.energy}`;
  }

  function thumb(card, index) {
    if (!card) return `<li><span class="deck-thumb">${art(null)}<span class="deck-thumb-name">第 ${index + 1} 张未选择</span></span></li>`;
    const flag = card.status === 'missing' ? '，已失效' : `，${tierText(card)}`;
    return `<li><button type="button" class="deck-thumb" data-card-index="${index}" data-tier="${esc(card.tier ?? '')}" data-status="${esc(card.status)}" aria-haspopup="dialog" aria-label="查看「${esc(card.name)}」完整效果${esc(flag)}">${art(card)}<span class="deck-thumb-name">${esc(card.name)}</span></button></li>`;
  }

  // Kicker (tier, energy, type), name, effect round, then the effect, matching orange_deck_macros.card_full.
  function cardFull(card, headingTag = 'h3', headingId = '') {
    const changes = (card.changes || []).map((text) => `<p class="deck-change">${esc(text)}</p>`).join('');
    const missing = card.status === 'missing';
    return `<div class="deck-card-full" data-status="${esc(card.status)}" data-tier="${esc(card.tier ?? '')}">${art(card)}<div class="deck-card-info">
      <p class="deck-card-kicker"><span class="deck-tier" data-tier="${esc(card.tier ?? '')}">${missing ? '当前资料中不存在' : esc(card.tier_name)}</span>${missing ? '' : `<span>能量 ${esc(card.energy)}</span>`}${card.category ? `<span>${esc(card.category)}</span>` : ''}</p>
      <${headingTag}${headingId ? ` id="${headingId}"` : ''}>${esc(card.name)}</${headingTag}>
      ${missing ? '' : `<p class="deck-rounds">${esc(roundText(card))}</p><p class="deck-card-effect">${esc(card.description)}</p>`}${changes}</div></div>`;
  }

  let dialog;
  function openCard(card, opener) {
    if (!dialog) {
      dialog = document.createElement('dialog');
      dialog.className = 'deck-dialog';
      dialog.setAttribute('aria-labelledby', 'deckCardDialogTitle');
      dialog.innerHTML = '<button type="button" class="deck-dialog-close" aria-label="关闭卡片效果">×</button><div data-deck-card-body></div>';
      dialog.querySelector('.deck-dialog-close').addEventListener('click', () => dialog.close());
      dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
      dialog.addEventListener('close', () => dialog.returnFocus?.focus({ preventScroll: true }));
      document.body.append(dialog);
    }
    dialog.returnFocus = opener;
    dialog.querySelector('[data-deck-card-body]').innerHTML = cardFull(card, 'h2', 'deckCardDialogTitle');
    if (!dialog.open) dialog.showModal();
  }

  // Same honeycomb as the simulator: 28 cells, rows of seven, offsets handled in CSS.
  function board(formation) {
    if (!formation) return '';
    if (!formation.available) return `<p class="deck-boundary">${esc(formation.message)}</p>`;
    const rows = formation.cells.map((cell) => {
      if (!cell) return '<li class="deck-cell" aria-hidden="true"><span class="deck-hex"></span></li>';
      const items = cell.items.map((item) => item.name).join('、');
      const label = `${cell.name}，${cell.star} 星${items ? `，装备：${items}` : ''}`;
      return `<li class="deck-cell has-unit cost-${Math.min(cell.cost || 1, 5)}${cell.missing ? ' is-missing' : ''}" aria-label="${esc(label)}" title="${esc(label)}"><span class="deck-unit"><span class="deck-unit-crop">${cell.icon ? `<img src="${esc(cell.icon)}" alt="" loading="lazy" decoding="async">` : ''}</span></span><span class="deck-unit-name" aria-hidden="true">${esc(cell.name)}</span><span class="deck-stars" aria-hidden="true">${'★'.repeat(cell.star)}</span><span class="deck-items" aria-hidden="true">${cell.items.map((item) => item.icon ? `<img src="${esc(item.icon)}" alt="" loading="lazy">` : '<i></i>').join('')}</span></li>`;
    }).join('');
    const traits = formation.traits.length
      ? `<ul class="deck-traits" aria-label="激活羁绊">${formation.traits.map((trait) => `<li><span class="deck-trait-emblem" aria-hidden="true"><img src="${esc(trait.frame)}" alt="">${trait.icon ? `<img src="${esc(trait.icon)}" alt="">` : ''}</span><b>${trait.count}</b><span>${esc(trait.name)}</span></li>`).join('')}</ul>`
      : '<p class="deck-boundary">没有激活的羁绊。</p>';
    const issues = formation.issues.length ? `<div class="deck-issues" role="note">${formation.issues.map(esc).join('<br>')}</div>` : '';
    const augments = formation.augments.length ? `<p class="deck-boundary">强化符文：${formation.augments.map(esc).join('、')}</p>` : '';
    return `${issues}<div class="deck-board-wrap"><ol class="deck-board" aria-label="阵容站位，${formation.unit_count} 个单位">${rows}</ol>${traits}</div>${augments}`;
  }

  function issues(deck) {
    if (!deck.compat?.issues?.length) return '';
    return `<div class="deck-issues" role="note"><strong>资料变化</strong><ul>${deck.compat.issues.map((text) => `<li>${esc(text)}</li>`).join('')}</ul></div>`;
  }

  async function copy(text) {
    try {
      if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); return true; }
    } catch { /* Fall back to a temporary selection. */ }
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.cssText = 'position:fixed;opacity:0;pointer-events:none';
    document.body.append(area);
    area.select();
    try { return document.execCommand('copy'); } catch { return false; } finally { area.remove(); }
  }

  function avatar(author, size, key) {
    try { return global.jccAvatar?.image(author.avatar_config, size, '', key) || null; } catch { return null; }
  }

  const notify = (message, variant = 'info') => global.jccNotify?.show(message, { variant });

  function bindTheme() {
    const toggle = document.getElementById('themeToggle');
    const apply = (theme) => {
      document.documentElement.dataset.theme = theme;
      global.jccApplyThemeToggleState?.(theme, toggle, document.getElementById('themeIcon'), document.getElementById('themeText'));
      try { localStorage.setItem('theme', theme); } catch { /* Theme still switches without storage. */ }
    };
    apply(document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');
    toggle?.addEventListener('click', () => apply(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  }

  global.JccOrangeDeck = { esc, api, recordCopy, art, portalMark, thumb, cardFull, openCard, board, issues, copy, avatar, notify, roundText, bindTheme };
})(window);
