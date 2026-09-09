(() => {
  'use strict';
  const titles = { success: '操作成功', info: '提示', warning: '请注意', error: '操作未完成' };
  const paths = {
    success: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
    warning: '<path d="m12 3 10 18H2L12 3Zm0 6v5m0 3v1"/>',
    error: '<circle cx="12" cy="12" r="9"/><path d="M12 7v7m0 3v1"/>',
  };
  const items = new Set();
  const dialogs = new WeakSet();
  let host;
  let sequence = 0;
  function position() {
    if (!host) return;
    const limit = matchMedia('(max-width: 640px)').matches ? 3 : 4;
    while (items.size > limit) items.values().next().value.close();
    const viewport = window.visualViewport;
    host.style.setProperty('--notification-offset', `${viewport?.offsetTop || 0}px`);
    host.style.setProperty('--notification-height', `${viewport?.height || innerHeight}px`);
  }
  function reveal() {
    if (host.showPopover && !host.matches(':popover-open')) host.showPopover();
  }
  function container() {
    if (!host) {
      host = document.createElement('section');
      host.className = 'jcc-notifications';
      host.setAttribute('aria-label', '操作通知');
      host.setAttribute('popover', 'manual');
    }
    const open = [...document.querySelectorAll('dialog[open]')];
    const dialog = open[open.length - 1];
    const parent = dialog || document.body;
    if (host.parentElement !== parent) parent.append(host);
    if (dialog && !dialogs.has(dialog)) {
      dialogs.add(dialog);
      dialog.addEventListener('close', () => {
        if (host.parentElement === dialog) {
          document.body.append(host);
          if (items.size) reveal();
        }
      });
    }
    position();
    reveal();
    return host;
  }
  function show(message, options = {}) {
    if (!message) return;
    const variant = Object.hasOwn(titles, options.variant) ? options.variant : 'info';
    const root = container();
    const limit = matchMedia('(max-width: 640px)').matches ? 3 : 4;
    while (items.size >= limit) items.values().next().value.close();
    const card = document.createElement('article');
    card.className = `jcc-notification is-${variant}`;
    card.dataset.notificationId = String(++sequence);
    card.setAttribute('role', variant === 'error' ? 'alert' : 'status');
    card.setAttribute('aria-atomic', 'true');
    const icon = document.createElement('span');
    icon.className = 'jcc-notification-icon';
    icon.setAttribute('aria-hidden', 'true');
    icon.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${paths[variant]}</svg>`;
    const content = document.createElement('div');
    content.className = 'jcc-notification-copy';
    const title = document.createElement('strong');
    title.textContent = options.title || titles[variant];
    const body = document.createElement('p');
    body.textContent = String(message).replace(/^✓\s*/, '');
    content.append(title, body);
    const dismiss = document.createElement('button');
    dismiss.type = 'button';
    dismiss.className = 'jcc-notification-close';
    dismiss.setAttribute('aria-label', '关闭通知');
    dismiss.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="m6 6 12 12M6 18 18 6"/></svg>';
    card.append(icon, content, dismiss);
    let timer, started, closed = false, paused = false, remaining = options.duration || (variant === 'error' ? 6500 : 3800);
    const entry = { close() {
      if (closed) return;
      closed = true;
      clearTimeout(timer);
      card.remove();
      items.delete(entry);
      if (!items.size) {
        host.remove();
        window.visualViewport?.removeEventListener('resize', position);
        window.visualViewport?.removeEventListener('scroll', position);
      }
    } };
    function pause() { if (closed || paused) return; paused = true; clearTimeout(timer); remaining = Math.max(0, remaining - (performance.now() - started)); }
    function resume() {
      if (closed || card.matches(':hover') || card.contains(document.activeElement)) return;
      clearTimeout(timer);
      paused = false;
      started = performance.now();
      timer = setTimeout(entry.close, remaining);
    }
    dismiss.addEventListener('click', entry.close);
    card.addEventListener('pointerenter', pause);
    card.addEventListener('pointerleave', resume);
    card.addEventListener('focusin', pause);
    card.addEventListener('focusout', () => queueMicrotask(resume));
    if (!items.size) {
      window.visualViewport?.addEventListener('resize', position, { passive: true });
      window.visualViewport?.addEventListener('scroll', position, { passive: true });
    }
    items.add(entry);
    // The oldest entry may have detached the container while enforcing the cap.
    if (!root.isConnected) container();
    root.append(card);
    started = performance.now();
    timer = setTimeout(entry.close, remaining);
    return entry.close;
  }
  function inline(element, message, variant = 'error') {
    if (element) { element.textContent = message; element.classList.add('jcc-inline-feedback'); }
    if (message) show(message, { variant });
  }
  function afterNavigation(message) {
    try { sessionStorage.setItem('jcc-notification-next', JSON.stringify({ message, at: Date.now() })); } catch (_) { /* Optional continuity; storage can be blocked. */ }
  }
  window.jccNotify = { show, inline, afterNavigation };
  try {
    const saved = sessionStorage.getItem('jcc-notification-next');
    sessionStorage.removeItem('jcc-notification-next');
    const next = saved && JSON.parse(saved);
    if (next && typeof next.message === 'string' && Date.now() - next.at < 10000) show(next.message, { variant: 'success' });
  } catch (_) { /* Invalid or unavailable session storage must not block the page. */ }
})();
