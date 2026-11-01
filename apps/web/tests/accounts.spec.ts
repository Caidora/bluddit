import { test, expect } from '@playwright/test';
import { mockApi, member, officer, login, noOverflow } from './fixtures';

test('entry, registration, validation preservation, and pending guidance', async ({
  page,
  context,
}) => {
  const state = await mockApi(context);
  await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
  await page.getByRole('link', { name: 'Create an account' }).click();
  await page.getByRole('button', { name: 'Continue with Battle.net', exact: true }).click();
  await page.getByLabel('Display name', { exact: true }).fill('Fern');
  await page.getByRole('checkbox').check();
  state.registerError = 409;
  await page.getByRole('button', { name: 'Request membership' }).click();
  await expect(page.getByRole('alert')).toContainText('Battle.net account already linked');
  await expect(page.getByLabel('Display name', { exact: true })).toHaveValue('Fern');
  state.registerError = 429;
  await page.getByRole('button', { name: 'Request membership' }).click();
  await expect(page.getByRole('alert')).toContainText('Please wait');
  state.registerError = 0;
  await page.getByRole('button', { name: 'Request membership' }).click();
  await expect(page.getByRole('heading', { name: 'Awaiting approval' })).toBeVisible();
  expect(state.requests.filter((r) => r.path === '/api/auth/login')).toHaveLength(0);
});

