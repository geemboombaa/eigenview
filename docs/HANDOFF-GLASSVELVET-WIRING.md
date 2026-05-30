# EigenView Dashboard — Glass Velvet Wiring Handoff

**Status:** Visual theme locked. Layout locked. Next step: make functional with real data + full search/sort/filter flexibility.

**Selected theme:** Glass Velvet (frosted glass surfaces, animated gradient base, Vision Pro inspired).

**Reference file:** `web/mockups/themes/b-glass.html` — visual styles to keep verbatim. Same CSS variables, same glassmorphism approach, same Inter + JetBrains Mono typography.

---

## What ships

A single-page dashboard. No panel framework, no chart panel. One scrollable canvas with five regions stacked top-to-bottom:

1. **Regime bar** (sticky top)
2. **Mode tabs + search + filter chips** (sticky under regime bar)
3. **Main data table** (single table, mode switches its contents)
4. **Bottom action bar** (slides up on row click; ✕ or click-same-row dismisses)
5. **TradingView link per row** (no in-app chart)

Glass Velvet aesthetic applied to every region. No gray-on-gray. No dull. Min 13px body text, 11px for labels only.

---

## Mode rules — STRICT, NO CAPS ANYWHERE

| Mode | Source endpoint | What it shows | Cap |
|---|---|---|---|
| **DAILY** | `GET /api/picks` (today) — fall back to most recent `/api/picks/dates` if today empty | Every pick from latest scan. Banner shown if not today. | **NONE** |
| **WEEKLY** | `GET /api/picks/week` (last 7 days excluding today) | Every pick from prior 7 days. Grouped by date in UI. | **NONE** |
| **ALL** | `GET /api/signals/matrix?date=<latest>` filtered to `ta_str > 0 OR dormant_str > 0` (passing TA gate OR Dormant gate) | Every ticker passing TA or Dormant. | **NONE** |

**Banned:** `.slice(0, N)`, `LIMIT N`, `_TOP_N`, "top 5", "max picks", anything that caps row count. Filter by gate criteria only. If 200 tickers pass, show 200. If 3, show 3.

**Daily pick highlighting:** Tickers in the Daily set get a colored left-border (green long / red short) in WEEK and ALL views too. Set `class="today-pick"` on the row when `tickerSet.has(row.ticker)`.

---

## Columns (table)

| Column | Source | Sortable | Searchable | Default visible | Default hidden |
|---|---|---|---|---|---|
| Ticker | row.ticker | ✓ | ✓ | ✓ | |
| Direction | row.direction / row.dir | ✓ | ✓ | ✓ | |
| Conviction | row.conviction / row.conv | ✓ | (numeric filter) | ✓ | |
| TA strength | row.fStr.ta | ✓ | (numeric filter) | ✓ | |
| GEX strength | row.fStr.gex | ✓ | (numeric filter) | ✓ | |
| Flow strength | row.fStr.flow | ✓ | (numeric filter) | ✓ | |
| Dormant strength | row.fStr.dorm | ✓ | (numeric filter) | ✓ | |
| Sentiment strength | row.fStr.sent | ✓ | (numeric filter) | ✓ | |
| Freshness | row.freshness | ✓ | ✓ | ✓ | |
| TradingView ↗ | computed link | — | — | ✓ | |
| Setup type | row.setup_type / row.setup | ✓ | ✓ | | ✓ |
| Call Wall | row.gex.call_wall | ✓ | (numeric) | | ✓ |
| Put Wall | row.gex.put_wall | ✓ | (numeric) | | ✓ |
| Gamma Flip | row.gex.gamma_flip | ✓ | (numeric) | | ✓ |
| Entry | row.entry_low / row.entry[0] | ✓ | | | ✓ |
| Stop | row.stop | ✓ | | | ✓ |
| Target | row.target | ✓ | | | ✓ |
| Spot | row.spot | ✓ | | | ✓ |
| Date | row.date | ✓ | ✓ | (in Week mode only) | |

**Column visibility toggle:** ⚙ COLS button in filter row opens a popover. Each column has a checkbox. Saved per view in localStorage.

**Sort:** click header — toggle asc/desc. Shift+click for secondary sort. Daily picks always float to top of WEEK/ALL regardless of sort.

---

## Search — required across all columns

Single search input at top of filter row. Behaviour:

- Searches across all text columns (ticker, direction, setup, freshness, date)
- Case-insensitive substring match
- Multiple space-separated terms = AND (must match all in any column)
- Example: `NVDA short fresh` matches a row where ticker=NVDA AND direction=SHORT AND freshness=fresh
- Numeric column filters live on column header (funnel icon) — open popover with min/max sliders
- ESC clears search
- Search state persists per mode in localStorage

Implementation: build a `searchString(row)` = `[ticker, dir, setup, freshness, date].join(' ').toLowerCase()`. Filter rows where every term in query appears in searchString OR in numeric range filters.

---

## Filter chips — pre-built quick filters

Chip row below mode tabs. Active chips combine with AND logic. All chips toggle.

