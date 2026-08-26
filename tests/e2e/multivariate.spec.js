import { Buffer } from 'node:buffer';

import { test, expect } from '@playwright/test';

const password = 'Playwright-Plan11-Password!42';

function retrySafeEmail(localPart, testInfo) {
  const suffix = testInfo.retry ? `-retry-${testInfo.retry}` : '';
  return `${localPart}${suffix}@example.com`;
}

async function signUp(page, email) {
  await page.goto('/accounts/signup/');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Display name', { exact: true }).fill('Multivariate Scientist');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Password confirmation', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
}

async function signOut(page) {
  await page.getByRole('button', { name: 'User menu', exact: true }).click();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
}

async function signIn(page, email) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
}

async function createProject(page) {
  const primary = page.getByRole('navigation', { name: 'Primary navigation' });
  await primary.getByRole('link', { name: 'Projects', exact: true }).click();
  await page.locator('#main-content').getByRole('link', { name: 'New Project', exact: true }).first().click();
  await page.getByLabel(/^Name/).fill('Plan 11 multivariate project');
  await page.getByRole('button', { name: 'Create project', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Plan 11 multivariate project', exact: true })).toBeVisible();
}

async function importAndPrepare(page) {
  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Datasets', exact: true }).click();
  await page.getByRole('link', { name: 'Import Dataset', exact: true }).first().click();
  await page.getByLabel(/^Name/).fill('Plan 11 vector signal');
  const rows = ['time,component_a,component_b'];
  for (let index = 0; index < 80; index += 1) {
    const t = index * 0.1;
    const a = Math.sin(2 * Math.PI * t);
    const b = 0.35 * Math.cos(0.7 * Math.PI * t) + 0.15 * Math.sin(1.3 * Math.PI * t);
    rows.push(`${t},${a},${b}`);
  }
  await page.getByLabel('Dataset file', { exact: true }).setInputFiles({
    name: 'plan11.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(`${rows.join('\n')}\n`),
  });
  await page.getByRole('button', { name: 'Store and inspect', exact: true }).click();
  await expect(page.locator('#dataset-import-status').getByText('READY', { exact: true })).toBeVisible({ timeout: 15000 });

  const datasetNav = page.getByRole('navigation', { name: 'Dataset navigation' });
  await datasetNav.getByRole('link', { name: 'Columns', exact: true }).click();
  await page.getByLabel('Role for time', { exact: true }).selectOption('TIME');
  await page.getByLabel('Unit for time', { exact: true }).fill('s');
  await page.getByLabel('Role for component_a', { exact: true }).selectOption('OBSERVABLE');
  await page.getByLabel('Unit for component_a', { exact: true }).fill('rad');
  await page.getByLabel('Role for component_b', { exact: true }).selectOption('OBSERVABLE');
  await page.getByLabel('Unit for component_b', { exact: true }).fill('rad');
  await page.getByRole('button', { name: 'Save column annotations', exact: true }).click();

  await datasetNav.getByRole('link', { name: 'Prepare', exact: true }).click();
  await page.getByRole('link', { name: 'New preparation', exact: true }).click();
  await page.getByLabel('Preparation name', { exact: true }).fill('Plan 11 prepared vector');
  await page.getByRole('button', { name: 'Create preparation', exact: true }).click();
  await page.getByLabel('Transformation', { exact: true }).selectOption('row_range');
  await page.getByLabel('Start row', { exact: true }).fill('1');
  await page.getByLabel('End row', { exact: true }).fill('80');
  await page.getByRole('button', { name: 'Add transformation', exact: true }).click();
  await page.getByRole('button', { name: 'Review complete — run preparation', exact: true }).click();
  await expect(page.locator('#preparation-status').getByText('READY', { exact: true })).toBeVisible({ timeout: 20000 });
}

async function returnToProject(page) {
  const primary = page.getByRole('navigation', { name: 'Primary navigation' });
  await primary.getByRole('link', { name: 'Projects', exact: true }).click();
  await page.locator('#main-content').getByRole('link', { name: 'Plan 11 multivariate project', exact: true }).click();
}

async function createSystem(page) {
  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Systems', exact: true }).click();
  await page.getByRole('link', { name: 'Define System', exact: true }).first().click();
  await page.getByLabel(/^System name/).fill('Plan 11 Vector Rotor');
  await page.getByLabel(/^Documentation status/).selectOption('DOCUMENTED');
  await page.getByLabel('Domain', { exact: true }).fill('mechanics');
  await page.getByLabel('System type', { exact: true }).fill('two-component rotor');
  await page.getByLabel('Physical/scientific mechanism', { exact: true }).fill('Two measured rotational observables sharing one coordinate.');
  await page.getByLabel('Environment', { exact: true }).fill('test laboratory');

  await page.getByLabel('Observable name', { exact: true }).nth(0).fill('Rotor angle A');
  await page.getByLabel('Symbol', { exact: true }).nth(0).fill('theta_A');
  await page.getByLabel('Unit', { exact: true }).nth(0).fill('rad');
  await page.getByLabel('Observable kind', { exact: true }).nth(0).fill('angle');
  await page.getByLabel(/^Measurement nature/).nth(0).selectOption('MEASUREMENT');
  await page.getByLabel('Measurement / simulation source', { exact: true }).nth(0).fill('Prepared component A');
  await page.getByLabel('Primary observable', { exact: true }).nth(0).check();

  await page.getByLabel('Observable name', { exact: true }).nth(1).fill('Rotor angle B');
  await page.getByLabel('Symbol', { exact: true }).nth(1).fill('theta_B');
  await page.getByLabel('Unit', { exact: true }).nth(1).fill('rad');
  await page.getByLabel('Observable kind', { exact: true }).nth(1).fill('angle');
  await page.getByLabel(/^Measurement nature/).nth(1).selectOption('MEASUREMENT');
  await page.getByLabel('Measurement / simulation source', { exact: true }).nth(1).fill('Prepared component B');

  await page.getByLabel('A_ref value', { exact: true }).fill('1.0');
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
  await expect(page.getByRole('heading', { name: 'Plan 11 Vector Rotor', exact: true })).toBeVisible();
}

test('Plan 11 prepared multivariate workflow executes through the real worker and exposes provenance', async ({ page }, testInfo) => {
  const email = retrySafeEmail('plan11-multivariate-owner', testInfo);
  await signUp(page, email);
  await signOut(page);
  await signIn(page, email);
  await createProject(page);
  await importAndPrepare(page);
  await returnToProject(page);
  await createSystem(page);

  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Analyses', exact: true }).click();
  await page.getByRole('link', { name: 'New Multivariate Analysis', exact: true }).click();
  await page.getByLabel('Analysis name', { exact: true }).fill('Plan 11 multivariate run');
  await page.getByLabel('Data source', { exact: true }).selectOption({ label: 'Prepared: Plan 11 prepared vector' });
  await page.getByRole('button', { name: 'Continue to components', exact: true }).click();

  await page.getByLabel('Shared coordinate / time column', { exact: true }).selectOption({ label: '1. time [s]' });
  await page.getByLabel('System Revision', { exact: true }).selectOption({ label: 'Plan 11 Vector Rotor · Revision 1' });
  await page.getByLabel('Number of components', { exact: true }).fill('2');
  await page.getByLabel('A_ref contract', { exact: true }).selectOption('SYSTEM_GLOBAL');
  await page.getByLabel('tau contract', { exact: true }).selectOption('SYSTEM_GLOBAL');
  await page.getByLabel('w contract', { exact: true }).selectOption('UNSPECIFIED');
  await page.getByLabel('P_c contract', { exact: true }).selectOption('SYSTEM_GLOBAL');
  await page.getByLabel('Component 1 source column', { exact: true }).selectOption({ label: '2. component_a [rad]' });
  await page.getByLabel('Component 1 System observable', { exact: true }).selectOption({ label: 'Rotor angle A' });
  await page.getByLabel('Component 2 source column', { exact: true }).selectOption({ label: '3. component_b [rad]' });
  await page.getByLabel('Component 2 System observable', { exact: true }).selectOption({ label: 'Rotor angle B' });
  await page.getByRole('button', { name: 'Continue to Review', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Multivariate Analysis Review', exact: true })).toBeVisible();
  await expect(page.getByText('Rotor angle A', { exact: false }).first()).toBeVisible();
  await expect(page.getByText('Rotor angle B', { exact: false }).first()).toBeVisible();
  await expect(page.getByText('Unspecified (w=None)', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('agencitylab.api.compute_multivariate_agencity', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Run Multivariate Analysis', exact: true }).click();

  const liveStatus = page.locator('[aria-live="polite"]').filter({ has: page.locator('.badge') }).first();
  await expect(liveStatus.getByText('COMPLETED', { exact: true })).toBeVisible({ timeout: 30000 });
  await page.reload();
  await expect(page.getByRole('link', { name: 'Explore multivariate results', exact: true })).toBeVisible();
  await expect(page.getByText('Ordered component snapshots', { exact: true })).toBeVisible();
  await expect(page.getByText('unspecified', { exact: true }).first()).toBeVisible();

  await page.getByRole('link', { name: 'Explore multivariate results', exact: true }).click();
  await expect(page.getByRole('heading', { name: /Plan 11 multivariate run · Run 1/ })).toBeVisible();
  await expect(page.getByText('VOLUME 2 MULTIVARIATE EXTENSION', { exact: true })).toBeVisible();
  await expect(page.getByText('agencitylab.api.compute_multivariate_agencity', { exact: true })).toBeVisible();
  await expect(page.getByText('A non-zero component or aggregate value is not by itself evidence of coherent or real agencity.', { exact: true })).toBeVisible();

  await page.getByRole('link', { name: 'Component Results', exact: true }).click();
  const componentWorkspace = page.locator('[data-scientific-workspace]');
  await expect(componentWorkspace).toBeVisible();
  await expect(componentWorkspace.locator('[data-chart-card]').first()).toHaveAttribute('data-chart-ready', 'true', { timeout: 10000 });

  await page.getByRole('link', { name: 'Lab Multivariate Result', exact: true }).click();
  await expect(page.getByText('AgencityLab aggregate only', { exact: true })).toBeVisible();
  await expect(page.getByText('Studio does not average, sum, normalize or weight component scientific outputs here.', { exact: true })).toBeVisible();

  await page.getByRole('link', { name: 'Reproducibility', exact: true }).click();
  await expect(page.getByText('Execution fingerprint', { exact: true })).toBeVisible();
  await expect(page.getByText('Public function', { exact: true })).toBeVisible();
  await expect(page.getByText('Rotor angle A ·', { exact: false })).toBeVisible();
  await expect(page.getByText('Rotor angle B ·', { exact: false })).toBeVisible();
});
