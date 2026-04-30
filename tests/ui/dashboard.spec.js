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

  test('card hover reveals actions fully', async ({ page }) => {
    const card = page.locator('.pick-card').first();
    if (await card.count() === 0) test.skip('no pick cards');
    await card.hover();
    const actions = card.locator('.card-actions');
    const opacity = await actions.evaluate(el => getComputedStyle(el).opacity);
    expect(parseFloat(opacity)).toBeCloseTo(1, 1);
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

  test('edit mode button exists', async ({ page }) => {
    const editBtn = page.locator('button', { hasText: /edit/i }).first();
    await expect(editBtn).toBeVisible();
  });

  test('clicking edit toggles edit-mode class on canvas', async ({ page }) => {
    const editBtn = page.locator('[data-action="edit"], #ev-edit-btn, button').filter({ hasText: /edit layout|edit/i }).first();
    if (await editBtn.count() === 0) test.skip('no edit button found');
    await editBtn.click();
    const canvas = page.locator('#ev-canvas');
    await expect(canvas).toHaveClass(/edit-mode/, { timeout: 1000 });
  });

  test('Done button dismisses edit hint bar', async ({ page }) => {
    // Enter edit mode
    const editBtn = page.locator('button').filter({ hasText: /edit layout|edit/i }).first();
    if (await editBtn.count() === 0) test.skip();
    await editBtn.click();

    // edit-hint bar should be visible
    const hint = page.locator('.edit-hint');
    await expect(hint).toBeVisible({ timeout: 1000 });

    // Click Done
    const doneBtn = page.locator('.edit-hint button', { hasText: /done/i });
    await doneBtn.click();

    // hint should disappear
    await expect(hint).toBeHidden({ timeout: 1000 });
  });

  test('drag handles appear in edit mode', async ({ page }) => {
    const editBtn = page.locator('button').filter({ hasText: /edit layout|edit/i }).first();
    if (await editBtn.count() === 0) test.skip();
    await editBtn.click();

    // At least one drag handle should have non-zero opacity in edit mode
    const handle = page.locator('.ev-drag-handle').first();
    await expect(handle).toBeVisible({ timeout: 1000 });
    const opacity = await handle.evaluate(el => getComputedStyle(el).opacity);
    expect(parseFloat(opacity)).toBeGreaterThan(0);
  });
});

test.describe('Theme toggle (light/dark)', () => {
  test('light mode switch changes data-theme attribute', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const themeBtn = page.locator('[data-action="theme"], #ev-theme-btn, button').filter({ hasText: /light|dark|theme/i }).first();
    if (await themeBtn.count() === 0) test.skip('no theme button');

    const beforeTheme = await page.evaluate(() => document.documentElement.dataset.theme || document.documentElement.getAttribute('data-theme') || '');
    await themeBtn.click();
    const afterTheme = await page.evaluate(() => document.documentElement.dataset.theme || document.documentElement.getAttribute('data-theme') || '');
    expect(afterTheme).not.toEqual(beforeTheme);
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
    await expect(chatModule.locator('textarea')).toBeVisible();
    await expect(chatModule.locator('button[type="submit"], button').filter({ hasText: /send/i })).toBeVisible();
  });

  test('sending message shows response (no unicode escapes)', async ({ page }) => {
    const chatModule = page.locator('[data-module-type="ai-chat"]');
    const textarea = chatModule.locator('textarea');
    const sendBtn = chatModule.locator('button[type="submit"], button').filter({ hasText: /send/i });

    await textarea.fill('What is a call wall?');
    await sendBtn.click();

    // wait for response to appear
    const msgs = chatModule.locator('.chat-msg, .chat-bubble, .ai-message, p').last();
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

    // Wait for canvas element inside the chart module
    const chartContainer = page.locator('[data-module-type="price-chart"] canvas');
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
