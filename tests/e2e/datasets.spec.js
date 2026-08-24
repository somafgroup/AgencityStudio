import { Buffer } from 'node:buffer';

import { test, expect } from '@playwright/test';

const password = 'Playwright-Plan4-Password!42';

function retrySafeEmail(localPart, testInfo) {
  const suffix = testInfo.retry ? `-retry-${testInfo.retry}` : '';
  return `${localPart}${suffix}@example.com`;
}

async function signUp(page, email) {
  await page.goto('/accounts/signup/');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Display name', { exact: true }).fill('Dataset Owner');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Password confirmation', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
}

async function createProject(page) {
  const navigation = page.getByRole('navigation', { name: 'Primary navigation' });
  await navigation.getByRole('link', { name: 'Projects', exact: true }).click();
  const main = page.locator('#main-content');
  await main.getByRole('link', { name: 'New Project', exact: true }).first().click();
  await page.getByLabel(/^Name/).fill('Dataset workspace project');
  await page.getByRole('button', { name: 'Create project', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Dataset workspace project', exact: true })).toBeVisible();
}

async function openProjectDatasets(page) {
  const navigation = page.getByRole('navigation', { name: 'Project navigation' });
  await navigation.getByRole('link', { name: 'Datasets', exact: true }).click();
}

async function startDatasetImport(page) {
  await page.getByRole('link', { name: 'Import Dataset', exact: true }).first().click();
}

async function openDatasetSection(page, name) {
  const navigation = page.getByRole('navigation', { name: 'Dataset navigation' });
  await navigation.getByRole('link', { name, exact: true }).click();
}

async function waitForReady(page) {
  const status = page.locator('#dataset-import-status');
  await expect(status.getByText('READY', { exact: true })).toBeVisible({ timeout: 15000 });
}

async function importPreparedFixture(page) {
  await openProjectDatasets(page);
  await startDatasetImport(page);
  await page.getByLabel(/^Name/).fill('Preparation signal');
  const source = 'time,velocity\n0.00,0.0\n0.01,3.6\n0.02,\n0.03,10.8\n0.04,14.4\n';
  await page.getByLabel('Dataset file', { exact: true }).setInputFiles({
    name: 'preparation.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(source),
  });
  await page.getByRole('button', { name: 'Store and inspect', exact: true }).click();
  await waitForReady(page);
  await openDatasetSection(page, 'Columns');
  await page.getByLabel('Role for time', { exact: true }).selectOption('TIME');
  await page.getByLabel('Unit for time', { exact: true }).fill('s');
  await page.getByLabel('Role for velocity', { exact: true }).selectOption('OBSERVABLE');
  await page.getByLabel('Unit for velocity', { exact: true }).fill('km/h');
  await page.getByRole('button', { name: 'Save column annotations', exact: true }).click();
  await openDatasetSection(page, 'Overview');
  await waitForReady(page);
}

test('raw CSV import is inspected annotated confirmed and remains downloadable', async ({ page }, testInfo) => {
  await signUp(page, retrySafeEmail('dataset-owner', testInfo));
  await createProject(page);

  await openProjectDatasets(page);
  await startDatasetImport(page);
  await page.getByLabel(/^Name/).fill('Rotor measurements');
  const source = 'time,velocity\n0.00,1.0\n0.01,1.2\n0.02,\n0.03,1.6\n';
  await page.getByLabel('Dataset file', { exact: true }).setInputFiles({
    name: 'rotor.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(source),
  });
  await page.getByRole('button', { name: 'Store and inspect', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Rotor measurements', exact: true })).toBeVisible();
  await waitForReady(page);
  await expect(page.getByText('4 rows · 2 columns', { exact: true })).toBeVisible();

  await openDatasetSection(page, 'Preview');
  await expect(page.getByRole('columnheader', { name: 'time', exact: true })).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'velocity', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: '1.2', exact: true })).toBeVisible();

  await openDatasetSection(page, 'Columns');
  await page.getByLabel('Role for time', { exact: true }).selectOption('TIME');
  await page.getByLabel('Unit for time', { exact: true }).fill('s');
  await page.getByLabel('Role for velocity', { exact: true }).selectOption('OBSERVABLE');
  await page.getByLabel('Unit for velocity', { exact: true }).fill('m/s');
  await page.getByRole('button', { name: 'Save column annotations', exact: true }).click();

  await openDatasetSection(page, 'Overview');
  await waitForReady(page);
  await page.getByRole('button', { name: 'Confirm as current', exact: true }).click();
  await expect(page.getByText('Current version', { exact: true })).toBeVisible();

  await openDatasetSection(page, 'Quality');
  await expect(page.getByText(/velocity contains 1 missing values/i)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Observed time-axis properties', exact: true })).toBeVisible();
  await expect(page.getByText('Sampling regular', { exact: true })).toBeVisible();

  await openDatasetSection(page, 'Source');
  await expect(page.getByText('SHA-256', { exact: true })).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download exact original', exact: true }).click();
  const downloaded = await download;
  expect(downloaded.suggestedFilename()).toBe('rotor.csv');
});

test('explicit preparation preserves raw source and materializes provenance', async ({ page }, testInfo) => {
  await signUp(page, retrySafeEmail('preparation-owner', testInfo));
  await createProject(page);
  await importPreparedFixture(page);

  await openDatasetSection(page, 'Prepare');
  await page.getByRole('link', { name: 'New preparation', exact: true }).click();
  await page.getByLabel('Preparation name', { exact: true }).fill('Analysis-ready view');
  await page.getByRole('button', { name: 'Create preparation', exact: true }).click();

  await page.getByLabel('Transformation', { exact: true }).selectOption('time_crop');
  await page.getByLabel('Time column', { exact: true }).selectOption({ label: 'time' });
  await page.getByLabel('Start', { exact: true }).fill('0.01');
  await page.getByLabel('End', { exact: true }).fill('0.04');
  await page.getByRole('button', { name: 'Add transformation', exact: true }).click();

  await page.getByLabel('Transformation', { exact: true }).selectOption('missing_values');
  await page.getByLabel('Target columns', { exact: true }).selectOption({ label: 'velocity' });
  await page.getByLabel('Missing-value treatment', { exact: true }).selectOption('interpolate_linear');
  await page.getByLabel('Interpolation coordinate', { exact: true }).selectOption({ label: 'time' });
  await page.getByRole('button', { name: 'Add transformation', exact: true }).click();

  await page.getByRole('button', { name: 'Review complete — run preparation', exact: true }).click();
  const status = page.locator('#preparation-status');
  await expect(status.getByText('READY', { exact: true })).toBeVisible({ timeout: 20000 });
  await page.reload();
  await expect(page.getByText('Prepared SHA-256', { exact: true })).toBeVisible();
  await expect(page.getByText('Original SHA-256', { exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: '4', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Preview result', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Prepared preview', exact: true })).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'velocity', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: '7.2', exact: true })).toBeVisible();
});

test('malformed XLSX produces a friendly failed import state', async ({ page }, testInfo) => {
  await signUp(page, retrySafeEmail('dataset-failure-owner', testInfo));
  await createProject(page);
  await openProjectDatasets(page);
  await startDatasetImport(page);
  await page.getByLabel(/^Name/).fill('Broken workbook');
  await page.getByLabel('Dataset file', { exact: true }).setInputFiles({
    name: 'broken.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('not an xlsx zip archive'),
  });
  await page.getByRole('button', { name: 'Store and inspect', exact: true }).click();

  const status = page.locator('#dataset-import-status');
  await expect(status.getByText('FAILED', { exact: true })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('The XLSX workbook could not be read.', { exact: true })).toBeVisible();
  await expect(page.getByText(/BadZipFile/)).toHaveCount(0);
});
