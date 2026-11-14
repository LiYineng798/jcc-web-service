/* Publish page: lineup codes (default) or deck submission (?type=submit); ?type=lineup / ?type=deck keep existing links working. */
(function () {
  'use strict';
  const tabs = [...document.querySelectorAll('[data-publish-type]')];
  if (!tabs.length) return;
  const deckPanel = document.getElementById('publishDeck');
  function select(type, focus = false) {
    tabs.forEach((tab) => {
      const active = tab.dataset.publishType === type;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      document.getElementById(tab.getAttribute('aria-controls')).hidden = !active;
      if (active && focus) tab.focus();
    });
    // The full deck editor is reached by its own link and leaves through the tabs.
    if (deckPanel) deckPanel.hidden = true;
    const params = new URLSearchParams(location.search);
    if (type === 'submit') params.set('type', 'submit'); else params.delete('type');
    params.delete('from');
    history.replaceState(history.state, '', `${location.pathname}${params.size ? `?${params}` : ''}`);
  }
  // With the full editor open no tab is selected; keep one focusable for keyboard users.
  if (!tabs.some((tab) => tab.getAttribute('aria-selected') === 'true')) tabs[0].tabIndex = 0;
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
