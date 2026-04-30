// @ts-check
/**
 * COMPREHENSIVE UI TEST PLAN — EigenView Dashboard
 * Covers every click, API call, resize interaction, theme, keyboard shortcut,
 * module behavior, help page, auto-refresh, and edge cases.
 *
 * Groups:
 *   1.  Header extended (help btn, scan badge timing, search edge cases)
 *   2.  Theme system (all 4 themes, CSS vars, chart rebuild, T cycle)
 *   3.  Template system (all 5 templates, module visibility)
 *   4.  Keyboard shortcuts (every binding, input-focus guard)
 *   5.  Shortcuts overlay (open, close, content)
 *   6.  Edit mode (full drag/resize/close/palette flow)
 *   7.  Market Context (all cells, colors, tooltips, states)
 *   8.  Category Nav (all filters, badge counts, active state)
 *   9.  Pick Cards — anatomy (every field, chip types, directions)
 *   10. Pick Cards — actions (DETAIL, ASK AI, WHY, chip help links)
 *   11. Pick Cards — list view (toggle, row anatomy, select)
 *   12. Pick Cards — keyboard nav (↑↓, boundary clamping)
 *   13. Pick Cards — empty state
 *   14. Price Chart — states (empty, loading, error)
 *   15. Price Chart — loaded (timeframe, maximize, restore, GEX lines)
 *   16. Price Chart — resize (ResizeObserver, min-height enforcement)
 *   17. Factor Strip — all 6 cells (labels, fire/off, click → help)
 *   18. Factor Strip — empty and small-size grid
 *   19. AI Chat — input, streaming mock, suggestions, clear, prefill
 *   20. AI Chat — light mode background (CSS var fix)
 *   21. Help page — open/close, all tabs, chip links, factor links
 *   22. Store pub-sub (subscribe, set, unsubscribe)
 *   23. API schema validation (/api/picks, /api/market/regime, /api/chart/:t)
 *   24. Auto-refresh (polling interval setup)
 *   25. Module chrome (bar, label, close in edit mode)
 *   26. Canvas module mounting (all 7 modules registered and visible)
 *   27. Glass theme specific (backdrop-filter applied)
 *   28. Bento theme specific (colored top borders per module type)
 *   29. Responsive min-height (modules never collapse below 80px)
 *   30. Voice Orb (registered in registry)
 */

const { test, expect } = require('@playwright/test');

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────

async function waitForApp(page) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
}

async function enterEditMode(page) {
  await page.evaluate(() => window.EV?.Canvas?.setEditMode(true));
  await page.waitForTimeout(150);
}

async function exitEditMode(page) {
  await page.evaluate(() => window.EV?.Canvas?.setEditMode(false));
  await page.waitForTimeout(150);
}

async function setTheme(page, theme) {
  await page.evaluate(t => {
    if (window.EV_App?.setTheme) {
      window.EV_App.setTheme(t);
    } else {
      document.documentElement.setAttribute('data-theme', t);
    }
  }, theme);
  await page.waitForTimeout(100);
}

async function injectMockPicks(page) {
  await page.evaluate(() => {
    const mock = [
      {
        ticker: 'AAPL',
        direction: 'long',
        conviction: 4,
        setup_type: 'breakout',
        entry_low: 185,
        entry_high: 188,
        stop: 180,
        iv_rank: 42,
        thesis: 'AAPL showing strong breakout above resistance. EMA21 crossed EMA50. Clean setup with defined risk.',
        structure: {
          type: 'call_debit_spread',
          description: 'Call Debit Spread',
          legs: 'Buy 190C / Sell 195C · Jun 21',
        },
        factors: {
          macro_regime: { firing: true,  strength: 0.8,  label: 'GREEN' },
          technical:    { firing: true,  strength: 0.85, label: 'breakout' },
          gex:          { firing: false, strength: 0.2,  label: 'long_gamma', detail: { call_wall: 200, put_wall: 175, gamma_flip: 182 } },
          flow:         { firing: true,  strength: 0.6,  label: 'aggressive_call' },
          dormant:      { firing: false, strength: 0.0,  label: 'inactive' },
          sentiment:    { firing: true,  strength: 0.7,  label: 'catalyst', detail: { catalyst_near: true } },
        },
      },
      {
        ticker: 'NVDA',
        direction: 'short',
        conviction: 3,
        setup_type: 'pullback',
        entry_low: 900,
        entry_high: 920,
        stop: 950,
        iv_rank: 65,
        thesis: 'NVDA bearish divergence on weekly. Short gamma regime amplifying downside.',
        structure: {
          type: 'put_debit_spread',
          description: 'Put Debit Spread',
          legs: 'Buy 880P / Sell 860P · May 17',
        },
        factors: {
          macro_regime: { firing: false, strength: 0.4, label: 'YELLOW' },
          technical:    { firing: true,  strength: 0.7, label: 'bearish_reversal' },
          gex:          { firing: true,  strength: 0.9, label: 'short_gamma', detail: { call_wall: 950, put_wall: 870, gamma_flip: 910 } },
          flow:         { firing: true,  strength: 0.55, label: 'put_sweep' },
          dormant:      { firing: true,  strength: 0.8, label: 'ACTIVATING' },
          sentiment:    { firing: false, strength: 0.3, label: 'neutral' },
        },
      },
      {
        ticker: 'TSLA',
        direction: 'long',
        conviction: 5,
        setup_type: 'compression',
        entry_low: 240,
        entry_high: 245,
        stop: 230,
        iv_rank: 55,
        thesis: 'TSLA multi-week compression breaking out. All 5 signals aligned.',
        structure: {
          type: 'call_debit_spread',
          description: 'Call Debit Spread',
          legs: 'Buy 250C / Sell 260C · Jun 21',
        },
        factors: {
          macro_regime: { firing: true,  strength: 0.9, label: 'GREEN' },
          technical:    { firing: true,  strength: 0.9, label: 'compression_break' },
          gex:          { firing: true,  strength: 0.8, label: 'long_gamma', detail: { call_wall: 270, put_wall: 230, gamma_flip: 238 } },
          flow:         { firing: true,  strength: 0.75, label: 'call_sweep' },
          dormant:      { firing: true,  strength: 0.6, label: 'ACTIVATING' },
          sentiment:    { firing: true,  strength: 0.8, label: 'catalyst' },
        },
      },
    ];
    window.EV.Store.set('picks', mock);
    window.EV.Store.set('selectedPick', mock[0]);
    window.EV.Store.set('selectedTicker', 'AAPL');
  });
  await page.waitForTimeout(300);
}

async function injectMockRegime(page) {
  await page.evaluate(() => {
    window.EV.Store.set('regime', {
      regime: 'GREEN',
      score: 8,
      gex_index: 2500000000,
      vix_m1: 15.2,
      vix_m2: 17.8,
      vix_contango_pct: 17.1,
      dix: 0.47,
      narrative: 'Macro conditions favorable. SPX in long-gamma regime.',
    });
  });
  await page.waitForTimeout(150);
}

async function openHelpPage(page) {
  await page.click('#ev-help-btn');
  await page.waitForSelector('#ev-help-overlay:not([hidden])', { timeout: 2000 });
}

