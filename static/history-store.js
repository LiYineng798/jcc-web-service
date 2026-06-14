(function () {
  const VIEW_KEY = 'jcc_guest_recent_views';
  const COPY_KEY = 'jcc_guest_recent_copies';
  const LIMIT = 20;

  function load(key) {
    try {
      return JSON.parse(localStorage.getItem(key) || '[]');
    } catch (_) {
      return [];
    }
  }

  function save(key, entries) {
    localStorage.setItem(key, JSON.stringify(entries.slice(0, LIMIT)));
  }

  function pushEntry(key, lineup) {
    const entries = load(key).filter((item) => item.lineup_id !== lineup.id);
    entries.unshift({
      lineup_id: lineup.id,
      at: new Date().toISOString().slice(0, 19).replace('T', ' '),
    });
    save(key, entries);
  }

  async function syncToAccount(csrfToken) {
    const views = load(VIEW_KEY);
    const copies = load(COPY_KEY);
    if (!views.length && !copies.length) return;
    await fetch('/api/me/history/sync', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken,
      },
      body: JSON.stringify({ views, copies }),
    });
    localStorage.removeItem(VIEW_KEY);
    localStorage.removeItem(COPY_KEY);
  }

  window.jccHistoryStore = {
    pushLocalView(lineup) {
      pushEntry(VIEW_KEY, lineup);
    },
    pushLocalCopy(lineup) {
      pushEntry(COPY_KEY, lineup);
    },
    syncToAccount,
  };
})();
