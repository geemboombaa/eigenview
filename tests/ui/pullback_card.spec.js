// @ts-check
/**
 * Phase 3 — pullback_in_trend pick card + TA checklist
 *
 * Selectors derived from actual source:
 *   .pick-card              — card root (pick-cards.js)
 *   .card-setup-name        — human-readable setup label (pick-cards.js)
 *   .btn-pin                — star/pin button in .card-row1 (pick-cards.js)
 *   .fs-dot-btn[data-fid]   — factor dot buttons in factor-strip (factor-strip.js)
 *   .fs-chk                 — checklist row (factor-strip.js)
 *   .fs-chk-label           — label text inside each check row
 *   .fs-chk-val             — value text (never raw "true"/"false")
 *   .fs-chk-icon            — pass/fail icon (✓ or ✗)
 */

const { test, expect } = require('@playwright/test');

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────

async function waitForApp(page) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
}

/**
 * Inject a mock pick with pullback_in_trend setup into the EV store,
 * and set it as the selected pick so factor-strip auto-renders it.
 */
async function injectPullbackPick(page) {
  await page.evaluate(() => {
    const mock = [
      {
        ticker: 'AAPL',
        direction: 'long',
        conviction: 4,
        setup_type: 'pullback_in_trend',
        entry_low: 185,
        entry_high: 190,
        stop: 178,
        iv_rank: 28,
        thesis: 'AAPL pulling back to 21-EMA within intact uptrend. Volume contracting on dip, RSI at 47. GEX support at $185 with call wall at $200. Flow shows institutional reloading on weakness.',
        structure: {
          type: 'long_call',
          description: 'Long Call',
          legs: 'Buy $190C, 4 weeks',
          rationale: 'IV rank 28, pullback entry'
        },
        factors: {
          macro_regime: { firing: true, strength: 0.78, label: 'GREEN',
            detail: { regime: 'bull', vix: 16.2, spy_trend: 'above_50d', breadth: 0.71 } },
          technical: {
            firing: true, strength: 0.82, label: 'pullback_in_trend',
            detail: {
              pattern: 'pullback_in_trend',
              confidence: 0.84,
              direction: 'long',
              trend: 'bullish',
              weekly_trend: 'bullish',
              rsi: 47.2,
              adx: 28.5,
              vol_ratio: 0.88,
              atr_rank: 0.44
            }
          },
          gex: { firing: true, strength: 0.70, label: 'SUPPORT',
            detail: { gamma_flip: 183.0, call_wall: 200.0, put_wall: 175.0, net_gex: 1.6, regime: 'positive' } },
          flow: { firing: true, strength: 0.75, label: 'SWEEP',
            detail: { flow_direction: 'bullish', largest_sweep: 2800000, dark_pool_cluster_price: 186.5, premium_usd: 2800000 } },
          dormant: { firing: false, strength: 0.10, label: '—',
            detail: { position_age_days: 3, open_interest_rank: 0.15, activation_probability: 0.10 } },
          sentiment: { firing: false, strength: 0.30, label: '—',
            detail: { sentiment_direction: 'neutral', catalyst_proximity: 0, novelty_score: 0.30 } },
        }
      }
    ];
    window.EV.Store.set('picks', mock);
    window.EV.Store.set('selectedPick', mock[0]);
    window.EV.Store.set('selectedTicker', 'AAPL');
  });
  await page.waitForTimeout(300);
}

// ─────────────────────────────────────────────────────────────────────────────
// TESTS
// ─────────────────────────────────────────────────────────────────────────────

