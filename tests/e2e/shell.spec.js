import { test, expect } from '@playwright/test';

test('desktop shell navigation, command palette and theme persistence', async ({ page }) => {
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Welcome to AgencityStudio', exact: true })).toBeVisible();
  const primaryNav = page.getByRole('navigation', { name: 'Primary navigation' });
  await primaryNav.getByRole('link', { name: 'Projects', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();

  await page.keyboard.press('Control+K');
  const commandPalette = page.getByRole('dialog', { name: 'Command palette' });
  await expect(commandPalette).toBeVisible();
  await commandPalette.getByRole('textbox', { name: 'Command search' }).fill('Dashboard');
  await commandPalette.getByRole('link', { name: /^Go to Dashboard/ }).click();
  await expect(page.getByRole('heading', { name: 'Welcome to AgencityStudio', exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Theme', exact: true }).click();
  await page.getByRole('button', { name: 'Dark', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect(pageErrors).toEqual([]);
});

test('mobile navigation opens and reaches a workspace', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
  const primaryNav = page.getByRole('navigation', { name: 'Primary navigation' });
  await expect(primaryNav).toBeVisible();
  await primaryNav.getByRole('link', { name: 'Reports', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Reports', exact: true })).toBeVisible();
});
