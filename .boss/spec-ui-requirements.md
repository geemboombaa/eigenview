# EigenView UI Requirements — Phase 4 Approved Design

## Approved Design: Option A (modified)

User approved Option A wireframe with the following changes locked:

---

## Acceptance Criteria

### AC1 — Pick card: remove clutter
GIVEN a pick card renders
THEN no AI commentary/thesis text appears on the card (thesis lives in AI panel only)
AND no valid_until statement is shown
AND no PRIMARY/tier badge is shown
AND no star/favorite icon or 3-dot menu is shown
AND only: ticker, direction, bucket tag, setup name, factor dots, entry/stop, R:R remain

### AC2 — Pick card: color contrast
GIVEN any two adjacent UI elements on a pick card
WHEN rendered
THEN foreground color has contrast ratio ≥ 4.5:1 against its background
AND no green text appears on green-tinted background
AND no gray text appears on same-shade-gray background
AND the overall layout does not read as "greenish wash"

### AC3 — Chart header: layout
GIVEN a ticker is selected
WHEN chart header renders
THEN layout is: [TICKER] [WEEKLY STATE PILL] [SIGNAL BADGE]
AND weekly state pill (BULLISH/NEUTRAL/BEARISH) appears between ticker and signal badge
AND no EMA/RSI/ADX text values appear in the weekly strip or header

### AC4 — Chart overlays: entry markers visible by default
GIVEN a pick with entry/stop/target data
WHEN chart first renders
THEN entry zone band, stop dashed line, and target dashed line are all visible (ON by default)
AND toggles for ENTRY, STOP, TARGET are present in the toolbar in ON state

### AC5 — Chart overlays: GEX walls shown with toggle
GIVEN chart toolbar
WHEN rendered
THEN GEX LEVEL, CALL WALL, PUT WALL toggles are present and default to ON
AND when toggled OFF the corresponding horizontal lines disappear from chart
AND when no GEX data is available the toggles are disabled/grayed

### AC6 — Factor strip: blank when no data
GIVEN any factor tab (TA, GEX, FLOW, DORM, SENT)
WHEN the data for that factor is unavailable or insufficient
THEN the tab body is empty — no placeholder text, no "need 30 days" messages, no loading state
AND when data is available the tab renders normally with checklist/values

### AC7 — All panels: movable and resizable
GIVEN any panel (left picks column, center chart, right AI chat, factor strip)
WHEN user drags the panel header
THEN panel moves to new position
AND when user drags the resize handle at panel edges
THEN panel resizes
AND the layout state is persisted to localStorage and restored on next load

### AC8 — Scan logic: configurable thresholds
GIVEN scan output rules (PRIMARY vs WATCH vs HIDDEN thresholds)
WHEN the following env vars are set: PRIMARY_MIN_CONVICTION, WATCH_MIN_CONVICTION, RR_MIN_RATIO, SIGNAL_VALID_DAYS
THEN scanner uses those values instead of hardcoded defaults
AND changing thresholds requires no code changes, only config file update

### AC9 — Matrix view: merged TA/BUCKET column
GIVEN matrix table renders
THEN SETUP and BUCKET are a single "TA / BUCKET" column
AND each cell shows: "Setup Name · BUCKET ●" where ● is colored per bucket
AND all column headers are clickable to sort ascending/descending
AND the full table is visible without horizontal clipping (scroll allowed, clipping not)

---

## Out of Scope
- Template switcher (post-MVP)
- Custom canvas / drag-drop canvas builder (post-MVP)
- Option B data-rich view (not chosen)
- Scan logic UI configuration panel (env/config file is sufficient for v1)

## Dependencies
- Approved wireframe: docs/wireframe-ux-options.html (v2 to be committed on feature branch)
- issues: REQ-UX-1 through REQ-UX-7 on GitHub
- Implementation blocked until UI issues created and CI audit passed (step 20/21)
