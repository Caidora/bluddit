import { test, expect } from '@playwright/test';
import { mockApi, member, officer } from './fixtures';

test('concurrent expired requests share one refresh and retry at most once', async ({
  page,
  context,
}) => {
  const state = await mockApi(context, member);
  await page.goto('/home');
  await expect(page.getByRole('heading', { name: 'Welcome, River' })).toBeVisible();
  const before = state.tokenCount;
  let failures = 0;
  await page.route('**/api/accounts/2', async (route) => {
    if (route.request().headers().authorization === 'Bearer access-1') {
      failures++;
      return route.fulfill({ status: 401, json: { detail: 'Authentication required' } });
    }
    return route.fallback();
  });
  const ids = await page.evaluate(async (path) => {
    const { api } = await import(path);
    return Promise.all([api.account(2), api.account(2)]).then((accounts) =>
      accounts.map((account) => account.id)
    );
  }, '/app/lib/api.ts');
  expect(ids).toEqual([2, 2]);
  expect(failures).toBe(2);
  expect(state.tokenCount - before).toBe(1);
});

test('permanent 401 performs bounded refresh/request retries and requires login', async ({
  page,
  context,
}) => {
  const state = await mockApi(context, member);
  await page.goto('/home');
  await expect(page.getByRole('heading', { name: 'Welcome, River' })).toBeVisible();
  let attempts = 0;
  await page.route('**/api/accounts/2', (route) => {
    attempts++;
    return route.fulfill({ status: 401, json: { detail: 'Authentication required' } });
  });
  await page.evaluate(async (path) => {
    const { api } = await import(path);
    try {
      await api.account(2);
    } catch {
      /* expected denied request */
    }
  }, '/app/lib/api.ts');
  await expect(page).toHaveURL(/\/login/);
  expect(attempts).toBe(2);
  expect(state.tokenCount).toBe(2);
});

test('session loss clears query data and credential mutations cache no secrets', async ({
  page,
  context,
}) => {
  await mockApi(context, officer());
  await page.goto('/home');
  await expect(page.getByRole('heading', { name: 'Welcome, River' })).toBeVisible();
  const result = await page.evaluate(
    async (paths) => {
      const { api } = await import(paths.api);
      const queries = await import(paths.queries);
      const client = queries.createQueryClient();
      const disconnect = queries.connectSession(client);
      await client.fetchQuery(queries.meOptions());
      await client.fetchQuery(queries.accountsOptions(1, { limit: 20, offset: 0 }));
      const mutation = client.getMutationCache().build(
        client,
        queries.loginOptions(() => ({ username: 'river', password: 'never-cache-this-password' }))
      );
      await mutation.execute(undefined);
      const mutationState = JSON.stringify(mutation.state);
      await api.logout();
      const protectedQueries = client.getQueryCache().findAll({ queryKey: ['member'] }).length;
      const currentAccount = client.getQueryData(queries.keys.me);
      disconnect();
      client.clear();
      return { mutationState, protectedQueries, currentAccount };
    },
    { api: '/app/lib/api.ts', queries: '/app/lib/queries.ts' }
  );
  expect(result.mutationState).not.toContain('never-cache-this-password');
  expect(result.mutationState).not.toContain('access_token');
  expect(result.protectedQueries).toBe(0);
  expect(result.currentAccount).toBeNull();
});

test('late protected response cannot restore data after logout', async ({ page, context }) => {
  await mockApi(context, officer());
  let release!: () => void;
  let requested!: () => void;
  const received = new Promise<void>((resolve) => {
    requested = resolve;
  });
  const response = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/api/accounts?**', async (route) => {
    requested();
    await response;
    await route
      .fulfill({
        json: {
          accounts: [
            {
              id: 2,
              display_name: 'Private old identity',
              username: 'private',
              role_name: 'member',
              membership_state: 'pending',
            },
          ],
          limit: 20,
          offset: 0,
        },
      })
      .catch(() => {});
  });
  await page.goto('/admin/accounts');
  await received;
  await page.getByRole('link', { name: 'Log out', exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  release();
  await expect(page.getByText('Private old identity')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Log in', exact: true })).toBeVisible();
});

test('two tabs serialize refresh requests through the same Web Lock', async ({ context }) => {
  const state = await mockApi(context, member);
  let inflight = 0;
  let peak = 0;
  await context.route('**/api/auth/token', async (route) => {
    inflight++;
    peak = Math.max(peak, inflight);
    await new Promise((resolve) => setTimeout(resolve, 80));
    inflight--;
    await route.fallback();
  });
  const a = await context.newPage();
  const b = await context.newPage();
  await Promise.all([a.goto('/home'), b.goto('/home')]);
  await expect(a.getByRole('heading', { name: 'Welcome, River' })).toBeVisible();
  await expect(b.getByRole('heading', { name: 'Welcome, River' })).toBeVisible();
  expect(peak).toBe(1);
  expect(state.tokenCount).toBeLessThanOrEqual(2);
});

test('account pagination and filter are encoded centrally', async ({ page, context }) => {
  await mockApi(context, officer());
  const searches: string[] = [];
  await page.route('**/api/accounts?**', (route) => {
    const url = new URL(route.request().url());
    searches.push(url.search);
    const offset = Number(url.searchParams.get('offset'));
    return route.fulfill({
      json: {
        accounts: offset
          ? []
          : Array.from({ length: 20 }, (_, i) => ({
              id: i + 2,
              display_name: `Applicant ${i}`,
              username: `applicant_${i}`,
              role_name: 'member',
              membership_state: 'pending',
            })),
        limit: 20,
        offset,
      },
    });
  });
  await page.goto('/admin/accounts');
  await expect(page.getByRole('button', { name: 'Next', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByText('No accounts here')).toBeVisible();
  expect(searches.some((search) => search.includes('offset=20'))).toBe(true);
  await page.getByLabel('Membership state', { exact: true }).selectOption('active');
  await expect.poll(() => searches.at(-1)).toContain('membership_state=active');
  expect(searches.at(-1)).toContain('offset=0');
});
