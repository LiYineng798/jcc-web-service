(function (global) {
  const mounts = new WeakMap();

  function mount(wrap, { seasons, selected, onSelect }) {
    mounts.get(wrap)?.();
    const controller = new AbortController();
    const options = { signal: controller.signal };
    const toggle = wrap.querySelector('.season-toggle');
    const menu = wrap.querySelector('[role="menu"]');
    const input = wrap.querySelector('input[type="hidden"]');
    const text = toggle.querySelector('span');
    let opened = false;

    function close() {
      opened = false;
      menu.classList.add('hidden');
      toggle.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
    }

    function open() {
      if (toggle.disabled) return;
      opened = true;
      menu.classList.remove('hidden');
      toggle.classList.add('is-open');
      toggle.setAttribute('aria-expanded', 'true');
      (menu.querySelector('[aria-checked="true"]') || menu.firstElementChild)?.focus();
    }

    toggle.setAttribute('aria-controls', menu.id);
    menu.setAttribute('aria-labelledby', toggle.id);
    toggle.disabled = !seasons.length;
    if (!seasons.length) text.textContent = '暂无可用赛季';
    menu.replaceChildren();
    seasons.forEach(season => {
      const option = document.createElement('button');
      option.type = 'button';
      option.className = `account-menu-item${season.id === selected ? ' is-active' : ''}`;
      option.textContent = season.name || season.id;
      option.setAttribute('role', 'menuitemradio');
      option.setAttribute('aria-checked', String(season.id === selected));
      option.tabIndex = -1;
      option.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        close();
        if (season.id !== selected) {
          input.value = season.id;
          text.textContent = season.name || season.id;
          onSelect(season.id);
        }
        // Selection may synchronously replace the workbench; focus the new trigger.
        document.getElementById(toggle.id)?.focus({ preventScroll: true });
      }, options);
      menu.append(option);
    });
    toggle.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      if (opened) close(); else open();
    }, options);
    wrap.addEventListener('keydown', event => {
      if (event.key === 'Escape' && opened) {
        event.preventDefault();
        event.stopPropagation();
        close();
        toggle.focus();
      } else if (event.key === 'Tab') {
        if (opened) {
          close();
          toggle.focus();
        }
      } else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
        event.preventDefault();
        if (!opened) { open(); return; }
        const items = Array.from(menu.children);
        const index = items.indexOf(document.activeElement);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1
          : (index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        items[next]?.focus();
      }
    }, options);
    function dismissOutside(event) {
      const onLabel = Array.from(toggle.labels || []).some(label => label.contains(event.target));
      if (!wrap.contains(event.target) && !onLabel) close();
    }
    // WebKit touch taps on non-interactive text may not synthesize a click.
    document.addEventListener('pointerdown', dismissOutside, options);
    document.addEventListener('click', dismissOutside, options);
    document.addEventListener('focusin', event => {
      if (!wrap.contains(event.target)) close();
    }, options);

    function destroy() {
      close();
      controller.abort();
      mounts.delete(wrap);
    }
    mounts.set(wrap, destroy);
    return destroy;
  }

  global.JccAdminSeasonPicker = Object.freeze({ mount });
})(window);
