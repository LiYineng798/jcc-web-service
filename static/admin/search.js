(function (global) {
  // Keep the actual form and every ancestor attached: refocusing a replacement
  // input does not reliably keep an iOS keyboard or IME composition alive.
  function replaceResults(root, next) {
    const form = root.querySelector('[data-search-key]');
    const replacement = form && next.querySelector(`[data-search-key="${form.dataset.searchKey}"]`);
    if (!replacement) {
      root.replaceChildren(...next.childNodes);
      return;
    }
    function patch(oldParent, newParent) {
      if (oldParent === form) return;
      const oldBranch = [...oldParent.children].find(child => child.contains(form));
      const newBranch = [...newParent.children].find(child => child.contains(replacement));
      for (const child of [...oldParent.childNodes]) if (child !== oldBranch) child.remove();
      let before = true;
      for (const child of [...newParent.childNodes]) {
        if (child === newBranch) { before = false; continue; }
        if (before) oldParent.insertBefore(child, oldBranch);
        else oldParent.append(child);
      }
      patch(oldBranch, newBranch);
    }
    patch(root, next);
  }

  function create({ key, value, placeholder, search, invalidate }) {
    const { el, button } = global.JccAdminCore;
    const form = el('form', 'admin-search');
    form.dataset.searchKey = key;
    const input = el('input');
    input.type = 'search'; input.value = value; input.placeholder = placeholder;
    input.setAttribute('aria-label', placeholder);
    input.enterKeyHint = 'search'; input.autocomplete = 'off';
    const submit = el('button', 'small-button', '查找'); submit.type = 'submit';
    let timer, composing = false, revision = 0;
    const run = async () => {
      clearTimeout(timer);
      if (composing || !form.isConnected) return;
      const current = ++revision;
      form.setAttribute('aria-busy', 'true');
      try { await search(input.value.trim()); }
      catch (error) {
        if (error.name !== 'AbortError' && current === revision && form.isConnected) {
          global.jccNotify.show(error.message || '搜索失败，请重试', { variant: 'error' });
        }
      } finally { if (current === revision) form.removeAttribute('aria-busy'); }
    };
    const changed = () => {
      clearTimeout(timer); ++revision; invalidate();
      form.removeAttribute('aria-busy');
      if (!composing) timer = setTimeout(run, 400);
    };
    input.addEventListener('compositionstart', () => { composing = true; changed(); });
    input.addEventListener('compositionend', () => { composing = false; changed(); });
    input.addEventListener('input', changed);
    form.addEventListener('submit', event => { event.preventDefault(); run(); });
    const clear = button('清空', () => { input.value = ''; changed(); input.focus(); return run(); });
    form.append(input, submit, clear);
    return form;
  }
  global.JccAdminSearch = { create, replaceResults };
})(window);
