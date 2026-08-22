import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';

import { test, expect } from '@playwright/test';

const password = 'Playwright-Plan2-Password!42';

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

async function signIn(page, email) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
}

async function signOut(page) {
  await page.getByRole('button', { name: 'User menu', exact: true }).click();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible();
}

async function invitationUrlFor(email) {
  const emailDir = path.resolve('.emails');
  const names = await readdir(emailDir);
  for (const name of names.reverse()) {
    const content = await readFile(path.join(emailDir, name), 'utf8');
    if (!content.includes(email)) continue;
    const match = content.match(/http:\/\/127\.0\.0\.1:8000\/workspaces\/invitations\/[A-Za-z0-9_-]+\//);
    if (match) return match[0];
  }
  throw new Error(`No invitation email found for ${email}`);
}

test('account signup creates a personal workspace and supports logout/login', async ({ page }, testInfo) => {
  const email = retrySafeEmail('account-owner', testInfo);
  await signUp(page, email, 'Account Owner');

  await expect(page.getByRole('heading', { name: 'Welcome, Account Owner', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Workspaces', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Workspaces', exact: true })).toBeVisible();
  await expect(
    page.locator('#main-content').getByRole('heading', { name: "Account Owner's workspace", exact: true }),
  ).toBeVisible();

  await signOut(page);
  await signIn(page, email);
  await expect(page.getByRole('heading', { name: 'Welcome, Account Owner', exact: true })).toBeVisible();
});

test('owner creates an organisation workspace and reaches member management', async ({ page }, testInfo) => {
  await signUp(page, retrySafeEmail('organisation-owner', testInfo), 'Organisation Owner');
  await page.getByRole('link', { name: 'Workspaces', exact: true }).first().click();
  await page.getByRole('link', { name: 'New organisation workspace', exact: true }).click();
  await page.getByLabel('Workspace name', { exact: true }).fill('Biomechanics Group');
  await page.getByLabel('Description', { exact: true }).fill('Shared scientific workspace');
  await page.getByRole('button', { name: 'Create workspace', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Biomechanics Group', exact: true })).toBeVisible();
  await expect(page.locator('#main-content').getByText('Owner', { exact: true }).first()).toBeVisible();
  await page.getByRole('link', { name: 'Members', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Members', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Invite member', exact: true })).toBeVisible();
});

test('invited viewer accepts securely and cannot manage members', async ({ page }, testInfo) => {
  const ownerEmail = retrySafeEmail('invitation-owner', testInfo);
  const viewerEmail = retrySafeEmail('invited-viewer', testInfo);
  await signUp(page, ownerEmail, 'Invitation Owner');
  await page.getByRole('link', { name: 'Workspaces', exact: true }).first().click();
  await page.getByRole('link', { name: 'New organisation workspace', exact: true }).click();
  await page.getByLabel('Workspace name', { exact: true }).fill('Invitation Laboratory');
  await page.getByRole('button', { name: 'Create workspace', exact: true }).click();
  const workspaceUrl = new URL(page.url());
  const workspaceSlug = workspaceUrl.pathname.split('/').filter(Boolean).at(-1);

  await page.getByRole('link', { name: 'Members', exact: true }).first().click();
  await page.getByRole('link', { name: 'Invite member', exact: true }).click();
  await page.getByLabel('Email', { exact: true }).fill(viewerEmail);
  await page.getByLabel('Role', { exact: true }).selectOption('VIEWER');
  await page.getByRole('button', { name: 'Send invitation', exact: true }).click();
  await expect(page.locator('#main-content').getByText(viewerEmail, { exact: true })).toBeVisible();

  const invitationUrl = await invitationUrlFor(viewerEmail);
  await signOut(page);
  await page.goto(invitationUrl);
  await expect(page.getByRole('heading', { name: 'Workspace invitation', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Create account to accept', exact: true }).click();
  await page.getByLabel('Display name', { exact: true }).fill('Invited Viewer');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Password confirmation', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account and join', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Invitation Laboratory', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Members', exact: true }).first().click();
  await expect(page.locator('#main-content').getByText(viewerEmail, { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Invite member', exact: true })).toHaveCount(0);

  await page.goto(`/workspaces/${workspaceSlug}/members/invite/`);
  await expect(page.getByRole('heading', { name: 'Access denied', exact: true })).toBeVisible();
});
