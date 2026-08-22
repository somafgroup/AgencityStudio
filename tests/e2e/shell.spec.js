import { test, expect } from '@playwright/test';

const password = 'Playwright-Scientific-Password!42';

function retrySafeEmail(localPart, testInfo) {
  const suffix = testInfo.retry ? `-retry-${testInfo.retry}` : '';
  return `${localPart}${suffix}@example.com`;
}

async function signUp(page, email, displayName) {
  await page.goto('/accounts/signup/');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Display name', { exact: true }).fill(displayName);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Password confirmation', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
}

test('authenticated desktop shell navigation, command palette and theme persistence', async ({ page }, testInfo) => {
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));

  await signUp(page, retrySafeEmail('shell-user', testInfo), 'Shell User');
  await expect(page.getByRole('heading', { name: 'Welcome, Shell User', exact: true })).toBeVisible();
  const primaryNav = page.getByRole('navigation', { name: 'Primary navigation' });
  await primaryNav.getByRole('link', { name: 'Projects', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();

  await page.keyboard.press('Control+K');
  const commandPalette = page.getByRole('dialog', { name: 'Command palette' });
  await expect(commandPalette).toBeVisible();
  await commandPalette.getByRole('textbox', { name: 'Command search' }).fill('Dashboard');
  await commandPalette.getByRole('link', { name: /^Go to Dashboard/ }).click();
  await expect(page.getByRole('heading', { name: 'Welcome, Shell User', exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Theme', exact: true }).click();
  await page.getByRole('button', { name: 'Dark', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByText('Theme set to dark.', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect(pageErrors).toEqual([]);
});

test('authenticated mobile navigation opens and reaches reports', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signUp(page, retrySafeEmail('shell-mobile', testInfo), 'Mobile Shell User');
  await expect(page.getByRole('heading', { name: 'Welcome, Mobile Shell User', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
  const primaryNav = page.getByRole('navigation', { name: 'Primary navigation' });
  await expect(primaryNav).toBeVisible();
  await primaryNav.getByRole('link', { name: 'Reports', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Reports', exact: true })).toBeVisible();
});
