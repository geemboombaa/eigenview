// @ts-check
const { test } = require('@playwright/test');
const path = require('path');

const PROOF_DIR = path.join(__dirname, '..', 'proof', 'phase-4');

async function openHelpTab(page, tabLabel) {
  const helpBtn = page.locator('[data-action="help"], .btn-help, #help-btn, button:has-text("?"), button:has-text("Help")').first();
  if (await helpBtn.count() > 0) {
    await helpBtn.click();
  } else {
    await page.keyboard.press('?');
  }
  await page.locator('#ev-help-overlay').waitFor({ state: 'visible', timeout: 3000 });
  await page.locator('.ev-help-tab').filter({ hasText: tabLabel }).click();
  await page.waitForTimeout(600);
}

test('screenshot: SPEC tab', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await openHelpTab(page, 'SPEC');
  // Wait for spec to load
  await page.locator('.spec-pattern').waitFor({ timeout: 5000 });
  await page.screenshot({ path: path.join(PROOF_DIR, 'spec-tab.png'), fullPage: false });
});

test('screenshot: AUDIT tab', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await openHelpTab(page, 'AUDIT');
  await page.locator('#ev-audit-run-btn').click();
  await page.locator('#ev-audit-tbody tr').first().waitFor({ timeout: 8000 });
  await page.screenshot({ path: path.join(PROOF_DIR, 'audit-tab.png'), fullPage: false });
});
