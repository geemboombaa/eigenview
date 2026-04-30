# Wireframes — Visual Source of Truth

Two HTML wireframes embody all the locked visual design decisions. They live in the parent `Tradingview/` folder and need to be copied into this `docs/wireframes/` folder before starting Phase 0 in Claude Code.

## Files to copy

From your Tradingview folder, copy these two files into this folder:

| Source file | Rename to |
|---|---|
| `eigenview-wireframe.html` | `wireframe-v1.html` |
| `eigenview-wireframe-v2.html` | `wireframe-v2.html` |

After copying, this folder should contain:

```
docs/wireframes/
├── README.md           (this file)
├── wireframe-v1.html   (first iteration — card-based)
└── wireframe-v2.html   (LOCKED — base UI on this)
```

## Which one is the source of truth

**`wireframe-v2.html` is the locked design.** When building UI, match this wireframe.

`wireframe-v1.html` is preserved for reference only — it shows the design evolution and earlier card layout before the chat dock and category nav were added.

## What v2 contains (visual reference)

- **App shell:** 3-column grid `220px | 1fr | 340px`, header `56px`
- **Header:** brand mark, search input, date, theme toggle
- **Left nav:** category groups (Daily Feed, Watchlists, History, Tools)
- **Market context strip:** 4 cells with hover tooltips (definition · now · so-what)
- **Picks views:** card grid (default), list, dense table — toggle in top-right
- **Detail view:** chart with TA + GEX overlay, factor strip (6 cells), tabs (Dormant Bet, News, Structure, History, Related)
- **AI chat dock:** persistent right-side, context-aware, suggested-prompt chips
- **Theme toggle:** dark + light fully implemented

## How Claude Code should use the wireframes

1. **Open `wireframe-v2.html` in a browser** at the start of any UI work
2. **Copy CSS variables** from the wireframe into `web/design-tokens.css` — match exactly
3. **Per-module: extract the relevant section** from the wireframe HTML, port it to a module file in `web/modules/<module-id>.{js,css}`, and wire to live data
4. **Don't reinvent visual decisions.** If the wireframe shows a chip with a specific border radius and color, that's the chip. Don't redesign it.
5. **For details the wireframe doesn't cover** (loading states, empty states, error states), follow `docs/10-ux-patterns.md`

## What the wireframes don't show (build per docs)

- Empty states (see `docs/10-ux-patterns.md`)
- Loading states (skeleton screens — see `docs/10-ux-patterns.md`)
- Custom canvas / drag-drop (see `docs/04-templates.md`)
- Mobile responsive behavior (out of scope for v1)
- Settings page, Journal page, Closed Picks archive (build per `docs/02-modules.md`)
- Real chart engine (wireframe uses static SVG — replace with TradingView Lightweight Charts per `docs/05-architecture.md`)
