/* The official card is already framed. Geometry comes from the selected local asset. */
(function (global) {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function render(card) {
    if (!card) return '<span class="deck-frame-empty">空卡槽</span>';
    const tier = Number(card.tier) || 1;
    const body = card.image_url ? `<img class="fortune-card-image" src="${esc(card.image_url)}" alt="" loading="lazy" decoding="async">`
      : `<span class="fortune-missing"><i aria-hidden="true">◇</i>${card.status === 'missing' ? '已失效' : '卡图暂缺'}</span>`;
    if (card.framed && card.image_url) {
      return `<span class="fortune-card-frame is-official" data-tier="${tier}" style="${esc(card.art_style)}"><span class="fortune-official-canvas">${body}</span><span class="fortune-official-title" style="font-size:${Math.min(6, 78 / Math.max(1, [...card.name].length))}cqi" aria-hidden="true">${esc(card.name)}</span><span class="fortune-official-seal" aria-hidden="true"><b>${esc(card.category)}</b><span>${'◆'.repeat(tier)}</span></span></span>`;
    }
    const bezel = document.getElementById(`bezel-${tier}`)?.innerHTML || '';
    return `<span class="fortune-card-frame is-art-only" data-tier="${tier}"><span class="fortune-card-surface fortune-art-${esc(card.layout || 'missing')}">${body}<span class="fortune-card-shade"></span></span>${bezel}</span>`;
  }
  function unavailable(img) {
    const frame = img.closest('.fortune-card-frame');
    if (!frame) return;
    img.hidden = true;
    frame.classList.add('is-unavailable');
    if (!img.parentElement.querySelector('.fortune-missing')) {
      const note = document.createElement('span');
      note.className = 'fortune-missing';
      note.textContent = '卡图暂不可用';
      img.parentElement.append(note);
    }
  }
  document.addEventListener('error', event => {
    if (event.target.matches?.('img.fortune-card-image')) unavailable(event.target);
  }, true);
  document.querySelectorAll('img.fortune-card-image').forEach(img => {
    if (img.complete && !img.naturalWidth) unavailable(img);
  });
  global.FortuneCardArt = {render};
})(window);
