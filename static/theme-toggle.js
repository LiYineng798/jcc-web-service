(function () {
  window.jccApplyThemeToggleState = function (theme, themeToggle, themeIcon, themeText) {
    if (themeToggle) {
      themeToggle.classList.toggle('is-dark', theme === 'dark');
      themeToggle.setAttribute('aria-label', theme === 'dark' ? '切换为白天模式' : '切换为夜间模式');
    }
    if (themeIcon && !themeIcon.querySelector('svg')) {
      themeIcon.textContent = theme === 'dark' ? '☼' : '☾';
    }
    if (themeText) themeText.textContent = theme === 'dark' ? '白天模式' : '夜间模式';
  };
  if (document.body.hasAttribute('data-page-theme-toggle')) {
    const toggle = document.getElementById('themeToggle');
    const apply = theme => {
      document.documentElement.dataset.theme = theme;
      window.jccApplyThemeToggleState(theme, toggle, document.getElementById('themeIcon'), document.getElementById('themeText'));
    };
    apply(document.documentElement.dataset.theme || 'light');
    toggle.addEventListener('click', () => {
      const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      apply(theme);
      try { localStorage.setItem('theme', theme); } catch { /* Storage is optional. */ }
    });
  }
})();
