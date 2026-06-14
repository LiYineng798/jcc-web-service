# Homepage Border Glow Design

## Context

The site is a Flask/Jinja application with plain CSS and JavaScript. React Bits' BorderGlow component should be adapted without React or new runtime dependencies.

The first version will apply the effect only to the homepage places approved for visual emphasis:

- The hero statistic card, `.stat-card`, in `templates/index.html`.
- Realtime lineup ranking cards created by `renderLiveCompCard()` in `static/app.js`.

Ordinary lineup cards, authentication pages, account pages, and admin pages stay unchanged.

## User Experience

The glow is an accent, not the main interface. On pointer-capable devices, moving the pointer near a glowing card edge reveals a directional edge light. The glow gets stronger near the edge and fades when the pointer leaves.

The homepage statistic card gets a subtle initial sweep after page load so the feature is discoverable. Realtime lineup cards only react to pointer movement and hover; they should not continuously animate in a list.

The visual palette should fit the existing JCC theme: warm amber, brick orange, and a small cool cyan highlight. It should not copy the React Bits purple/pink/blue defaults.

## Implementation Shape

Add a small native helper in `static/app.js`:

- `initBorderGlowCard(card, options)` sets CSS custom properties, adds the required light element when missing, and registers pointer handlers.
- `applyBorderGlowToStaticCards()` initializes the homepage `.stat-card`.
- `renderLiveCompCard()` initializes each realtime lineup card before returning it.

Add CSS in `static/styles.css`:

- `.border-glow-card` as the reusable wrapper class.
- `.border-glow-card::before` for the colored mesh-gradient edge.
- `.border-glow-card::after` for very subtle interior color fill.
- `.border-glow-card > .edge-light` for the outer directional light.
- `.border-glow-inner` only if wrapping is needed; for existing cards the first version should avoid extra wrappers unless required.

The helper computes two CSS variables from pointer position:

- `--edge-proximity`: 0 to 100, based on how close the pointer is to the card edge.
- `--cursor-angle`: an angle in degrees, based on the pointer direction from the card center.

## Constraints

- No React, build step, package install, or external dependency.
- Keep markup changes minimal.
- Keep the effect scoped to homepage selectors.
- Respect reduced motion by disabling the initial sweep under `prefers-reduced-motion: reduce`.
- Keep mobile behavior calm: touch devices should not receive continuous pointer-tracking visual noise.
- Do not change data loading, ranking logic, authentication, or API behavior.

## Testing

Manual verification should cover:

- Homepage loads with no JavaScript errors.
- `.stat-card` shows a subtle glow on pointer movement.
- Realtime lineup cards receive the glow class when the realtime view renders.
- Latest/hot/recommended ordinary lineup cards do not receive the glow.
- Theme toggle still works in light and dark modes.
- Mobile-width viewport remains readable and does not show overlapping glow layers.

Automated tests are not required for the visual-only CSS behavior unless an existing UI route test fails because of markup changes.