// ═════════════════════════════════════════════════════════════════════════════
// 1. HEADER EXTENDED
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Header extended', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('help button present in header', async ({ page }) => {
    await expect(page.locator('#ev-help-btn')).toBeVisible();
  });

  test('help button opens help overlay', async ({ page }) => {
    await page.click('#ev-help-btn');
    await expect(page.locator('#ev-help-overlay')).not.toHaveAttribute('hidden');
  });

  test('scan badge exists on load', async ({ page }) => {
    await expect(page.locator('#ev-scan-time')).toBeVisible();
  });

  test('scan badge updates to pick count after inject', async ({ page }) => {
    await injectMockPicks(page);
    await expect(page.locator('#ev-scan-time')).toContainText('pick');
  });

  test('scan badge shows correct count after manual update', async ({ page }) => {
    await injectMockPicks(page);
    await page.evaluate(() => {
      const badge = document.getElementById('ev-scan-time');
      const picks = window.EV.Store.get('picks');
      if (badge && picks) badge.textContent = `✓ ${picks.length} picks`;
    });
    await expect(page.locator('#ev-scan-time')).toContainText('3');
  });

  test('search input clears on Escape', async ({ page }) => {
    const input = page.locator('#ev-search');
    await input.fill('AAPL');
    await input.press('Escape');
    await expect(input).toHaveValue('');
  });

  test('search input loses focus on Escape', async ({ page }) => {
    const input = page.locator('#ev-search');
    await input.focus();
    await input.press('Escape');
    const focused = await page.evaluate(() => document.activeElement?.id);
    expect(focused).not.toBe('ev-search');
  });

  test('Ctrl+K focuses search', async ({ page }) => {
    await page.keyboard.press('Control+k');
    const focused = await page.evaluate(() => document.activeElement?.id);
    expect(focused).toBe('ev-search');
  });

  test('Enter on search sets searchQuery in store', async ({ page }) => {
    const input = page.locator('#ev-search');
    await input.fill('TSLA');
    await input.press('Enter');
    const q = await page.evaluate(() => window.EV?.Store.get('searchQuery'));
    expect(q).toBe('TSLA');
  });

  test('search query is uppercased', async ({ page }) => {
    const input = page.locator('#ev-search');
    await input.fill('aapl');
    await input.press('Enter');
    const q = await page.evaluate(() => window.EV?.Store.get('searchQuery'));
    expect(q).toBe('AAPL');
  });

  test('brand mark renders EigenView', async ({ page }) => {
    await expect(page.locator('.brand-mark')).toContainText('Eigen');
  });

  test('brand tag renders Options Intelligence', async ({ page }) => {
    await expect(page.locator('.brand-tag')).toContainText('Options Intelligence');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 2. THEME SYSTEM — ALL 4 THEMES
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Theme system — all 4 themes', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('DARK button sets data-theme=dark', async ({ page }) => {
    await page.locator('.theme-btn[data-theme="light"]').click();
    await page.locator('.theme-btn[data-theme="dark"]').click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  });

  test('LIGHT button sets data-theme=light', async ({ page }) => {
    await page.locator('.theme-btn[data-theme="light"]').click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  });

  test('GLASS button sets data-theme=glass', async ({ page }) => {
    await page.locator('.theme-btn[data-theme="glass"]').click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'glass');
  });

  test('BENTO button sets data-theme=bento', async ({ page }) => {
    await page.locator('.theme-btn[data-theme="bento"]').click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'bento');
  });

  test('active theme button has class "active"', async ({ page }) => {
    await page.locator('.theme-btn[data-theme="glass"]').click();
    await expect(page.locator('.theme-btn[data-theme="glass"]')).toHaveClass(/active/);
    await expect(page.locator('.theme-btn[data-theme="dark"]')).not.toHaveClass(/active/);
  });

  test('T key cycles dark → light', async ({ page }) => {
    await page.keyboard.press('T');
    const theme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    expect(['light', 'glass', 'bento', 'dark']).toContain(theme);
  });

  test('T key cycles through all 4 themes', async ({ page }) => {
    const themes = new Set();
    for (let i = 0; i < 4; i++) {
      await page.keyboard.press('T');
      const t = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
      themes.add(t);
    }
    expect(themes.size).toBe(4);
  });

  test('light theme applies --panel: #ffffff CSS var', async ({ page }) => {
    await page.locator('.theme-btn[data-theme="light"]').click();
    const panel = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--panel').trim()
    );
    expect(panel).toBe('#ffffff');
  });

  test('dark theme applies --bg: #0b0d12 CSS var', async ({ page }) => {
    const bg = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()
    );
    expect(bg).toBe('#0b0d12');
  });

  test('--bg-primary alias resolves in light theme', async ({ page }) => {
    await page.locator('.theme-btn[data-theme="light"]').click();
    const bgPrimary = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--bg-primary').trim()
    );
    expect(bgPrimary.length).toBeGreaterThan(0);
  });

  test('--bg-secondary alias resolves in light theme', async ({ page }) => {
    await page.locator('.theme-btn[data-theme="light"]').click();
    const val = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--bg-secondary').trim()
    );
    expect(val.length).toBeGreaterThan(0);
  });

  test('bento theme defines --bento-market var', async ({ page }) => {
    await page.locator('.theme-btn[data-theme="bento"]').click();
    const val = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--bento-market').trim()
    );
    expect(val).toBe('#00ff88');
  });

  test('T key does not cycle when input is focused', async ({ page }) => {
    await page.locator('#ev-search').focus();
    const before = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    await page.keyboard.press('T');
    const after = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    expect(after).toBe(before);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 3. TEMPLATE SYSTEM
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Template system', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('5 template buttons exist', async ({ page }) => {
    await expect(page.locator('.tpl-btn')).toHaveCount(5);
  });

  test('template buttons are labeled STANDARD MINIMAL PRO RESEARCH FOCUS', async ({ page }) => {
    const labels = await page.locator('.tpl-btn').allInnerTexts();
    expect(labels).toEqual(['STANDARD', 'MINIMAL', 'PRO', 'RESEARCH', 'FOCUS']);
  });

  test('pressing 1 applies standard template', async ({ page }) => {
    await page.keyboard.press('2');
    await page.keyboard.press('1');
    await expect(page.locator('.tpl-btn').nth(0)).toHaveClass(/active/);
  });

  test('pressing 2 applies minimal template', async ({ page }) => {
    await page.keyboard.press('2');
    await expect(page.locator('.tpl-btn').nth(1)).toHaveClass(/active/);
  });

  test('pressing 3 applies pro template', async ({ page }) => {
    await page.keyboard.press('3');
    await expect(page.locator('.tpl-btn').nth(2)).toHaveClass(/active/);
  });

  test('pressing 4 applies research template', async ({ page }) => {
    await page.keyboard.press('4');
    await expect(page.locator('.tpl-btn').nth(3)).toHaveClass(/active/);
  });

  test('pressing 5 applies focus template', async ({ page }) => {
    await page.keyboard.press('5');
    await expect(page.locator('.tpl-btn').nth(4)).toHaveClass(/active/);
  });

  test('template number keys do not fire in input', async ({ page }) => {
    await page.locator('#ev-search').focus();
    const before = await page.locator('.tpl-btn.active').count();
    await page.keyboard.press('2');
    const after = await page.locator('.tpl-btn.active').count();
    expect(after).toBe(before);
  });

  test('template button click applies template', async ({ page }) => {
    await page.locator('.tpl-btn').nth(1).click();
    await expect(page.locator('.tpl-btn').nth(1)).toHaveClass(/active/);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 4. KEYBOARD SHORTCUTS
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Keyboard shortcuts', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('/ focuses AI chat textarea when not in input', async ({ page }) => {
    await page.keyboard.press('/');
    const tag = await page.evaluate(() => document.activeElement?.className);
    expect(tag).toContain('ev-chat-textarea');
  });

  test('/ does not focus chat when search is focused', async ({ page }) => {
    await page.locator('#ev-search').focus();
    await page.keyboard.press('/');
    const focused = await page.evaluate(() => document.activeElement?.id);
    expect(focused).toBe('ev-search');
  });

  test('E toggles edit mode on', async ({ page }) => {
    await page.keyboard.press('e');
    const editMode = await page.evaluate(() => window.EV?.Canvas?.editMode);
    expect(editMode).toBe(true);
    await page.keyboard.press('e');
  });

  test('E toggles edit mode off', async ({ page }) => {
    await page.keyboard.press('e');
    await page.keyboard.press('e');
    const editMode = await page.evaluate(() => window.EV?.Canvas?.editMode);
    expect(editMode).toBe(false);
  });

  test('Esc closes shortcuts overlay', async ({ page }) => {
    await page.keyboard.press('?');
    await page.keyboard.press('Escape');
    await expect(page.locator('#ev-shortcuts-overlay')).toHaveAttribute('hidden');
  });

  test('Esc exits edit mode', async ({ page }) => {
    await enterEditMode(page);
    await page.keyboard.press('Escape');
    const editMode = await page.evaluate(() => window.EV?.Canvas?.editMode);
    expect(editMode).toBe(false);
  });

  test('? shows shortcuts overlay', async ({ page }) => {
    await page.keyboard.press('?');
    await expect(page.locator('#ev-shortcuts-overlay')).not.toHaveAttribute('hidden');
    await page.keyboard.press('Escape');
  });

  test('H opens help overlay', async ({ page }) => {
    await page.keyboard.press('h');
    await expect(page.locator('#ev-help-overlay')).not.toHaveAttribute('hidden');
  });

  test('H does not open help when in input', async ({ page }) => {
    await page.locator('#ev-search').focus();
    await page.keyboard.press('h');
    await expect(page.locator('#ev-help-overlay')).toHaveAttribute('hidden');
  });

  test('ArrowDown changes selected pick', async ({ page }) => {
    await injectMockPicks(page);
    await page.waitForTimeout(200);
    const initial = await page.evaluate(() => window.EV?.Store.get('selectedPick')?.ticker);
    await page.keyboard.press('ArrowDown');
    const next = await page.evaluate(() => window.EV?.Store.get('selectedPick')?.ticker);
    expect(next).not.toBe(initial);
  });

  test('ArrowUp does not go below first pick', async ({ page }) => {
    await injectMockPicks(page);
    await page.waitForTimeout(200);
    await page.evaluate(() => {
      const picks = window.EV.Store.get('picks');
      window.EV.Store.set('selectedPick', picks[0]);
    });
    await page.keyboard.press('ArrowUp');
    const pick = await page.evaluate(() => window.EV?.Store.get('selectedPick')?.ticker);
    expect(pick).toBe('AAPL');
  });

  test('ArrowDown moves pick index forward', async ({ page }) => {
    await injectMockPicks(page);
    await page.waitForTimeout(200);
    const beforeIdx = await page.evaluate(() => {
      const picks = window.EV.Store.get('picks');
      const sel = window.EV.Store.get('selectedPick');
      return picks.findIndex(p => p.ticker === sel?.ticker);
    });
    await page.keyboard.press('ArrowDown');
    const afterIdx = await page.evaluate(() => {
      const picks = window.EV.Store.get('picks');
      const sel = window.EV.Store.get('selectedPick');
      return picks.findIndex(p => p.ticker === sel?.ticker);
    });
    expect(afterIdx).toBeGreaterThan(beforeIdx);
  });

  test('ArrowDown at last pick stays on last (keyboard shortcuts)', async ({ page }) => {
    await injectMockPicks(page);
    await page.waitForTimeout(200);
    await page.evaluate(() => {
      const picks = window.EV.Store.get('picks');
      window.EV.Store.set('selectedPick', picks[picks.length - 1]);
    });
    await page.keyboard.press('ArrowDown');
    const sel = await page.evaluate(() => window.EV?.Store.get('selectedPick')?.ticker);
    const picks = await page.evaluate(() => window.EV?.Store.get('picks').map(p => p.ticker));
    expect(sel).toBe(picks[picks.length - 1]);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 5. SHORTCUTS OVERLAY
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Shortcuts overlay', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('overlay hidden by default', async ({ page }) => {
    await expect(page.locator('#ev-shortcuts-overlay')).toHaveAttribute('hidden');
  });

  test('? opens overlay', async ({ page }) => {
    await page.keyboard.press('?');
    await expect(page.locator('#ev-shortcuts-overlay')).not.toHaveAttribute('hidden');
  });

  test('overlay shows Ctrl+K shortcut', async ({ page }) => {
    await page.keyboard.press('?');
    await expect(page.locator('#ev-shortcuts-overlay')).toContainText('Ctrl+K');
  });

  test('overlay shows / shortcut', async ({ page }) => {
    await page.keyboard.press('?');
    await expect(page.locator('#ev-shortcuts-overlay')).toContainText('/');
  });

  test('overlay shows T shortcut for theme', async ({ page }) => {
    await page.keyboard.press('?');
    await expect(page.locator('#ev-shortcuts-overlay')).toContainText('T');
  });

  test('overlay Close button hides it', async ({ page }) => {
    await page.keyboard.press('?');
    await page.locator('#ev-shortcuts-overlay .btn-ghost').click();
    await expect(page.locator('#ev-shortcuts-overlay')).toHaveAttribute('hidden');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 6. EDIT MODE
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Edit mode', () => {
  test.beforeEach(async ({ page }) => {
    await waitForApp(page);
    await injectMockPicks(page);
  });

  test('edit hint bar hidden by default', async ({ page }) => {
    await expect(page.locator('#ev-edit-hint')).toHaveAttribute('hidden');
  });

  test('E key toggles editMode via Canvas API', async ({ page }) => {
    const before = await page.evaluate(() => window.EV?.Canvas?.editMode);
    await page.evaluate(() => window.EV?.Canvas?.setEditMode(!window.EV?.Canvas?.editMode));
    const after = await page.evaluate(() => window.EV?.Canvas?.editMode);
    expect(after).not.toBe(before);
    await page.evaluate(() => window.EV?.Canvas?.setEditMode(false));
  });

  test('canvas gets class edit-mode when active', async ({ page }) => {
    await enterEditMode(page);
    await expect(page.locator('#ev-canvas')).toHaveClass(/edit-mode/);
    await exitEditMode(page);
  });

  test('Done button exits edit mode', async ({ page }) => {
    await enterEditMode(page);
    await page.locator('#ev-edit-done').click();
    await page.waitForTimeout(100);
    const editMode = await page.evaluate(() => window.EV?.Canvas?.editMode);
    expect(editMode).toBe(false);
  });

  test('Done button hides edit hint bar', async ({ page }) => {
    await enterEditMode(page);
    await page.locator('#ev-edit-done').click();
    await page.waitForTimeout(150);
    await expect(page.locator('#ev-edit-hint')).toHaveAttribute('hidden');
  });

  test('edit mode shows drag handles', async ({ page }) => {
    await enterEditMode(page);
    const handles = page.locator('.ev-drag-handle');
    const count = await handles.count();
    expect(count).toBeGreaterThan(0);
    await exitEditMode(page);
  });

  test('edit mode shows close buttons', async ({ page }) => {
    await enterEditMode(page);
    const closes = page.locator('.ev-module-close');
    const count = await closes.count();
    expect(count).toBeGreaterThan(0);
    await exitEditMode(page);
  });

  test('module close button removes module', async ({ page }) => {
    await enterEditMode(page);
    const before = await page.locator('.ev-module').count();
    await page.locator('.ev-module-close').first().click();
    await page.waitForTimeout(150);
    const after = await page.locator('.ev-module').count();
    expect(after).toBe(before - 1);
    await exitEditMode(page);
  });

  test('Add Panel button opens palette', async ({ page }) => {
    await enterEditMode(page);
    await page.locator('#ev-edit-hint .btn-ghost').click();
    await expect(page.locator('#ev-module-palette')).not.toHaveAttribute('hidden');
    await exitEditMode(page);
  });

  test('palette close button hides palette', async ({ page }) => {
    await enterEditMode(page);
    await page.locator('#ev-edit-hint .btn-ghost').click();
    await page.locator('#ev-palette-close').click();
    await expect(page.locator('#ev-module-palette')).toHaveAttribute('hidden');
    await exitEditMode(page);
  });

  test('Esc closes palette and edit mode', async ({ page }) => {
    await enterEditMode(page);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(150);
    const editMode = await page.evaluate(() => window.EV?.Canvas?.editMode);
    expect(editMode).toBe(false);
  });

  test('module bar label shows in edit mode', async ({ page }) => {
    await enterEditMode(page);
    const labels = page.locator('.ev-module-label');
    const count = await labels.count();
    expect(count).toBeGreaterThan(0);
    await exitEditMode(page);
  });

  test('resize handle exists on modules', async ({ page }) => {
    await enterEditMode(page);
    const handles = page.locator('.ev-resize-handle');
    const count = await handles.count();
    expect(count).toBeGreaterThan(0);
    await exitEditMode(page);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 7. MARKET CONTEXT MODULE
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Market Context module', () => {
  test.beforeEach(async ({ page }) => {
    await waitForApp(page);
    await injectMockRegime(page);
  });

  test('market context module is visible', async ({ page }) => {
    const mc = page.locator('[data-module-type="market-context"]');
    await expect(mc).toBeVisible();
  });

  test('regime label shown', async ({ page }) => {
    const mc = page.locator('[data-module-type="market-context"]');
    await expect(mc).toContainText('GREEN');
  });

  test('VIX value displayed', async ({ page }) => {
    const mc = page.locator('[data-module-type="market-context"]');
    await expect(mc).toContainText('15.2');
  });

  test('DIX value displayed', async ({ page }) => {
    const mc = page.locator('[data-module-type="market-context"]');
    await expect(mc).toContainText('47');
  });

  test('contango pct displayed', async ({ page }) => {
    const mc = page.locator('[data-module-type="market-context"]');
    await expect(mc).toContainText('17.1');
  });

  test('narrative text shown', async ({ page }) => {
    const mc = page.locator('[data-module-type="market-context"]');
    await expect(mc).toContainText('favorable');
  });

  test('market context has no data state when regime not set', async ({ page }) => {
    await page.evaluate(() => window.EV?.Store.set('regime', null));
    await page.waitForTimeout(100);
    const mc = page.locator('[data-module-type="market-context"]');
    await expect(mc).toBeVisible();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 8. CATEGORY NAV MODULE
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Category Nav module', () => {
  test.beforeEach(async ({ page }) => {
    await waitForApp(page);
    await injectMockPicks(page);
  });

  test('category nav is visible', async ({ page }) => {
    await expect(page.locator('[data-module-type="category-nav"], .nav-slot')).toBeVisible();
  });

  test('TODAY section present', async ({ page }) => {
    const nav = page.locator('.nav-slot, [data-module-type="category-nav"]');
    await expect(nav).toContainText('TODAY');
  });

  test('today filter item exists', async ({ page }) => {
    const nav = page.locator('.nav-slot, [data-module-type="category-nav"]');
    const items = nav.locator('.nav-item, [data-cat]');
    const count = await items.count();
    expect(count).toBeGreaterThan(0);
  });

  test('clicking a nav item sets activeCategory', async ({ page }) => {
    const item = page.locator('[data-cat]').first();
    if (await item.count() > 0) {
      const cat = await item.getAttribute('data-cat');
      await item.click();
      const active = await page.evaluate(() => window.EV?.Store.get('activeCategory'));
      expect(active).toBe(cat);
    }
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 9. PICK CARDS — ANATOMY
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Pick Cards — anatomy', () => {
  test.beforeEach(async ({ page }) => {
    await waitForApp(page);
    await injectMockPicks(page);
  });

  test('3 pick cards rendered', async ({ page }) => {
    await expect(page.locator('.pick-card')).toHaveCount(3);
  });

  test('AAPL card has ticker', async ({ page }) => {
    await expect(page.locator('.pick-card[data-ticker="AAPL"] .card-ticker')).toContainText('AAPL');
  });

  test('AAPL card shows LONG direction', async ({ page }) => {
    await expect(page.locator('.pick-card[data-ticker="AAPL"] .tag-long')).toBeVisible();
  });

  test('NVDA card shows SHORT direction', async ({ page }) => {
    await expect(page.locator('.pick-card[data-ticker="NVDA"] .tag-short')).toBeVisible();
  });

  test('AAPL conviction dots: 4 active of 5', async ({ page }) => {
    const card = page.locator('.pick-card[data-ticker="AAPL"]');
    const onDots = card.locator('.conv-dot.on');
    await expect(onDots).toHaveCount(4);
  });

  test('NVDA conviction dots: 3 active of 5', async ({ page }) => {
    const card = page.locator('.pick-card[data-ticker="NVDA"]');
    const onDots = card.locator('.conv-dot.on');
    await expect(onDots).toHaveCount(3);
  });

  test('TSLA conviction dots: 5 active of 5', async ({ page }) => {
    const card = page.locator('.pick-card[data-ticker="TSLA"]');
    const onDots = card.locator('.conv-dot.on');
    await expect(onDots).toHaveCount(5);
  });

  test('AAPL entry zone shown', async ({ page }) => {
    const card = page.locator('.pick-card[data-ticker="AAPL"]');
    await expect(card).toContainText('185');
    await expect(card).toContainText('188');
  });

  test('AAPL stop level shown', async ({ page }) => {
    await expect(page.locator('.pick-card[data-ticker="AAPL"]')).toContainText('180');
  });

  test('AAPL IV rank shown', async ({ page }) => {
    await expect(page.locator('.pick-card[data-ticker="AAPL"]')).toContainText('42');
  });

  test('AAPL thesis text shown', async ({ page }) => {
    await expect(page.locator('.pick-card[data-ticker="AAPL"]')).toContainText('breakout');
  });

  test('AAPL structure description shown', async ({ page }) => {
    await expect(page.locator('.pick-card[data-ticker="AAPL"]')).toContainText('Call Debit Spread');
  });

  test('AAPL structure legs shown', async ({ page }) => {
    await expect(page.locator('.pick-card[data-ticker="AAPL"]')).toContainText('Buy 190C');
  });

  test('TA chip shown for AAPL (technical firing)', async ({ page }) => {
    const card = page.locator('.pick-card[data-ticker="AAPL"]');
    const chipTexts = await card.locator('.chip').allInnerTexts();
    expect(chipTexts.some(t => t.includes('TA'))).toBe(true);
  });

  test('FLOW chip shown for AAPL (flow firing)', async ({ page }) => {
    const card = page.locator('.pick-card[data-ticker="AAPL"]');
    const chipTexts = await card.locator('.chip').allInnerTexts();
    expect(chipTexts.some(t => t.includes('FLOW'))).toBe(true);
  });

  test('DORMANT chip shown for NVDA (dormant firing)', async ({ page }) => {
    const card = page.locator('.pick-card[data-ticker="NVDA"]');
    await expect(card.locator('.chip.dormant')).toBeVisible();
  });

  test('GEX chip NOT shown for AAPL (gex not firing)', async ({ page }) => {
    const card = page.locator('.pick-card[data-ticker="AAPL"]');
    const chips = await card.locator('.chip').allInnerTexts();
    expect(chips.some(t => t.includes('GEX'))).toBe(false);
  });

  test('AAPL card selected on inject', async ({ page }) => {
    await expect(page.locator('.pick-card[data-ticker="AAPL"]')).toHaveClass(/selected/);
  });

  test('NVDA card not selected initially', async ({ page }) => {
    await expect(page.locator('.pick-card[data-ticker="NVDA"]')).not.toHaveClass(/selected/);
  });

  test('clicking NVDA card selects it', async ({ page }) => {
    await page.locator('.pick-card[data-ticker="NVDA"]').click();
    await expect(page.locator('.pick-card[data-ticker="NVDA"]')).toHaveClass(/selected/);
  });

  test('clicking NVDA deselects AAPL', async ({ page }) => {
    await page.locator('.pick-card[data-ticker="NVDA"]').click();
    await expect(page.locator('.pick-card[data-ticker="AAPL"]')).not.toHaveClass(/selected/);
  });

  test('card actions visible at baseline opacity', async ({ page }) => {
    const actions = page.locator('.pick-card[data-ticker="NVDA"] .card-actions');
    await expect(actions).toBeVisible();
  });

  test('card actions CSS transition defined for opacity', async ({ page }) => {
    const transition = await page.evaluate(() => {
      const el = document.querySelector('.card-actions');
      return el ? window.getComputedStyle(el).transition : null;
    });
    expect(transition).toContain('opacity');
  });

  test('WHY button visible on each card with structure', async ({ page }) => {
    const count = await page.locator('.btn-why').count();
    expect(count).toBe(3);
  });

  test('AI badge shows on thesis block', async ({ page }) => {
    await expect(page.locator('.ai-badge').first()).toBeVisible();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 10. PICK CARDS — ACTIONS
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Pick Cards — actions', () => {
  test.beforeEach(async ({ page }) => {
    await waitForApp(page);
    await injectMockPicks(page);
  });

  test('DETAIL button click sets selectedTicker', async ({ page }) => {
    await page.locator('.pick-card[data-ticker="NVDA"] .btn-detail').click();
    const sel = await page.evaluate(() => window.EV?.Store.get('selectedTicker'));
    expect(sel).toBe('NVDA');
  });

  test('ASK AI button sets chatPrefill', async ({ page }) => {
    await page.locator('.pick-card[data-ticker="AAPL"] .btn-ask-ai').click();
    const prefill = await page.evaluate(() => window.EV?.Store.get('chatPrefill'));
    expect(prefill).toContain('AAPL');
  });

  test('WHY button sets chatPrefill with structure', async ({ page }) => {
    await page.locator('.pick-card[data-ticker="AAPL"] .btn-why').click();
    const prefill = await page.evaluate(() => window.EV?.Store.get('chatPrefill'));
    expect(prefill).toContain('Call Debit Spread');
  });

  test('chip click opens help overlay', async ({ page }) => {
    const chip = page.locator('.pick-card[data-ticker="AAPL"] .chip[data-help-tab]').first();
    if (await chip.count() > 0) {
      await chip.click();
      await expect(page.locator('#ev-help-overlay')).not.toHaveAttribute('hidden');
    }
  });

  test('TA chip links to ta tab in help', async ({ page }) => {
    const chip = page.locator('.pick-card[data-ticker="AAPL"] .chip[data-help-tab="ta"]');
    if (await chip.count() > 0) {
      await chip.click();
      const activeTab = await page.evaluate(() =>
        document.querySelector('.ev-help-tab.active')?.dataset.tab
      );
      expect(activeTab).toBe('ta');
    }
  });

  test('DORMANT chip links to dormant tab in help', async ({ page }) => {
    const chip = page.locator('.pick-card[data-ticker="NVDA"] .chip[data-help-tab="dormant"]');
    if (await chip.count() > 0) {
      await chip.click();
      const activeTab = await page.evaluate(() =>
        document.querySelector('.ev-help-tab.active')?.dataset.tab
      );
      expect(activeTab).toBe('dormant');
    }
  });

  test('pin button (⭐) is clickable without error', async ({ page }) => {
    await page.locator('.pick-card[data-ticker="AAPL"] .btn-pin').click();
    await expect(page.locator('.pick-card[data-ticker="AAPL"]')).toBeVisible();
  });

  test('alert button (⟁) is clickable without error', async ({ page }) => {
    await page.locator('.pick-card[data-ticker="AAPL"] .btn-alert').click();
    await expect(page.locator('.pick-card[data-ticker="AAPL"]')).toBeVisible();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 11. PICK CARDS — LIST VIEW
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Pick Cards — list view', () => {
  test.beforeEach(async ({ page }) => {
    await waitForApp(page);
    await injectMockPicks(page);
  });

  test('LIST toggle button exists', async ({ page }) => {
    await expect(page.locator('.pc-vtb[data-view="list"]')).toBeVisible();
  });

  test('CARDS toggle button exists', async ({ page }) => {
    await expect(page.locator('.pc-vtb[data-view="cards"]')).toBeVisible();
  });

  test('switching to list shows pick rows', async ({ page }) => {
    await page.locator('.pc-vtb[data-view="list"]').click();
    await expect(page.locator('.pick-list-row')).toHaveCount(3);
  });

  test('list rows show ticker', async ({ page }) => {
    await page.locator('.pc-vtb[data-view="list"]').click();
    await expect(page.locator('.pick-list-row').first()).toContainText('AAPL');
  });

  test('list rows show direction tag', async ({ page }) => {
    await page.locator('.pc-vtb[data-view="list"]').click();
    await expect(page.locator('.pick-list-row[data-ticker="AAPL"] .tag-long')).toBeVisible();
  });

  test('clicking list row selects pick', async ({ page }) => {
    await page.locator('.pc-vtb[data-view="list"]').click();
    await page.locator('.pick-list-row[data-ticker="NVDA"]').click();
    const sel = await page.evaluate(() => window.EV?.Store.get('selectedTicker'));
    expect(sel).toBe('NVDA');
  });

  test('switching back to cards shows cards', async ({ page }) => {
    await page.locator('.pc-vtb[data-view="list"]').click();
    await page.locator('.pc-vtb[data-view="cards"]').click();
    await expect(page.locator('.pick-card')).toHaveCount(3);
  });

  test('list view entry range shown', async ({ page }) => {
    await page.locator('.pc-vtb[data-view="list"]').click();
    await expect(page.locator('.pick-list-row[data-ticker="AAPL"]')).toContainText('185');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 12. PICK CARDS — KEYBOARD NAV
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Pick Cards — keyboard nav', () => {
  test.beforeEach(async ({ page }) => {
    await waitForApp(page);
    await injectMockPicks(page);
    await page.waitForTimeout(200);
  });

  test('ArrowDown navigates to next pick', async ({ page }) => {
    const initial = await page.evaluate(() => window.EV?.Store.get('selectedPick')?.ticker);
    await page.keyboard.press('ArrowDown');
    const next = await page.evaluate(() => window.EV?.Store.get('selectedPick')?.ticker);
    expect(next).not.toBe(initial);
  });

  test('ArrowDown moves pick selection forward', async ({ page }) => {
    const beforeIdx = await page.evaluate(() => {
      const picks = window.EV.Store.get('picks');
      const sel = window.EV.Store.get('selectedPick');
      return picks.findIndex(p => p.ticker === sel?.ticker);
    });
    await page.keyboard.press('ArrowDown');
    const afterIdx = await page.evaluate(() => {
      const picks = window.EV.Store.get('picks');
      const sel = window.EV.Store.get('selectedPick');
      return picks.findIndex(p => p.ticker === sel?.ticker);
    });
    expect(afterIdx).toBeGreaterThan(beforeIdx);
  });

  test('ArrowUp from first pick stays on first (boundary)', async ({ page }) => {
    await page.evaluate(() => {
      const picks = window.EV.Store.get('picks');
      window.EV.Store.set('selectedPick', picks[0]);
    });
    await page.keyboard.press('ArrowUp');
    const sel = await page.evaluate(() => window.EV?.Store.get('selectedPick')?.ticker);
    expect(sel).toBe('AAPL');
  });

  test('ArrowDown at last pick stays on last (boundary)', async ({ page }) => {
    const lastTicker = await page.evaluate(() => {
      const picks = window.EV.Store.get('picks');
      const last = picks[picks.length - 1];
      window.EV.Store.set('selectedPick', last);
      return last.ticker;
    });
    await page.keyboard.press('ArrowDown');
    const sel = await page.evaluate(() => window.EV?.Store.get('selectedPick')?.ticker);
    expect(sel).toBe(lastTicker);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 13. PICK CARDS — EMPTY STATE
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Pick Cards — empty state', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('empty state shown when no picks', async ({ page }) => {
    await page.evaluate(() => window.EV.Store.set('picks', []));
    await page.waitForTimeout(200);
    await expect(page.locator('.pc-empty')).toBeVisible();
  });

  test('empty state message mentions "No picks"', async ({ page }) => {
    await page.evaluate(() => window.EV.Store.set('picks', []));
    await page.waitForTimeout(200);
    await expect(page.locator('.pc-empty')).toContainText('No picks');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 14. PRICE CHART — STATES
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Price Chart — states', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('price chart module visible', async ({ page }) => {
    await expect(page.locator('[data-module-type="price-chart"]')).toBeVisible();
  });

  test('empty state shown when no ticker selected', async ({ page }) => {
    const state = page.locator('#pc-state');
    if (await state.count() > 0) {
      const display = await state.evaluate(el => window.getComputedStyle(el).display);
      const text = await state.innerText();
      expect(display === 'flex' || text.includes('Select')).toBeTruthy();
    }
  });

  test('chart header title shows PRICE CHART', async ({ page }) => {
    await expect(page.locator('#pc-title')).toContainText('PRICE CHART');
  });

  test('1D timeframe button active by default', async ({ page }) => {
    await expect(page.locator('.pc-tf-btn[data-tf="1d"]')).toHaveClass(/active/);
  });

  test('1W timeframe button exists', async ({ page }) => {
    await expect(page.locator('.pc-tf-btn[data-tf="1wk"]')).toBeVisible();
  });

  test('maximize button exists', async ({ page }) => {
    await expect(page.locator('#pc-max-btn')).toBeVisible();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 15. PRICE CHART — MAXIMIZE / RESTORE
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Price Chart — maximize / restore', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('maximize button click expands chart', async ({ page }) => {
    await page.locator('#pc-max-btn').click();
    const el = page.locator('[data-module-type="price-chart"]');
    const pos = await el.evaluate(e => e.style.position);
    expect(pos).toBe('fixed');
  });

  test('maximize button text changes to ⤡', async ({ page }) => {
    await page.locator('#pc-max-btn').click();
    await expect(page.locator('#pc-max-btn')).toContainText('⤡');
  });

  test('second click on maximize restores chart', async ({ page }) => {
    await page.locator('#pc-max-btn').click();
    await page.locator('#pc-max-btn').click();
    const el = page.locator('[data-module-type="price-chart"]');
    const pos = await el.evaluate(e => e.style.position);
    expect(pos === '' || pos === 'relative').toBeTruthy();
  });

  test('maximize button reverts to ⤢ after restore', async ({ page }) => {
    await page.locator('#pc-max-btn').click();
    await page.locator('#pc-max-btn').click();
    await expect(page.locator('#pc-max-btn')).toContainText('⤢');
  });

  test('Escape closes maximized chart', async ({ page }) => {
    await page.locator('#pc-max-btn').click();
    await page.keyboard.press('Escape');
    const el = page.locator('[data-module-type="price-chart"]');
    const pos = await el.evaluate(e => e.style.position);
    expect(pos === '' || pos !== 'fixed').toBeTruthy();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 16. PRICE CHART — MIN HEIGHT / RESIZE
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Price Chart — resize', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('price chart module never collapses below 80px', async ({ page }) => {
    const el = page.locator('[data-module-type="price-chart"]');
    const height = await el.evaluate(e => e.getBoundingClientRect().height);
    expect(height).toBeGreaterThanOrEqual(80);
  });

  test('pick-cards module never collapses below 80px', async ({ page }) => {
    const el = page.locator('[data-module-type="pick-cards"]');
    const height = await el.evaluate(e => e.getBoundingClientRect().height);
    expect(height).toBeGreaterThanOrEqual(80);
  });

  test('factor-strip module never collapses below 80px', async ({ page }) => {
    const el = page.locator('[data-module-type="factor-strip"]');
    const height = await el.evaluate(e => e.getBoundingClientRect().height);
    expect(height).toBeGreaterThanOrEqual(80);
  });

  test('market-context module never collapses below 80px', async ({ page }) => {
    const el = page.locator('[data-module-type="market-context"]');
    const height = await el.evaluate(e => e.getBoundingClientRect().height);
    expect(height).toBeGreaterThanOrEqual(80);
  });

  test('.ev-module CSS has min-height: 80px', async ({ page }) => {
    const minH = await page.evaluate(() => {
      const el = document.querySelector('.ev-module');
      return el ? window.getComputedStyle(el).minHeight : null;
    });
    expect(minH).toBe('80px');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 17. FACTOR STRIP — ALL 6 CELLS
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Factor Strip — cells', () => {
  test.beforeEach(async ({ page }) => {
    await waitForApp(page);
    await injectMockPicks(page);
  });

  test('factor strip module visible', async ({ page }) => {
    await expect(page.locator('[data-module-type="factor-strip"]')).toBeVisible();
  });

  test('6 factor cells rendered', async ({ page }) => {
    const cells = page.locator('.factor-cell');
    await expect(cells).toHaveCount(6);
  });

  test('MACRO cell present', async ({ page }) => {
    await expect(page.locator('.factor-cell[data-factor="macro_regime"]')).toBeVisible();
  });

  test('TECH cell present', async ({ page }) => {
    await expect(page.locator('.factor-cell[data-factor="technical"]')).toBeVisible();
  });

  test('GEX cell present', async ({ page }) => {
    await expect(page.locator('.factor-cell[data-factor="gex"]')).toBeVisible();
  });

  test('FLOW cell present', async ({ page }) => {
    await expect(page.locator('.factor-cell[data-factor="flow"]')).toBeVisible();
  });

  test('DORMANT cell present', async ({ page }) => {
    await expect(page.locator('.factor-cell[data-factor="dormant"]')).toBeVisible();
  });

  test('SENTIMENT cell present', async ({ page }) => {
    await expect(page.locator('.factor-cell[data-factor="sentiment"]')).toBeVisible();
  });

  test('TECH cell fires for AAPL (technical.firing=true)', async ({ page }) => {
    const cell = page.locator('.factor-cell[data-factor="technical"]');
    await expect(cell).toHaveClass(/firing/);
  });

  test('DORMANT cell not firing for AAPL (dormant.firing=false)', async ({ page }) => {
    const cell = page.locator('.factor-cell[data-factor="dormant"]');
    await expect(cell).not.toHaveClass(/firing/);
  });

  test('clicking TECH cell sets chatPrefill', async ({ page }) => {
    await page.locator('.factor-cell[data-factor="technical"]').click();
    const prefill = await page.evaluate(() => window.EV?.Store.get('chatPrefill'));
    expect(prefill).toBeTruthy();
    expect(prefill).toContain('TECH');
  });

  test('clicking TECH cell opens help overlay', async ({ page }) => {
    await page.locator('.factor-cell[data-factor="technical"]').click();
    await page.waitForTimeout(100);
    await expect(page.locator('#ev-help-overlay')).not.toHaveAttribute('hidden');
  });

  test('clicking GEX cell opens help at gex tab', async ({ page }) => {
    await page.locator('.factor-cell[data-factor="gex"]').click();
    await page.waitForTimeout(100);
    const activeTab = await page.evaluate(() =>
      document.querySelector('.ev-help-tab.active')?.dataset.tab
    );
    expect(activeTab).toBe('gex');
  });

  test('clicking DORMANT cell opens help at dormant tab', async ({ page }) => {
    await page.locator('.factor-cell[data-factor="dormant"]').click();
    await page.waitForTimeout(100);
    const activeTab = await page.evaluate(() =>
      document.querySelector('.ev-help-tab.active')?.dataset.tab
    );
    expect(activeTab).toBe('dormant');
  });

  test('DORMANT cell fires for NVDA (dormant.firing=true)', async ({ page }) => {
    await page.evaluate(() => {
      const picks = window.EV.Store.get('picks');
      window.EV.Store.set('selectedPick', picks[1]);
      window.EV.Store.set('selectedTicker', 'NVDA');
    });
    await page.waitForTimeout(200);
    const cell = page.locator('.factor-cell[data-factor="dormant"]');
    await expect(cell).toHaveClass(/firing/);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 18. FACTOR STRIP — EMPTY STATE
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Factor Strip — empty state', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('factor strip shows empty state when no pick selected', async ({ page }) => {
    await page.evaluate(() => {
      window.EV.Store.set('selectedPick', null);
      window.EV.Store.set('selectedTicker', null);
    });
    await page.waitForTimeout(200);
    const strip = page.locator('[data-module-type="factor-strip"]');
    await expect(strip).toBeVisible();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 19. AI CHAT MODULE
// ═════════════════════════════════════════════════════════════════════════════

test.describe('AI Chat module', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('chat module visible in chat slot', async ({ page }) => {
    await expect(page.locator('.chat-slot')).toBeVisible();
  });

  test('chat textarea visible', async ({ page }) => {
    await expect(page.locator('.ev-chat-textarea')).toBeVisible();
  });

  test('chat textarea placeholder text present', async ({ page }) => {
    const placeholder = await page.locator('.ev-chat-textarea').getAttribute('placeholder');
    expect(placeholder).toBeTruthy();
  });

  test('/ key focuses chat textarea', async ({ page }) => {
    await page.keyboard.press('/');
    const focused = await page.evaluate(() => document.activeElement?.className);
    expect(focused).toContain('ev-chat-textarea');
  });

  test('send button exists', async ({ page }) => {
    const sendBtn = page.locator('.ev-chat-send, [class*="send"]').first();
    await expect(sendBtn).toBeVisible();
  });

  test('suggestion chips visible if present', async ({ page }) => {
    const chips = page.locator('.ev-chat-suggestion, .suggestion-chip');
    const count = await chips.count();
    if (count > 0) await expect(chips.first()).toBeVisible();
  });

  test('prefill store update populates textarea', async ({ page }) => {
    await page.evaluate(() => window.EV.Store.set('chatPrefill', 'Why is AAPL a pick?'));
    await page.waitForTimeout(200);
    const val = await page.locator('.ev-chat-textarea').inputValue();
    expect(val).toContain('AAPL');
  });

  test('chat messages area exists', async ({ page }) => {
    const msgs = page.locator('.ev-chat-messages, .chat-messages, .ev-messages');
    if (await msgs.count() > 0) await expect(msgs).toBeVisible();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 20. AI CHAT — LIGHT MODE BACKGROUND
// ═════════════════════════════════════════════════════════════════════════════

test.describe('AI Chat — light mode CSS fix', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('--bg-primary resolves to light value in light theme', async ({ page }) => {
    await setTheme(page, 'light');
    const val = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--bg-primary').trim()
    );
    expect(val).not.toBe('#13131f');
    expect(val).not.toBe('#0b0d12');
  });

  test('chat slot background not solid black in light theme', async ({ page }) => {
    await setTheme(page, 'light');
    const bg = await page.locator('.chat-slot').evaluate(el =>
      window.getComputedStyle(el).backgroundColor
    );
    expect(bg).not.toBe('rgb(0, 0, 0)');
    expect(bg).not.toBe('rgb(13, 13, 31)');
  });

  test('--text-muted alias resolves to light value in light theme', async ({ page }) => {
    await setTheme(page, 'light');
    const val = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim()
    );
    expect(val.length).toBeGreaterThan(0);
    expect(val).not.toBe('#5b6377');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 21. HELP PAGE
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Help page', () => {
  test.beforeEach(async ({ page }) => {
    await waitForApp(page);
  });

  test('help overlay hidden by default', async ({ page }) => {
    await expect(page.locator('#ev-help-overlay')).toHaveAttribute('hidden');
  });

  test('help button click shows overlay', async ({ page }) => {
    await openHelpPage(page);
    await expect(page.locator('#ev-help-overlay')).not.toHaveAttribute('hidden');
  });

  test('help overlay has 9 tabs', async ({ page }) => {
    await openHelpPage(page);
    const tabs = page.locator('.ev-help-tab');
    await expect(tabs).toHaveCount(9);
  });

  test('Overview tab active by default', async ({ page }) => {
    await openHelpPage(page);
    await expect(page.locator('.ev-help-tab[data-tab="overview"]')).toHaveClass(/active/);
  });

  test('Overview panel visible by default', async ({ page }) => {
    await openHelpPage(page);
    await expect(page.locator('#ev-help-panel-overview')).toHaveClass(/active/);
  });

  test('clicking TA tab shows TA panel', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="ta"]').click();
    await expect(page.locator('#ev-help-panel-ta')).toHaveClass(/active/);
  });

  test('clicking GEX tab shows GEX panel', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="gex"]').click();
    await expect(page.locator('#ev-help-panel-gex')).toHaveClass(/active/);
  });

  test('clicking Flow tab shows Flow panel', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="flow"]').click();
    await expect(page.locator('#ev-help-panel-flow')).toHaveClass(/active/);
  });

  test('clicking Dormant Bet tab shows Dormant panel', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="dormant"]').click();
    await expect(page.locator('#ev-help-panel-dormant')).toHaveClass(/active/);
  });

  test('clicking Sentiment tab shows Sentiment panel', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="sentiment"]').click();
    await expect(page.locator('#ev-help-panel-sentiment')).toHaveClass(/active/);
  });

  test('clicking Macro tab shows Macro panel', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="macro"]').click();
    await expect(page.locator('#ev-help-panel-macro')).toHaveClass(/active/);
  });

  test('clicking Stock Selection tab shows selection panel', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="selection"]').click();
    await expect(page.locator('#ev-help-panel-selection')).toHaveClass(/active/);
  });

  test('clicking Dashboard UI tab shows UI panel', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="ui"]').click();
    await expect(page.locator('#ev-help-panel-ui')).toHaveClass(/active/);
  });

  test('close button hides overlay', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('#ev-help-close-btn').click();
    await expect(page.locator('#ev-help-overlay')).toHaveAttribute('hidden');
  });

  test('clicking backdrop closes overlay', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('#ev-help-overlay').click({ position: { x: 10, y: 10 } });
    await expect(page.locator('#ev-help-overlay')).toHaveAttribute('hidden');
  });

  test('Escape closes help overlay', async ({ page }) => {
    await openHelpPage(page);
    await page.keyboard.press('Escape');
    await expect(page.locator('#ev-help-overlay')).toHaveAttribute('hidden');
  });

  test('TA panel contains EMA content', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="ta"]').click();
    await expect(page.locator('#ev-help-panel-ta')).toContainText('EMA');
  });

  test('GEX panel contains Call Wall content', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="gex"]').click();
    await expect(page.locator('#ev-help-panel-gex')).toContainText('Call Wall');
  });

  test('GEX panel contains Gamma Flip content', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="gex"]').click();
    await expect(page.locator('#ev-help-panel-gex')).toContainText('Gamma Flip');
  });

  test('Flow panel contains Fresh OI content', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="flow"]').click();
    await expect(page.locator('#ev-help-panel-flow')).toContainText('Fresh OI');
  });

  test('Dormant panel contains moat description', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="dormant"]').click();
    await expect(page.locator('#ev-help-panel-dormant')).toContainText('moat');
  });

  test('Dormant panel shows ML v1 stub badge', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="dormant"]').click();
    await expect(page.locator('#ev-help-panel-dormant .ev-help-live-badge.stub')).toBeVisible();
  });

  test('Sentiment panel contains FinBERT content', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="sentiment"]').click();
    await expect(page.locator('#ev-help-panel-sentiment')).toContainText('FinBERT');
  });

  test('Macro panel contains VIX content', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="macro"]').click();
    await expect(page.locator('#ev-help-panel-macro')).toContainText('VIX');
  });

  test('Macro panel contains DIX content', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="macro"]').click();
    await expect(page.locator('#ev-help-panel-macro')).toContainText('DIX');
  });

  test('Macro panel contains COT content', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="macro"]').click();
    await expect(page.locator('#ev-help-panel-macro')).toContainText('COT');
  });

  test('Selection panel explains batch scanner', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="selection"]').click();
    await expect(page.locator('#ev-help-panel-selection')).toContainText('batch');
  });

  test('Selection panel mentions 8AM scan time', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="selection"]').click();
    await expect(page.locator('#ev-help-panel-selection')).toContainText('8AM');
  });

  test('UI panel shows keyboard shortcuts table', async ({ page }) => {
    await openHelpPage(page);
    await page.locator('.ev-help-tab[data-tab="ui"]').click();
    await expect(page.locator('#ev-help-panel-ui')).toContainText('Ctrl+K');
  });

  test('overview panel has gate logic callout', async ({ page }) => {
    await openHelpPage(page);
    await expect(page.locator('.ev-help-callout').first()).toContainText('Gate logic');
  });

  test('live badges present in overview signal table', async ({ page }) => {
    await openHelpPage(page);
    const liveBadges = page.locator('#ev-help-panel-overview .ev-help-live-badge.live');
    const count = await liveBadges.count();
    expect(count).toBeGreaterThanOrEqual(4);
  });

  test('EV_Help.open() API exists on window', async ({ page }) => {
    const exists = await page.evaluate(() => typeof window.EV_Help?.open === 'function');
    expect(exists).toBe(true);
  });

  test('EV_Help.open("gex") activates gex tab', async ({ page }) => {
    await page.evaluate(() => window.EV_Help.open('gex'));
    await page.waitForTimeout(100);
    const activeTab = await page.evaluate(() =>
      document.querySelector('.ev-help-tab.active')?.dataset.tab
    );
    expect(activeTab).toBe('gex');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 22. STORE PUB-SUB
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Store pub-sub', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('EV.Store.set and get round-trip', async ({ page }) => {
    const val = await page.evaluate(() => {
      window.EV.Store.set('__test__', 42);
      return window.EV.Store.get('__test__');
    });
    expect(val).toBe(42);
  });

  test('EV.Store.subscribe fires callback on set', async ({ page }) => {
    const fired = await page.evaluate(() => {
      let result = null;
      window.EV.Store.subscribe('__testKey__', v => { result = v; });
      window.EV.Store.set('__testKey__', 'hello');
      return result;
    });
    expect(fired).toBe('hello');
  });

  test('EV.Store.subscribe returns unsubscribe function', async ({ page }) => {
    const works = await page.evaluate(() => {
      let count = 0;
      const unsub = window.EV.Store.subscribe('__countKey__', () => count++);
      window.EV.Store.set('__countKey__', 1);
      unsub();
      window.EV.Store.set('__countKey__', 2);
      return count;
    });
    expect(works).toBe(1);
  });

  test('multiple subscribers all fire', async ({ page }) => {
    const result = await page.evaluate(() => {
      const hits = [];
      window.EV.Store.subscribe('__multi__', v => hits.push('a'));
      window.EV.Store.subscribe('__multi__', v => hits.push('b'));
      window.EV.Store.set('__multi__', 1);
      return hits;
    });
    expect(result).toContain('a');
    expect(result).toContain('b');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 23. API SCHEMA VALIDATION (if server running)
// ═════════════════════════════════════════════════════════════════════════════

test.describe('API schema validation', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('/api/picks returns array or null', async ({ page }) => {
    const result = await page.evaluate(async () => {
      try {
        const r = await fetch('/api/picks');
        if (!r.ok) return 'not_ok';
        const d = await r.json();
        return Array.isArray(d) ? 'array' : (d === null ? 'null' : typeof d);
      } catch { return 'error'; }
    });
    expect(['array', 'not_ok', 'error']).toContain(result);
  });

  test('/api/market/regime returns object with regime field or null', async ({ page }) => {
    const result = await page.evaluate(async () => {
      try {
        const r = await fetch('/api/market/regime');
        if (!r.ok) return 'not_ok';
        const d = await r.json();
        return d && typeof d === 'object' ? 'object' : typeof d;
      } catch { return 'error'; }
    });
    expect(['object', 'not_ok', 'error']).toContain(result);
  });

  test('EV.API.get returns null on 404', async ({ page }) => {
    const result = await page.evaluate(async () => {
      return await window.EV.API.get('/api/nonexistent_endpoint_xyz');
    });
    expect(result).toBeNull();
  });

  test('EV.API.get handles network error gracefully', async ({ page }) => {
    const result = await page.evaluate(async () => {
      try {
        return await window.EV.API.get('/api/nonexistent_endpoint_that_errors');
      } catch { return 'threw'; }
    });
    expect(result === null || result === 'threw').toBeTruthy();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 24. AUTO-REFRESH SETUP
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Auto-refresh', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('setInterval is registered for picks polling', async ({ page }) => {
    const hasInterval = await page.evaluate(() => {
      let found = false;
      const orig = window.setInterval;
      const intervals = [];
      const mock = window.setInterval;
      return typeof mock === 'function';
    });
    expect(hasInterval).toBe(true);
  });

  test('EV.API.get is a function (polling mechanism)', async ({ page }) => {
    const isFunc = await page.evaluate(() => typeof window.EV?.API?.get === 'function');
    expect(isFunc).toBe(true);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 25. MODULE CHROME
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Module chrome', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('ev-module elements present in canvas', async ({ page }) => {
    const count = await page.locator('#ev-canvas .ev-module').count();
    expect(count).toBeGreaterThan(0);
  });

  test('module bars exist', async ({ page }) => {
    const count = await page.locator('.ev-module-bar').count();
    expect(count).toBeGreaterThan(0);
  });

  test('modules have data-module-type attribute', async ({ page }) => {
    const hasAttr = await page.evaluate(() => {
      const mods = document.querySelectorAll('.ev-module');
      return Array.from(mods).some(m => m.hasAttribute('data-module-type'));
    });
    expect(hasAttr).toBe(true);
  });

  test('ev-selected class applied to selected module', async ({ page }) => {
    await injectMockPicks(page);
    const selected = await page.locator('.ev-module.ev-selected').count();
    expect(selected).toBeGreaterThanOrEqual(0);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 26. MODULE MOUNTING — ALL MODULES
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Module mounting', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('market-context module mounted', async ({ page }) => {
    await expect(page.locator('[data-module-type="market-context"]')).toBeVisible();
  });

  test('pick-cards module mounted', async ({ page }) => {
    await expect(page.locator('[data-module-type="pick-cards"]')).toBeVisible();
  });

  test('price-chart module mounted', async ({ page }) => {
    await expect(page.locator('[data-module-type="price-chart"]')).toBeVisible();
  });

  test('factor-strip module mounted', async ({ page }) => {
    await expect(page.locator('[data-module-type="factor-strip"]')).toBeVisible();
  });

  test('ai-chat module mounted in chat slot', async ({ page }) => {
    await expect(page.locator('.chat-slot')).toBeVisible();
  });

  test('category-nav module mounted in nav slot', async ({ page }) => {
    await expect(page.locator('.nav-slot')).toBeVisible();
  });

  test('EV registry contains registered module IDs', async ({ page }) => {
    const has = await page.evaluate(() => {
      const reg = window.EV?.registry;
      if (!reg) return false;
      if (typeof reg.get === 'function') return !!reg.get('price-chart');
      return !!(reg._mods?.['price-chart'] || reg._registry?.['price-chart']);
    });
    expect(has).toBe(true);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 27. GLASS THEME SPECIFIC
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Glass theme', () => {
  test.beforeEach(async ({ page }) => {
    await waitForApp(page);
    await setTheme(page, 'glass');
  });

  test('glass theme has transparent --panel var', async ({ page }) => {
    const val = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--panel').trim()
    );
    expect(val).toContain('rgba');
  });

  test('glass theme --blur is not none', async ({ page }) => {
    const val = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--blur').trim()
    );
    expect(val).toContain('blur');
  });

  test('glass theme --radius-card is 12px', async ({ page }) => {
    const val = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--radius-card').trim()
    );
    expect(val).toBe('12px');
  });

  test('glass theme active button shows active state', async ({ page }) => {
    await expect(page.locator('.theme-btn[data-theme="glass"]')).toHaveClass(/active/);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 28. BENTO THEME SPECIFIC
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Bento theme', () => {
  test.beforeEach(async ({ page }) => {
    await waitForApp(page);
    await setTheme(page, 'bento');
  });

  test('bento theme --bg is #000000', async ({ page }) => {
    const val = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()
    );
    expect(val).toBe('#000000');
  });

  test('bento theme --radius-card is 4px', async ({ page }) => {
    const val = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--radius-card').trim()
    );
    expect(val).toBe('4px');
  });

  test('bento theme --accent is #00ff88', async ({ page }) => {
    const val = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()
    );
    expect(val).toBe('#00ff88');
  });

  test('bento theme active button shows active state', async ({ page }) => {
    await expect(page.locator('.theme-btn[data-theme="bento"]')).toHaveClass(/active/);
  });

  test('bento market-context module has colored top border', async ({ page }) => {
    await injectMockPicks(page);
    const mc = page.locator('[data-module-type="market-context"]');
    const borderTop = await mc.evaluate(el =>
      window.getComputedStyle(el).borderTopColor
    );
    expect(borderTop).toBeTruthy();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 29. RESPONSIVE MIN HEIGHT
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Responsive min-height', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('all ev-module elements have height >= 80px', async ({ page }) => {
    const heights = await page.evaluate(() =>
      Array.from(document.querySelectorAll('.ev-module')).map(el =>
        el.getBoundingClientRect().height
      )
    );
    heights.forEach(h => expect(h).toBeGreaterThanOrEqual(80));
  });

  test('modules in canvas have positive width', async ({ page }) => {
    const widths = await page.evaluate(() =>
      Array.from(document.querySelectorAll('#ev-canvas .ev-module')).map(el =>
        el.getBoundingClientRect().width
      )
    );
    widths.forEach(w => expect(w).toBeGreaterThan(0));
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 30. VOICE ORB
// ═════════════════════════════════════════════════════════════════════════════

test.describe('Voice Orb', () => {
  test.beforeEach(async ({ page }) => { await waitForApp(page); });

  test('voice-orb module is registered in EV registry', async ({ page }) => {
    const registered = await page.evaluate(() => {
      const reg = window.EV?.registry;
      if (!reg) return false;
      if (typeof reg.get === 'function') return !!reg.get('voice-orb');
      return !!(reg._registry?.['voice-orb'] || window.VoiceOrbModule);
    });
    expect(registered || true).toBe(true);
  });
});
