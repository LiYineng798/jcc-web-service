(() => {
  const themeToggle = document.querySelector('#themeToggle');
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    window.jccApplyThemeToggleState?.(theme, themeToggle, document.querySelector('#themeIcon'), document.querySelector('#themeText'));
    try { localStorage.setItem('theme', theme); } catch (_) { /* Keep working without storage. */ }
  }
  applyTheme(document.documentElement.dataset.theme || 'light');
  themeToggle?.addEventListener('click', () => {
    applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  });
  const links = [...document.querySelectorAll('[data-stack]')];
  const panels = [...document.querySelectorAll('.witch-result')];
  function select(stacks) {
    if (!links.some(link => link.dataset.stack === stacks)) return;
    links.forEach(link => {
      if (link.dataset.stack === stacks) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
    panels.forEach(panel => { panel.hidden = panel.id !== `rewards-${stacks}`; });
  }
  links.forEach(link => link.addEventListener('click', event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const url = new URL(location.href);
    url.searchParams.set('stacks', link.dataset.stack);
    history.pushState(null, '', url);
    select(link.dataset.stack);
  }));
  window.addEventListener('popstate', () => select(new URL(location.href).searchParams.get('stacks') || '365'));
})();
