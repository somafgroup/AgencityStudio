import { test, expect } from '@playwright/test';

test('desktop shell navigation, command palette and theme persistence', async ({ page }) => {
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Welcome to AgencityStudio' })).toBeVisible();
  const primaryNav = page.getByRole('navigation', { name: 'Primary navigation' });
  await primaryNav.getByRole('link', { name: 'Projects' }).click();
  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();

  await page.keyboard.press('Control+K');
  const commandPalette = page.getByRole('dialog', { name: 'Command palette' });
  await expect(commandPalette).toBeVisible();
  await commandPalette.getByRole('textbox', { name: 'Command search' }).fill('Dashboard');
  await commandPalette.getByRole('link', { name: 'Go to Dashboard' }).click();
  await expect(page.getByRole('heading', { name: 'Welcome to AgencityStudio' })).toBeVisible();

  await page.getByRole('button', { name: 'Theme' }).click();
  await page.getByRole('button', { name: 'Dark' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect(pageErrors).toEqual([]);
});

test('mobile navigation opens and reaches a workspace', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Open navigation' }).click();
  const primaryNav = page.getByRole('navigation', { name: 'Primary navigation' });
  await expect(primaryNav).toBeVisible();
  await primaryNav.getByRole('link', { name: 'Reports' }).click();
  await expect(page.getByRole('heading', { name: 'Reports' })).toBeVisible();
});
