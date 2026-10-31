import { test, expect } from '@playwright/test';
import { login } from './fixtures';

test('real registration → GM approval → login, refresh, and logout', async ({ page, browser }) => {
  test.skip(
    !process.env.TEST_DATABASE_URL,
    'Set TEST_DATABASE_URL for the disposable real API fixture; make verify and CI require it.'
  );
  await page.goto('/register');
  await page.getByLabel('Display name', { exact: true }).fill('Browser Member');
  await page.getByLabel('Username', { exact: true }).fill('browser_member');
  await page.getByLabel('Password', { exact: true }).fill('browser-only-password');
  await page.getByRole('button', { name: 'Request membership' }).click();
  await expect(page.getByRole('heading', { name: 'Awaiting approval' })).toBeVisible();
  await login(page, 'browser_member', 'browser-only-password');
  await expect(page.getByRole('alert')).toContainText('Invalid username or password');
  const adminContext = await browser.newContext();
  const admin = await adminContext.newPage();
  try {
    await login(admin, 'browser_gm', 'browser-only-password');
    await expect(admin.getByRole('heading', { name: 'Welcome, Browser GM' })).toBeVisible();
    await admin.getByRole('link', { name: 'Membership', exact: true }).click();
    await admin.getByRole('link', { name: 'Review browser_member' }).click();
    await admin.getByRole('button', { name: 'Approve membership' }).click();
    await expect(admin.getByRole('button', { name: 'Deactivate account' })).toBeVisible();
    await login(page, 'browser_member', 'browser-only-password');
    await expect(page.getByRole('heading', { name: 'Welcome, Browser Member' })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Welcome, Browser Member' })).toBeVisible();
    await page.getByRole('link', { name: 'Log out', exact: true }).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Log in', exact: true })).toBeVisible();
  } finally {
    await adminContext.close();
  }
});
