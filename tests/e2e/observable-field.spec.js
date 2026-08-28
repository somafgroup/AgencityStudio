import { execFileSync } from 'node:child_process';

import { test, expect } from '@playwright/test';

const password = 'Playwright-Plan12-Password!42';

function retrySafeEmail(localPart, testInfo) {
  const suffix = testInfo.retry ? `-retry-${testInfo.retry}` : '';
  return `${localPart}${suffix}@example.com`;
}

function fieldNpzBuffer() {
  const script = `
import io, sys
import numpy as np
buf = io.BytesIO()
t = np.arange(72, dtype=np.float64) * 0.05
x = np.linspace(-1.0, 1.0, 6, dtype=np.float64)
u = np.stack([np.sin((1.0 + 0.1*j) * 2*np.pi*t) + 0.03*j for j in range(x.size)], axis=1)
np.savez(buf, u=u, t=t, x=x)
sys.stdout.buffer.write(buf.getvalue())
`;
  return execFileSync('python', ['-c', script]);
}

async function signUp(page, email) {
  await page.goto('/accounts/signup/');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Display name', { exact: true }).fill('Observable Field Scientist');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Password confirmation', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
}

async function createProject(page) {
  const primary = page.getByRole('navigation', { name: 'Primary navigation' });
  await primary.getByRole('link', { name: 'Projects', exact: true }).click();
  await page.locator('#main-content').getByRole('link', { name: 'New Project', exact: true }).first().click();
  await page.getByLabel(/^Name/).fill('Plan 12 observable field project');
  await page.getByRole('button', { name: 'Create project', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Plan 12 observable field project', exact: true })).toBeVisible();
}

async function importFieldSource(page) {
  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Datasets', exact: true }).click();
  await page.getByRole('link', { name: 'Import Field Source', exact: true }).first().click();
  await expect(page.getByText('EXPERIMENTAL FIELD DATA', { exact: true })).toBeVisible();
  await page.getByLabel('Dataset name', { exact: true }).fill('Plan 12 field source');
  await page.getByLabel('NPZ field source', { exact: true }).setInputFiles({
    name: 'plan12-field.npz',
    mimeType: 'application/x-npz',
    buffer: fieldNpzBuffer(),
  });
  await page.getByRole('button', { name: 'Store and inspect field source', exact: true }).click();
  await expect(page.locator('#dataset-import-status').getByText('READY', { exact: true })).toBeVisible({ timeout: 20000 });
  await expect(page.getByText('N-D FIELD SOURCE', { exact: true })).toBeVisible();
  await expect(page.getByText('u', { exact: true }).first()).toBeVisible();
  const confirm = page.getByRole('button', { name: 'Confirm as current', exact: true });
  if (await confirm.isVisible()) await confirm.click();
}

async function returnToProject(page) {
  const primary = page.getByRole('navigation', { name: 'Primary navigation' });
  await primary.getByRole('link', { name: 'Projects', exact: true }).click();
  await page.locator('#main-content').getByRole('link', { name: 'Plan 12 observable field project', exact: true }).click();
}

async function createSystem(page) {
  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Systems', exact: true }).click();
  await page.getByRole('link', { name: 'Define System', exact: true }).first().click();
  await page.getByLabel(/^System name/).fill('Plan 12 Field Rotor');
  await page.getByLabel(/^Documentation status/).selectOption('DOCUMENTED');
  await page.getByLabel('Domain', { exact: true }).fill('mechanics');
  await page.getByLabel('System type', { exact: true }).fill('distributed observable rotor');
  await page.getByLabel('Physical/scientific mechanism', { exact: true }).fill('Measured local angular trajectories on an explicit spatial coordinate.');
  await page.getByLabel('Environment', { exact: true }).fill('test laboratory');

  await page.getByLabel('Observable name', { exact: true }).nth(0).fill('Angle field');
  await page.getByLabel('Symbol', { exact: true }).nth(0).fill('q');
  await page.getByLabel('Unit', { exact: true }).nth(0).fill('rad');
  await page.getByLabel('Observable kind', { exact: true }).nth(0).fill('angle');
  await page.getByLabel(/^Measurement nature/).nth(0).selectOption('MEASUREMENT');
  await page.getByLabel('Measurement / simulation source', { exact: true }).nth(0).fill('Plan 12 NPZ observable field');
  await page.getByLabel('Primary observable', { exact: true }).nth(0).check();

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
  await expect(page.getByRole('heading', { name: 'Plan 12 Field Rotor', exact: true })).toBeVisible();
}

test('Plan 12 observable field executes through the real worker and exposes exact field provenance', async ({ page }, testInfo) => {
  const email = retrySafeEmail('plan12-field-owner', testInfo);
  await signUp(page, email);
  await createProject(page);
  await importFieldSource(page);
  await returnToProject(page);
  await createSystem(page);

  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Analyses', exact: true }).click();
  await page.getByRole('link', { name: 'New Observable Field', exact: true }).click();
  await expect(page.getByText('EXPERIMENTAL', { exact: true }).first()).toBeVisible();
  await page.getByLabel('Analysis name', { exact: true }).fill('Plan 12 observable field run');
  await page.getByLabel('Immutable NPZ field source', { exact: true }).selectOption({ label: 'Plan 12 field source · v1 · plan12-field.npz' });
  await page.getByRole('button', { name: 'Continue to field configuration', exact: true }).click();

  await page.getByLabel('Observable array u', { exact: true }).selectOption('u');
  await page.getByLabel('Time coordinate array t', { exact: true }).selectOption('t');
  await page.getByLabel('time_axis', { exact: true }).fill('0');
  await page.getByLabel('Time unit', { exact: true }).fill('s');
  await page.getByLabel('Observable unit', { exact: true }).fill('rad');
  await page.getByLabel('Spatial coordinates', { exact: true }).selectOption('EXPLICIT');
  await page.getByLabel('Spatial coordinate array keys', { exact: true }).fill('x');
  await page.getByLabel('Spatial axis names', { exact: true }).fill('x');
  await page.getByLabel('Spatial axis units', { exact: true }).fill('m');
  await page.getByLabel('System Revision', { exact: true }).selectOption({ index: 1 });
  await page.getByLabel('Observable', { exact: true }).selectOption({ index: 1 });
  await page.getByLabel('A_ref', { exact: true }).selectOption('SCALAR');
  await page.getByLabel('tau', { exact: true }).selectOption('SCALAR');
  await page.getByLabel('w', { exact: true }).selectOption('UNSPECIFIED');
  await page.getByLabel('P_c', { exact: true }).selectOption('SCALAR');
  await page.getByRole('button', { name: 'Continue to Review', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Observable Spatial Agencity Field Review', exact: true })).toBeVisible();
  await expect(page.getByText('Scientific status: EXPERIMENTAL', { exact: true })).toBeVisible();
  await expect(page.getByText('Unspecified (w=None)', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('agencitylab.fields.compute_agencity_field', { exact: true })).toBeVisible();
  await expect(page.getByText('shape =', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /Run Observable Field/ }).click();

  const liveStatus = page.locator('[aria-live="polite"]').filter({ has: page.locator('.badge') }).first();
  await expect(liveStatus.getByText('COMPLETED', { exact: true })).toBeVisible({ timeout: 30000 });
  await page.reload();
  await expect(page.getByRole('link', { name: 'Explore observable field', exact: true })).toBeVisible();
  await expect(page.getByText('Unspecified (w=None)', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Observable field result artifact', { exact: true })).toBeVisible();

  await page.getByRole('link', { name: 'Explore observable field', exact: true }).click();
  await expect(page.getByText('OBSERVABLE SPATIAL EXTENSION', { exact: true })).toBeVisible();
  await expect(page.getByText('EXPERIMENTAL', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('agencitylab.fields.compute_agencity_field', { exact: true })).toBeVisible();
  await expect(page.getByText('A non-zero local beta_obs or large b_obs is not by itself evidence of coherent or real agencity.', { exact: true })).toBeVisible();
  await expect(page.locator('[data-field-point]')).toContainText('t[0]', { timeout: 10000 });

  await page.getByRole('link', { name: 'Field Observable', exact: true }).click();
  await expect(page.locator('[data-field-chart] canvas')).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(/Display-only index sampling/)).toBeVisible();
  await page.getByRole('button', { name: 'Next time', exact: true }).click();
  await page.getByRole('button', { name: 'Next first spatial coordinate', exact: true }).click();
  await expect(page.locator('[data-field-point]')).toContainText('t[1]');

  await page.getByRole('link', { name: 'Agencity State Field', exact: true }).click();
  await expect(page.getByLabel('Complex display', { exact: true })).toBeVisible();
  await page.getByLabel('Complex display', { exact: true }).selectOption('real');
  await expect(page.locator('[data-field-chart] canvas')).toBeVisible({ timeout: 10000 });

  await page.getByRole('link', { name: 'Local Trace', exact: true }).click();
  await expect(page.locator('[data-field-trace-chart] canvas')).toBeVisible({ timeout: 10000 });

  await page.getByRole('link', { name: 'Reproducibility', exact: true }).click();
  await expect(page.getByText('Execution fingerprint', { exact: true })).toBeVisible();
  await expect(page.getByText('Source SHA-256', { exact: true })).toBeVisible();
  await expect(page.getByText('Public function', { exact: true })).toBeVisible();
  await expect(page.getByText('Parameter modes', { exact: true })).toBeVisible();
});
