/* Publish page: switch between lineup codes and Orange Fortune decks; the choice stays in ?type=. */
(function () {
  'use strict';
  const tabs = [...document.querySelectorAll('[data-publish-type]')];
  if (!tabs.length) return;
  function select(type, focus = false) {
    tabs.forEach((tab) => {
      const active = tab.dataset.publishType === type;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      document.getElementById(tab.getAttribute('aria-controls')).hidden = !active;
      if (active && focus) tab.focus();
    });
    const params = new URLSearchParams(location.search);
    if (type === 'deck') params.set('type', 'deck'); else params.delete('type');
    history.replaceState(history.state, '', `${location.pathname}${params.size ? `?${params}` : ''}`);
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => select(tab.dataset.publishType));
    tab.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
        : (index + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length;
      select(tabs[next].dataset.publishType, true);
    });
  });
})();
