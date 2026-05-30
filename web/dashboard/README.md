# EigenView — Glass Velvet Dashboard

Single-page dashboard wired to the live FastAPI. Real data only — no caps, no fallback, no
mocks. Full spec: `docs/13-dashboard-spec.md`.

## Run

```powershell
uv run uvicorn eigenview.api.main:app --port 8000
```
Open: **http://localhost:8000/dashboard/**

FastAPI serves `web/` as static, so the page is same-origin with the API (relative `/api/...`
fetches, no CORS dance).

## Files
| File | Job |
|---|---|
| `index.html` | Page shell, loads the modules |
| `glass.css` | Glass Velvet visual tokens (from `mockups/themes/b-glass.html`) + components |
| `data.js` | Fetches real endpoints, normalizes rows. No caps, no fallback dates, no invented thresholds |
| `filters.js` | Column registry, quick-filter chips, search + numeric predicates |
| `views.js` | Favorites + saved views + UI-state persistence (localStorage) |
| `scan.js` | SCAN trigger + status polling + progress bar |
| `table.js` | Controller: regime / tabs / chips / table / action bar / popovers |

## The three lists
- **DAILY** — today's final picks (`/api/picks`). Every ticker that passed the gate. No cap.
- **WEEKLY** — prior 7 days' picks (`/api/picks/week`), today excluded; today's tickers removed;
  one row per ticker (most recent). Grouped by date.
- **ALL** — every scanned ticker where TA or dormant fired (`/api/signals/matrix`). No cap.

## Features
Search (multi-term AND across text columns, ESC clears) · sort (click header, shift-click =
secondary) · quick-filter chips (AND) · numeric range filters (⏷ on numeric headers) · column
show/hide (⚙ COLS) · saved views + 4 seeded defaults + `?view=Name` shareable URL · favorites
(★, count badge, jump-to-row) · row detail bar (entry/stop/walls/γ/thesis + TradingView) ·
SCAN button (async, progress bar, polls status, auto-refresh, honest 4h-cooldown message) ·
full mobile layout (5 columns, drawer action bar).

## localStorage keys
`ev:favs` · `ev:views` · `ev:ui` (last mode/search/chips/numeric/cols/sort).

## Notes
- The scan engine reports a text status + running flag, no percentage → the progress bar is an
  indeterminate "working" animation plus the live status text.
- Pre-scan, today's lists are empty by design — that is the honest state. Hit SCAN to populate.
