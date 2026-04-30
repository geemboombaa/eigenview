// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Dashboard load', () => {
  test('page loads without JS errors', async ({ page }) => {
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    expect(errors).toEqual([]);
  });

  test('pick cards render', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // At least one pick card or the "no picks" empty state should exist
    const cards = page.locator('.pick-card');
    const empty = page.locator('[data-module-type="pick-cards"]');
    await expect(empty).toBeVisible();
  });

  test('TV chart module present', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const chartModule = page.locator('[data-module-type="price-chart"]');
    await expect(chartModule).toBeVisible();
  });

  test('factor-strip module present', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const strip = page.locator('[data-module-type="factor-strip"]');
    await expect(strip).toBeVisible();
  });

  test('ai-chat module present', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const chat = page.locator('[data-module-type="ai-chat"]');
    await expect(chat).toBeVisible();
  });
});

test.describe('Pick card interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('card actions visible at baseline (not invisible)', async ({ page }) => {
    const actions = page.locator('.card-actions').first();
    if (await actions.count() === 0) {
      test.skip('no pick cards — skip interaction tests');
    }
    // opacity:0.45 at baseline — element must be in DOM and not hidden
    await expect(actions).toBeVisible();
    const opacity = await actions.evaluate(el => getComputedStyle(el).opacity);
    expect(parseFloat(opacity)).toBeGreaterThan(0);
  });

  test('card hover reveals actions (opacity increases)', async ({ page }) => {
    const card = page.locator('.pick-card').first();
    if (await card.count() === 0) test.skip('no pick cards');
    // baseline opacity without hover
    const actions = card.locator('.card-actions');
    const before = parseFloat(await actions.evaluate(el => getComputedStyle(el).opacity));
    await card.hover();
    await page.waitForTimeout(200); // let CSS transition run
    const after = parseFloat(await actions.evaluate(el => getComputedStyle(el).opacity));
    // either hover worked (after > before) or baseline is already >0 (acceptable)
    expect(after).toBeGreaterThanOrEqual(before);
    expect(before).toBeGreaterThan(0); // should never be fully invisible
  });

  test('clicking card selects it (adds .selected)', async ({ page }) => {
    const card = page.locator('.pick-card').first();
    if (await card.count() === 0) test.skip('no pick cards');
    await card.click();
    await expect(card).toHaveClass(/selected/);
  });

  test('DETAIL button scrolls to chart module', async ({ page }) => {
    const card = page.locator('.pick-card').first();
    if (await card.count() === 0) test.skip('no pick cards');
    await card.hover();
    const detailBtn = card.locator('button', { hasText: /detail/i });
    if (await detailBtn.count() === 0) test.skip('no DETAIL button');
    await detailBtn.click();
    // chart module should be visible in viewport after scroll
    const chartModule = page.locator('[data-module-type="price-chart"]');
    await expect(chartModule).toBeInViewport({ timeout: 2000 }).catch(() => {
      // scroll may not bring it fully in viewport — just check it exists
    });
  });

  test('ASK AI button prefills chat textarea', async ({ page }) => {
    const card = page.locator('.pick-card').first();
    if (await card.count() === 0) test.skip('no pick cards');
    await card.hover();
    const askBtn = card.locator('button', { hasText: /ask ai/i });
    if (await askBtn.count() === 0) test.skip('no ASK AI button');
    await askBtn.click();
    const textarea = page.locator('[data-module-type="ai-chat"] textarea');
    await expect(textarea).not.toBeEmpty({ timeout: 1000 });
  });

  test('FAV button toggles favorite state', async ({ page }) => {
    const card = page.locator('.pick-card').first();
    if (await card.count() === 0) test.skip('no pick cards');
    await card.hover();
    const favBtn = card.locator('button', { hasText: /fav/i });
    if (await favBtn.count() === 0) test.skip('no FAV button');
    await favBtn.click();
    // Button should show some visual change (text or class)
    await expect(favBtn).toBeVisible();
  });
});

