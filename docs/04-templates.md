# 04 — UI Templates

Five preset layouts shipped out of the box. User picks one at first run, can switch anytime, or build their own via drag-drop canvas.

Templates are JSON configs describing which modules to render at which grid positions and sizes.

## Template 1 — Minimal

**For:** users who want signal-only, nothing else.

```json
{
  "id": "minimal",
  "name": "Minimal",
  "grid": "1fr 320px",
  "rows": "auto",
  "modules": [
    { "id": "category-nav",  "col": 1, "row": 1, "size": "S" },
    { "id": "pick-cards",    "col": 1, "row": 1, "size": "M" },
    { "id": "ai-chat",       "col": 2, "row": 1, "size": "M" }
  ]
}
```

Layout: narrow left nav, picks center, chat right. No market context strip, no detail view inline (picks open chat preview on click, full detail in modal).

---

## Template 2 — Standard (default)

**For:** typical user — context + feed + detail + chat.

```json
{
  "id": "standard",
  "name": "Standard",
  "grid": "220px 1fr 340px",
  "rows": "56px 1fr",
  "modules": [
    { "id": "category-nav",     "col": 1, "row": "1/3", "size": "M" },
    { "id": "global-search",    "col": 2, "row": 1, "size": "S" },
    { "id": "theme-toggle",     "col": 3, "row": 1, "size": "S" },
    { "id": "market-context",   "col": 2, "row": 2, "size": "M" },
    { "id": "pick-cards",       "col": 2, "row": 2, "size": "M" },
    { "id": "detail-combo",     "col": 2, "row": 2, "size": "L" },
    { "id": "ai-chat",          "col": 3, "row": 2, "size": "M" }
  ]
}
```

`detail-combo` is a composite container that includes `price-chart` + `factor-strip` + tabs for `dormant-bet-panel` / `news-sentiment` / `suggested-structure` / `history-hit-rate` / `related-setups`.

---

## Template 3 — Pro Trader

**For:** power users who want dense data.

Modules:
- Category nav (left)
- Market context strip (top, compact)
- Pick **table** (default, not cards) — full grid with sortable columns
- Mini-chart grid below table
- Pick detail opens as **right-side drawer** over the feed
- AI chat as **bottom drawer** (press `/` to expand)

Motivation: let the user scan many data points at once, with chat available but not taking screen space.

---

## Template 4 — Research

**For:** idea hunters, not execution-focused.

Modules:
- `dormant-bet-panel` front and center (shows all active dormant bets, not just selected pick)
- `history-hit-rate` prominent
- `related-setups` expanded
- `closed-picks` archive visible in sidebar
- `ai-chat` full-height on right, used for "find me setups like X"

No suggested structure, no alerts — this template is for exploration, not trading.

---

## Template 5 — Focus

**For:** active trade monitoring on one pick.

Single selected pick fills the screen:
- `price-chart` at 70% width
- `factor-strip` below chart
- `ai-chat` right (narrow)
- `alert-setup` persistent at bottom

Minimal chrome. For when you're in a position and want to watch it.

---

## Custom canvas

Empty grid, user drags modules from a palette. Each module can be resized (S/M/L/XL), moved, removed. Layout saves to user settings. Can export / import layout JSON.

---

## Template switcher

Top-bar dropdown shows all templates + "Custom" + "Save current as template…". Switching preserves the currently-selected pick — just re-arranges the modules.
