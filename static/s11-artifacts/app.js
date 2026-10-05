(() => {
  'use strict';
  const themeToggle = document.querySelector('#themeToggle');
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    window.jccApplyThemeToggleState?.(theme, themeToggle, document.querySelector('#themeIcon'), document.querySelector('#themeText'));
    try { localStorage.setItem('theme', theme); } catch (_) { /* The control still works when storage is unavailable. */ }
  }
  applyTheme(document.documentElement.dataset.theme || 'light');
  themeToggle?.addEventListener('click', () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));

  const form = document.querySelector('#artifactSearch');
  const query = document.querySelector('#artifactQuery');
  const cards = [...document.querySelectorAll('.artifact-card')];
  const fees = [...form.querySelectorAll('button[name="cost"]')];
  const count = document.querySelector('#artifactCount');
  const empty = document.querySelector('#artifactEmpty');
  let cost = fees.find(button => button.getAttribute('aria-pressed') === 'true')?.value || '';
  let composing = false;
  const normalize = value => value.normalize('NFKC').toLowerCase();

  function filter(updateUrl = true) {
    const text = normalize(query.value.trim());
    const tokens = text.split(/\s+/).filter(Boolean);
    let found = 0;
    cards.forEach(card => {
      const visible = tokens.every(token => card.dataset.search.includes(token)) && (!cost || card.dataset.costs.split(' ').includes(cost));
      card.hidden = !visible;
      if (visible) found++;
      card.querySelectorAll('[data-champion]').forEach(champion => champion.classList.toggle('is-match', !!text && normalize(champion.dataset.champion).includes(text)));
    });
    count.textContent = text || cost ? `找到 ${found} / ${cards.length} 件神器` : `共 ${cards.length} 件神器`;
    empty.hidden = found > 0;
    fees.forEach(button => button.setAttribute('aria-pressed', String(button.value === cost)));
    document.querySelector('#artifactCost').value = cost;
    if (updateUrl) {
      const url = new URL(location.href);
      if (query.value.trim()) url.searchParams.set('q', query.value.trim()); else url.searchParams.delete('q');
      if (cost) url.searchParams.set('cost', cost); else url.searchParams.delete('cost');
      history.replaceState(null, '', url);
    }
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (event.submitter?.name === 'cost') cost = event.submitter.value;
    filter();
  });
  query.addEventListener('compositionstart', () => { composing = true; });
  query.addEventListener('compositionend', () => { composing = false; filter(); });
  query.addEventListener('input', () => { if (!composing) filter(); });

  function reset(event) {
    event.preventDefault();
    query.value = ''; cost = ''; filter(); query.focus({ preventScroll: true });
  }
  document.querySelector('#artifactReset').addEventListener('click', reset);
  document.querySelector('.artifacts-empty-reset').addEventListener('click', reset);
  document.querySelectorAll('[data-champion]').forEach(champion => {
    champion.addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      query.value = champion.dataset.champion; cost = ''; filter();
      form.scrollIntoView({ block: 'start', behavior: 'instant' });
      query.focus({ preventScroll: true });
    });
  });
  window.addEventListener('popstate', () => {
    const params = new URL(location.href).searchParams;
    query.value = (params.get('q') || '').slice(0, 100);
    cost = /^[1-5]$/.test(params.get('cost') || '') ? params.get('cost') : '';
    filter(false);
  });
  filter(false);
})();
