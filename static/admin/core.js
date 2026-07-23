(function (global) {
  function el(tag, className = '', text = '') {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function escapeAttribute(value) {
    return escapeHtml(value)
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function button(label, handler, className = 'small-button', disabled = false) {
    const node = el('button', className, label);
    node.type = 'button';
    node.disabled = disabled;
    node.addEventListener('click', async (event) => {
      try {
        await handler(event, node);
      } catch (error) {
        if (error?.name === 'AbortError') return;
        alert(error.message || '操作失败，请刷新后重试');
      }
    });
    return node;
  }

  function buildDeltaText(today, yesterday) {
    const delta = Number(today || 0) - Number(yesterday || 0);
    if (delta === 0) return '与昨日持平';
    return delta > 0 ? `较昨日 +${delta}` : `较昨日 ${delta}`;
  }

  function formatDay(value) {
    const parts = String(value || '').split('-');
    if (parts.length !== 3) return value || '-';
    return `${parts[1]}-${parts[2]}`;
  }

  function formatPercent(value) {
    return `${Number(value || 0).toFixed(2)}%`;
  }

  function todayInputValue() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function debounce(callback, delay) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => callback(...args), delay);
    };
  }

  global.JccAdminCore = Object.freeze({
    buildDeltaText,
    button,
    debounce,
    el,
    escapeAttribute,
    escapeHtml,
    formatDay,
    formatPercent,
    todayInputValue,
  });
})(window);
