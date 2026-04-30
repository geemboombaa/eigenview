# 09 — Design System

The visual language for EigenView. All values extracted from the locked wireframe (`docs/wireframes/wireframe-v2.html`). Use these tokens — do not improvise colors, type, or spacing.

---

## Color tokens (CSS variables)

### Dark theme (default)

```css
--bg:          #0b0d12;   /* app background */
--bg-2:        #0f121a;   /* nav background */
--panel:       #12151d;   /* primary surface */
--panel-2:     #171b26;   /* secondary surface */
--panel-3:     #1d2231;   /* tertiary / chip surface */
--border:      #232836;   /* primary border */
--border-soft: #1a1e2a;   /* hairline / inner border */
--text:        #e7ebf3;   /* primary text */
--text-dim:    #8a92a6;   /* secondary text */
--text-faint:  #5b6377;   /* tertiary text, labels */
--accent:      #5ee3a1;   /* primary accent (long, success, AI) */
--accent-dim:  #2f8c63;   /* accent border / hover */
--long:        #5ee3a1;   /* long direction */
--short:       #ff6b6b;   /* short direction, danger */
--vol:         #d2a6ff;   /* vol play, AI badge color */
--warn:        #ffc857;   /* dormant bet, warning, gamma flip */
--info:        #6ab7ff;   /* info, VPOC */
--chip-bg:     #1d2231;
--chip-border: #2b3245;
```

### Light theme

```css
--bg:          #f6f7fa;
--bg-2:        #eff1f5;
--panel:       #ffffff;
--panel-2:     #fafbfd;
--panel-3:     #f1f3f8;
--border:      #dfe3eb;
--border-soft: #e8ebf0;
--text:        #16181d;
--text-dim:    #54606f;
--text-faint:  #8a94a5;
--accent:      #0d9d63;
--accent-dim:  #7ccba8;
--long:        #0d9d63;
--short:       #d9342b;
--vol:         #7c3aed;
--warn:        #b56a00;
--info:        #1e6fce;
--chip-bg:     #eef1f6;
--chip-border: #d7dce4;
```

Theme switches by setting `data-theme="dark"` or `data-theme="light"` on `<html>`.

---

## Typography

```css
--font-mono: 'SF Mono', 'Consolas', 'Monaco', monospace;   /* default UI */
--font-prose: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;  /* AI thesis, news, narrative */
--font-display: 'Georgia', serif;                          /* headers, brand mark */
```

**Type scale (px):**
- `9px` — meta labels, badges (letter-spaced 1.5px, uppercase)
- `10px` — secondary labels, source attribution
- `11px` — small body, dense table content
- `12.5px` — primary AI thesis text
- `13px` — base UI text
- `14px` — list-row tickers
- `16px` — section headers
- `18px` — page titles
- `20px` — pick card ticker
- `24–28px` — detail-view ticker

Line-height: 1.5 default, 1.55 for thesis prose, 1.4 for tight UI.

---

## Spacing scale (px)

`2 · 4 · 6 · 8 · 10 · 12 · 14 · 16 · 18 · 20 · 24 · 28`

No magic numbers. Every padding/margin uses the scale.

---

## Border radius

- `2–3px` — chips, badges
- `4–5px` — buttons, factor cells
- `6–8px` — cards, panels
- `10px` — chat message bubbles

---

## Component patterns

### Card (pick card, factor cell, panel block)

```
background: var(--panel)
border: 1px solid var(--border)
border-radius: 8px
padding: 14–18px
hover: border-color → var(--accent-dim), translateY(-1px)
active: border-color → var(--accent), box-shadow 0 0 0 1px var(--accent-dim)
transition: 0.12–0.15s
```

### Chip / badge

```
font-size: 9–10px
padding: 3px 7–8px
background: var(--chip-bg)
border: 1px solid var(--chip-border)
border-radius: 3px
color: var(--text-dim)
letter-spacing: 0.3px
```

**Chip variants** (semantic):
- `.dormant` — color/border var(--warn), bg rgba(255,200,87,0.06)
- `.novelty` — color/border var(--vol), bg rgba(210,166,255,0.06)
- `.align` — color/border var(--info), bg rgba(106,183,255,0.06)

### Direction tag

```
font-size: 10–11px
padding: 3px 8px
border-radius: 3px
letter-spacing: 1px
text-transform: uppercase
```

- `.long` — color var(--long), border rgba(94,227,161,0.3), bg rgba(94,227,161,0.12)
- `.short` — color var(--short)
- `.vol` — color var(--vol)

### Button

```
background: var(--panel-3)
border: 1px solid var(--border)
color: var(--text-dim)
padding: 6–9px 12–14px
border-radius: 4–6px
font: monospace, 10–11px, letter-spaced 1px
hover: color var(--text), border var(--accent-dim)
```

`.btn.primary` — color var(--accent), border var(--accent-dim), hover bg rgba(94,227,161,0.08).

### AI badge

```
font-size: 8–9px
color: var(--vol)
border: 1px solid rgba(210,166,255,0.35)
padding: 1px 5px
border-radius: 2px
letter-spacing: 1.5px
```

Used wherever AI is doing the work — on thesis blocks, on suggested structures, on classifier outputs.

### Conviction bar

5 dots, 18×4px each, 3px gap. Filled = var(--accent), unfilled = var(--chip-border). Label "X/5" + hit-rate "pattern hit: NN%" right-aligned.

### Tooltip (market-context cells, factor explainers)

```
position: absolute below cell
width: 320px
background: var(--panel-2)
border + radius like a card
shadow: 0 2px 12px rgba(0,0,0,0.4) [dark] / rgba(20,30,50,0.08) [light]
content structure:
  TIP-T (label, 10px letter-spaced)
  TIP-DEF (12px text — what it is)
  TIP-NOW (12px dim — what's true now)
  TIP-SO (12px accent, prefixed "→" — so what for the user)
```

---

## Layout grid

- App shell: `grid-template-columns: 220px 1fr 340px` (nav · main · chat) on Standard template
- Main padding: `16px 20px 40px 20px`
- Pick card grid: `repeat(auto-fill, minmax(320px, 1fr))`, gap 12px
- Detail factor strip: `repeat(6, 1fr)`, gap 10px
- Detail history grid: `repeat(2, 1fr)`, gap 12px

---

## Iconography (text-based, for v1)

Avoid icon libraries. Use simple unicode characters and text symbols to keep the build clean:
- `◈` dormant bet marker (warn color)
- `◆` AI thesis marker (accent color)
- `◉` selected pick / context indicator (accent color)
- `→` so-what prefix
- `⌕` search prefix
- `⭐` pin
- `⟁` alert
- `☾` `☀` theme toggle
- `✓` `✗` gates

---

## Motion

- Hover transitions: 0.12–0.15s
- Theme toggle: instant (no animation)
- Card click → detail open: smooth scrollIntoView, 150ms
- Chat message stream: token-by-token via SSE (no fake typewriter delay)

Keep motion subtle. This is a trader's tool, not a marketing site.

---

## Accessibility (v1 baseline)

- Color contrast meets WCAG AA on both themes (verify with checker)
- All clickable elements ≥ 32px touch target
- Focus rings visible on keyboard nav (don't suppress)
- ARIA labels on icon-only buttons

---

## Source of truth

The wireframe HTML files in `docs/wireframes/` are the visual source of truth. When in doubt, match the wireframe. If the wireframe is silent on something, follow this design system.
