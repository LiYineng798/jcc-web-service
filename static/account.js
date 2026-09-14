// Browser integrations used by the /me React profile island.
(() => {
  if (location.hash === '#lineup-notifications') { location.replace('/?notifications=open'); return; }
  let leaving = false;
  window.addEventListener('pagehide', () => { leaving = true; });
  window.addEventListener('pageshow', () => { leaving = false; });
  async function request(url, options = {}) {
    if (leaving) throw new DOMException('Page is unloading', 'AbortError');
    const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...options });
    const payload = await response.json();
    if (!response.ok) throw Object.assign(new Error(payload.error || '加载失败，请稍后重试'), { status: response.status });
    return payload;
  }
  async function copyLineupCode(text) {
    try {
      if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); return true; }
    } catch (_) { /* Use the browser copy command as fallback. */ }
    const focused = document.activeElement;
    const textarea = document.createElement('textarea');
    textarea.value = text; textarea.readOnly = true;
    Object.assign(textarea.style, { position: 'fixed', opacity: '0', pointerEvents: 'none' });
    document.body.append(textarea); textarea.select(); textarea.setSelectionRange(0, textarea.value.length);
    try { return document.execCommand('copy'); }
    catch (_) { return false; }
    finally { textarea.remove(); focused?.focus?.({ preventScroll: true }); }
  }
  async function copy(item, csrfToken) {
    if (!await copyLineupCode(item.code)) throw new Error('复制失败，请打开阵容详情手动复制');
    window.jccNotify.show('阵容码已复制，可以返回游戏粘贴', { variant: 'success', title: '复制成功' });
    try {
      await request(`/api/lineups/${item.id}/copy?source=account`, { method: 'POST', headers: { 'X-CSRF-Token': csrfToken } });
    } catch (_) {
      window.jccNotify.show('阵容码已复制，但复制记录未同步，请稍后刷新', { variant: 'warning' });
    }
  }
  window.JccAccount = { request, copy };
})();
