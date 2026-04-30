# 02 — Module Catalog

Every panel in the UI is a **self-contained module**. A module owns its data contract, renders at any size, emits events, and can be placed on any canvas. UI design = module composition.

## Module specification format

Every module is specified with:
- **ID** — short slug (e.g. `market-context`)
- **Purpose** — one sentence
- **Sizes supported** — S / M / L / XL (defines min/max responsive grid cells)
- **Data contract** — what it subscribes to from the global state
- **Emits** — events it fires when user interacts
- **Config options** — per-instance settings (if any)

---

## Module Catalog

### Context & Navigation

#### `market-context`
- **Purpose:** Show current market regime (SPY GEX, VIX term, short-gamma sectors, macro flags) with hover explainers
- **Sizes:** S (compact strip), M (4 cells)
- **Data:** `/api/market/context`
- **Emits:** `macro_flag_click`
- **Config:** show/hide specific cells

#### `category-nav`
- **Purpose:** Left-sidebar navigation across pick categories (Today's Picks, Earnings, Dormant, Compression, Reversals, Macro, Signal Bench, My List, Closed, Alerts)
- **Sizes:** S (collapsed icon-only), M (full labels), L (with live counts)
- **Data:** `/api/categories/counts`
- **Emits:** `category_selected`
- **Config:** collapsed by default, categories visible

#### `global-search`
- **Purpose:** Search ticker / factor / chat across the app
- **Sizes:** S (header inline), M (expanded overlay)
- **Data:** `/api/search`
- **Emits:** `result_selected`

#### `theme-toggle`
- **Purpose:** Switch dark / light
- **Sizes:** S
- **State:** local

### Feed views (mutually exclusive in a given slot)

#### `pick-cards`
- **Purpose:** Card grid of today's picks with thesis, conviction, factor chips
- **Sizes:** M, L, XL
- **Data:** `/api/picks?category=<cat>`
- **Emits:** `pick_selected`

#### `pick-list`
- **Purpose:** Compact one-line-per-pick list
- **Sizes:** M, L
- **Data:** same as `pick-cards`
- **Emits:** `pick_selected`

#### `pick-table`
- **Purpose:** Dense table with sortable columns (ticker, conviction, IV rank, GEX, flow, dormant, catalyst, pattern, hit%)
- **Sizes:** L, XL
- **Data:** same
- **Emits:** `pick_selected`, `column_sorted`

#### `mini-chart-grid`
- **Purpose:** Grid of small price-action charts for quick scan
- **Sizes:** L, XL
- **Data:** `/api/picks` + `/api/chart/<ticker>`
- **Emits:** `pick_selected`

### Pick Detail (each independently placeable)

#### `price-chart`
- **Purpose:** Main chart with TA overlay (EMAs, levels, patterns) + GEX walls + VPOC + gamma flip
- **Sizes:** L, XL
- **Data:** `/api/chart/<ticker>?tf=<1H|1D|1W>`
- **Emits:** `tf_changed`, `level_clicked`
- **Config:** timeframe default, indicators visible

#### `factor-strip`
- **Purpose:** 6-cell horizontal strip showing each factor's state for the selected pick
- **Sizes:** M (wraps to 2 rows), L (single row)
- **Data:** `/api/pick/<ticker>/factors`
- **Emits:** `factor_clicked` → opens explanation

#### `dormant-bet-panel`
- **Purpose:** Full detail of any dormant bets activating on the selected ticker (original bet date/strike/expiry/premium, stock behavior since, ML activation prob, narrative)
- **Sizes:** M, L
- **Data:** `/api/pick/<ticker>/dormant`
- **Emits:** `explain_clicked`

#### `news-sentiment`
- **Purpose:** LLM-filtered news items with novelty z-scores and "why it matters"
- **Sizes:** M, L
- **Data:** `/api/pick/<ticker>/news`
- **Emits:** `news_clicked`

#### `suggested-structure`
- **Purpose:** AI-generated options structure recommendation with trigger / invalidation / R:R
- **Sizes:** M, L
- **Data:** `/api/pick/<ticker>/structure`
- **Emits:** `alternative_clicked`

#### `history-hit-rate`
- **Purpose:** Historical performance cards for this pattern, this ticker, this factor combination
- **Sizes:** M, L
- **Data:** `/api/pick/<ticker>/history`

#### `related-setups`
- **Purpose:** Similar active picks + historical analogues of this setup on this ticker
- **Sizes:** S, M
- **Data:** `/api/pick/<ticker>/related`

#### `alert-setup`
- **Purpose:** Configure price/condition alerts on this pick
- **Sizes:** S, M
- **Data:** writes to `/api/alerts`

### Intelligence

#### `ai-chat`
- **Purpose:** Persistent AI chat dock, context-aware (knows selected pick)
- **Sizes:** M (narrow dock), L (wide dock), XL (full-screen)
- **Data:** `/api/chat` (SSE stream)
- **Emits:** `command_issued` (for NL filter/view commands)
- **Config:** suggested-prompt chips visible, context-chip visible

#### `ask-about-this`
- **Purpose:** Contextual chat entry button on any pick — prefills a query about that specific pick
- **Sizes:** S (inline button)
- **Emits:** `chat_opened_with_context`

### Workflow

#### `closed-picks`
- **Purpose:** Archive of historical picks with outcomes (hit / miss / still open), P&L, time held
- **Sizes:** L, XL
- **Data:** `/api/picks/closed`

#### `journal`
- **Purpose:** User's trade journal — log entries, link to picks, review notes
- **Sizes:** M, L

#### `settings`
- **Purpose:** User preferences, data source config, universe management
- **Sizes:** L

---

## Module framework (implementation note)

Every module must implement a common interface:

```javascript
class Module {
  static id = 'module-id';
  static defaultSize = 'M';
  static supportedSizes = ['S', 'M', 'L'];

  constructor(container, config, store) { ... }
  mount() { ... }              // render into container
  unmount() { ... }            // cleanup, remove event listeners
  onStateChange(key, value) { ... }  // react to global state changes
  resize(size) { ... }         // re-render for new size
}
```

Canvas (template renderer) reads a layout config (array of `{module, size, position}`), instantiates each module, and mounts them into a CSS grid. Users drag to move, resize, or delete.
