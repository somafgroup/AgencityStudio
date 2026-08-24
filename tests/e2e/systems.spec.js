import { test, expect } from '@playwright/test';

const password = 'Playwright-Plan6-Password!42';

function retrySafeEmail(localPart, testInfo) {
  const suffix = testInfo.retry ? `-retry-${testInfo.retry}` : '';
  return `${localPart}${suffix}@example.com`;
}

async function signUp(page, email) {
  await page.goto('/accounts/signup/');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Display name', { exact: true }).fill('System Scientist');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Password confirmation', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
}

async function createProject(page) {
  const navigation = page.getByRole('navigation', { name: 'Primary navigation' });
  await navigation.getByRole('link', { name: 'Projects', exact: true }).click();
  await page.locator('#main-content').getByRole('link', { name: 'New Project', exact: true }).first().click();
  await page.getByLabel(/^Name/).fill('Systems workspace project');
  await page.getByRole('button', { name: 'Create project', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Systems workspace project', exact: true })).toBeVisible();
}

async function openSystems(page) {
  const navigation = page.getByRole('navigation', { name: 'Project navigation' });
  await navigation.getByRole('link', { name: 'Systems', exact: true }).click();
}

async function fillDocumentedSystem(page) {
  await page.getByLabel('Name', { exact: true }).fill('Rotor MTR-04');
  await page.getByLabel('Description', { exact: true }).fill('Rotor identity used across experiments.');
  await page.getByLabel('Documentation status', { exact: true }).selectOption('DOCUMENTED');
  await page.getByLabel('Domain', { exact: true }).fill('mechanics');
  await page.getByLabel('System type', { exact: true }).fill('rotating machine');
  await page.getByLabel('Physical/scientific mechanism', { exact: true }).fill('Rotational oscillation under load');
  await page.getByLabel('Environment', { exact: true }).fill('laboratory');

  await page.getByLabel('Observable name', { exact: true }).first().fill('Rotor angular position');
  await page.getByLabel('Symbol', { exact: true }).first().fill('theta_rotor');
  await page.getByLabel('Unit', { exact: true }).first().fill('rad');
  await page.getByLabel('Observable kind', { exact: true }).first().fill('angle');
  await page.getByLabel('Measurement nature', { exact: true }).first().selectOption('MEASUREMENT');
  await page.getByLabel('Measurement / simulation source', { exact: true }).first().fill('Encoder ENC-04');
  await page.getByLabel('Primary observable', { exact: true }).first().check();

  await page.getByLabel('A_ref value', { exact: true }).fill('1.2');
  await page.getByLabel('A_ref unit', { exact: true }).fill('rad');
  await page.getByLabel('A_ref origin', { exact: true }).selectOption('CALIBRATION');
  await page.getByLabel('A_ref source detail', { exact: true }).fill('CAL-2026-014');
  await page.getByLabel('A_ref justification', { exact: true }).fill('Reference amplitude from calibration.');

  await page.getByLabel('tau value', { exact: true }).fill('0.8');
  await page.getByLabel('tau unit', { exact: true }).fill('s');
  await page.getByLabel('tau origin', { exact: true }).selectOption('CALIBRATION');
  await page.getByLabel('tau source detail / mechanism', { exact: true }).fill('Mechanical relaxation measurement');
  await page.getByLabel('tau justification', { exact: true }).fill('Measured structural relaxation timescale.');

  await page.getByLabel('Memory window w', { exact: true }).selectOption('EXPLICIT');
  await page.getByLabel('w value', { exact: true }).fill('0.8');
  await page.getByLabel('w unit', { exact: true }).fill('s');
  await page.getByLabel('w origin', { exact: true }).selectOption('CONVENTION');
  await page.getByLabel('w source detail', { exact: true }).fill('Explicit baseline');
  await page.getByLabel('w justification', { exact: true }).fill('Explicit CRM memory window for the reference configuration.');

  await page.getByLabel('P_c value', { exact: true }).fill('250');
  await page.getByLabel('P_c unit', { exact: true }).fill('W');
  await page.getByLabel('P_c origin', { exact: true }).selectOption('MANUFACTURER');
  await page.getByLabel('P_c source detail', { exact: true }).fill('MTR-04 datasheet');
  await page.getByLabel('P_c justification', { exact: true }).fill('Characteristic motor power from manufacturer specification.');

  await page.getByLabel('Reference title', { exact: true }).first().fill('Calibration report');
  await page.getByLabel('Citation', { exact: true }).first().fill('CAL-2026-014');
  await page.getByLabel('Supports A_ref', { exact: true }).first().check();
  await page.getByLabel('Supports tau', { exact: true }).first().check();
}

async function createSystem(page) {
  await openSystems(page);
  await page.getByRole('link', { name: 'Define System', exact: true }).first().click();
  await fillDocumentedSystem(page);
  await page.getByRole('button', { name: 'Review', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Review scientific context', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Create system', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Rotor MTR-04', exact: true })).toBeVisible();
}

test('scientist defines an explicit documented System without signal-derived defaults', async ({ page }, testInfo) => {
  await signUp(page, retrySafeEmail('system-owner', testInfo));
  await createProject(page);
  await createSystem(page);

  await expect(page.getByText('1.2 rad', { exact: true })).toBeVisible();
  await expect(page.getByText('0.8 s', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('250 W', { exact: true })).toBeVisible();
  await expect(page.getByText('Rotor angular position', { exact: true })).toBeVisible();
  await expect(page.getByText('Documented', { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/not sampling interval dt/i)).toBeVisible();
  await expect(page.getByText('Configuration fingerprint', { exact: true })).toBeVisible();
});

test('new scientific revision changes tau while Revision 1 remains immutable', async ({ page }, testInfo) => {
  await signUp(page, retrySafeEmail('system-revision-owner', testInfo));
  await createProject(page);
  await createSystem(page);

  await page.getByRole('link', { name: 'Revise scientific context', exact: true }).click();
  await page.getByLabel('tau value', { exact: true }).fill('1.1');
  await page.getByLabel('Reason for this revision', { exact: true }).fill('Updated after calibration CAL-2026-022.');
  await page.getByRole('button', { name: 'Review', exact: true }).click();
  await page.getByRole('button', { name: 'Create new revision', exact: true }).click();

  await expect(page.getByText('Revision 2', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('1.1 s', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Revision 1', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Revision 1', exact: true })).toBeVisible();
  await expect(page.getByText('0.8 s', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('This scientific snapshot is immutable.', { exact: true })).toBeVisible();
});
