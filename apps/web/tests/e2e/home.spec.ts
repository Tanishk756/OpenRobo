import { test, expect } from '@playwright/test';

test('homepage renders OpenRobo foundation title', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('h1')).toContainText('OpenRobo');
  await expect(page.getByText('Platform Foundation Status')).toBeVisible();
});
