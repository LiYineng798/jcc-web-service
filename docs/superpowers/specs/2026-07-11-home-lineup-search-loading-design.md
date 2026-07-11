# Homepage Lineup Search And Loading Design

## Goal

Improve the homepage regular-lineup experience with an animated clearable search field and layout-stable skeleton loading cards, while preserving the existing API, filters, pagination, caching, and lineup interactions.

## Scope

This change applies only to the regular lineup list on the homepage. Live comp rankings continue to disable search and keep their existing loading UI. The backend search contract remains `GET /api/lineups?q=<query>` and continues to match lineup names only.

## Architecture

Add `static/home-transitions.js` as a focused browser module exposed through `window.JccHomeTransitions`. It owns search presentation state, clear animation frames, reduced-motion behavior, and skeleton/reveal DOM helpers. `static/app.js` remains responsible for application state, requests, caching, and lineup actions, and calls the transition module at defined lifecycle points.

The existing `templates/index.html` search label becomes a `.t-clear` wrapper containing the real search input, a value mirror, a fake placeholder, a glow overlay, and an icon clear button. The existing input ID and event path remain stable.

## Search Clear Interaction

- Typing synchronizes the real input value to the mirror and toggles `.has-value`.
- The clear button is available only when the input has a value and the regular lineup view is active.
- Clicking clear captures the old text for the mirror, immediately clears `state.query`, resets `state.page` to `1`, and starts `loadLineups()`.
- The result reset and the one-second dissolve animation run concurrently. Network latency never delays the clear interaction.
- The animation measures word or text-run positions from rendered content and writes a stack of radial gradients to `.t-clear-glow` on each frame.
- The old mirror text rises, fades, and lightly blurs while the placeholder enters from below. At completion, temporary inline styles and gradients are removed.
- New typing, a second clear, view changes, or disabling the field cancels any active animation and returns the control to a consistent state.
- Pressing the browser-provided search clear affordance or deleting text manually uses the existing debounced input path without replaying the custom dissolve.
- With `prefers-reduced-motion: reduce`, clearing is immediate and no glow or per-frame motion runs.

## Skeleton Loading And Reveal

- Skeleton cards resemble the regular lineup card geometry: title line, metadata line, code block, and action controls.
- Skeletons use stable minimum dimensions so the content reveal does not shift the list layout.
- Show skeletons for regular-lineup requests on first load and on uncached search, sort, season, or pagination changes.
- Do not show skeletons for front-end cache hits.
- Mutation refreshes after copy, like, or favorite preserve the current cards while the request runs. This avoids flashing the entire list during a user action.
- When fresh data arrives, real cards are mounted into the content layer and the wrapper receives `.is-revealed`, cross-fading from skeleton to content over 400 ms.
- When replaying a loading state, `.is-resetting` disables reverse transitions before the next reveal.
- On request failure, skeletons are removed and the existing message/error path remains responsible for feedback.
- With reduced motion enabled, skeleton/content transitions and skeleton pulses are disabled.

## Request And Cache Integration

`loadLineups()` determines whether loading UI is needed before awaiting data. The existing request key remains the source of cache identity. The cached JSON helper will expose whether a response came from cache, or an equivalent cache-presence helper will be used, so the UI can avoid a skeleton for synchronous cache hits.

Each active request retains the existing `AbortController` behavior. An aborted stale request must not reveal, clear, or overwrite the loading state owned by a newer request.

Mutation-triggered reloads call `loadLineups({ preserveContent: true })`. Navigation-triggered reloads use the default loading behavior.

## Styling

Add the Transitions.dev-inspired variables and state selectors to `static/styles.css`, adapted to the existing surface, border, radius, light/dark theme, and mobile rules. Dark mode changes the glow blend mode from `multiply` to `screen`.

The clear control uses a familiar icon-only button with an accessible label and tooltip. Text and placeholder padding reserve space for the button so they cannot overlap it. The existing 380 px responsive search width remains.

Skeleton colors use existing neutral surface and line tokens rather than introducing a new dominant palette.

## Error And Edge Cases

- Empty or whitespace-only input never sends `q`.
- Repeated fast searches continue to abort stale requests.
- A failed search leaves a usable search field and removes the loading placeholder.
- Switching to live comps cancels a clear animation, clears the visible input, and disables the clear button without discarding the stored regular-lineup query.
- Switching back restores the stored query and synchronized mirror.
- Empty successful results reveal the existing empty state without leaving skeleton cards mounted.

## Testing

Add focused tests that verify:

- The homepage contains the clear wrapper layers, accessible clear button, and transition script.
- The stylesheet contains clear, skeleton, reveal, dark-mode, and reduced-motion states.
- The homepage script initializes the transition module, clears query/page immediately, and distinguishes navigation loading from mutation refreshes.
- Skeleton loading is limited to regular lineup requests and cache hits do not flash it.
- Existing lineup search, pagination, permissions, and route tests continue to pass.

Run focused UI tests first, then the complete Web suite. Perform browser verification at desktop and mobile widths for clear animation, cache-hit behavior, slow-network skeleton reveal, dark mode, reduced motion, and button/text overlap.

## Documentation

Update the Web repository `AGENTS.md` after implementation to document the homepage regular-lineup search clear interaction and skeleton loading rules.

