# Homepage Pagination Navigation Design

## Goal

Replace the homepage morphing-dot pagination with accessible numbered navigation inspired by the supplied shadcn component, adapted to the existing Flask, vanilla JavaScript, and CSS architecture and the site's brick-red theme.

## Technology Decision

The Web repository has no React, TypeScript, Tailwind, shadcn, `package.json`, or frontend build pipeline. Introducing those systems for one pagination control would add dependency installation, compiled artifacts, deployment steps, and a second component architecture.

The implementation will therefore reproduce the supplied component's structure and behavior in `static/app.js` and `static/styles.css`. It will not create `/components/ui`, install npm packages, or add Tailwind configuration. The existing Jinja mount point remains the component boundary.

## Shared Pagination Data

Regular lineups and live comps continue to share the homepage pagination renderer and `state.page`, `state.pageSize`, and `state.totalPages` values. Their backends remain responsible for calculating dynamic totals:

- Regular lineups use 10 items per page.
- Live comps use 6 items per page.
- Search, season, sort, favorites, and ownership filters return their own current `total_pages` values.
- Pagination is hidden when `totalPages <= 1`.

No backend API or database change is required.

## Page Token Algorithm

Replace `buildPaginationDots()` with a pure `buildPaginationItems(currentPage, totalPages, compact)` helper. It returns page-number tokens and ellipsis tokens.

Desktop behavior:

- Show every page when the total is 7 or fewer.
- For larger totals, always show page 1 and the last page.
- Near the beginning, show pages 1 through 5, a trailing ellipsis, and the last page.
- In the middle, show page 1, a leading ellipsis, the current page with one neighbor on each side, a trailing ellipsis, and the last page.
- Near the end, show page 1, a leading ellipsis, and the final five pages.

Examples for 18 pages:

```text
1 2 3 4 5 ... 18
1 ... 7 8 9 ... 18
1 ... 14 15 16 17 18
```

Compact mobile behavior uses a smaller token budget:

- Show every page when the total is 5 or fewer.
- Otherwise keep the first page, last page, current page, and only the necessary neighboring page or ellipses.
- The renderer recomputes when crossing the mobile breakpoint.

## Component Structure

The existing `#pagination` element becomes a navigation landmark with `aria-label="分页导航"`. JavaScript renders:

- A previous button with a chevron icon and `上一页` label.
- A list-style content wrapper.
- Numbered page buttons.
- Non-interactive ellipsis items with a three-dot icon and screen-reader text.
- A next button with a `下一页` label and chevron icon.

The chevrons and ellipsis use small inline icon elements matching Lucide geometry. They are implemented locally because `lucide-react` cannot run without React and no icon package is currently part of the site.

## Visual Design

The supplied component's bordered, slightly offset-button character is adapted to the existing theme:

- Default buttons use `--surface-solid`, `--text`, and `--line`.
- The active page uses `--accent` with light text.
- Hover uses `--accent-soft` and `--accent-strong`.
- A restrained hard shadow uses the site's accent-neutral border color rather than the supplied blue and black palette.
- Hover and active states shift the button slightly and remove or reduce the shadow.
- Borders and radii remain consistent with the existing site instead of importing the supplied global neo-brutalist theme variables.

The old morphing dots and ripple animation are removed.

## Responsive Behavior

Desktop and tablet layouts show chevrons plus `上一页` and `下一页` text. At the mobile breakpoint:

- Direction labels are visually hidden, leaving icon-only controls with unchanged accessible labels.
- Buttons remain at least 40 by 40 pixels.
- The compact page-token algorithm reduces the number of number and ellipsis items.
- The pagination row remains a single horizontal line without overflow.

## Interaction And Scrolling

Clicking a valid page updates `state.page` and calls the existing `loadCurrentView()` request path. The current page and unavailable previous/next controls remain disabled.

After the requested page has rendered successfully, the page scrolls to the homepage list heading. Smooth scrolling is used normally; `prefers-reduced-motion: reduce` uses immediate scrolling. Aborted or failed requests do not trigger scrolling.

Both regular-lineup skeleton loading and live-comp rendering continue to work through their existing request paths. Rapid page changes retain the current abort-controller protection.

## Accessibility

- The container uses navigation semantics and a Chinese accessible label.
- Each page button uses `aria-label="前往第 N 页"`.
- The active page uses `aria-current="page"` and is disabled.
- Direction controls use `aria-label="上一页"` and `aria-label="下一页"`.
- Ellipses are non-interactive and hidden from assistive technology, with a screen-reader-only explanation.
- Focus-visible styles remain clear in light and dark themes.

## Testing

Add focused tests for:

- Full page lists at small totals.
- Beginning, middle, and ending desktop token windows.
- Compact mobile token windows.
- Previous, next, numbered page, and ellipsis markup contracts.
- Active and disabled accessibility states.
- Successful page loads triggering list-heading scrolling.
- Reduced-motion scroll behavior.
- Removal of the old morphing-dot and ripple implementation.

Run the focused homepage UI tests, JavaScript syntax checks, and the complete Web test suite. Browser verification should cover desktop and mobile widths, first/middle/last pages, light/dark themes, long page counts, loading states, and control overlap.

## Documentation

Update the Web repository `AGENTS.md` to describe the numbered pagination, dynamic ellipses, shared regular/live behavior, and successful-load scrolling rule.
