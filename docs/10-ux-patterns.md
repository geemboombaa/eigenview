# 10 — UX Patterns

The interaction language of EigenView. These patterns are intentionally consistent — same gesture means the same thing across modules.

---

## Core principles

1. **Curated, not configurable.** No filter panels in default templates. The synthesis is the product.
2. **Explainability is one click away.** Every term in the UI is hover-explainable. Every pick has a "why this" answer accessible.
3. **Read first, write second.** Default modules show curated signal. Customization is opt-in.
4. **Same gesture, same meaning.** Click ticker = open detail. Hover label = explainer. ⌘K = search. Always.

---

## Key flows

### Flow 1 — Daily morning open

User opens dashboard at 8:30 AM ET.

1. Dashboard loads with **last completed daily scan** (8:00 AM run, cached in SQLite).
2. **Top strip** shows current market regime — user reads in 2 seconds.
3. **Pick cards** display 3–5 ranked picks. AI thesis on each card is the primary read.
4. User clicks the top conviction pick → detail view opens (chart + factors + tabs).
5. User checks dormant-bet panel (if firing) and structure tab.
6. User asks chat: "what would invalidate this?" → gets answer in plain English.
7. User decides to trade or skip.

Total time from open → decision: **<60 seconds per pick.**

### Flow 2 — "Why this pick?"

1. User clicks any pick card.
2. Detail view opens with chart + factor strip dominant.
3. User clicks any factor cell → it briefly highlights and pre-fills the chat: "Why is GEX firing on NVDA?"
4. Chat answers contextually, referencing the actual numbers, not boilerplate.
5. User asks follow-up — chat retains pick context.

### Flow 3 — Discover dormant-bet activations

1. User clicks "Dormant Bets Firing" in left nav.
2. Category page shows all picks where dormant-bet factor is firing (could overlap with Today's Picks or be separate).
3. Each card prominently displays the "◈ DORMANT FIRING" chip with original-bet date and stock-since-then movement.
4. Click → detail view → Dormant Bet tab open by default.

### Flow 4 — Switch templates

1. User clicks template name in top bar (default: "Standard").
2. Dropdown shows: Minimal · Standard · Pro Trader · Research · Focus · Custom · "Save current as…"
3. Selecting a template re-arranges modules. **Selected pick is preserved.**
4. User can save any layout as a custom named template.

### Flow 5 — Build custom canvas

1. User clicks "+ Custom Layout" or selects existing custom layout.
2. Empty grid appears with module palette on the side.
3. User drags modules onto grid cells. Resize handles appear on hover. Modules can be moved by drag or removed by ✕.
4. Saved automatically. Named on save.

### Flow 6 — Set an alert

1. User clicks the ⟁ ALERT button on any pick.
2. Modal: "Notify when NVDA crosses [trigger] / closes [invalid] / earnings hits / new factor fires"
3. Save → alert lives in left-nav "Alerts" section.
4. Notification fires via Windows toast (v1). Email/Telegram in v2.

---

## Interaction patterns

### Click

| Target | Action |
|---|---|
| Pick card | Open detail view |
| Ticker text in any module | Open detail view for that ticker |
| Factor cell in detail | Highlight + prefill chat with explainer prompt |
| News item | Expand "why it matters" inline |
| Tab | Switch tab content |
| Suggested-prompt chip | Send that prompt to chat |
| Theme toggle | Switch dark / light immediately |
| Category in left nav | Filter feed to that category |

### Hover

| Target | Action |
|---|---|
| Market context cell (SPY GEX, VIX, etc.) | Show 3-line tooltip: definition · current state · so-what |
| Factor cell | Show calculation detail tooltip |
| Conviction dots | Show "why N/5" tooltip with score breakdown |
| Pick card | Border highlight (var(--accent-dim)), translateY(-1px) |
| Chat suggested-prompt chip | Underline, color shift to accent |
| Module edge (custom canvas) | Show resize handle |

### Keyboard

| Key | Action |
|---|---|
| `⌘K` / `Ctrl+K` | Focus global search |
| `/` | Focus chat input |
| `Esc` | Close detail view / cancel modal |
| `↑ ↓` | Navigate pick cards |
| `Enter` on focused card | Open detail |
| `T` | Toggle theme |
| `1–5` | Switch to template 1–5 |
| `?` | Open keyboard shortcut overlay |

### Drag

| Target | Action |
|---|---|
| Module in custom canvas | Reposition (snap to grid) |
| Module corner | Resize (S/M/L/XL) |
| Pick card | (v1: nothing; v2: move to "My List") |

---

## Loading & empty states

### Loading

- Dashboard initial: skeleton screens (gray panels matching final layout) — never spinners
- Chat response: streaming token-by-token via SSE
- Pick detail switching: chart re-renders in <300ms on cached data

### Empty states (always have one)

| Scenario | Empty state |
|---|---|
| No picks today (no qualifications) | "No picks qualified today's gates. Rare but real. Check back tomorrow or browse Signal Bench." |
| Signal Bench empty | "No partial fires. Market is unusually neutral or scan hasn't run." |
| My List empty | "Pin tickers from any pick (⭐) to track them here." |
| Closed Picks empty | "Your closed picks will appear here as picks resolve." |
| Chat empty | "Hi. I'm reading [selected pick] alongside you. Ask me anything." |

---

## Error states

- API fetch failure: red border on affected module, retry button. Never block whole dashboard.
- Stale data: amber timestamp ("Last scan: 14h ago — refresh?")
- Chat error: inline message "Couldn't reach Claude — retry" with retry button.
- Auth failure: route to settings with clear message.

Never silent-fail. Never blank.

---

## Confirmation & destructive actions

- Deleting a custom layout: confirm modal
- Closing a pick (manual close in journal): confirm modal
- Resetting all settings: confirm modal with typed confirmation
- Switching theme / template: instant, no confirm

---

## Accessibility

- All flows must work without mouse (keyboard only)
- Screen reader labels on icon-only controls (⌘K, ⭐, ⟁, ⌕, ✓)
- Focus states visible — never `outline: none` without replacement
- Tab order matches visual order
- Live regions for chat streaming (`aria-live="polite"`)
