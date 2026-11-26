const patchThemeToggle = document.querySelector('#themeToggle');
function applyPatchTheme(theme) {
  document.documentElement.dataset.theme = theme;
  window.jccApplyThemeToggleState(theme, patchThemeToggle, document.querySelector('#themeIcon'), document.querySelector('#themeText'));
}
applyPatchTheme(document.documentElement.dataset.theme || 'light');
patchThemeToggle.addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  applyPatchTheme(theme);
  try { localStorage.setItem('theme', theme); } catch { /* Storage is optional. */ }
});

setupFilters();
setupContents();

function setupFilters() {
  const tools = document.querySelector('[data-pn-filter]');
  if (!tools) return;

  const input = tools.querySelector('input');
  const buttons = tools.querySelectorAll('[data-filter]');
  const status = tools.querySelector('[data-filter-status]');
  const reset = tools.querySelector('[data-filter-reset]');
  const toc = document.querySelector('.pn-toc');
  const sections = Array.from(document.querySelectorAll('[data-section]'), section => {
    const title = section.querySelector('h2')?.textContent || '';
    return {
      section,
      title: title.toLowerCase(),
      link: document.querySelector(`[data-toc-link="${section.id}"]`)?.closest('li'),
      tallies: section.querySelectorAll('[data-count-kind]'),
      entries: Array.from(section.querySelectorAll('.pn-text, .pn-change'), node => ({
        node,
        text: node.textContent.toLowerCase(),
      })),
    };
  });
  let kind = 'all';

  function apply() {
    const query = input.value.trim().toLowerCase();
    const active = Boolean(query || kind !== 'all');
    let count = 0;
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === kind)));
    for (const { section, title, link, entries, tallies } of sections) {
      let visible = 0;
      const counts = { buff: 0, nerf: 0, adjust: 0 };
      for (const { node, text } of entries) {
        const match = (kind === 'all' || node.dataset.kind === kind) && (title.includes(query) || text.includes(query));
        node.hidden = !match;
        if (!match) continue;
        visible++;
        if (node.dataset.kind) counts[node.dataset.kind]++;
      }
      for (const tally of tallies) {
        const total = counts[tally.dataset.countKind];
        tally.hidden = !total;
        tally.querySelector('b').textContent = total;
      }
      count += visible;
      section.hidden = active && visible === 0;
      if (link) link.hidden = section.hidden;
    }
    if (toc) toc.hidden = !toc.querySelector('li:not([hidden])');
    reset.hidden = !active;
    status.textContent = active ? (count ? `匹配 ${count} 条内容` : '没有匹配的内容') : '';
  }

  buttons.forEach(button => button.addEventListener('click', () => {
    kind = button.dataset.filter;
    apply();
  }));
  input.addEventListener('input', apply);
  reset.addEventListener('click', () => {
    kind = 'all';
    input.value = '';
    apply();
    input.focus();
  });
  tools.hidden = false;
  apply();
}

function setupContents() {
  const original = document.getElementById('original');
  function openOriginalFromHash() {
    if (original && location.hash === '#original') original.open = true;
  }
  openOriginalFromHash();
  window.addEventListener('hashchange', openOriginalFromHash);

  const contents = document.querySelector('.pn-toc details');
  if (!contents) return;
  const compact = matchMedia('(max-width: 760px)');
  const sizeContents = () => { contents.open = !compact.matches; };
  sizeContents();
  compact.addEventListener('change', sizeContents);
  contents.addEventListener('click', event => {
    const link = event.target.closest('a');
    if (!link) return;
    if (link.hash === '#original' && original) original.open = true;
    if (compact.matches) contents.open = false;
  });

  if (!('IntersectionObserver' in window)) return;
  const links = [...contents.querySelectorAll('[data-toc-link]')];
  const visible = new Set();
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) visible.add(entry.target.id);
      else visible.delete(entry.target.id);
    }
    const current = links.find(link => visible.has(link.dataset.tocLink) && !link.closest('li').hidden);
    for (const link of links) {
      if (link === current) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    }
  }, { rootMargin: '-12% 0px -55% 0px' });
  links.forEach(link => observer.observe(document.getElementById(link.dataset.tocLink)));
}