test.describe('Pick card — pullback_in_trend', () => {

  test.beforeEach(async ({ page }) => {
    await waitForApp(page);
    await injectPullbackPick(page);
  });

  // ── 1. Card setup name shows human-readable text ──────────────────────────
  test('card setup name displays human-readable label', async ({ page }) => {
    const setupEl = page.locator('.card-setup-name').first();
    await expect(setupEl).toBeVisible({ timeout: 5000 });
    const text = await setupEl.textContent();
    // Must show "Pullback to Support" not raw key "pullback_in_trend"
    expect(text).toBeTruthy();
    expect(text.trim().toLowerCase()).not.toBe('pullback_in_trend');
    expect(text.trim()).toMatch(/Pullback/i);
  });

  // ── 2. TA dot button visible in factor strip ───────────────────────────────
  test('TA factor dot visible in factor strip', async ({ page }) => {
    const taDot = page.locator('.fs-dot-btn[data-fid="technical"]').first();
    await expect(taDot).toBeVisible({ timeout: 8000 });
  });

  // ── 3. TA dot has "fired" class since technical.firing = true ─────────────
  test('TA dot has fired class when technical factor is firing', async ({ page }) => {
    const taDot = page.locator('.fs-dot-btn[data-fid="technical"]').first();
    await expect(taDot).toBeVisible({ timeout: 8000 });
    await expect(taDot).toHaveClass(/fired/);
  });

  // ── 4. Clicking TA dot opens checklist ────────────────────────────────────
  test('clicking TA dot opens TA checklist', async ({ page }) => {
    const taDot = page.locator('.fs-dot-btn[data-fid="technical"]').first();
    await expect(taDot).toBeVisible({ timeout: 8000 });

    // TA auto-expands when firing — checklist may already be open
    // If not, click to open
    const checklistAlreadyOpen = await page.locator('.fs-chk').first().isVisible().catch(() => false);
    if (!checklistAlreadyOpen) {
      await taDot.click();
      await page.waitForTimeout(200);
    }

    const checklist = page.locator('.fs-chk').first();
    await expect(checklist).toBeVisible({ timeout: 3000 });
  });

  // ── 5. Checklist items show real data values, not "true" or "false" ───────
  test('TA checklist values are real data not raw booleans', async ({ page }) => {
    const taDot = page.locator('.fs-dot-btn[data-fid="technical"]').first();
    await expect(taDot).toBeVisible({ timeout: 8000 });

    // Ensure checklist is open
    const checklistAlreadyOpen = await page.locator('.fs-chk').first().isVisible().catch(() => false);
    if (!checklistAlreadyOpen) {
      await taDot.click();
      await page.waitForTimeout(200);
    }

    const valEls = await page.locator('.fs-chk-val').all();
    expect(valEls.length).toBeGreaterThan(0);

    for (const el of valEls) {
      const text = (await el.textContent()).trim();
      // Values must not be literal "true" or "false"
      expect(text.toLowerCase()).not.toBe('true');
      expect(text.toLowerCase()).not.toBe('false');
      // Values must not be empty
      expect(text.length).toBeGreaterThan(0);
    }
  });

  // ── 6. Checklist items have pass/fail icons (✓ or ✗) ─────────────────────
  test('TA checklist rows have pass/fail icons', async ({ page }) => {
    const taDot = page.locator('.fs-dot-btn[data-fid="technical"]').first();
    await expect(taDot).toBeVisible({ timeout: 8000 });

    const checklistAlreadyOpen = await page.locator('.fs-chk').first().isVisible().catch(() => false);
    if (!checklistAlreadyOpen) {
      await taDot.click();
      await page.waitForTimeout(200);
    }

    const icons = await page.locator('.fs-chk-icon').all();
    expect(icons.length).toBeGreaterThan(0);

    for (const icon of icons) {
      const text = (await icon.textContent()).trim();
      expect(['✓', '✗']).toContain(text);
    }
  });

  // ── 7. Checklist shows pullback-specific checks ───────────────────────────
  test('TA checklist contains pullback_in_trend specific check labels', async ({ page }) => {
    const taDot = page.locator('.fs-dot-btn[data-fid="technical"]').first();
    await expect(taDot).toBeVisible({ timeout: 8000 });

    const checklistAlreadyOpen = await page.locator('.fs-chk').first().isVisible().catch(() => false);
    if (!checklistAlreadyOpen) {
      await taDot.click();
      await page.waitForTimeout(200);
    }

    const labels = await page.locator('.fs-chk-label').allTextContents();
    const allText = labels.join(' ').toLowerCase();

    // pullback_in_trend checks: uptrend, RSI dip zone, volume light
    expect(allText).toMatch(/uptrend|trend/i);
    expect(allText).toMatch(/rsi/i);
    expect(allText).toMatch(/volume|vol/i);
  });

  // ── 8. Pin button visible on pick card ───────────────────────────────────
  test('pin button (star) is visible on pick card', async ({ page }) => {
    const pinBtn = page.locator('.pick-card .btn-pin').first();
    await expect(pinBtn).toBeVisible({ timeout: 5000 });
  });

  // ── 9. Pin button toggles on click ───────────────────────────────────────
  test('pin button toggles active state on click', async ({ page }) => {
    const pinBtn = page.locator('.pick-card .btn-pin').first();
    await expect(pinBtn).toBeVisible({ timeout: 5000 });

    const initialText = await pinBtn.textContent();
    await pinBtn.click({ force: true });
    await page.waitForTimeout(200);

    const afterText = await pinBtn.textContent();
    // ☆ → ★ or ★ → ☆
    expect(afterText).not.toBe(initialText);
  });

  // ── 10. All 5 factor dots present in strip ────────────────────────────────
  test('factor strip shows all 5 factor dots', async ({ page }) => {
    const dots = page.locator('.fs-dot-btn');
    await expect(dots.first()).toBeVisible({ timeout: 8000 });
    const count = await dots.count();
    expect(count).toBe(5);
  });

});

// ─────────────────────────────────────────────────────────────────────────────
// SCREENSHOT CAPTURE (runs after all tests pass)
// ─────────────────────────────────────────────────────────────────────────────

test.describe('Phase 3 proof screenshots', () => {
  test('capture card + checklist screenshot', async ({ page }) => {
    await waitForApp(page);
    await injectPullbackPick(page);

    // Wait for card
    await page.locator('.pick-card').first().waitFor({ timeout: 5000 });

    // Ensure TA checklist is open
    const taDot = page.locator('.fs-dot-btn[data-fid="technical"]').first();
    if (await taDot.isVisible()) {
      const checklistOpen = await page.locator('.fs-chk').first().isVisible().catch(() => false);
      if (!checklistOpen) {
        await taDot.click();
        await page.waitForTimeout(300);
      }
    }

    await page.screenshot({ path: 'tests/proof/phase-3/card-passing.png', fullPage: false });

    // Factor strip area screenshot
    const strip = page.locator('[data-module-type="factor-strip"]');
    if (await strip.isVisible().catch(() => false)) {
      await strip.screenshot({ path: 'tests/proof/phase-3/ta-checklist.png' });
    } else {
      // Fallback — full page
      await page.screenshot({ path: 'tests/proof/phase-3/ta-checklist.png', fullPage: false });
    }
  });
});
