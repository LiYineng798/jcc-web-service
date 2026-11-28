function unitStarIcons(stars, index) {
  const gradientId = `star-metal-${index}`;
  const star = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11.1 3.1Q12 1.3 12.9 3.1L15.2 7.8Q15.5 8.4 16.2 8.5L21.4 9.3Q23.3 9.6 21.9 10.9L18.2 14.6Q17.7 15.1 17.8 15.8L18.7 21Q19 22.9 17.3 22L12.7 19.6Q12 19.3 11.3 19.6L6.7 22Q5 22.9 5.3 21L6.2 15.8Q6.3 15.1 5.8 14.6L2.1 10.9Q.7 9.6 2.6 9.3L7.8 8.5Q8.5 8.4 8.8 7.8Z" fill="url(#${gradientId})" stroke="#fff0bc" stroke-width=".7" stroke-linejoin="round"/></svg>`;
  return `<svg class="star-palette" aria-hidden="true" width="0" height="0"><defs><linearGradient id="${gradientId}" x1="0" y1="0" x2=".2" y2="1"><stop stop-color="#fff7d5"/><stop offset=".38" stop-color="#f5d478"/><stop offset=".62" stop-color="#cc963a"/><stop offset="1" stop-color="#ffe9a0"/></linearGradient></defs></svg>${star.repeat(stars)}`;
}
