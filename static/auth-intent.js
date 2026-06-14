(function () {
  const KEY = 'jcc_pending_auth_intent';

  function save(intent) {
    sessionStorage.setItem(KEY, JSON.stringify(intent));
  }

  function read() {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (_) {
      sessionStorage.removeItem(KEY);
      return null;
    }
  }

  function clear() {
    sessionStorage.removeItem(KEY);
  }

  window.jccAuthIntent = { save, read, clear };
})();
