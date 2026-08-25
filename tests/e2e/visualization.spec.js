import { Buffer } from 'node:buffer';

import { test, expect } from '@playwright/test';

const password = 'Playwright-Plan8-Password!42';

function retrySafeEmail(localPart, testInfo) {
  const suffix = testInfo.retry ? `-retry-${testInfo.retry}` : '';
  return `${localPart}${suffix}@example.com`;
}

async function signUp(page, email) {
  await page.goto('/accounts/signup/');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Display name', { exact: true }).fill('Visualization Scientist');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Password confirmation', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
}

async function createProject(page) {
  const primary = page.getByRole('navigation', { name: 'Primary navigation' });
  await primary.getByRole('link', { name: 'Projects', exact: true }).click();
  await page.locator('#main-content').getByRole('link', { name: 'New Project', exact: true }).first().click();
  await page.getByLabel(/^Name/).fill('Visualization project');
  await page.getByRole('button', { name: 'Create project', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Visualization project', exact: true })).toBeVisible();
}

async function importRawDataset(page) {
  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Datasets', exact: true }).click();
  await page.getByRole('link', { name: 'Import Dataset', exact: true }).first().click();
  await page.getByLabel(/^Name/).fill('Visualization signal');
  const rows = [
    'time,angle',
    '0.0,0.0', '0.1,0.6', '0.2,1.0', '0.3,0.6', '0.4,0.0',
    '0.5,-0.6', '0.6,-1.0', '0.7,-0.6', '0.8,0.0', '0.9,0.6',
    '1.0,1.0', '1.1,0.6', '1.2,0.0', '1.3,-0.6', '1.4,-1.0',
    '1.5,-0.6', '1.6,0.0', '1.7,0.6', '1.8,1.0', '1.9,0.6', '2.0,0.0',
  ];
  await page.getByLabel('Dataset file', { exact: true }).setInputFiles({
    name: 'visualization.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(`${rows.join('\n')}\n`),
  });
  await page.getByRole('button', { name: 'Store and inspect', exact: true }).click();
  const status = page.locator('#dataset-import-status');
  await expect(status.getByText('READY', { exact: true })).toBeVisible({ timeout: 15000 });

  const datasetNav = page.getByRole('navigation', { name: 'Dataset navigation' });
  await datasetNav.getByRole('link', { name: 'Columns', exact: true }).click();
  await page.getByLabel('Role for time', { exact: true }).selectOption('TIME');
  await page.getByLabel('Unit for time', { exact: true }).fill('s');
  await page.getByLabel('Role for angle', { exact: true }).selectOption('OBSERVABLE');
  await page.getByLabel('Unit for angle', { exact: true }).fill('rad');
  await page.getByRole('button', { name: 'Save column annotations', exact: true }).click();
}

async function returnToProject(page) {
  const primary = page.getByRole('navigation', { name: 'Primary navigation' });
  await primary.getByRole('link', { name: 'Projects', exact: true }).click();
  await page.locator('#main-content').getByRole('link', { name: 'Visualization project', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Visualization project', exact: true })).toBeVisible();
}

async function createSystem(page) {
  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Systems', exact: true }).click();
  await page.getByRole('link', { name: 'Define System', exact: true }).first().click();
  await page.getByLabel(/^System name/).fill('Visualization Rotor');
  await page.getByLabel(/^Documentation status/).selectOption('DOCUMENTED');
  await page.getByLabel('Domain', { exact: true }).fill('mechanics');
  await page.getByLabel('System type', { exact: true }).fill('test rotor');
  await page.getByLabel('Physical/scientific mechanism', { exact: true }).fill('Deterministic rotational oscillator');
  await page.getByLabel('Environment', { exact: true }).fill('laboratory');

  await page.getByLabel('Observable name', { exact: true }).first().fill('Rotor angle');
  await page.getByLabel('Symbol', { exact: true }).first().fill('theta');
  await page.getByLabel('Unit', { exact: true }).first().fill('rad');
  await page.getByLabel('Observable kind', { exact: true }).first().fill('angle');
  await page.getByLabel(/^Measurement nature/).first().selectOption('MEASUREMENT');
  await page.getByLabel('Measurement / simulation source', { exact: true }).first().fill('Encoder series');
  await page.getByLabel('Primary observable', { exact: true }).first().check();

  await page.getByLabel('A_ref value', { exact: true }).fill('1.5');
  await page.getByLabel('A_ref unit', { exact: true }).fill('rad');
  await page.getByLabel(/^A_ref origin/).selectOption('CALIBRATION');
  await page.getByLabel('A_ref justification', { exact: true }).fill('Explicit calibration reference amplitude.');

  await page.getByLabel('tau value', { exact: true }).fill('0.2');
  await page.getByLabel('tau unit', { exact: true }).fill('s');
  await page.getByLabel(/^tau origin/).selectOption('CALIBRATION');
  await page.getByLabel('tau justification', { exact: true }).fill('Explicit structural time from calibration.');

  await page.getByLabel(/^Memory window w/).selectOption('UNSPECIFIED');

  await page.getByLabel('P_c value', { exact: true }).fill('12');
  await page.getByLabel('P_c unit', { exact: true }).fill('W');
  await page.getByLabel(/^P_c origin/).selectOption('MANUFACTURER');
  await page.getByLabel('P_c justification', { exact: true }).fill('Explicit characteristic power from specification.');

  await page.getByRole('button', { name: 'Review', exact: true }).click();
  await page.getByRole('button', { name: 'Create system', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Visualization Rotor', exact: true })).toBeVisible();
}

async function runAnalysis(page) {
  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Analyses', exact: true }).click();
  await page.getByRole('link', { name: 'New Analysis', exact: true }).click();
  await page.getByLabel('Analysis name', { exact: true }).fill('Rotor visualization analysis');
  await page.getByLabel('Data source', { exact: true }).selectOption({ label: 'Original: Visualization signal · v1' });
  await page.getByRole('button', { name: 'Continue to mapping', exact: true }).click();

  await page.getByLabel('Coordinate / time column', { exact: true }).selectOption({ label: '1. time [s]' });
  await page.getByLabel('Observable column', { exact: true }).selectOption({ label: '2. angle [rad]' });
  await page.getByLabel('System Revision', { exact: true }).selectOption({ label: 'Visualization Rotor · Revision 1' });
  await page.getByLabel('System observable', { exact: true }).selectOption({ label: 'Rotor angle' });
  await page.getByRole('button', { name: 'Review exact configuration', exact: true }).click();
  await page.getByRole('button', { name: 'Run Analysis', exact: true }).click();

  const liveStatus = page.locator('[aria-live="polite"]').filter({ has: page.locator('.badge') }).first();
  await expect(liveStatus.getByText('COMPLETED', { exact: true })).toBeVisible({ timeout: 25000 });
  await page.reload();
  await page.getByRole('link', { name: 'Explore canonical results', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible();
}

async function openResultSection(page, name) {
  const navigation = page.getByRole('navigation', { name: 'Canonical result sections' });
  await navigation.getByRole('link', { name, exact: true }).click();
}

async function expectChartsReady(page, count = 1) {
  const charts = page.locator('[data-chart-card]');
  await expect(charts).toHaveCount(count);
  for (let index = 0; index < count; index += 1) {
    await expect(charts.nth(index)).toHaveAttribute('data-chart-ready', 'true', { timeout: 15000 });
  }
}

test('completed Run opens synchronized canonical Results and complex planes', async ({ page }, testInfo) => {
  await signUp(page, retrySafeEmail('visualization-owner', testInfo));
  await createProject(page);
  await importRawDataset(page);
  await returnToProject(page);
  await createSystem(page);
  await runAnalysis(page);

  const workspace = page.locator('[data-scientific-workspace]');
  await expect(workspace).toHaveAttribute('data-workspace-ready', 'true', { timeout: 15000 });
  await expect(page.getByText('COMPLETED is not a coherence or real-agencity conclusion.', { exact: false })).toBeVisible();

  await openResultSection(page, 'Observable');
  await expectChartsReady(page, 1);
  await page.getByRole('button', { name: 'Next sample', exact: true }).click();
  await expect(page.locator('[data-scientific-workspace]')).toHaveAttribute('data-selected-sample', '1');
  await expect(page.locator('[data-sample-summary]')).toHaveText('2 / 21');
  await expect(page.locator('[data-sample-values]')).toContainText('u');

  await openResultSection(page, 'Dynamics');
  await expect(page).toHaveURL(/sample=1/);
  await expectChartsReady(page, 3);

  await openResultSection(page, 'Structure');
  await expectChartsReady(page, 2);

  await openResultSection(page, 'Contrast & Orientation');
  await expectChartsReady(page, 3);
  await expect(page.getByText('Theta is the structural orientation returned by AgencityLab.', { exact: false })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'U complex plane', exact: true })).toBeVisible();

  await openResultSection(page, 'Agencity State');
  await expectChartsReady(page, 2);
  await expect(page.getByRole('heading', { name: 'β complex plane', exact: true })).toBeVisible();
  await expect(page.getByText('A non-zero beta alone is not a coherence diagnostic.', { exact: false })).toBeVisible();

  await openResultSection(page, 'Agencity Flux');
  await expectChartsReady(page, 2);
  await expect(page.getByRole('heading', { name: 'b complex plane', exact: true })).toBeVisible();
  await expect(page.locator('[data-scientific-workspace]')).toHaveAttribute('data-selected-sample', '1');

  await page.getByRole('button', { name: 'Theme', exact: true }).click();
  await page.getByRole('button', { name: 'Dark', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('[data-chart-card]').first()).toHaveAttribute('data-chart-theme', 'dark');

  await openResultSection(page, 'Exact table');
  await expect(page.getByRole('heading', { name: 'Exact canonical table', exact: true })).toBeVisible();
  await expect(page.locator('tbody tr').nth(1)).toHaveAttribute('data-selected', 'true');

  await openResultSection(page, 'Reproducibility');
  await expect(page.getByRole('heading', { name: 'Reproducibility', exact: true })).toBeVisible();
  await expect(page.getByText('Result SHA-256', { exact: true })).toBeVisible();
});
