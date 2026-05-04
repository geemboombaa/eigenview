// @ts-check
const { test, expect } = require('@playwright/test');

// Helper: open help overlay and switch to a tab
async function openHelpTab(page, tabLabel) {
  // Try various selectors for the help button
  const helpBtn = page.locator('[data-action="help"], .btn-help, #help-btn, [title*="help" i], [aria-label*="help" i], button:has-text("?"), button:has-text("Help")').first();
  if (await helpBtn.count() > 0) {
    await helpBtn.click();
  } else {
    // Trigger via keyboard shortcut '?'
    await page.keyboard.press('?');
  }
  await expect(page.locator('#ev-help-overlay')).toBeVisible({ timeout: 3000 });
  await page.locator('.ev-help-tab').filter({ hasText: tabLabel }).click();
}

test.describe('SPEC tab', () => {
  test('renders pullback pattern from API', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await openHelpTab(page, 'SPEC');

    // Panel must be visible
    const specPanel = page.locator('#ev-help-panel-spec');
    await expect(specPanel).toBeVisible();

    // Pattern loads from /api/spec/ta
    await expect(page.locator('.spec-pattern')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.spec-pattern-name')).toContainText('Pullback');
    await expect(page.locator('.spec-conditions')).toBeVisible();
  });

  test('spec conditions table has 5 rows', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await openHelpTab(page, 'SPEC');
    await expect(page.locator('.spec-conditions tbody tr')).toHaveCount(5, { timeout: 5000 });
  });

  test('note input and save button present', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await openHelpTab(page, 'SPEC');
    await expect(page.locator('.spec-pattern')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.spec-note-input').first()).toBeVisible();
    await expect(page.locator('.spec-note-btn').first()).toBeVisible();
  });
});

test.describe('AUDIT tab', () => {
  test('RUN AUDIT button present', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await openHelpTab(page, 'AUDIT');

    const auditPanel = page.locator('#ev-help-panel-audit');
    await expect(auditPanel).toBeVisible();
    await expect(page.locator('#ev-audit-run-btn')).toBeVisible();
  });

  test('RUN AUDIT returns 5 findings rows', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await openHelpTab(page, 'AUDIT');
    await page.locator('#ev-audit-run-btn').click();
    // Wait for rows to appear
    await expect(page.locator('#ev-audit-tbody tr')).toHaveCount(5, { timeout: 8000 });
  });

  test('audit summary shows PASS/FAIL/WARN counts', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await openHelpTab(page, 'AUDIT');
    await page.locator('#ev-audit-run-btn').click();
    await expect(page.locator('#ev-audit-summary')).toBeVisible({ timeout: 8000 });
    await expect(page.locator('.audit-sum-pass')).toBeVisible();
  });

  test('all 5 findings are PASS or WARN (no FAIL)', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await openHelpTab(page, 'AUDIT');
    await page.locator('#ev-audit-run-btn').click();
    await expect(page.locator('#ev-audit-tbody tr')).toHaveCount(5, { timeout: 8000 });
    const failRows = page.locator('#ev-audit-tbody tr.audit-fail');
    expect(await failRows.count()).toBe(0);
  });
});
