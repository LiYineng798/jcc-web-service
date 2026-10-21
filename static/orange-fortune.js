(() => {
  'use strict';
  const form = document.querySelector('.fortune-filters');
  if (!form) return;
  const themeToggle = document.querySelector('#themeToggle');
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    window.jccApplyThemeToggleState?.(theme, themeToggle, document.querySelector('#themeIcon'), document.querySelector('#themeText'));
    try { localStorage.setItem('theme', theme); } catch (_) { /* Optional preference. */ }
  }
  applyTheme(document.documentElement.dataset.theme || 'light');
  themeToggle?.addEventListener('click', () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  const cards = [...document.querySelectorAll('.fortune-card')];
  const groups = [...document.querySelectorAll('.fortune-group')];
  const dialog = document.querySelector('.fortune-dialog');
  const query = form.elements.q;
  let activeCard = null;
  let returnFocus = null;
  const searchText = new Map(cards.map(card => [card, `${card.querySelector('.fortune-card-title').textContent} ${card.querySelector('.fortune-card-description').textContent} ${card.dataset.id}`.toLowerCase()]));
  function watchImage(img) {
    function fallback() {
      if (img.parentElement.querySelector('.fortune-missing')) return;
      img.hidden = true;
      const note = document.createElement('span');
      note.className = 'fortune-missing';
      note.textContent = '卡图暂不可用';
      img.parentElement.append(note);
    }
    img.addEventListener('error', fallback, { once: true });
    if (img.complete && !img.naturalWidth) fallback();
  }
  cards.forEach(card => card.querySelectorAll('img').forEach(watchImage));

  function updateURL(cardId = activeCard?.dataset.id) {
    const url = new URL(location.href);
    for (const key of ['q', 'tier', 'category', 'round']) {
      const value = String(new FormData(form).get(key) || '').trim();
      if (value) url.searchParams.set(key, value); else url.searchParams.delete(key);
    }
    if (cardId) url.searchParams.set('card', cardId); else url.searchParams.delete('card');
    history.replaceState(null, '', url);
  }

  function filter(writeURL = true) {
    const data = new FormData(form);
    const terms = query.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    let count = 0;
    cards.forEach(card => {
      card.hidden = Boolean((data.get('tier') && card.dataset.tier !== data.get('tier')) ||
        (data.get('category') && card.dataset.category !== data.get('category')) ||
        (data.get('round') && !card.dataset.rounds.split(' ').includes(data.get('round'))) ||
        !terms.every(term => searchText.get(card).includes(term)));
      if (!card.hidden) count++;
    });
    groups.forEach(group => {
      const visible = group.querySelectorAll('.fortune-card:not([hidden])').length;
      group.hidden = !visible;
      group.querySelector('.fortune-group-heading b').textContent = visible;
    });
    document.querySelector('#fortune-count strong').textContent = count;
    document.querySelector('.fortune-empty').hidden = count !== 0;
    if (writeURL) updateURL();
  }

  function openCard(card, writeURL = true) {
    activeCard = card;
    returnFocus = document.activeElement;
    const title = card.querySelector('.fortune-card-title').textContent;
    document.querySelector('#fortune-detail-title').textContent = title;
    document.querySelector('#fortune-detail-meta').textContent = `${card.dataset.tier} 星时间卡片 · ${card.querySelector('.fortune-card-category').textContent}`;
    document.querySelector('#fortune-detail-effect').textContent = card.querySelector('.fortune-card-description').textContent;
    const rounds = card.dataset.rounds.split(' ').filter(Boolean);
    document.querySelector('#fortune-detail-rounds').replaceChildren(...rounds.map((round, i) => {
      const span = document.createElement('span');
      span.textContent = `${i ? '后续回合' : '生效回合'} ${round}`;
      return span;
    }));
    const art = document.querySelector('.fortune-detail-art');
    art.dataset.tier = card.dataset.tier;
    art.replaceChildren(card.querySelector('.fortune-card-frame').cloneNode(true));
    art.querySelectorAll('img').forEach(img => { img.loading = 'eager'; watchImage(img); });
    document.querySelector('.fortune-copy-status').textContent = '';
    if (!dialog.open) dialog.showModal();
    document.body.style.overflow = 'hidden';
    dialog.scrollTop = 0;
    dialog.querySelector('.fortune-close').focus({ preventScroll: true });
    if (writeURL) updateURL();
  }
  cards.forEach(card => card.querySelector('button').addEventListener('click', () => openCard(card)));
  form.addEventListener('submit', event => { event.preventDefault(); filter(); });
  form.addEventListener('input', () => filter());
  form.addEventListener('change', () => filter());
  document.querySelectorAll('.fortune-reset').forEach(link => link.addEventListener('click', event => {
    event.preventDefault();
    form.elements.tier.value = '';
    query.value = '';
    form.elements.category.value = '';
    form.elements.round.value = '';
    filter();
    query.focus({ preventScroll: true });
  }));
  function closeCard() {
    activeCard = null;
    updateURL();
    dialog.close();
  }
  dialog.querySelector('.fortune-close').addEventListener('click', closeCard);
  dialog.addEventListener('cancel', event => { event.preventDefault(); closeCard(); });
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeCard();
  });
  dialog.addEventListener('close', () => {
    activeCard = null;
    document.body.style.overflow = '';
    updateURL();
    if (returnFocus?.getClientRects().length) returnFocus.focus({ preventScroll: true });
    else query.focus({ preventScroll: true });
  });
  document.querySelector('.fortune-copy-link').addEventListener('click', async () => {
    const url = new URL(location.pathname, location.origin);
    url.searchParams.set('card', activeCard.dataset.id);
    try {
      await navigator.clipboard.writeText(url.href);
      document.querySelector('.fortune-copy-status').textContent = '链接已复制，可直接打开这张卡片。';
      window.jccNotify?.show('卡片链接已复制', { variant: 'success' });
    } catch (_) {
      document.querySelector('.fortune-copy-status').textContent = '未能访问剪贴板，请复制浏览器地址栏中的卡片链接。';
    }
  });
  function restoreURL() {
    const params = new URLSearchParams(location.search);
    for (const key of ['q', 'tier', 'category', 'round']) form.elements[key].value = params.get(key) || '';
    if (!form.elements.tier.value) form.elements.tier.value = '';
    filter(false);
    const card = cards.find(item => item.dataset.id === params.get('card'));
    if (card) openCard(card, false); else if (dialog.open) dialog.close();
  }
  window.addEventListener('popstate', restoreURL);
  restoreURL();
})();
