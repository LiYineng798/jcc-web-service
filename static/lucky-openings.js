(() => {
  'use strict';
  const themeToggle = document.querySelector('#themeToggle');
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    window.jccApplyThemeToggleState?.(theme, themeToggle, document.querySelector('#themeIcon'), document.querySelector('#themeText'));
    try { localStorage.setItem('theme', theme); } catch (_) { /* Theme still works with blocked storage. */ }
  }
  applyTheme(document.documentElement.dataset.theme || 'light');
  themeToggle?.addEventListener('click', () => {
    applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  });

  async function copyText(text) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_) { /* Older browsers and insecure LAN previews use the fallback. */ }
    const active = document.activeElement;
    const field = document.createElement('textarea');
    field.value = text;
    field.readOnly = true;
    field.style.cssText = 'position:fixed;top:0;left:0;opacity:0;font-size:16px;pointer-events:none';
    document.body.append(field);
    field.select();
    field.setSelectionRange(0, text.length);
    try { return document.execCommand('copy'); }
    catch (_) { return false; }
    finally { field.remove(); active?.focus({ preventScroll: true }); }
  }
  document.querySelectorAll('.opening-copy').forEach((button) => {
    let timer;
    button.addEventListener('click', async () => {
      if (button.disabled) return;
      clearTimeout(timer);
      button.disabled = true;
      const label = button.querySelector('span');
      label.textContent = '复制中…';
      const copied = await copyText(button.dataset.code);
      button.disabled = false;
      label.textContent = copied ? '已复制' : '复制阵容码';
      if (copied) {
        window.jccNotify?.show(`${button.dataset.name}阵容码已复制`, { variant: 'success' });
        timer = setTimeout(() => { label.textContent = '复制阵容码'; }, 1800);
      } else {
        const manual = button.parentElement.querySelector('.opening-manual');
        manual.open = true;
        const field = manual.querySelector('textarea');
        field.focus({ preventScroll: true });
        field.select();
        window.jccNotify?.show('请长按或选中下方阵容码手动复制', { variant: 'warning' });
      }
    });
  });
  document.querySelectorAll('.opening-portrait img').forEach((img) => {
    img.addEventListener('error', () => { img.hidden = true; });
    if (img.complete && !img.naturalWidth) img.hidden = true;
  });
})();
