import { signIn } from "./auth-helper";
import { test, expect } from '@playwright/test';

test('failed registry never masquerades as an empty fleet and can recover', async ({ page }) => {
  await page.route('**/api/agents', route => route.abort('connectionfailed'));
  await page.goto('/app/agents');
  await signIn(page);
  await expect(page.getByRole('heading', { name: 'Unable to load agents' })).toBeVisible();
  await expect(page.getByText('No agents found', { exact: true })).toHaveCount(0);
  await page.unroute('**/api/agents');
  await page.getByRole('button', { name: 'Retry connection' }).click();
  await expect(page.getByRole('heading', { name: 'Unable to load agents' })).toHaveCount(0);
});

test('failed incident query does not claim there is no incident', async ({ page }) => {
  await page.route('**/api/incidents', route => route.abort('connectionfailed'));
  await page.goto('/app');
  await signIn(page);
  await expect(page.getByRole('heading', { name: 'Operational data unavailable' })).toBeVisible();
  await expect(page.getByText('NO ACTIVE INCIDENT', { exact: true })).toHaveCount(0);
});
