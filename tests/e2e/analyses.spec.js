import { Buffer } from 'node:buffer';

import { test, expect } from '@playwright/test';

const password = 'Playwright-Plan7-Password!42';

function retrySafeEmail(localPart, testInfo) {
  const suffix = testInfo.retry ? `-retry-${testInfo.retry}` : '';
  return `${localPart}${suffix}@example.com`;
}

async function signUp(page, email) {
  await page.goto('/accounts/signup/');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Display name', { exact: true }).fill('Analysis Scientist');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Password confirmation', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
}

async function createProject(page) {
  const primary = page.getByRole('navigation', { name: 'Primary navigation' });
  await primary.getByRole('link', { name: 'Projects', exact: true }).click();
  await page.locator('#main-content').getByRole('link', { name: 'New Project', exact: true }).first().click();
  await page.getByLabel(/^Name/).fill('Canonical analysis project');
  await page.getByRole('button', { name: 'Create project', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Canonical analysis project', exact: true })).toBeVisible();
}

async function importAndPrepare(page) {
  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Datasets', exact: true }).click();
  await page.getByRole('link', { name: 'Import Dataset', exact: true }).first().click();
  await page.getByLabel(/^Name/).fill('Canonical signal');
  const rows = [
    'time,angle',
    '0.0,0.0', '0.1,0.6', '0.2,1.0', '0.3,0.6', '0.4,0.0',
    '0.5,-0.6', '0.6,-1.0', '0.7,-0.6', '0.8,0.0', '0.9,0.6',
    '1.0,1.0', '1.1,0.6', '1.2,0.0', '1.3,-0.6', '1.4,-1.0',
    '1.5,-0.6', '1.6,0.0', '1.7,0.6', '1.8,1.0', '1.9,0.6', '2.0,0.0',
  ];
  await page.getByLabel('Dataset file', { exact: true }).setInputFiles({
    name: 'canonical.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(`${rows.join('\n')}\n`),
  });
  await page.getByRole('button', { name: 'Store and inspect', exact: true }).click();
  const importStatus = page.locator('#dataset-import-status');
  await expect(importStatus.getByText('READY', { exact: true })).toBeVisible({ timeout: 15000 });

  const datasetNav = page.getByRole('navigation', { name: 'Dataset navigation' });
  await datasetNav.getByRole('link', { name: 'Columns', exact: true }).click();
  await page.getByLabel('Role for time', { exact: true }).selectOption('TIME');
  await page.getByLabel('Unit for time', { exact: true }).fill('s');
  await page.getByLabel('Role for angle', { exact: true }).selectOption('OBSERVABLE');
  await page.getByLabel('Unit for angle', { exact: true }).fill('rad');
  await page.getByRole('button', { name: 'Save column annotations', exact: true }).click();

  await datasetNav.getByRole('link', { name: 'Prepare', exact: true }).click();
  await page.getByRole('link', { name: 'New preparation', exact: true }).click();
  await page.getByLabel('Preparation name', { exact: true }).fill('Canonical prepared source');
  await page.getByRole('button', { name: 'Create preparation', exact: true }).click();
  await page.getByLabel('Transformation', { exact: true }).selectOption('row_range');
  await page.getByLabel('Start row', { exact: true }).fill('1');
  await page.getByLabel('End row', { exact: true }).fill('21');
  await page.getByRole('button', { name: 'Add transformation', exact: true }).click();
  await page.getByRole('button', { name: 'Review complete — run preparation', exact: true }).click();
  const preparationStatus = page.locator('#preparation-status');
  await expect(preparationStatus.getByText('READY', { exact: true })).toBeVisible({ timeout: 20000 });
}

async function returnToProject(page) {
  const primary = page.getByRole('navigation', { name: 'Primary navigation' });
  await primary.getByRole('link', { name: 'Projects', exact: true }).click();
  await page.locator('#main-content').getByRole('link', { name: 'Canonical analysis project', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Canonical analysis project', exact: true })).toBeVisible();
}

async function createSystem(page) {
  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Systems', exact: true }).click();
  await page.getByRole('link', { name: 'Define System', exact: true }).first().click();
  await page.getByLabel(/^System name/).fill('Canonical Rotor');
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
  await page.getByLabel('Measurement / simulation source', { exact: true }).first().fill('Prepared encoder series');
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
  await expect(page.getByRole('heading', { name: 'Review scientific context', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Create system', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Canonical Rotor', exact: true })).toBeVisible();
}

test('prepared data executes canonical Analysis, sensitivity, then diagnostics through real workers', async ({ page }, testInfo) => {
  await signUp(page, retrySafeEmail('analysis-owner', testInfo));
  await createProject(page);
  await importAndPrepare(page);
  await returnToProject(page);
  await createSystem(page);

  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Analyses', exact: true }).click();
  await page.getByRole('link', { name: 'New Analysis', exact: true }).click();
  await page.getByLabel('Analysis name', { exact: true }).fill('Prepared rotor canonical');
  await page.getByLabel('Data source', { exact: true }).selectOption({ label: 'Prepared: Canonical prepared source' });
  await page.getByRole('button', { name: 'Continue to mapping', exact: true }).click();

  await page.getByLabel('Coordinate / time column', { exact: true }).selectOption({ label: '1. time [s]' });
  await page.getByLabel('Observable column', { exact: true }).selectOption({ label: '2. angle [rad]' });
  await page.getByLabel('System Revision', { exact: true }).selectOption({ label: 'Canonical Rotor · Revision 1' });
  await page.getByLabel('System observable', { exact: true }).selectOption({ label: 'Rotor angle' });
  await page.getByRole('button', { name: 'Review exact configuration', exact: true }).click();

  await expect(page.getByText('PREPARED_DATA', { exact: true })).toBeVisible();
  await expect(page.getByText('unspecified — Lab public default contract', { exact: true })).toBeVisible();
  await expect(page.getByText('AgencityLab 1.1.3 · CANONICAL SCALAR', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Run Analysis', exact: true }).click();

  let liveStatus = page.locator('[aria-live="polite"]').filter({ has: page.locator('.badge') }).first();
  await expect(liveStatus.getByText('COMPLETED', { exact: true })).toBeVisible({ timeout: 25000 });
  await page.reload();
  await expect(page.getByText('The complete canonical result is stored as a private immutable artifact.', { exact: true })).toBeVisible();
  await expect(page.getByText(/beta · complex128/)).toBeVisible();
  await expect(page.getByText(/b · complex128/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Reproducibility', exact: true })).toBeVisible();
  await expect(page.getByText('AgencityLab', { exact: true })).toBeVisible();
  await expect(page.getByText('COMPLETED means the canonical software execution completed successfully.', { exact: false })).toBeVisible();

  await page.getByRole('link', { name: 'Sensitivity', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sensitivity studies', exact: true })).toBeVisible();
  await expect(page.getByText('dt ≠ tau ≠ w', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'New sensitivity study', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Configure sensitivity study', exact: true })).toBeVisible();
  await page.getByLabel('Study type', { exact: true }).selectOption('TAU_MULTISCALE');
  await page.getByLabel('Grid generation', { exact: true }).selectOption('EXPLICIT');
  await page.getByLabel('Explicit scale values', { exact: false }).fill('0.1,0.2,0.3');
  await page.getByRole('button', { name: 'Review study', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Review sensitivity study', exact: true })).toBeVisible();
  await expect(page.getByText('agencitylab.api.compute_agencity_spectrum', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Run sensitivity study', exact: true }).click();
  await expect(page.getByText('COMPLETED', { exact: true }).first()).toBeVisible({ timeout: 25000 });
  const sensitivityWorkspace = page.locator('[data-sensitivity-workspace]');
  await expect(sensitivityWorkspace).toHaveAttribute('data-chart-ready', 'true', { timeout: 10000 });
  await expect(page.getByRole('heading', { name: 'Exact scale table', exact: true })).toBeVisible();
  await expect(page.getByText('effective_w', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('A numerical maximum does not automatically identify the physical tau.', { exact: false })).toBeVisible();

  await page.getByRole('link', { name: 'Diagnostics', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Scientific Diagnostics', exact: true })).toBeVisible();
  await expect(page.getByText('A non-zero beta is not by itself evidence of coherent or real agencity.', { exact: false })).toBeVisible();
  await page.getByRole('link', { name: 'New Diagnostic Run', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Configure diagnostics', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Review diagnostic configuration', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Review exact diagnostic contract', exact: true })).toBeVisible();
  await expect(page.getByText('Threshold provenance', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Run diagnostics', exact: true }).click();

  liveStatus = page.locator('[aria-live="polite"]').filter({ has: page.locator('.badge') }).first();
  await expect(liveStatus.getByText('COMPLETED', { exact: true })).toBeVisible({ timeout: 25000 });
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Diagnostic result artifact', exact: true })).toBeVisible();
  await expect(page.getByText('undetermined', { exact: true }).first()).toBeVisible();
  await page.getByRole('link', { name: 'Explore diagnostics', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Diagnostic Workspace', exact: true })).toBeVisible();
  await expect(page.getByText('CANONICAL', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('DIAGNOSTIC', { exact: true }).first()).toBeVisible();
  await page.getByRole('link', { name: 'Coherence & Orientation', exact: true }).click();
  const diagnosticChart = page.locator('[data-chart-card]').first();
  await expect(diagnosticChart).toHaveAttribute('data-chart-ready', 'true', { timeout: 10000 });

  const sampleInput = page.getByLabel('Sample index', { exact: true });
  await sampleInput.fill('2');
  await sampleInput.press('Tab');
  const workspace = page.locator('[data-scientific-workspace]');
  await expect(workspace).toHaveAttribute('data-selected-sample', '1');
  await expect(page.getByRole('link', { name: 'Open canonical workspace', exact: true })).toHaveAttribute('href', /sample=1/);

  await page.getByRole('link', { name: 'Real Agencity', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Real-agencity diagnostic', exact: true })).toBeVisible();
  await expect(page.getByText('A non-zero beta alone is not sufficient evidence', { exact: false })).toBeVisible();
  await expect(page.getByText('undetermined', { exact: true }).first()).toBeVisible();
});