- `LONG` `SHORT` — direction
- `CONV 4+` `CONV 5` — minimum conviction
- `FLOW ✓` `DORM ✓` `SENT ✓` `GEX ✓` — factor firing (strength > 0)
- `FRESH` — only fresh signals
- `GEX LONG γ` `GEX SHORT γ` — GEX regime label match
- `IN PICKS` — ticker is in today's daily picks
- `CLEAR` — wipes all filters + search

Filter state persists per view in localStorage. Chip-level filters apply on top of search. Counter chip `(N)` next to mode tab shows post-filter count.

---

## Saved Views — required

Button: `+ SAVE VIEW` in filter row. Modal: name input, save. Stored in localStorage under `ev:views`. Each view captures:

- Mode (daily/weekly/all)
- Search query
- Active filter chips
- Visible columns
- Sort key + direction
- Optional: numeric range filters per column

Dropdown next to mode tabs: `View ▾` lists all saved views + 4 pre-built defaults:

- **Morning Alpha** — Daily, FRESH, CONV 4+, sorted by conviction desc
- **Dormant Watch** — All, DORM ✓, sorted by dormant strength desc
- **Flow Surge** — All, FLOW ✓, sorted by flow strength desc
- **Short Book** — Weekly, SHORT only, sorted by date desc

Pre-built defaults are seeded on first load if not already in localStorage.

URL params support: `?view=Morning+Alpha` loads that view on page open. Used for sharing.

---

## Favorites — required

Star icon on every row. Click to toggle. Favorites persist in localStorage under `ev:favs`.

- ★ FAVS button in top bar shows count badge
- Click button → popover lists all faved tickers with current direction/conv
- Click ticker in popover → scroll-into-view + highlight row + open action bar
- Faved tickers float to top of any sort (above daily-pick float)

Sort priority within a view: favorites first → today picks → user sort.

---

## Row interaction

- **Click row** → bottom action bar slides up with full detail (entry / stop / target / call wall / put wall / γ regime / thesis / TradingView ↗)
- **Click same row again** → action bar dismisses (toggle)
- **Click ✕** → action bar dismisses
- **Click another row** → action bar updates with new row (stays open)
- **Click ↗ icon in row** → opens TradingView in new tab, no action bar change (`event.stopPropagation()` required)
- **Star icon** → toggles fav, no row select (`event.stopPropagation()` required)

---

## TradingView linking

Format: `https://www.tradingview.com/chart/?symbol=<EXCHANGE>%3A<TICKER>`

Default exchange: `NASDAQ`. If row has `row.exchange` field, use it. Future enhancement: maintain a `EXCHANGE_MAP = {AAPL: 'NASDAQ', NYSE_tickers: 'NYSE', ...}` — for MVP, NASDAQ default is acceptable for the universe (NDX100 + SP500).

---

## Mobile (320px–760px)

- Regime cells wrap to second row
- Filter row collapses to: search + mode tabs visible; chips behind a `Filters ▾` button
- Default columns: Ticker + Dir + Conv + Freshness + ↗ (5 cols)
- Table cells: 11px padding, 12.5px body text
- Tap row → action bar fills bottom 60% of viewport (drawer style)
- Touch targets minimum 44px
- ⚙ COLS modal becomes full-screen sheet

Glass blur effects work on mobile — test FPS, reduce blur radius from 32px to 18px if jank.

---

## API endpoints — confirmed working

Base: `http://localhost:8000` (FastAPI). All return JSON. CORS open.

```
GET  /api/health                            → {status, service}
GET  /api/market/regime                     → {regime, score, dix, gex_index, vix_m1, vix_m2, vix_contango_pct, narrative, date}
GET  /api/picks                             → array of today's picks (may be empty)
GET  /api/picks?date=YYYY-MM-DD             → picks for specific date
GET  /api/picks/dates                       → array of all dates with picks
GET  /api/picks/week                        → last 7 days of picks, excluding today
GET  /api/signals/matrix?date=YYYY-MM-DD    → {date, rows: [...]} every ticker scored
POST /api/scan                              → triggers daily scan (4h cooldown)
GET  /api/scan/status                       → {running, message, picks, error, last_scan_at}
```

Pick row shape (from `/api/picks` and `/api/picks/week`):
```json
{
  "ticker": "AMD",
  "date": "2026-05-24",
  "direction": "short",
  "setup_type": "overbought_reversal",
  "conviction": 4,
  "entry_low": 429.8,
  "entry_high": 461.0,
  "stop": 470.22,
  "thesis": "...",
  "spot": null,
  "freshness": "stale",
  "signal_fired_at": "2026-05-24T22:34:12",
  "signal_age_hours": 103.0,
  "structure": {...},
  "factors": {
    "technical": {"firing": true, "strength": 0.73, "label": "overbought_reversal", "detail": {...}},
    "gex":       {"firing": true, "strength": 0.10, "label": "long_gamma", "detail": {"call_wall": 500, "put_wall": 250, "gamma_flip": 14.7, "regime": "long_gamma"}},
    "flow":      {"firing": true, "strength": 1.0, ...},
    "dormant":   {...},
    "sentiment": {...}
  }
}
```

