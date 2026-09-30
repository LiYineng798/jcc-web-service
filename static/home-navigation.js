(function (global) {
  const KEY = 'jccHomeReturn:v1';
  const MAX_AGE = 30 * 60 * 1000;
  let returnTarget = '';
  function stored() {
    try { return JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch (_) { return null; }
  }
  function valid(snapshot) {
    return snapshot?.version === 1 && Date.now() - snapshot.savedAt < MAX_AGE && Date.now() >= snapshot.savedAt;
  }
  function owner(user) { return user ? String(user.id) : 'guest'; }
  function capture(state, target = '') {
    const cards = [...document.querySelectorAll('#lineupList [data-lineup-key]')];
    const visible = cards.find(card => card.getBoundingClientRect().bottom > 0 && card.getBoundingClientRect().top < innerHeight);
    return {
      version: 1, savedAt: Date.now(), owner: owner(state.user), sort: state.sort, view: state.view,
      query: state.query, page: state.page, lineupSeason: state.selectedLineupSeasonId,
      liveSeason: state.selectedLiveCompSeasonId, y: scrollY,
      anchor: visible?.dataset.lineupKey || '', offset: visible?.getBoundingClientRect().top || 0,
      tabsX: document.querySelector('#tabs')?.scrollLeft || 0, target,
    };
  }
  function save(state, target = returnTarget) {
    returnTarget = target;
    const snapshot = capture(state, target);
    try { history.replaceState({ ...(history.state || {}), jccHome: snapshot }, '', location.href); } catch (_) {}
    try { sessionStorage.setItem(KEY, JSON.stringify(snapshot)); } catch (_) {}
    return snapshot;
  }
  function read(user) {
    const params = new URLSearchParams(location.search);
    const explicit = params.get('restore_list') === '1';
    const type = performance.getEntriesByType('navigation')[0]?.type;
    if (!explicit && !['back_forward', 'reload'].includes(type)) return null;
    const snapshot = explicit ? stored() : history.state?.jccHome;
    if (!valid(snapshot) || snapshot.owner !== owner(user)) return null;
    const pairs = new Set(['live-comps:live', 'all:latest', 'all:hot', 'all:rising', 'all:recommended', 'all:ss', 'favorites:latest', 'mine:latest']);
    if (!pairs.has(`${snapshot.view}:${snapshot.sort}`)) return null;
    if (!user && ['favorites','mine'].includes(snapshot.view)) return null;
    if (typeof snapshot.query !== 'string' || snapshot.query.length > 80 || !Number.isInteger(snapshot.page) || snapshot.page < 1 || snapshot.page > 100000) return null;
    return snapshot;
  }
  function consumeFlag() {
    const params = new URLSearchParams(location.search);
    if (!params.has('restore_list')) return;
    params.delete('restore_list');
    history.replaceState(history.state, '', `${location.pathname}${params.size ? '?'+params : ''}${location.hash}`);
  }
  async function restorePosition(snapshot) {
    if (!snapshot) return;
    const tabs = document.querySelector('#tabs');
    if (tabs) tabs.scrollLeft = snapshot.tabsX || 0;
    let cancelled = false;
    const cancel = () => { cancelled = true; };
    const keys = event => { if (['ArrowDown','ArrowUp','PageDown','PageUp','Home','End',' '].includes(event.key)) cancel(); };
    global.addEventListener('wheel', cancel, { once: true, passive: true });
    global.addEventListener('touchstart', cancel, { once: true, passive: true });
    global.addEventListener('keydown', keys);
    const position = () => {
      if (cancelled) return;
      const card = [...document.querySelectorAll('#lineupList [data-lineup-key]')].find(node => node.dataset.lineupKey === snapshot.anchor);
      const y = card ? scrollY + card.getBoundingClientRect().top - snapshot.offset : Number(snapshot.y) || 0;
      global.scrollTo({ top: Math.max(0,y), behavior: 'instant' });
    };
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    position();
    const observer = global.ResizeObserver ? new ResizeObserver(position) : null;
    if (observer && document.querySelector('#lineupList')) observer.observe(document.querySelector('#lineupList'));
    await new Promise(resolve => setTimeout(resolve, 700));
    position();
    observer?.disconnect();
    global.removeEventListener('wheel',cancel);
    global.removeEventListener('touchstart',cancel);
    global.removeEventListener('keydown',keys);
  }
  function install(state) {
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
    global.addEventListener('pagehide', () => save(state));
    document.addEventListener('click', event => {
      const link = event.target.closest('a[href]');
      if (!link) return;
      const url = new URL(link.href,location.href);
      if (url.origin === location.origin && /^\/(lineup|live-comps|author)\//.test(url.pathname)) save(state,url.pathname);
    }, true);
  }
  document.querySelectorAll('[data-home-return]').forEach(link => {
    const snapshot = stored();
    if (valid(snapshot) && snapshot.target === location.pathname) link.href = '/?restore_list=1';
    link.addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      let referrer;
      try { referrer = new URL(document.referrer); } catch (_) { return; }
      if (referrer.origin === location.origin && referrer.pathname === '/' && history.length > 1) {
        event.preventDefault(); history.back();
      }
    });
  });
  global.JccHomeNavigation = { save, read, install, restorePosition, consumeFlag };
})(window);
