"""Build the folio's editable vector fabric, corner engravings and bronze leaves.

Only authored SVG paths, deterministic patterns and SVG noise filters are used;
there are no raster images, external references or image-generation services.
"""
from pathlib import Path

DESTINATION = Path(__file__).resolve().parents[1] / 'static/tools/orange-fortune/creator/material-folio.svg'


def build():
    # Two crossing families of fine curves, like the lathe engraving on old bookplates.
    arcs = []
    for i in range(14):
        x, y = 290 + i * 23, 128 + i * 25
        arcs.append(f'<path d="M-24 {y} C{42+i*7} {40+i*8} {150+i*15} {28+i*2} {x} -24"/>')
        arcs.append(f'<path d="M-24 {x} C{28+i*2} {150+i*15} {40+i*8} {42+i*7} {y} -24"/>')
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1600" viewBox="0 0 1200 1600">
  <title>蓝绒藏典 — vector woven cloth, engraved curves and bronze acanthus</title>
  <!-- Rebuild with scripts/build_folio_material.py. No embedded bitmap. -->
  <defs>
    <linearGradient id="blue" x2=".85" y2="1">
      <stop stop-color="#10255b"/><stop offset=".43" stop-color="#173b7e"/>
      <stop offset=".72" stop-color="#10316c"/><stop offset="1" stop-color="#0c2353"/>
    </linearGradient>
    <radialGradient id="light" cx=".28" cy=".3" r=".75">
      <stop stop-color="#6782b1" stop-opacity=".1"/><stop offset="1" stop-color="#05214a" stop-opacity=".22"/>
    </radialGradient>
    <pattern id="weave" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(38)">
      <path d="M0 0V4m2-4v4" stroke="#061a3d" stroke-width=".6" opacity=".42"/>
      <path d="M.7 0V4m2-4v4" stroke="#a1b7d2" stroke-width=".4" opacity=".18"/>
      <path d="M0 1h2m0 2h2" stroke="#bbcadb" stroke-width=".5" opacity=".07"/>
      <path d="M0 3h2m0-2h2" stroke="#061b42" stroke-width=".6" opacity=".24"/>
    </pattern>
    <pattern id="slubs" width="113" height="97" patternUnits="userSpaceOnUse" patternTransform="rotate(32)">
      <path d="M8 6v13m63 21v7m-33 29v11m57-13v5m-74-35v4" stroke="#a0b5ce" stroke-width=".6" opacity=".16"/>
      <path d="M20 15v8m64 16v16M51 80v9" stroke="#071d42" stroke-width=".8" opacity=".22"/>
    </pattern>
    <filter id="patina" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency=".011 .018" numOctaves="3" seed="24"/>
      <feColorMatrix type="saturate" values="0"/>
    </filter>
    <filter id="fibre" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency=".72 .5" numOctaves="2" seed="8"/>
      <feColorMatrix type="saturate" values="0"/>
    </filter>
    <radialGradient id="engraving-fade" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="690">
      <stop stop-color="white"/><stop offset=".45" stop-color="#aaa"/><stop offset="1" stop-color="black"/>
    </radialGradient>
    <mask id="engraving-mask"><path d="M0 0h650v650H0z" fill="url(#engraving-fade)"/></mask>
    <g id="engraving" mask="url(#engraving-mask)" fill="none" stroke="#c4d5e8" stroke-width=".8" opacity=".28">
