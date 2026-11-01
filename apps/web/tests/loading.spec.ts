import { test, expect } from '@playwright/test';
import { mockApi, officer, noOverflow } from './fixtures';

test('hydration fallback has no loading message', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:4173/home');
  await expect(page.getByText('Loading Bluddit…')).toHaveCount(0);
  await expect(page.locator('main[data-bluddit-shell]')).toHaveCount(1);
  await expect(page.locator('main')).toHaveText(/^(Enable JavaScript to use Bluddit\.)?$/);
  await expect(page.getByRole('status')).toHaveCount(0);
  await context.close();
});

for (const endpoint of ['token', 'me']) {
  test(`shell renders while ${endpoint} is pending and protected requests wait`, async ({
    page,
    context,
  }) => {
    const state = await mockApi(context, officer());
    let release!: () => void;
    const blocked = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route(`**/api/auth/${endpoint}`, async (route) => {
      await blocked;
      await route.fallback();
    });
    try {
      await page.goto('/admin/accounts');
      await expect(page.getByRole('link', { name: 'Bluddit home' })).toBeVisible();
      await expect(page.getByRole('link', { name: 'Events', exact: true })).toBeVisible();
      await expect(page.getByRole('status')).toContainText('Loading your session');
      await expect(page.getByRole('link', { name: 'Membership', exact: true })).toHaveCount(0);
      await expect(page.getByText('River', { exact: true })).toHaveCount(0);
      expect(state.requests.filter((r) => r.path === '/api/accounts')).toHaveLength(0);
      await page.screenshot({ path: test.info().outputPath('session-loading-desktop.png') });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.getByRole('button', { name: 'Toggle navigation' }).click();
      await expect(page.getByRole('link', { name: 'Events', exact: true })).toBeVisible();
      await noOverflow(page);
      await page.getByRole('link', { name: 'Events', exact: true }).click();
      await expect(page).toHaveURL(/\/events$/);
      await expect(page.getByRole('heading', { name: 'Events', exact: true })).toHaveCount(0);
    } finally {
      release();
    }
    await expect(page.getByRole('heading', { name: 'Events', exact: true })).toBeVisible();
    await page.setViewportSize({ width: 1280, height: 900 });
    await expect(page.getByRole('link', { name: 'Membership', exact: true })).toBeVisible();
  });
}

for (const path of ['/login', '/register']) {
  test(`${path} fields render during session check without allowing a premature submit`, async ({
    page,
    context,
  }) => {
    await mockApi(context);
    let release!: () => void;
    const blocked = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route('**/api/auth/token', async (route) => {
      await blocked;
      await route.fallback();
    });
    try {
      await page.goto(path);
      await expect(
        page.getByRole('button', { name: 'Migrate existing account', exact: true })
      ).toBeVisible();
      await expect(page.getByRole('button', { name: 'Checking session…' })).toBeDisabled();
    } finally {
      release();
    }
    await expect(
      page.getByRole('button', {
        name: 'Continue with Battle.net',
        exact: true,
      })
    ).toBeEnabled();
    await expect(page.getByLabel('Password', { exact: true })).toHaveCount(0);
  });
}
