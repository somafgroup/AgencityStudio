import { test, expect } from '@playwright/test';

const password = 'Playwright-Plan13-Password!42';

function retrySafeEmail(localPart, testInfo) {
  const suffix = testInfo.retry ? `-retry-${testInfo.retry}` : '';
  return `${localPart}${suffix}@example.com`;
}

async function signUp(page, email) {
  await page.goto('/accounts/signup/');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Display name', { exact: true }).fill('Research Field Scientist');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Password confirmation', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
}

async function createProject(page) {
  const primary = page.getByRole('navigation', { name: 'Primary navigation' });
  await primary.getByRole('link', { name: 'Projects', exact: true }).click();
  await page.locator('#main-content').getByRole('link', { name: 'New Project', exact: true }).first().click();
  await page.getByLabel(/^Name/).fill('Plan 13 research field project');
  await page.getByRole('button', { name: 'Create project', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Plan 13 research field project', exact: true })).toBeVisible();
}

test('Plan 13 autonomous RESEARCH field executes through the real worker with exact provenance', async ({ page }, testInfo) => {
  await signUp(page, retrySafeEmail('plan13-research-owner', testInfo));
  await createProject(page);

  const projectNav = page.getByRole('navigation', { name: 'Project navigation' });
  await projectNav.getByRole('link', { name: 'Analyses', exact: true }).click();
  await expect(page.getByText('Scientific hierarchy', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'New Research Field', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'New Research Field', exact: true })).toBeVisible();
  await expect(page.getByText('AgencityLab 1.2.0 capability audit', { exact: true })).toBeVisible();
  await expect(page.getByText('UNAVAILABLE', { exact: true })).toBeVisible();
  await expect(page.getByText(/does not simulate gravity/)).toBeVisible();
  await page.getByLabel('Analysis name', { exact: true }).fill('Plan 13 autonomous wall evolution');
  await page.getByRole('button', { name: 'Continue to Research configuration', exact: true }).click();

  await expect(page.getByText('beta_obs(x,t) ≠ phi(x,t)', { exact: true })).toBeVisible();
  await expect(page.locator('label[for="id_model"]')).toContainText('Autonomous field model');
  await expect(page.locator('label[for="id_generated_shape"]')).toContainText('Generated grid shape');
  await page.locator('select[name="model"]').selectOption('KLEIN_GORDON');
  await page.locator('select[name="initial_mode"]').selectOption('DOMAIN_WALL');
  await page.locator('select[name="initial_velocity_mode"]').selectOption('ZERO');
  await page.locator('input[name="generated_shape"]').fill('17');
  await page.locator('input[name="generated_spacings"]').fill('0.25');
  await page.locator('input[name="generated_origins"]').fill('-2.0');
  await page.locator('input[name="domain_wall_center"]').fill('0');
  await page.locator('select[name="domain_wall_orientation"]').selectOption('1');
  await page.locator('input[name="lambda_"]').fill('1');
  await page.locator('input[name="lambda_origin"]').fill('AgencityLab dimensionless benchmark fixture');
  await page.locator('input[name="mu"]').fill('1');
  await page.locator('input[name="mu_origin"]').fill('AgencityLab dimensionless benchmark fixture');
  await page.locator('select[name="units_convention"]').selectOption('dimensionless');
  await page.locator('select[name="boundary_kind"]').selectOption('DIRICHLET');
  await page.locator('input[name="boundary_value_real"]').fill('0');
  await page.locator('input[name="boundary_value_imag"]').fill('0');
  await page.locator('input[name="dt_solver"]').fill('0.01');
  await page.locator('input[name="n_steps"]').fill('4');
  await page.getByRole('button', { name: 'Continue to Review', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Research Field Review', exact: true })).toBeVisible();
  await expect(page.getByText('RESEARCH FIELD STUDY', { exact: true })).toBeVisible();
  await expect(page.getByText('agencitylab.fields.simulate_klein_gordon', { exact: true })).toBeVisible();
  await expect(page.getByText(/dt_solver is not tau/)).toBeVisible();
  await expect(page.getByText(/Successful numerical execution confirms software execution/)).toBeVisible();
  await page.getByRole('button', { name: 'Run RESEARCH Field', exact: true }).click();

  const liveStatus = page.locator('[aria-live="polite"]').first();
  await expect(liveStatus.getByText('COMPLETED', { exact: true })).toBeVisible({ timeout: 30000 });
  await page.reload();
  await expect(page.getByRole('link', { name: 'Explore Research field', exact: true })).toBeVisible();
  await expect(page.getByText('USER_SELECTED_EXPLICIT_ZERO')).toBeVisible();
  await expect(page.getByText('Research result artifact', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Explore Research field', exact: true }).click();

  await expect(page.getByText('ADVANCED AGENCITY FIELD EXTENSION', { exact: true })).toBeVisible();
  await expect(page.getByText(/Autonomous phi\(x,t\) research dynamics/)).toBeVisible();
  await expect(page.locator('[data-research-point]')).toContainText('phi', { timeout: 10000 });

  await page.getByRole('link', { name: 'Field State', exact: true }).click();
  await expect(page.getByLabel('Complex display', { exact: true })).toBeVisible();
  await expect(page.locator('[data-research-field-chart] canvas').first()).toBeVisible({ timeout: 10000 });
  await expect(page.locator('[data-research-trace-chart] canvas').first()).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(/arg\(phi\) is a display representation/)).toBeVisible();

  await page.getByRole('link', { name: 'Reproducibility', exact: true }).click();
  await expect(page.getByText('Execution fingerprint:', { exact: true })).toBeVisible();
  await expect(page.getByText('Initial condition SHA-256:', { exact: true })).toBeVisible();
  await expect(page.getByText('Public function:', { exact: true })).toBeVisible();
  await expect(page.getByText('agencitylab.fields.simulate_klein_gordon', { exact: true })).toBeVisible();
  await expect(page.getByText(/does not constitute experimental validation/)).toBeVisible();
});
