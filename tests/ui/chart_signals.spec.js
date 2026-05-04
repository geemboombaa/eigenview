// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Chart toggle toolbar', () => {
  test('toggle buttons are rendered in chart module', async ({ page }) => {
    await page.goto('http://localhost:8000');
    await page.waitForSelector('.chart-toggles, [data-toggle]', { timeout: 10000 });
    await expect(page.locator('[data-toggle="ema21"]')).toBeVisible();
    await expect(page.locator('[data-toggle="ema50"]')).toBeVisible();
    await expect(page.locator('[data-toggle="signals"]')).toBeVisible();
  });

  test('EMA21 toggle button toggles active class', async ({ page }) => {
    await page.goto('http://localhost:8000');
    const btn = page.locator('[data-toggle="ema21"]');
    await btn.waitFor({ timeout: 10000 });

    // Read initial active state
    const initActive = await btn.evaluate(el => el.classList.contains('active'));

    // Toggle once
    await btn.click();
    const afterFirst = await btn.evaluate(el => el.classList.contains('active'));
    expect(afterFirst).toBe(!initActive);

    // Toggle back
    await btn.click();
    const afterSecond = await btn.evaluate(el => el.classList.contains('active'));
    expect(afterSecond).toBe(initActive);
  });

  test('SIGNALS toggle button toggles active class', async ({ page }) => {
    await page.goto('http://localhost:8000');
    const btn = page.locator('[data-toggle="signals"]');
    await btn.waitFor({ timeout: 10000 });

    const initActive = await btn.evaluate(el => el.classList.contains('active'));
    await btn.click();
    const after = await btn.evaluate(el => el.classList.contains('active'));
    expect(after).toBe(!initActive);
  });

  test('EMA50 toggle button is present and clickable', async ({ page }) => {
    await page.goto('http://localhost:8000');
    const btn = page.locator('[data-toggle="ema50"]');
    await btn.waitFor({ timeout: 10000 });
    await expect(btn).toBeVisible();
    await expect(btn).toBeEnabled();
  });
});
