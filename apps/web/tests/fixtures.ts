import { expect, type BrowserContext, type Page } from '@playwright/test';
import type { Account, AccountAction, Role } from '../app/features/accounts/types';
import type { CurrentAccount } from '../app/features/auth/types';

export const member: CurrentAccount = {
  id: 1,
  username: 'river',
  display_name: 'River',
  membership_state: 'active',
  role_name: 'member',
  timezone: null,
  permissions: ['guild.read', 'bluds.view', 'bluds.edit_own', 'events.create', 'events.manage'],
};
export const applicant: Account = {
  ...member,
  id: 2,
  username: 'fern',
  display_name: 'Fern',
  membership_state: 'pending',
};
export function officer(role: Role = 'officer'): CurrentAccount {
  return {
    ...member,
    role_name: role,
    permissions: [
      'guild.read',
      'bluds.view',
      'bluds.edit_own',
      'events.create',
      'events.manage',
      'accounts.manage',
      'policy.read',
      'handbook.edit',
      ...(role === 'guild_master' ? ['handbook.delete'] : []),
      'shared_records.correct',
    ],
  };
}
export async function mockApi(context: BrowserContext, initial: CurrentAccount | null = null) {
  const state = {
    account: initial,
    target: { ...applicant },
    tokenCount: 0,
    actionCount: 0,
    meCount: 0,
    failLogout: false,
    registerError: 0,
    actionError: 0,
    authError: false,
    requests: [] as { path: string; method: string; body: unknown }[],
  };
  await context.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const body = request.postDataJSON();
    state.requests.push({ path, method, body });
    const reply = (status: number, json?: unknown) =>
      route.fulfill({
        status,
        ...(status === 204 ? {} : { json: json ?? { detail: 'Test failure' } }),
      });
    if (method !== 'GET') expect(request.headers()['x-csrf-protection']).toBe('1');
    if (path === '/api/auth/register') {
      if (state.registerError)
        return reply(state.registerError, {
          detail: state.registerError === 409 ? 'Username unavailable' : 'Try again later',
        });
      return reply(201, state.target);
    }
    if (path === '/api/auth/login') {
      expect(Object.keys(body).sort()).toEqual(['password', 'username']);
      if (state.authError) return reply(401, { detail: 'Invalid username or password' });
      state.account ??= member;
      return reply(200, { access_token: 'access-login', expires_in: 600, token_type: 'Bearer' });
    }
    if (path === '/api/auth/token' && method === 'DELETE') {
      if (state.failLogout) return reply(503, { detail: 'Database unavailable' });
      state.account = null;
      return reply(204);
    }
    if (path === '/api/auth/token') {
      state.tokenCount++;
      return state.account
        ? reply(200, {
            access_token: `access-${state.tokenCount}`,
            expires_in: 600,
            token_type: 'Bearer',
          })
        : reply(401);
    }
    if (path === '/api/auth/me') {
      state.meCount++;
      return reply(state.account ? 200 : 401, state.account);
    }
    if (path === '/api/events') return reply(200, { events: [], offset: 0, limit: 25, has_more: false });
    if (path === '/api/accounts') {
      if (!state.account?.permissions.includes('accounts.manage')) return reply(403);
      return reply(200, {
        accounts: [state.target],
        offset: Number(url.searchParams.get('offset')),
        limit: Number(url.searchParams.get('limit')),
      });
    }
    if (path === '/api/permissions')
      return reply(200, {
        permissions: ['guild.read', 'accounts.manage', 'handbook.delete'],
        roles: {
          member: ['guild.read'],
          officer: ['guild.read', 'accounts.manage'],
          guild_master: ['guild.read', 'accounts.manage', 'handbook.delete'],
        },
      });
    if (path === '/api/accounts/2' && method === 'GET') return reply(200, state.target);
    if (path.startsWith('/api/accounts/2/')) {
      state.actionCount++;
      if (state.actionError)
        return reply(state.actionError, { detail: 'Account update conflicts with current state' });
      const action = path.split('/').at(-1) as AccountAction;
      if (action === 'approve' || action === 'activate') state.target.membership_state = 'active';
      if (action === 'reject') state.target.membership_state = 'rejected';
      if (action === 'deactivate') state.target.membership_state = 'inactive';
      if (action === 'promote-to-officer') state.target.role_name = 'officer';
      if (action === 'demote-to-member') state.target.role_name = 'member';
      if (action === 'pass-guild-master') {
        state.target.role_name = 'guild_master';
        state.account = officer();
      }
      return reply(200, state.target);
    }
    return reply(404);
  });
  return state;
}
export async function login(page: Page, username = 'river', password = 'valid-password') {
  await page.goto('/login');
  await page.getByLabel('Username', { exact: true }).fill(username);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Log in', exact: true }).click();
}
export async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}