test('login errors stay generic, preserve inputs, and reject external return URLs', async ({
  page,
  context,
}) => {
  const state = await mockApi(context);
  state.authError = true;
  await page.goto('/login?returnTo=https://example.com');
  await page.getByRole('button', { name: 'Migrate existing account', exact: true }).click();
  await page.getByLabel('Username', { exact: true }).fill('river');
  await page.getByLabel('Password', { exact: true }).fill('valid-password');
  await page.getByRole('button', { name: 'Verify existing account', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Invalid username or password');
  await expect(page.getByLabel('Password', { exact: true })).toHaveValue('valid-password');
  state.authError = false;
  await page.getByRole('button', { name: 'Verify existing account', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Connect Battle.net' })).toBeVisible();
  await page.getByRole('link', { name: 'Connect Battle.net', exact: true }).click();
  await expect(page).toHaveURL(/\/home$/);
});

test('protected deep link returns after login; reload preserves session', async ({
  page,
  context,
}) => {
  const state = await mockApi(context);
  await page.goto('/events');
  await expect(page).toHaveURL(/\/login\?returnTo=/);
  await page.getByRole('button', { name: 'Continue with Battle.net', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Events', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Events', exact: true })).toBeVisible();
  expect(state.tokenCount).toBeGreaterThan(2);
  await expect(page.getByRole('link', { name: 'Membership', exact: true })).toHaveCount(0);
  await page.goto('/admin/accounts');
  await expect(page.getByRole('heading', { name: 'Access restricted' })).toBeVisible();
});

test('officer approval refetches records; role controls stay GM only', async ({
  page,
  context,
}) => {
  const state = await mockApi(context, officer());
  await page.goto('/admin/accounts');
  await page.getByRole('link', { name: 'Review fern' }).click();
  await expect(page.getByRole('button', { name: 'Promote to Officer' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Approve membership' }).click();
  await expect(page.getByRole('button', { name: 'Deactivate account' })).toBeVisible();
  expect(state.actionCount).toBe(1);
  await page.getByRole('button', { name: 'Deactivate account' }).click();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  expect(state.actionCount).toBe(1);
  state.actionError = 409;
  await page.getByRole('button', { name: 'Deactivate account' }).click();
  await page.getByRole('button', { name: 'Confirm', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('conflicts');
  await expect(page.getByRole('button', { name: 'Deactivate account' })).toBeEnabled();
  expect(
    state.requests.filter((r) => r.path === '/api/accounts/2' && r.method === 'GET').length
  ).toBeGreaterThanOrEqual(3);
  await page.getByRole('link', { name: 'Permissions', exact: true }).click();
  await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByText('This view is read-only.', { exact: false })).toBeVisible();
});

test('GM succession confirms consequences and immediately removes GM controls', async ({
  page,
  context,
}) => {
  const state = await mockApi(context, officer('guild_master'));
  state.target.membership_state = 'active';
  await page.goto('/admin/accounts/2');
  await page.getByRole('button', { name: 'Pass Guild Master' }).click();
  await expect(page.getByRole('alertdialog')).toContainText('You will become an Officer');
  await page.getByRole('button', { name: 'Confirm', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Pass Guild Master' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Demote to Member' })).toHaveCount(0);
  expect(state.account?.role_name).toBe('officer');
});

test('live capability changes gate previously accessible routes', async ({ page, context }) => {
  const state = await mockApi(context, officer());
  await page.goto('/admin/accounts');
  await expect(page.getByRole('link', { name: 'Review fern' })).toBeVisible();
  state.account = member;
  await page.getByRole('link', { name: 'Home', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Membership', exact: true })).toHaveCount(0);
  await page.goto('/admin/accounts');
  await expect(page.getByRole('heading', { name: 'Access restricted' })).toBeVisible();
});

for (const width of [320, 375]) {
  test(`mobile ${width}px forms, navigation, membership, and policy do not overflow`, async ({
    page,
    context,
  }) => {
    await page.setViewportSize({ width, height: 812 });
    const state = await mockApi(context);
    await page.goto('/register');
    await expect(page.getByRole('heading', { name: 'Join Bluds' })).toBeVisible();
    await noOverflow(page);
    state.account = officer();
    await page.goto('/home');
    await page.getByRole('button', { name: 'Toggle navigation' }).click();
    await page.getByRole('link', { name: 'Membership', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Review fern' })).toBeVisible();
    await noOverflow(page);
    await page.goto('/admin/permissions');
    await expect(page.getByRole('table')).toBeVisible();
    await noOverflow(page);
  });
}

test('keyboard can open navigation and use a confirmation dialog', async ({ page, context }) => {
  await mockApi(context, officer());
  await page.goto('/admin/accounts/2');
  await page.getByRole('button', { name: 'Reject application' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('alertdialog')).toHaveCount(0);
});

test('failed logout clears local access, notifies tabs, and permits server retry', async ({
  page,
  context,
}) => {
  const state = await mockApi(context, member);
  await page.goto('/home');
  await expect(page.getByRole('heading', { name: 'Welcome, River' })).toBeVisible();
  const other = await context.newPage();
  await other.goto('/events');
  await expect(other.getByRole('heading', { name: 'Events', exact: true })).toBeVisible();
  state.failLogout = true;
  await page.getByRole('link', { name: 'Log out', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Database unavailable');
  await expect(other).toHaveURL(/\/login/);
  expect(
    await other.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage } }))
  ).toEqual({ local: {}, session: {} });
  state.failLogout = false;
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test('outages recover without rendering protected content or redirecting to login', async ({
  page,
  context,
}) => {
  let failing = true;
  await mockApi(context, member);
  await page.route('**/api/auth/token', async (route) => {
    if (failing) return route.fulfill({ status: 503, json: { detail: 'Database unavailable' } });
    return route.fallback();
  });
  await page.goto('/events');
  await expect(page.getByRole('alert')).toContainText('Database unavailable');
  await expect(page).toHaveURL(/\/events$/);
  failing = false;
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Events', exact: true })).toBeVisible();
});

test('unknown route has a useful not-found screen', async ({ page, context }) => {
  await mockApi(context);
  await page.goto('/missing-page');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
});

test('return navigation rejects protocol-relative and control-character URLs', async ({
  page,
  context,
}) => {
  await mockApi(context);
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: 'Log in', exact: true })).toBeVisible();
  const results = await page.evaluate(async (path) => {
    const { safeReturn } = await import(path);
    return [
      '//example.com',
      '/\\example.com',
      '/\n/example.com',
      '/logout',
      '/LoGoUt/',
      '/register/',
      '/%6cogout',
      '/events/../logout',
      '/%E0%A4%A',
      '/events?view=upcoming',
    ].map(safeReturn);
  }, '/app/features/auth/safe-return.ts');
  expect(results).toEqual([
    '/home',
    '/home',
    '/home',
    '/home',
    '/home',
    '/home',
    '/home',
    '/home',
    '/home',
    '/events?view=upcoming',
  ]);
});

for (const [path, heading] of [
  ['/login/', 'Log in'],
  ['/REGISTER/', 'Join Bluds'],
  ['/pending-approval/', 'Awaiting approval'],
  ['/unauthorized/', 'Access restricted'],
] as const) {
  test(`router renders the matched auth screen at ${path}`, async ({ page, context }) => {
    await mockApi(context);
    await page.goto(path);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    if (heading === 'Join Bluds') {
      await expect(
        page.getByRole('button', { name: 'Continue with Battle.net', exact: true })
      ).toBeVisible();
      await expect(page.getByLabel('Password', { exact: true })).toHaveCount(0);
    }
  });
}

test('trailing slash logout ends the session and member routes keep their identity', async ({
  page,
  context,
}) => {
  const state = await mockApi(context, member);
  await page.goto('/EVENTS/');
  await expect(page.getByRole('heading', { name: 'Events', exact: true })).toBeVisible();
  await page.goto('/logout/');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('heading', { name: 'Log in', exact: true })).toBeVisible();
  expect(state.account).toBeNull();
});

for (const width of [320, 1280]) {
  test(`Battle.net signup and migration work with keyboard at ${width}px`, async ({
    page,
    context,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockApi(context);
    await page.goto('/login');
    await expect(
      page.getByRole('button', { name: 'Continue with Battle.net', exact: true })
    ).toBeEnabled();
    await noOverflow(page);
    await page.screenshot({
      path: `../../docs/screenshots/issue55/login-${width}.png`,
      fullPage: true,
    });
    const migration = page.getByRole('button', { name: 'Migrate existing account', exact: true });
    await migration.focus();
    await page.keyboard.press('Enter');
    await page.getByLabel('Username', { exact: true }).fill('river');
    await page.getByLabel('Password', { exact: true }).fill('synthetic-password');
    await page.getByRole('button', { name: 'Verify existing account', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Connect Battle.net', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Log out', exact: true })).toHaveCount(0);
    await noOverflow(page);
    await page.screenshot({
      path: `../../docs/screenshots/issue55/migration-${width}.png`,
      fullPage: true,
    });
    await page.goto('/register/complete');
    await page.getByLabel('Display name', { exact: true }).fill('Fern');
    await expect(
      page.getByRole('button', { name: 'Request membership', exact: true })
    ).toBeDisabled();
    await page.getByRole('checkbox').focus();
    await page.keyboard.press('Space');
    await expect(
      page.getByRole('button', { name: 'Request membership', exact: true })
    ).toBeEnabled();
    await noOverflow(page);
    await page.screenshot({
      path: `../../docs/screenshots/issue55/signup-${width}.png`,
      fullPage: true,
    });
  });
}
