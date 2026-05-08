// @ts-check
/**
 * Suite A gap coverage — areas NOT covered by comprehensive.spec.js or full-ui.spec.js:
 *   1. Favorites → Mine tab appearance
 *   2. LocalStorage persistence across reload
 *   3. GEX overlay lines on price chart
 *   4. Actual drag interaction in edit mode
 *   5. Signal freshness badges (Fresh / Valid / Stale)
 *   6. Signal matrix view (SIGNAL MATRIX pill → matrix rows + star column)
 *   7. Chart EMA/BB overlay toggles
 *   8. Theme × template cross-persistence
 *
 * Stubs raise explicit errors until green phase implements.
 * All tests run against real server at BASE_URL (no mocked API).
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.EIGENVIEW_TEST_URL || 'http://localhost:8000';

async function waitForApp(page) {
  await page.goto(BASE_URL);
  await page.waitForLoadState('networkidle');
}

async function injectPicks(page, picks) {
  await page.evaluate(p => {
    window.EV.Store.set('picks', p);
    window.EV.Store.set('selectedPick', p[0]);
  }, picks);
  await page.waitForTimeout(150);
}

const REAL_PICK = {
  ticker: 'NVDA', direction: 'long', conviction: 4, setup_type: 'pullback_in_trend',
  entry_low: 875, entry_high: 882.5, stop: 861.25, target: 912, rr_ratio: 2.31,
  thesis: 'NVDA consolidating above EMA21 with declining volume on pullback.',
  factors_json: {
    technical: { firing: true, confidence: 0.82 },
    gex: { firing: true, net_gex: 450000, gamma_flip: 860, call_wall: 910, put_wall: 840 },
    flow: { firing: true, direction: 'bullish', largest_sweep_premium: 620000 },
    dormant: { firing: false },
    sentiment: { firing: false },
  },
  fired_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(), // 30 min ago = Fresh
};

// ── 1. Favorites → Mine tab ───────────────────────────────────────────────────

test('pin card adds it to Mine tab', async ({ page }) => {
  test.fail(true, 'STUB: Mine tab filter after pin not yet implemented');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK]);
  const pinBtn = page.locator('[data-action="pin"], button.pin-btn, [aria-label*="pin"]').first();
  await pinBtn.click();
  const mineTab = page.locator('[data-category="mine"], button:has-text("Mine")');
  await mineTab.click();
  const card = page.locator(`.pick-card[data-ticker="NVDA"]`);
  await expect(card).toBeVisible();
});

test('Mine tab is empty before any pins', async ({ page }) => {
  test.fail(true, 'STUB: Mine tab empty state not yet verified');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK]);
  const mineTab = page.locator('[data-category="mine"], button:has-text("Mine")');
  await mineTab.click();
  const empty = page.locator('.empty-state, [data-empty]');
  await expect(empty).toBeVisible();
});

// ── 2. LocalStorage persistence ───────────────────────────────────────────────

test('pinned card survives page reload', async ({ page }) => {
  test.fail(true, 'STUB: localStorage persistence across reload not yet tested');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK]);
  await page.evaluate(() => {
    const favs = JSON.parse(localStorage.getItem('ev_favorites') || '[]');
    favs.push('NVDA');
    localStorage.setItem('ev_favorites', JSON.stringify(favs));
  });
  await page.reload();
  await page.waitForLoadState('networkidle');
  await injectPicks(page, [REAL_PICK]);
  const mineTab = page.locator('[data-category="mine"], button:has-text("Mine")');
  await mineTab.click();
  const card = page.locator(`.pick-card[data-ticker="NVDA"]`);
  await expect(card).toBeVisible();
});

test('unpinning removes from Mine tab and clears localStorage', async ({ page }) => {
  test.fail(true, 'STUB: unpin → Mine tab removal not yet tested');
  await waitForApp(page);
  await page.evaluate(() => localStorage.setItem('ev_favorites', JSON.stringify(['NVDA'])));
  await injectPicks(page, [REAL_PICK]);
  const mineTab = page.locator('[data-category="mine"], button:has-text("Mine")');
  await mineTab.click();
  const pinBtn = page.locator('[data-action="pin"], button.pin-btn').first();
  await pinBtn.click(); // toggle off
  const card = page.locator(`.pick-card[data-ticker="NVDA"]`);
  await expect(card).not.toBeVisible();
  const stored = await page.evaluate(() => localStorage.getItem('ev_favorites'));
  expect(JSON.parse(stored || '[]')).not.toContain('NVDA');
});

// ── 3. GEX overlay lines on chart ────────────────────────────────────────────

test('gamma flip line visible on price chart when GEX firing', async ({ page }) => {
  test.fail(true, 'STUB: GEX overlay lines not yet implemented or tested');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK]);
  // GEX overlay lines would be rendered as SVG lines or canvas elements
  // Exact selector depends on TradingView createPriceLine() implementation
  const gammaFlipLine = page.locator('[data-price-line="gamma-flip"], .gex-gamma-flip');
  await expect(gammaFlipLine).toBeVisible();
});

test('call wall line visible on price chart', async ({ page }) => {
  test.fail(true, 'STUB: call wall price line not yet tested');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK]);
  const callWallLine = page.locator('[data-price-line="call-wall"], .gex-call-wall');
  await expect(callWallLine).toBeVisible();
});

test('put wall line visible on price chart', async ({ page }) => {
  test.fail(true, 'STUB: put wall price line not yet tested');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK]);
  const putWallLine = page.locator('[data-price-line="put-wall"], .gex-put-wall');
  await expect(putWallLine).toBeVisible();
});

test('GEX overlay lines absent when pick has no GEX data', async ({ page }) => {
  test.fail(true, 'STUB: absent GEX lines not yet tested');
  await waitForApp(page);
  const pickNoGex = { ...REAL_PICK, factors_json: { ...REAL_PICK.factors_json, gex: { firing: false } } };
  await injectPicks(page, [pickNoGex]);
  const anyGexLine = page.locator('[data-price-line^="gex"], .gex-overlay-line');
  await expect(anyGexLine).toHaveCount(0);
});

// ── 4. Edit mode — actual drag ────────────────────────────────────────────────

test('dragging module changes its position', async ({ page }) => {
  test.fail(true, 'STUB: drag position change not yet tested (handles visible only)');
  await waitForApp(page);
  await page.evaluate(() => window.EV?.Canvas?.setEditMode(true));
  await page.waitForTimeout(150);
  const module = page.locator('ev-module, .ev-module').first();
  const handle = module.locator('.drag-handle, [data-drag-handle]');
  const before = await module.boundingBox();
  await handle.dragTo(page.locator('body'), { targetPosition: { x: (before?.x || 0) + 100, y: (before?.y || 0) + 50 } });
  await page.waitForTimeout(200);
  const after = await module.boundingBox();
  expect(after?.x).not.toBe(before?.x);
});

test('dragging resize handle increases module height', async ({ page }) => {
  test.fail(true, 'STUB: resize drag not yet tested');
  await waitForApp(page);
  await page.evaluate(() => window.EV?.Canvas?.setEditMode(true));
  await page.waitForTimeout(150);
  const module = page.locator('ev-module, .ev-module').first();
  const resizeHandle = module.locator('.ev-resize-handle, [data-resize-handle]');
  const before = await module.boundingBox();
  await resizeHandle.dragTo(page.locator('body'), { targetPosition: { x: before?.x || 0, y: (before?.y || 0) + (before?.height || 0) + 80 } });
  await page.waitForTimeout(200);
  const after = await module.boundingBox();
  expect((after?.height || 0)).toBeGreaterThan((before?.height || 0));
});

// ── 5. Signal freshness badges ────────────────────────────────────────────────

test('pick fired < 2h ago shows Fresh badge', async ({ page }) => {
  test.fail(true, 'STUB: Fresh badge not yet implemented');
  await waitForApp(page);
  const freshPick = { ...REAL_PICK, fired_at: new Date(Date.now() - 30 * 60 * 1000).toISOString() };
  await injectPicks(page, [freshPick]);
  const badge = page.locator('.pick-card[data-ticker="NVDA"] .freshness-badge, [data-freshness]');
  await expect(badge).toHaveText(/fresh/i);
});

test('pick fired 2-8h ago shows Valid badge', async ({ page }) => {
  test.fail(true, 'STUB: Valid badge not yet implemented');
  await waitForApp(page);
  const validPick = { ...REAL_PICK, fired_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString() };
  await injectPicks(page, [validPick]);
  const badge = page.locator('.pick-card[data-ticker="NVDA"] .freshness-badge, [data-freshness]');
  await expect(badge).toHaveText(/valid/i);
});

test('pick fired > 8h ago shows Stale badge', async ({ page }) => {
  test.fail(true, 'STUB: Stale badge not yet implemented');
  await waitForApp(page);
  const stalePick = { ...REAL_PICK, fired_at: new Date(Date.now() - 10 * 60 * 60 * 1000).toISOString() };
  await injectPicks(page, [stalePick]);
  const badge = page.locator('.pick-card[data-ticker="NVDA"] .freshness-badge, [data-freshness]');
  await expect(badge).toHaveText(/stale/i);
});

// ── 6. Signal matrix view ─────────────────────────────────────────────────────

test('clicking SIGNAL MATRIX pill shows matrix view', async ({ page }) => {
  test.fail(true, 'STUB: signal matrix view not yet tested');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK]);
  const matrixPill = page.locator('button:has-text("SIGNAL MATRIX"), [data-nav="matrix"]');
  await matrixPill.click();
  const matrixView = page.locator('.signal-matrix, [data-view="matrix"]');
  await expect(matrixView).toBeVisible();
});

test('signal matrix star column shows conviction as stars', async ({ page }) => {
  test.fail(true, 'STUB: star column in matrix not yet tested');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK]);
  const matrixPill = page.locator('button:has-text("SIGNAL MATRIX"), [data-nav="matrix"]');
  await matrixPill.click();
  const starCell = page.locator('.matrix-row .star-col, [data-col="stars"]').first();
  await expect(starCell).toBeVisible();
});

test('signal matrix row click selects pick', async ({ page }) => {
  test.fail(true, 'STUB: matrix row → selectedPick not yet tested');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK]);
  const matrixPill = page.locator('button:has-text("SIGNAL MATRIX"), [data-nav="matrix"]');
  await matrixPill.click();
  const firstRow = page.locator('.matrix-row, [data-matrix-row]').first();
  await firstRow.click();
  const selected = await page.evaluate(() => window.EV?.Store?.get('selectedTicker'));
  expect(selected).toBe('NVDA');
});

test('signal matrix shows all 5 factor columns (TA, GEX, FLOW, DORM, SENT)', async ({ page }) => {
  test.fail(true, 'STUB: matrix factor columns not yet tested');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK]);
  const matrixPill = page.locator('button:has-text("SIGNAL MATRIX"), [data-nav="matrix"]');
  await matrixPill.click();
  for (const factor of ['TA', 'GEX', 'FLOW', 'DORM', 'SENT']) {
    const col = page.locator(`th:has-text("${factor}"), [data-col="${factor.toLowerCase()}"]`);
    await expect(col).toBeVisible();
  }
});

// ── 7. Chart EMA / BB toggles ─────────────────────────────────────────────────

test('EMA21 overlay toggle defaults to ON', async ({ page }) => {
  test.fail(true, 'STUB: chart overlay toggle defaults not yet tested');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK]);
  const ema21Toggle = page.locator('[data-toggle="ema21"], button:has-text("EMA21")');
  await expect(ema21Toggle).toHaveClass(/active|on/);
});

test('clicking EMA21 toggle turns it OFF and removes series', async ({ page }) => {
  test.fail(true, 'STUB: EMA21 toggle interaction not yet tested');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK]);
  const ema21Toggle = page.locator('[data-toggle="ema21"], button:has-text("EMA21")');
  await ema21Toggle.click();
  await expect(ema21Toggle).not.toHaveClass(/active|on/);
  // Verify localStorage persists the toggle state
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('ev_chart_toggles') || '{}'));
  expect(stored['ema21']).toBe(false);
});

test('BB overlay defaults to OFF', async ({ page }) => {
  test.fail(true, 'STUB: BB overlay default state not yet tested');
  await waitForApp(page);
  const bbToggle = page.locator('[data-toggle="bb"], button:has-text("BB")');
  await expect(bbToggle).not.toHaveClass(/active|on/);
});

test('chart overlay toggle states persist across pick selection change', async ({ page }) => {
  test.fail(true, 'STUB: overlay persistence across pick change not yet tested');
  await waitForApp(page);
  await injectPicks(page, [REAL_PICK, { ...REAL_PICK, ticker: 'AAPL' }]);
  const ema50Toggle = page.locator('[data-toggle="ema50"], button:has-text("EMA50")');
  await ema50Toggle.click(); // turn off
  // Switch pick selection
  await page.evaluate(() => window.EV?.Store?.set('selectedTicker', 'AAPL'));
  await page.waitForTimeout(200);
  // EMA50 should still be OFF
  await expect(ema50Toggle).not.toHaveClass(/active|on/);
});

// ── 8. Theme × template cross-persistence ────────────────────────────────────

test('theme survives template switch', async ({ page }) => {
  test.fail(true, 'STUB: theme × template cross-persistence not yet tested');
  await waitForApp(page);
  // Set glass theme
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'glass'));
  // Switch to MINIMAL template
  await page.keyboard.press('2');
  await page.waitForTimeout(100);
  // Theme must be unchanged
  const theme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
  expect(theme).toBe('glass');
});

test('template survives theme switch', async ({ page }) => {
  test.fail(true, 'STUB: template × theme cross-persistence not yet tested');
  await waitForApp(page);
  // Apply PRO template
  await page.keyboard.press('3');
  await page.waitForTimeout(100);
  // Switch to LIGHT theme
  await page.locator('button:has-text("LIGHT")').click();
  await page.waitForTimeout(100);
  // Template must still be PRO
  const tmpl = await page.evaluate(() => window.EV?.Store?.get('template'));
  expect(tmpl).toBe('pro');
});
