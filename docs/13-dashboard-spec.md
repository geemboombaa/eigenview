# 13 — Glass Velvet Dashboard Spec (locked 2026-05-29)

Single-page dashboard, wired to the live FastAPI on `:8000`, served same-origin at
`http://localhost:8000/dashboard/`. Theme: **Glass Velvet** — frosted glass surfaces,
animated gradient base, Inter + JetBrains Mono. Visual tokens lifted verbatim from
`web/mockups/themes/b-glass.html`.

## Hard rules (user-locked, non-negotiable)

1. **No caps anywhere.** No `slice(0,N)`, no `LIMIT`, no `_TOP_N`, no "top". Show what the
   scan returns. The backend `max_picks` cap was removed too.
2. **No fallback** to old scan dates. No "virtual today" promotion. Today is empty until a
   scan runs — that is the honest state.
3. **No invented thresholds.** No client-side `ta_str > 0.5` style magic numbers. Row
   inclusion is the backend's decision, surfaced as-is.
4. **No fake data, no stubs, no mocks.** Real endpoints only.
5. **No data download triggered during dev.** The SCAN button is the only thing that starts a
   real download, and only when the user clicks it.

## Three lists

| List | Source | Definition |
|---|---|---|
| **DAILY** | `GET /api/picks` (today, no date param) | Today's final picks — every ticker that passed the full gate (macro OK, TA firing, GEX firing, ≥2 of flow/dormant/sentiment). No cap. |
| **WEEKLY** | `GET /api/picks/week` | Picks from the prior 7 days, today excluded. Each ticker is the store of "moved from daily, kept a week." |
| **ALL** | `GET /api/signals/matrix` (today) | Every scanned ticker where **TA OR dormant** fired, with all five factor strengths. No cap. |

### Dedupe rule — "today wins"
- A ticker present in today's DAILY is **removed** from the WEEKLY list.
- WEEKLY shows each ticker **once** — its most recent prior-day alert.
- DAILY tickers get a colored left border (green long / red short) wherever they appear in
  WEEKLY and ALL too.

## Columns

Default visible: Ticker, Direction, Conviction, TA, GEX, Flow, Dormant, Sentiment, Freshness,
TradingView ↗.
Default hidden (toggle on): Setup, Call Wall, Put Wall, Gamma Flip, Entry, Stop, Target, Spot.
Date column shows in WEEKLY (and ALL when available).

Each column wires 1:1 to a real field. ALL-mode rows come from the matrix and have no
entry/stop/wall fields — those cells render "—", never faked. Direction in ALL is inferred from
`setup_type` (short patterns → short, else long); this is display inference, not data invention.

## Search
Single input. Multi-term, space-separated = AND. Case-insensitive substring across all text
columns (ticker, direction, setup, freshness, date). ESC clears. Persists per mode.

## Filter chips (AND logic, all toggle)
LONG · SHORT · CONV 4+ · CONV 5 · FLOW ✓ · DORM ✓ · SENT ✓ · GEX ✓ · FRESH ·
GEX LONG γ · GEX SHORT γ · IN PICKS · CLEAR. Persist per view.

## Numeric range filters
Funnel icon on numeric headers (strengths, prices) → min/max popover. Combine with chips +
search. Persist per view.

## Sort
Click header asc/desc. Shift+click adds secondary. Sort priority within a view:
favorites → today picks → user sort.

## Column visibility
⚙ COLS popover, checkbox per column, persisted per view in localStorage.

## Saved views
`+ SAVE VIEW` captures mode, search, chips, visible columns, sort, numeric filters.
Stored under `ev:views`. `View ▾` dropdown lists saved + 4 seeded defaults:
- **Morning Alpha** — Daily, FRESH + CONV 4+, sort conviction desc
- **Dormant Watch** — All, DORM ✓, sort dormant desc
- **Flow Surge** — All, FLOW ✓, sort flow desc
- **Short Book** — Weekly, SHORT, sort date desc

URL `?view=Morning+Alpha` loads that view on open (shareable).

## Favorites
Star per row → `ev:favs`. ★ FAVS button shows count + popover list; click a ticker → scroll +
highlight + open detail bar. Faved tickers float to the very top.

## Row detail bar
Click row → bottom bar slides up: direction + ticker, entry / stop / target / call wall /
put wall / γ regime, thesis, "Open in TradingView" (new tab). Click same row or ✕ → dismiss.
Click another row → updates in place. ↗ and ★ stop propagation (no row select).

## TradingView link
`https://www.tradingview.com/chart/?symbol=NASDAQ%3A<TICKER>`. NASDAQ default for the NDX/SPX
universe. Uses `row.exchange` if present.

## SCAN button (async, non-blocking)
```
press SCAN:
  if engine already running -> show its status, do nothing
  else POST /api/scan -> {status: started | too_recent | already_running}
       if too_recent -> show the engine's cooldown message verbatim (4h gap)
  show animated progress bar + live status text
  poll GET /api/scan/status every ~2s -> update bar + text
  when running flips false -> reload daily/weekly/all -> table refreshes
UI stays fully usable (search/sort/filter/click) the whole time.
```
The engine reports a text status and running/done flag — **no exact percentage**. Progress bar
is an indeterminate "working" animation + the status text. A real % bar needs the engine to
report a count (future backend change).

## Mobile (320–760px)
Regime cells wrap. Chips behind a `Filters ▾` button. Default 5 columns
(Ticker, Dir, Conv, Freshness, ↗). Row tap → drawer fills bottom 60%. Touch targets ≥44px.
Glass blur reduced 32→18px if jank.

## Files
```
web/dashboard/
  index.html   page shell, wires modules
  glass.css    visual tokens (verbatim) + components
  data.js      fetch real endpoints, normalize, NO caps, NO fallback
  table.js     render + sort + search + numeric filters
  filters.js   chips + column visibility
  views.js     saved views + favorites + localStorage + URL params
  scan.js      scan trigger + status poll + progress bar
```

## Backend changes made for this (2026-05-29)
- Removed `max_picks` cap (ranker, config, env, this spec, CLAUDE.md).
- Matrix endpoint filter: `ta>0` → `ta>0 OR dormant>0`.
No other backend logic touched.

## Acceptance (all must pass)
Regime bar real (or honest "no macro"); DAILY/WEEKLY/ALL show full counts in tab badges;
search/sort/chips/numeric filters work; saved view persists + `?view=` loads; favorite
survives refresh; row detail bar + TradingView; mobile 360px 5-col no h-scroll; SCAN polls +
refreshes + honest cooldown; **zero caps in code**; glass smooth on mobile.