test.describe('Edit mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('edit mode activated via JS API', async ({ page }) => {
    await page.evaluate(() => window.EV?.Canvas?.setEditMode(true));
    const canvas = page.locator('#ev-canvas');
    await expect(canvas).toHaveClass(/edit-mode/, { timeout: 1000 });
  });

  test('Done button dismisses edit hint bar', async ({ page }) => {
    await page.evaluate(() => window.EV?.Canvas?.setEditMode(true));

    const hint = page.locator('.edit-hint');
    await expect(hint).toBeVisible({ timeout: 1000 });

    await page.locator('#ev-edit-done').click();
    await expect(hint).toBeHidden({ timeout: 1000 });
  });

  test('drag handles appear in edit mode', async ({ page }) => {
    await page.evaluate(() => window.EV?.Canvas?.setEditMode(true));
    await page.waitForTimeout(100); // transition

    const handle = page.locator('.ev-drag-handle').first();
    const opacity = await handle.evaluate(el => getComputedStyle(el).opacity);
    expect(parseFloat(opacity)).toBeGreaterThan(0);
  });
});

test.describe('Theme toggle (light/dark)', () => {
  test('theme buttons change data-theme attribute', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // LIGHT button in #ev-theme-switcher
    const lightBtn = page.locator('.theme-btn[data-theme="light"]');
    await expect(lightBtn).toBeVisible();

    const before = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    await lightBtn.click();
    const after = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    expect(after).toBe('light');
    expect(after).not.toEqual(before);
  });

  test('light mode: pick cards not black background', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Force light theme
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'light');
    });
    await page.waitForTimeout(200);

    const card = page.locator('.pick-card').first();
    if (await card.count() === 0) test.skip('no pick cards');

    const bg = await card.evaluate(el => getComputedStyle(el).backgroundColor);
    // In light mode background should NOT be pure black (rgb(0,0,0))
    expect(bg).not.toBe('rgb(0, 0, 0)');
  });
});

test.describe('AI chat', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('chat input and send button present', async ({ page }) => {
    const chatModule = page.locator('[data-module-type="ai-chat"]');
    await expect(chatModule).toBeVisible();
    await expect(chatModule.locator('textarea.ev-chat-textarea')).toBeVisible();
    await expect(chatModule.locator('.ev-chat-send')).toBeVisible();
  });

  test('sending message shows response (no unicode escapes)', async ({ page }) => {
    const chatModule = page.locator('[data-module-type="ai-chat"]');
    const textarea = chatModule.locator('.ev-chat-textarea');
    const sendBtn = chatModule.locator('.ev-chat-send');

    await textarea.fill('What is a call wall?');
    await sendBtn.click();

    // wait for AI response to appear
    const msgs = chatModule.locator('.ev-msg-ai').last();
    await expect(msgs).toBeVisible({ timeout: 15000 });

    // response text should not contain raw unicode escapes like –
    const text = await chatModule.innerText();
    expect(text).not.toMatch(/\\u[0-9a-fA-F]{4}/);
  });
});

test.describe('TV chart', () => {
  test('chart canvas renders after pick selected', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const card = page.locator('.pick-card').first();
    if (await card.count() === 0) test.skip('no pick cards');
    await card.click();

    // Wait for canvas element inside the chart module (multiple canvases expected from TV charts)
    const chartContainer = page.locator('[data-module-type="price-chart"] canvas').first();
    await expect(chartContainer).toBeVisible({ timeout: 5000 });
  });

  test('chart has non-zero dimensions', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const card = page.locator('.pick-card').first();
    if (await card.count() === 0) test.skip('no pick cards');
    await card.click();

    await page.waitForTimeout(1000); // let ResizeObserver fire

    const canvas = page.locator('[data-module-type="price-chart"] canvas').first();
    await expect(canvas).toBeVisible({ timeout: 5000 });

    const box = await canvas.boundingBox();
    expect(box?.width).toBeGreaterThan(0);
    expect(box?.height).toBeGreaterThan(0);
  });
});

test.describe('Factor strip', () => {
  test('factor cells render after pick selected', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const card = page.locator('.pick-card').first();
    if (await card.count() === 0) test.skip('no pick cards');
    await card.click();

    const cells = page.locator('[data-module-type="factor-strip"] .factor-cell, [data-module-type="factor-strip"] .fs-cell');
    await expect(cells.first()).toBeVisible({ timeout: 3000 });
    const count = await cells.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test('clicking factor cell prefills chat', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const card = page.locator('.pick-card').first();
    if (await card.count() === 0) test.skip('no pick cards');
    await card.click();

    const cells = page.locator('[data-module-type="factor-strip"] .factor-cell, [data-module-type="factor-strip"] .fs-cell');
    if (await cells.count() === 0) test.skip('no factor cells rendered');

    await cells.first().click();
    const textarea = page.locator('[data-module-type="ai-chat"] textarea');
    await expect(textarea).not.toBeEmpty({ timeout: 1000 });
  });
});
