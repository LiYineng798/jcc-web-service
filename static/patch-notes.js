// Patch note pages are rendered on the server; this script only adds theme, filtering and navigation helpers.
const patchThemeToggle = document.querySelector('#themeToggle');
const patchThemeIcon = document.querySelector('#themeIcon');
const patchThemeText = document.querySelector('#themeText');

setPatchTheme(readTheme());
patchThemeToggle?.addEventListener('click', () => setPatchTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));

setupKindFilter();
setupTocHighlight();
setupTocSheet();
openOriginalFromHash();
window.addEventListener('hashchange', openOriginalFromHash);

function setupKindFilter() {
  const group = document.querySelector('[data-pn-filter]');
  if (!group) return;
  group.hidden = false;
  const sections = [...document.querySelectorAll('.pn-section')];
  group.addEventListener('click', (event) => {
    const button = event.target.closest('[data-filter]');
    if (!button) return;
    const kind = button.dataset.filter;
    group.querySelectorAll('[data-filter]').forEach((node) => node.setAttribute('aria-pressed', String(node === button)));
    document.querySelectorAll('.pn-change').forEach((node) => {
      node.hidden = kind !== 'all' && node.dataset.kind !== kind;
    });
    // Plain notes stay with "all"; a filtered view only keeps sections that still have matching changes.
    sections.forEach((section) => {
      section.classList.toggle('is-filtered', kind !== 'all');
      section.hidden = kind !== 'all' && !section.querySelector('.pn-change:not([hidden])');
    });
    document.querySelectorAll('[data-toc-link]').forEach((link) => {
      const target = document.getElementById(link.dataset.tocLink);
      link.closest('li').classList.toggle('is-muted', Boolean(target?.hidden));
    });
  });
}

function setupTocHighlight() {
  const links = [...document.querySelectorAll('[data-toc-link]')];
  if (!links.length || !('IntersectionObserver' in window)) return;
  const byId = new Map(links.map((link) => [link.dataset.tocLink, link]));
  const visible = new Set();
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => (entry.isIntersecting ? visible.add(entry.target.id) : visible.delete(entry.target.id)));
    const current = [...byId.keys()].find((id) => visible.has(id));
    if (!current) return;
    links.forEach((link) => link.classList.toggle('is-active', link.dataset.tocLink === current));
  }, { rootMargin: '-15% 0px -70% 0px' });
  byId.forEach((_, id) => {
    const target = document.getElementById(id);
    if (target) observer.observe(target);
  });
}

function setupTocSheet() {
  const button = document.querySelector('#pnTocButton');
  const sheet = document.querySelector('#pnTocSheet');
  if (!button || !sheet?.showModal) return;
  button.addEventListener('click', () => sheet.showModal());
  sheet.addEventListener('click', (event) => {
    if (event.target === sheet || event.target.closest('[data-sheet-close]')) sheet.close();
    const link = event.target.closest('[data-sheet-link]');
    if (!link) return;
    sheet.close();
    if (link.hasAttribute('data-scroll-top')) {
      event.preventDefault();
      window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
    }
  });
  sheet.addEventListener('close', () => button.focus({ preventScroll: true }));
}

function openOriginalFromHash() {
  if (location.hash !== '#original') return;
  const original = document.querySelector('#original');
  if (original && !original.open) original.open = true;
}

function prefersReducedMotion() {
  return matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function readTheme() {
  try { return localStorage.getItem('theme') || 'light'; } catch { return 'light'; }
}

function setPatchTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('theme', theme); } catch { /* Storage can be unavailable in private browsing. */ }
  window.jccApplyThemeToggleState?.(theme, patchThemeToggle, patchThemeIcon, patchThemeText);
  if (!window.jccApplyThemeToggleState && patchThemeText) patchThemeText.textContent = theme === 'dark' ? '白天模式' : '夜间模式';
}
