import { test, expect } from '@playwright/test';

test('health page is available', async ({ page }) => {
  const response = await page.goto('/health/');
  expect(response.ok()).toBeTruthy();
});