''' + '\n'.join('      ' + path for path in arcs) + '''
      <path d="M12 470C80 230 230 80 470 12M12 500C100 250 250 100 500 12" stroke-width=".45" opacity=".65"/>
    </g>
    <linearGradient id="bronze" x1="0" y1="0" x2=".7" y2="1">
      <stop stop-color="#4b3922"/><stop offset=".18" stop-color="#c6b17e"/>
      <stop offset=".32" stop-color="#8e7444"/><stop offset=".5" stop-color="#cdbb8b"/>
      <stop offset=".62" stop-color="#806337"/><stop offset=".83" stop-color="#a48b58"/><stop offset="1" stop-color="#40321f"/>
    </linearGradient>
    <linearGradient id="leaf" x2="1" y2=".8">
      <stop stop-color="#ddce9e"/><stop offset=".27" stop-color="#685030"/><stop offset=".52" stop-color="#bea16c"/>
      <stop offset=".72" stop-color="#5b4327"/><stop offset="1" stop-color="#cbb681"/>
    </linearGradient>
    <filter id="relief" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="1" dy="2" stdDeviation="1.6" flood-color="#020c20" flood-opacity=".9"/>
    </filter>
    <g id="arm">
      <path d="M10 17C29 17 52 14 79 10c19-3 31-10 42-5 6 3-2 7-9 7-16 1-20 11-37 15-18 4-36 1-49 5L12 34Z" fill="url(#bronze)" stroke="#382b1b" stroke-width="1.2"/>
      <path d="M23 21c28-3 52-4 74-12m-68 21c17-5 33-2 48-6 12-3 18-11 28-12" fill="none" stroke="#e5d3a0" stroke-opacity=".6" stroke-width=".9"/>
      <path d="M50 18c-9-12-18-2-11 4 7 6 16-5 10-9m18 4c8-8 13-4 10 2-3 5-11 2-10-2" fill="none" stroke="#45341e" stroke-width="2"/>
      <path d="M39 13c-3 5 1 8 5 7m26-4c4-3 5 0 3 2" fill="none" stroke="#e8d8ab" stroke-width=".9"/>
      <path d="m83 10-3 3m7-4-3 3m7-4-3 3m7-4-3 3" stroke="#5e482b" stroke-width=".65"/>
    </g>
    <g id="corner" filter="url(#relief)">
      <use href="#arm"/><use href="#arm" transform="matrix(0 1 1 0 0 0)"/>
      <!-- Hand-drawn curled acanthus blades; dark incisions and fine raised veins. -->
      <g fill="url(#leaf)" stroke="#4a3823" stroke-width="1">
        <path d="M23 24C8 20 5 11 13 6c-2 8 10 6 12 17Z"/>
        <path d="M25 25C19 9 24 2 31 5c-8 5 3 13-6 20Z"/>
        <path d="M28 25c5-17 15-17 19-12-10-1-7 13-19 12Z"/>
        <path d="M27 28c14-5 18 0 16 7 8 3 7 11 10 16-9-3-17-4-19-12-7 2-9-4-7-11Z"/>
        <path d="M25 28C7 24 2 31 8 37c2-9 13 3 17-9Z"/>
        <path d="M26 31c-5 9-4 15 3 17-2-7 8-9-3-17Z"/>
      </g>
      <g fill="none" stroke="#e9d8a5" stroke-width=".8" opacity=".78">
        <path d="M24 24 13 11m13 12 2-13m1 15 12-10M29 30l19 17m-23-18-13 3m15 1 1 11"/>
        <path d="m34 35 4-5m-1 8 6-2m-3 5 6-1m-15-7 0 5"/>
      </g>
      <path d="M24 18c-7 0-10 10-4 14 7 4 14-4 10-10-2-3-7-4-8 0-2 5 4 6 5 3" fill="url(#bronze)" stroke="#3a2d1d" stroke-width="1.2"/>
      <path d="M20 23c0-5 8-6 10-1" fill="none" stroke="#f0dfae" stroke-width="1.2"/>
      <circle cx="12" cy="16" r="2.4" fill="#3b2d1d" stroke="#bca477" stroke-width=".7"/>
      <path d="m10.7 16 2.6-.5" stroke="#cfbb91" stroke-width=".65"/>
    </g>
  </defs>
  <path d="M0 0h1200v1600H0z" fill="url(#blue)"/>
  <path d="M0 0h1200v1600H0z" fill="url(#light)"/>
  <path d="M0 0h1200v1600H0z" filter="url(#patina)" opacity=".06"/>
  <path d="M0 0h1200v1600H0z" fill="url(#weave)"/>
  <path d="M0 0h1200v1600H0z" fill="url(#slubs)"/>
  <path d="M0 0h1200v1600H0z" filter="url(#fibre)" opacity=".04"/>
  <use href="#engraving"/><use href="#engraving" transform="translate(1200 0) scale(-1 1)"/>
  <use href="#engraving" transform="translate(0 1600) scale(1 -1)"/>
  <use href="#engraving" transform="translate(1200 1600) scale(-1 -1)"/>
  <!-- Fine interrupted bookplate frame, kept in the gutters. -->
  <g fill="none" stroke="#c2ced8" stroke-width=".7" opacity=".26">
    <path d="M140 28H1060M28 140V1460M1172 140V1460M140 1572H1060"/>
    <path d="M154 33H1046M33 154V1446M1167 154V1446M154 1567H1046" opacity=".35"/>
  </g>
  <use href="#corner" transform="translate(16 16) scale(.85)"/>
  <use href="#corner" transform="translate(1184 16) scale(-.85 .85)"/>
  <use href="#corner" transform="translate(16 1584) scale(.85 -.85)"/>
  <use href="#corner" transform="translate(1184 1584) scale(-.85 -.85)"/>
</svg>
'''


if __name__ == '__main__':
    DESTINATION.write_text(build(), encoding='utf-8', newline='\n')
    print(f'Built {DESTINATION.name}')
