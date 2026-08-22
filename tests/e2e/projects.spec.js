import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';

import { test, expect } from '@playwright/test';

const password = 'Playwright-Plan3-Password!42';

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

async function signOut(page) {
  await page.getByRole('button', { name: 'User menu', exact: true }).click();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
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

test('project lifecycle creates edits archives and restores real project metadata', async ({ page }, testInfo) => {
  await signUp(page, retrySafeEmail('project-owner', testInfo), 'Project Owner');
  await page.getByRole('link', { name: 'Projects', exact: true }).first().click();
  await page.getByRole('link', { name: 'New Project', exact: true }).first().click();
  await page.getByLabel('Name', { exact: true }).fill('Rotor vibration study');
  await page.getByLabel('Description', { exact: true }).fill('Initial rotor description');
  await page.getByLabel('Domain', { exact: true }).fill('mechanics');
  await page.getByLabel('Tags', { exact: true }).fill('rotor, vibration');
  await page.getByRole('button', { name: 'Create project', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Rotor vibration study', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await page.getByLabel('Description', { exact: true }).fill('Updated rotor description');
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(page.getByText('Project settings updated.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Archive project', exact: true }).click();
  await expect(page.getByText('ARCHIVED', { exact: true })).toBeVisible();

  await page.getByRole('link', { name: 'Projects', exact: true }).first().click();
  await page.getByRole('link', { name: 'Archived', exact: true }).click();
  await page.getByRole('link', { name: 'Rotor vibration study', exact: true }).click();
  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Restore project', exact: true }).click();
  await expect(page.getByText('ACTIVE', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Activity', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Project Activity', exact: true })).toBeVisible();
  await expect(page.getByText('Restored', { exact: true })).toBeVisible();
});

test('viewer can inspect a project but cannot reach project settings', async ({ page }, testInfo) => {
  const ownerEmail = retrySafeEmail('project-sharing-owner', testInfo);
  const viewerEmail = retrySafeEmail('project-sharing-viewer', testInfo);
  await signUp(page, ownerEmail, 'Sharing Owner');
  await page.getByRole('link', { name: 'Workspaces', exact: true }).first().click();
  await page.getByRole('link', { name: 'New organisation workspace', exact: true }).click();
  await page.getByLabel('Workspace name', { exact: true }).fill('Shared Project Laboratory');
  await page.getByRole('button', { name: 'Create workspace', exact: true }).click();
  await page.getByRole('link', { name: 'New Project', exact: true }).first().click();
  await page.getByLabel('Name', { exact: true }).fill('Shared Rotor Project');
  await page.getByRole('button', { name: 'Create project', exact: true }).click();
  const projectUrl = page.url();

  await page.getByRole('button', { name: 'User menu', exact: true }).click();
  await page.getByRole('link', { name: 'Members', exact: true }).click();
  await page.getByRole('link', { name: 'Invite member', exact: true }).click();
  await page.getByLabel('Email', { exact: true }).fill(viewerEmail);
  await page.getByLabel('Role', { exact: true }).selectOption('VIEWER');
  await page.getByRole('button', { name: 'Send invitation', exact: true }).click();
  const invitationUrl = await invitationUrlFor(viewerEmail);

  await signOut(page);
  await page.goto(invitationUrl);
  await page.getByRole('link', { name: 'Create account to accept', exact: true }).click();
  await page.getByLabel('Display name', { exact: true }).fill('Project Viewer');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Password confirmation', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account and join', exact: true }).click();

  await page.goto(projectUrl);
  await expect(page.getByRole('heading', { name: 'Shared Rotor Project', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Settings', exact: true })).toHaveCount(0);
  await page.goto(`${projectUrl}settings/`);
  await expect(page.getByRole('heading', { name: 'Access denied', exact: true })).toBeVisible();
});
