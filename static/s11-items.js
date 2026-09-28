(() => {
  'use strict';
  const root = document.querySelector('.ink-page');
  const toggle = root.querySelector('#themeToggle');
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    window.jccApplyThemeToggleState?.(theme, toggle, root.querySelector('#themeIcon'), root.querySelector('#themeText'));
    try { localStorage.setItem('theme', theme); } catch (_) { /* Theme works when storage is unavailable. */ }
  }
  applyTheme(document.documentElement.dataset.theme || 'light');
  toggle.addEventListener('click', () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  const input = root.querySelector('#ink-search');
  const filters = [...root.querySelectorAll('[data-cost]')];
  const groups = [...root.querySelectorAll('[data-group-cost]')].map(element => ({
    element, cards: [...element.querySelectorAll('.ink-card')],
  }));
  let cost = 'all';
  function update() {
    const terms = input.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    let total = 0;
    groups.forEach(({element, cards}) => {
      let count = 0;
      cards.forEach(card => {
        const matches = (cost === 'all' || cost === element.dataset.groupCost)
          && terms.every(term => card.dataset.search.toLocaleLowerCase().includes(term));
        card.hidden = !matches;
        if (matches) count++;
      });
      element.hidden = count === 0;
      element.querySelector('.ink-group-count').textContent = `${count} 位`;
      total += count;
    });
    filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.cost === cost)));
    root.querySelector('.ink-result').textContent = `共 ${total} 位弈子`;
    root.querySelector('.ink-empty').hidden = total > 0;
  }
  filters.forEach(button => button.addEventListener('click', () => { cost = button.dataset.cost; update(); }));
  input.addEventListener('input', update);
  root.querySelectorAll('.ink-reset').forEach(button => button.addEventListener('click', () => {
    cost = 'all'; input.value = ''; update(); input.focus();
  }));
  root.querySelector('.ink-controls').hidden = false;
  update();
})();
