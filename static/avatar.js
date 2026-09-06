/* Adapted from the user-provided yangshi/avatar.js. Fixed system geometry. */
(() => {
/** Shared, deterministic SVG renderer. Geometry fitted to avatar.webp (104 × 104). */
const RADIAL_PALETTES = {
  blue: {
    light: '#6097ff',
    mid: '#0021ed',
    deep: '#0035df',
    dark: '#00149c',
    name: '经典宝蓝'
  },
  emerald: {
    light: '#34d399',
    mid: '#059669',
    deep: '#047857',
    dark: '#064e3b',
    name: '翡翠绿'
  },
  purple: {
    light: '#a855f7',
    mid: '#7c3aed',
    deep: '#6b21a8',
    dark: '#3b0764',
    name: '赛博紫'
  },
  amber: {
    light: '#fb923c',
    mid: '#ea580c',
    deep: '#c2410c',
    dark: '#7c2d12',
    name: '落霞橙'
  },
  rose: {
    light: '#f43f5e',
    mid: '#e11d48',
    deep: '#be123c',
    dark: '#881337',
    name: '洋红玫瑰'
  },
  monochrome: {
    light: '#94a3b8',
    mid: '#334155',
    deep: '#1e293b',
    dark: '#020617',
    name: '极客炭黑'
  },
  sky: {
    light: '#38bdf8',
    mid: '#0284c7',
    deep: '#0369a1',
    dark: '#0c4a6e',
    name: '晴空湖蓝'
  },
  indigo: {
    light: '#818cf8',
    mid: '#4f46e5',
    deep: '#3730a3',
    dark: '#1e1b4b',
    name: '青金石蓝'
  }
};

const AVATAR_DEFAULTS = Object.freeze({ size: 48, angle: -47.989, slitWidth: 6.414 });
const AVATAR_GEOMETRY = Object.freeze({ cx: 52.328, cy: 52.328, outerRadius: 51.02, innerRadius: 45.074, pitch: 13.608, phase: 0.146 });
const KEYS = Object.keys(RADIAL_PALETTES);
// RGB samples of the original on white, from t = .15 to .85 of the diagonal.
const REFERENCE_STOPS = [
  [1, 1, 1],
  [.958253, .958058, .990401],
  [.873477, .876304, .983835],
  [.756633, .755316, .971893],
  [.589739, .602734, .963848],
  [.375106, .426410, .939980],
  [.127526, .183452, .937394],
  [.092352, .157874, .933971],
  [.101552, .169440, .932362]
];
function hashString(value) {
  let hash = 5381;
  for (const char of String(value)) hash = (Math.imul(hash, 33) + char.codePointAt(0)) >>> 0;
  return hash;
}
function hexRgb(value) {
  if (typeof value !== 'string' || !/^#(?:[a-f0-9]{3}|[a-f0-9]{6})$/i.test(value)) {
    throw new TypeError('Color must be a #RGB or #RRGGBB hex value.');
  }
  let hex = value.slice(1);
  if (hex.length === 3) hex = [...hex].map(c => c+c).join('');
  return [0, 2, 4].map(i => parseInt(hex.slice(i, i+2), 16) / 255);
}
function numeric(value, fallback, min, max, name) {
  const n = value ?? fallback;
  if (typeof n !== 'number' || !Number.isFinite(n) || n < min || n > max) {
    throw new RangeError(`${name} must be a finite number between ${min} and ${max}.`);
  }
  return n;
}
function rgbCss(rgb) {
  return `rgb(${rgb.map(v => Math.round(Math.max(0, Math.min(1, v))*255)).join(',')})`;
}
/** Empty seed reproduces the reference blue; a nonempty seed selects a stable palette. */
function getAvatarSvg(seed = '', options = {}) {
  const size = numeric(options.size, 48, 1, 4096, 'size');
  const angle = numeric(options.angle, AVATAR_DEFAULTS.angle, -360, 360, 'angle');
  const slitWidth = numeric(options.slitWidth, AVATAR_DEFAULTS.slitWidth, 0, 13, 'slitWidth');
  const paletteKey = options.palette ?? (seed === '' ? 'blue' : KEYS[hashString(seed) % KEYS.length]);
  if (!Object.hasOwn(RADIAL_PALETTES, paletteKey)) throw new TypeError('Unknown avatar palette.');
  const color = options.color || RADIAL_PALETTES[paletteKey].mid;
  const base = hexRgb(color);
  const originalBlue = color.toLowerCase() === RADIAL_PALETTES.blue.mid;
  const background = options.background ?? 'transparent';
  if (background !== 'transparent') hexRgb(background);
  // No random IDs, timestamps, or raw user identifiers: stable output for SSR and caching.
  const id = 'avatar_' + hashString(JSON.stringify([color, angle, slitWidth])).toString(36);
  const { cx, cy, outerRadius, innerRadius, pitch, phase } = AVATAR_GEOMETRY;
  const stops = REFERENCE_STOPS.map((rgb, i) => {
    const opacity = 1-Math.min(...rgb);
    const ink = opacity < .00001 ? base : originalBlue
      ? rgb.map(v => (v-1+opacity)/opacity) : base;
    return `<stop offset="${((.15 + i*.0875)*100).toFixed(2)}%" stop-color="${rgbCss(ink)}" stop-opacity="${opacity.toFixed(6)}"/>`;
  }).join('');
  const slits = Array.from({ length: 9 }, (_, i) =>
    `<rect x="${((i-4)*pitch+phase-slitWidth/2).toFixed(4)}" y="-80" width="${slitWidth}" height="160" fill="black"/>`
  ).join('');
  const ga = 41.804 * Math.PI/180;
  const dx = 73.54*Math.cos(ga), dy = 73.54*Math.sin(ga);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 104 104" fill="none">
<defs>
  <filter id="${id}_soft" x="-10%" y="-10%" width="120%" height="120%" color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="0.35"/></filter>
  <linearGradient id="${id}_g" gradientUnits="userSpaceOnUse" x1="${52-dx}" y1="${52-dy}" x2="${52+dx}" y2="${52+dy}">${stops}</linearGradient>
  <clipPath id="${id}_i"><circle cx="${cx}" cy="${cy}" r="${innerRadius}"/></clipPath>
  <mask id="${id}_m" maskUnits="userSpaceOnUse" x="0" y="0" width="104" height="104" style="mask-type:luminance">
    <rect width="104" height="104" fill="white"/>
    <g clip-path="url(#${id}_i)"><g transform="translate(${cx} ${cy}) rotate(${angle})">${slits}</g></g>
  </mask>
</defs>
${background === 'transparent' ? '' : `<rect width="104" height="104" fill="${background}"/>`}
<g filter="url(#${id}_soft)"><circle cx="${cx}" cy="${cy}" r="${outerRadius}" fill="url(#${id}_g)" mask="url(#${id}_m)"/></g>
</svg>`;
}
/** Safe to assign to an image src; no user input is interpolated as SVG markup. */
function getAvatarDataUrl(seed = '', options = {}) {
  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(getAvatarSvg(seed, options));
}

function image(color, size = 36, alt = '') {
  const img = document.createElement('img');
  img.className = 'user-avatar';
  img.width = size; img.height = size; img.alt = alt;
  img.src = getAvatarDataUrl('', {color: /^#[a-f0-9]{6}$/i.test(color) ? color : '#0021ed', size});
  return img;
}
window.jccAvatar = { image, getAvatarDataUrl, palettes: RADIAL_PALETTES };

})();