Matrix row shape (from `/api/signals/matrix`):
```json
{
  "ticker": "AAPL", "setup_type": "...", "in_picks": false, "conviction": 0,
  "spot": 308.61, "macro_str": 0.0,
  "ta_str": 0.78,  "ta_label": "...",
  "gex_str": 0.10, "gex_label": "...",
  "flow_str": 1.0, "flow_label": "...",
  "dormant_str": 0.0,  "dormant_label": "...",
  "sentiment_str": 0.0, "sentiment_label": "...",
  "factors_firing": 4
}
```

Regime shape (from `/api/market/regime`):
```json
{"regime": "GREEN|YELLOW|RED|UNKNOWN", "score": 0-10, "dix": 0.471, "gex_index": 4.2e9, "vix_m1": 14.2, "vix_m2": 15.1, "vix_contango_pct": 6.4, "narrative": "...", "date": "2026-05-26"}
```

---

## Where the current mockup falls short — fix these

The existing `b-glass.html` was a quick visual mockup. The next session must do all of the following:

1. **Move shared logic into modules.** Currently `_render.js` is shared with theme A/C/D. Build dedicated Glass Velvet files in `web/dashboard/` (NOT mockups/).
2. **Add real search input** with multi-term AND logic across text columns.
3. **Add column visibility toggle** with ⚙ COLS popover. Persist in localStorage.
4. **Add Saved Views** with localStorage + URL param support + 4 pre-built defaults.
5. **Add Favorites** with star toggle, count badge, popover list.
6. **Add numeric range filters** on header click for strength/price columns.
7. **Add SCAN button + scan status polling** (already in old `_panels.js`, port the logic).
8. **Daily pick highlighting** in Week + All modes (left border + subtle row glow).
9. **Mobile breakpoints** — test on 360px, 768px, 1024px.
10. **No row caps** — search/grep for `slice`, `_TOP_N`, `LIMIT`, `top` in code review.
11. **Replace existing `/dashboard.html`** if there is one — point to new file.

---

## Files to create / edit

```
web/dashboard/
├── index.html              # Glass Velvet dashboard (new)
├── glass.css               # Visual tokens + components (extracted from b-glass.html)
├── data.js                 # API loader, no caps, normalizers
├── render.js               # Table render, search, sort, filter
├── views.js                # Saved views + favs + localStorage
└── README.md               # Run instructions

docs/
└── 13-dashboard-spec.md    # Lock all decisions from this handoff into project docs
```

Run with: `uv run uvicorn eigenview.api.main:app --port 8000` then open `http://localhost:8000/dashboard/` (FastAPI already serves `web/` as static).

---

## Acceptance criteria (must all pass before declaring done)

- [ ] Open `http://localhost:8000/dashboard/` shows live regime bar with real macro data (or honest "no macro data" message)
- [ ] DAILY mode shows every today pick — count visible in tab badge
- [ ] WEEKLY mode shows every pick from last 7 days, grouped by date label
- [ ] ALL mode shows every ticker where TA OR Dormant strength > 0 — no cap
- [ ] Search `NVDA short` filters to NVDA short rows
- [ ] Sort by any column works ascending and descending
- [ ] Filter chips toggle correctly, combine with AND
- [ ] Saved view persists in localStorage and reloads on refresh
- [ ] URL `?view=Morning+Alpha` loads that view
- [ ] Favorite a ticker, refresh page, star still on
- [ ] Click a row → action bar slides up with entry/stop/walls/thesis + TradingView link opens in new tab
- [ ] Click same row → action bar dismisses
- [ ] Mobile 360px width shows 5 columns, no horizontal scroll, drawer works
- [ ] SCAN button triggers `/api/scan`, polls status, refreshes data when done
- [ ] No `slice(0,N)`, no `_TOP_N`, no row caps anywhere in `data.js` or `render.js`
- [ ] Glass blur is smooth on mobile (no jank at 360px)

---

## Out of scope for this session

- Chart panel (dropped — TradingView opens in new tab instead)
- News panel wiring (`/api/news` — separate session)
- Dormant Radar panel wiring (separate session)
- AI Chat wiring (`/api/chat` — separate session)
- Voice / orb (already in old chrome — port if time, otherwise defer)
- Streaming updates (poll on SCAN complete; live websocket = later)

---

## Test data state

As of 2026-05-29:
- `picks` table: 3 rows from 2026-05-24 (AMD, ADBE, ADSK — all short)
- `factor_scores` table: 504 rows from 2026-05-26
- `signal_triggers` table: 558 rows total, latest 2026-05-26
- `macro_daily` table: rows present but may have nulls — regime falls back to "no macro data" gracefully

When no picks for today: fall back to most recent date in `/api/picks/dates` and show banner: `Showing scan from <date> — run SCAN for today`.
