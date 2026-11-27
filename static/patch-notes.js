const filters = document.querySelector('[data-pn-filter]');
if (filters) {
  const buttons = filters.querySelectorAll('[data-filter]');
  const sections = document.querySelectorAll('[data-section]');

  filters.addEventListener('click', event => {
    const selected = event.target.closest('button[data-filter]');
    if (!selected || selected.disabled) return;
    const kind = selected.dataset.filter;
    const showAll = kind === 'all';
    for (const button of buttons) {
      button.setAttribute('aria-pressed', String(button === selected));
    }
    for (const section of sections) {
      let count = 0;
      for (const change of section.querySelectorAll('[data-kind]')) {
        change.hidden = !showAll && change.dataset.kind !== kind;
        if (!change.hidden) count++;
      }
      const tally = section.querySelector('[data-section-count]');
      if (tally) tally.textContent = count;
      for (const paragraph of section.querySelectorAll('.pn-text')) paragraph.hidden = !showAll;
      section.hidden = !showAll && count === 0;
    }
  });
  filters.hidden = false;
}

function openLinkedOriginal() {
  const original = document.getElementById('original');
  if (original && location.hash === '#original') original.open = true;
}
openLinkedOriginal();
window.addEventListener('hashchange', openLinkedOriginal);
