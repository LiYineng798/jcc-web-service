(() => {
  const NS = 'http://www.w3.org/2000/svg';
  function node(tag, attributes) {
    const el = document.createElementNS(NS, tag);
    Object.entries(attributes).forEach(([key, value]) => el.setAttribute(key, value));
    return el;
  }
  function render(element, value) {
    const text = String(value);
    if (element.dataset.handwritingValue === text) return;
    delete element.dataset.handwritingValue;
    element.textContent = text;
    element.classList.remove('has-handwriting');
    const digits = window.jccHandwritingDigits;
    if (!digits || !/^\d+$/.test(text)) return;
    const svg = node('svg', {'aria-hidden': 'true', focusable: 'false', class: 'handwriting-count-svg'});
    let x = 0;
    const strokes = [];
    for (const digit of text) {
      const glyph = digits[digit];
      if (!glyph) return;
      const group = node('g', {transform: `translate(${x} 0)`});
      // Preserve counters (the holes in 0, 6, 8, 9) in a single compound fill.
      group.append(node('path', {d: glyph.path, fill: 'currentColor', class: 'handwriting-count-fill'}));
      for (const contour of glyph.path.split(/(?=M)/).filter(Boolean)) {
        const stroke = node('path', {d: contour, fill: 'none', stroke: 'currentColor', 'stroke-width': '1.6', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', pathLength: '1', class: 'handwriting-count-stroke'});
        strokes.push(stroke); group.append(stroke);
      }
      svg.append(group); x += glyph.advance + 3;
    }
    const width = x + 16;
    svg.setAttribute('viewBox', `-8 8 ${width} 108`);
    svg.style.width = `${width / 108 * 1.2}em`;
    strokes.forEach((stroke, index) => {
      stroke.style.animationDelay = `${.05 + index / strokes.length * 1.5}s`;
      stroke.style.animationDuration = `${1.5 / strokes.length * 2.4}s`;
    });
    const fallback = document.createElement('span');
    fallback.className = 'handwriting-count-text';
    fallback.textContent = text;
    element.replaceChildren(fallback, svg);
    element.classList.add('has-handwriting');
    element.dataset.handwritingValue = text;
  }
  window.jccHandwritingCount = {render};
})();
