# UI GLAM — change log (numbered, individually revertable)

Additive polish layer on the Glass Velvet dashboard. **Master switch:** remove the two lines
in `web/dashboard/index.html` (`<link href="glam.css">` and `<script src="glam.js">`) → every
effect below disappears, original UI restored, nothing else touched.

All effects reuse existing `glass.css` palette vars (no new colors). Verified: 0 console errors,
GREEN aurora live, gradient edges render, 426 ALL rows intact.

| # | Effect | What you see | Files | Revert |
|---|---|---|---|---|
| 1 | **Regime aurora** | Whole dashboard gets a faint ambient tint matching Gate-0 (green/amber/red glow from top). Unique signature. | `glam.css` GLAM-1, `glam.js` setRegime | Delete GLAM-1 block + `setRegime` hook |
| 2 | **Active-row aurora edge** | Selected row: violet inset edge + soft outer glow (on top of existing gradient bg). | `glam.css` GLAM-2 | Delete GLAM-2 block |
| 3 | **Direction gradient edge** | Every row's left edge: 3px gradient — LONG green→cyan, SHORT red→orange. Instant directional scan. | `glam.css` GLAM-3 | Delete GLAM-3 block (restores flat 4px today-only bar) |
| 4 | **Conviction star pop** | Hover a row → its conviction bars pop in sequence (40ms stagger). | `glam.css` GLAM-4 | Delete GLAM-4 block |
| 5 | **Live-arrival flash** | During a scan, each new ticker row pulses cyan→violet as it streams in (pairs with DAILY trickle-in). | `glam.css` GLAM-5, `glam.js` diffTable | Delete GLAM-5 block + new-row branch in `diffTable` |
| 6 | **Number pulse** | A price cell glows cyan for a beat when its value changes between refreshes. | `glam.css` GLAM-6, `glam.js` diffTable | Delete GLAM-6 block + changed-value branch in `diffTable` |

## Deliberately NOT built (rejected as gaudy / hurt trader credibility)
- Glitch RGB-split hover, scanline sweep on mount, Orbitron font, neon-hexagon stars.
- Amber Bloomberg accent as default (clashes with violet/cyan palette) — could be an opt-in toggle later.

## Deferred (needs data plumbing, not "straightforward CSS")
- **Per-ticker sparkline (20d)** — rows don't carry price history; needs an API field. Propose separately.
- **GEX wall overlay on detail chart** — real value; do when the detail/chart view is next touched.

## Mechanism
`glam.js` is observer-driven: a `MutationObserver` watches `#regimeBar` (→ body regime class)
and `#tableHost` (→ diff rows for arrival flash + number pulse). It edits no existing JS, so the
revert is clean. All hooks are wrapped in try/catch — a glam failure can never break the table.
