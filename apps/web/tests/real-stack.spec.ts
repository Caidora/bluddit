import { test, expect } from '@playwright/test';
import { login } from './fixtures';

test('real Battle.net registration → GM approval → login, refresh, and logout', async ({
  page,
  browser,
}) => {
  test.skip(
    !process.env.TEST_DATABASE_URL,
    'Set TEST_DATABASE_URL for the disposable real API fixture; make verify and CI require it.'
  );
  await page.goto('/register');
  await page.getByRole('button', { name: 'Continue with Battle.net', exact: true }).click();
  await page.getByRole('button', { name: 'Authorize Browser Member' }).click();
  await page.getByLabel('Display name', { exact: true }).fill('Browser Member');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Request membership' }).click();
  await expect(page.getByRole('heading', { name: 'Awaiting approval' })).toBeVisible();
  await login(page, 'browser_member', 'browser-only-password');
  await expect(page.getByRole('heading', { name: 'Awaiting approval' })).toBeVisible();
  const adminContext = await browser.newContext();
  const admin = await adminContext.newPage();
  try {
    await login(admin, 'browser_gm', 'browser-only-password');
    await expect(admin.getByRole('heading', { name: 'Welcome, Browser GM' })).toBeVisible();
    await admin.getByRole('link', { name: 'Membership', exact: true }).click();
    await admin.getByRole('link', { name: 'Review BrowserMember#1234' }).click();
    await admin.getByRole('button', { name: 'Approve membership' }).click();
    await expect(admin.getByRole('button', { name: 'Deactivate account' })).toBeVisible();
    await login(page, 'browser_member', 'browser-only-password');
    await expect(page.getByRole('heading', { name: 'Welcome, Browser Member' })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Welcome, Browser Member' })).toBeVisible();
    // The handbook starts empty; officers author all policy content themselves.
    await admin.goto('/handbook');
    await expect(admin.getByRole('heading', { name: 'No handbook sections yet' })).toBeVisible();
    await admin.getByRole('button', { name: 'Add section' }).click();
    await admin.getByLabel('URL slug').fill('browser-policy');
    await admin.getByLabel('Title', { exact: true }).fill('Browser policy');
    await admin.getByLabel('Section text').fill('Synthetic browser policy text');
    await admin.getByRole('button', { name: 'Create section', exact: true }).click();
    await expect(admin.getByRole('heading', { name: 'Browser policy' })).toBeVisible();
    await admin.getByRole('button', { name: 'Edit section' }).click();
    await admin.getByLabel('Section text').fill('Updated synthetic policy');
    await admin.getByRole('button', { name: 'Save revision' }).click();
    await expect(admin.getByRole('status')).toContainText('Revision saved.');
    await admin.getByRole('button', { name: 'View revisions' }).click();
    await admin.locator('summary').filter({ hasText: 'Revision 1:' }).click();
    await expect(admin.getByRole('region', { name: 'Revision history' })).toContainText(
      'Synthetic browser policy text'
    );
    await page.goto('/handbook/browser-policy');
    await expect(page.getByRole('article')).toHaveText('Updated synthetic policy');
    await expect(page.getByRole('button', { name: 'Edit section' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Delete section' })).toHaveCount(0);
    await admin.getByRole('button', { name: 'Delete section' }).click();
    await admin.getByRole('button', { name: 'Permanently delete' }).click();
    await expect(admin).toHaveURL(/\/handbook$/);
    await expect(admin.getByRole('heading', { name: 'No handbook sections yet' })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('alert')).toContainText('Handbook section not found');
    // Bluds use the real reference endpoint and persist through a page reload.
    await page.goto('/bluds');
    await page.getByRole('button', { name: 'Add Blud' }).click();
    await page.getByLabel('Character name', { exact: true }).fill('Browserfrost');
    await page.getByLabel('Class', { exact: true }).selectOption('mage');
    await page.getByLabel('Character creation date').fill('2026-10-28');
    await page.getByRole('button', { name: 'Create Blud' }).click();
    await expect(page.getByRole('heading', { name: 'Browserfrost', exact: true })).toBeVisible();
    await page.getByRole('region', { name: 'Dungeon progress' }).locator('summary').click();
    await page.getByLabel('Ragefire Chasm status', { exact: true }).selectOption('completed_rerun');
    await page.getByRole('button', { name: 'Save Ragefire Chasm status', exact: true }).click();
    await expect(page.getByText('1/35 dungeons completed', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Edit professions' }).click();
    await page.getByRole('checkbox', { name: 'Mining', exact: true }).check();
    await page.getByLabel('Mining level', { exact: true }).fill('75');
    await page.getByRole('button', { name: 'Save professions' }).click();
    await expect(page.getByRole('region', { name: 'Professions', exact: true })).toContainText(
      'Mining · 75'
    );
    await page.reload();
    await expect(page.getByText('1/35 dungeons completed', { exact: true })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Professions', exact: true })).toContainText(
      'Mining · 75'
    );
    // Events persist member scheduling and officer-only organizer assignments.
    await page.goto('/events/new');
    await page.getByLabel('Title', { exact: true }).fill('Browser member event');
    await page
      .getByRole('combobox', { name: 'Scheduling timezone', exact: true })
      .selectOption('Australia/Perth');
    await page.getByLabel('Local start date and time').fill('2090-11-01T19:00');
    await page.getByRole('button', { name: 'Create event', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Browser member event' })).toBeVisible();
    const eventPath = new URL(page.url()).pathname;
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Browser member event' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Organizer assignments' })).toHaveCount(0);
    await admin.goto(eventPath);
    await admin.getByRole('checkbox', { name: 'Browser GM (browser_gm)' }).check();
    await admin.getByRole('button', { name: 'Save organizers' }).click();
    await expect(admin.getByRole('region', { name: 'Event details' })).toContainText('Browser GM');
    await page.reload();
    await expect(page.getByRole('region', { name: 'Event details' })).toContainText('Browser GM');
    await page.getByRole('link', { name: 'Edit event', exact: true }).click();
    await page.getByLabel('Title', { exact: true }).fill('Updated member event');
    await page.getByRole('button', { name: 'Save event', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Updated member event' })).toBeVisible();
    await page.getByRole('button', { name: 'Cancel event', exact: true }).click();
    await page.getByRole('button', { name: 'Confirm cancellation' }).click();
    await expect(
      page.getByRole('region', { name: 'Event details' }).getByText('Cancelled', { exact: true })
    ).toBeVisible();
    await page.getByRole('link', { name: 'Log out', exact: true }).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Log in', exact: true })).toBeVisible();
  } finally {
    await adminContext.close();
  }
});

test('real legacy migration keeps the existing account and requires Battle.net', async ({
  page,
}) => {
  test.skip(!process.env.TEST_DATABASE_URL, 'Requires disposable PostgreSQL fixture');
  await page.goto('/login?migrate=1');
  await page.getByLabel('Username', { exact: true }).fill('browser_legacy');
  await page.getByLabel('Password', { exact: true }).fill('browser-only-password');
  await page.getByRole('button', { name: 'Verify existing account', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Connect Battle.net' })).toBeVisible();
  await page.getByRole('link', { name: 'Connect Battle.net', exact: true }).click();
  await page.getByRole('button', { name: 'Authorize Browser Legacy' }).click();
  await expect(page.getByRole('heading', { name: 'Welcome, Browser Legacy' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Welcome, Browser Legacy' })).toBeVisible();
});
