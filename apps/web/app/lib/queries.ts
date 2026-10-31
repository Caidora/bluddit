import { QueryClient, mutationOptions, queryOptions } from '@tanstack/react-query';
import {
  api,
  ApiError,
  type AccountFilter,
  type AccountAction,
  type Credentials,
  type Registration,
  type CurrentAccount,
} from './api';

export const keys = {
  me: ['auth', 'me'] as const,
  member: (id: number) => ['member', id] as const,
  accounts: (id: number, filter: AccountFilter) => ['member', id, 'accounts', filter] as const,
  account: (id: number, target: number) => ['member', id, 'account', target] as const,
  policy: (id: number) => ['member', id, 'permissions'] as const,
};
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 0,
        retry: (count, error) =>
          count < 1 && error instanceof ApiError && (error.status === 0 || error.status >= 500),
        refetchOnWindowFocus: true,
      },
      mutations: { retry: false, gcTime: 0 },
    },
  });
}
export function connectSession(client: QueryClient) {
  return api.subscribe(({ account }) => {
    const previous = client.getQueryData<CurrentAccount | null>(keys.me);
    // Cancel before removal: stale responses must not restore protected data.
    if (!account || previous?.id !== account.id) {
      void client.cancelQueries({ queryKey: ['member'] });
      client.removeQueries({ queryKey: ['member'] });
    }
    void client.cancelQueries({ queryKey: keys.me });
    client.setQueryData(keys.me, account);
  });
}
export const meOptions = () =>
  queryOptions({ queryKey: keys.me, queryFn: ({ signal }) => api.me(signal) });
export const accountsOptions = (actor: number, filter: AccountFilter) =>
  queryOptions({
    queryKey: keys.accounts(actor, filter),
    queryFn: ({ signal }) => api.accounts(filter, signal),
  });
export const accountOptions = (actor: number, id: number) =>
  queryOptions({
    queryKey: keys.account(actor, id),
    queryFn: ({ signal }) => api.account(id, signal),
  });
export const policyOptions = (actor: number) =>
  queryOptions({
    queryKey: keys.policy(actor),
    queryFn: ({ signal }) => api.permissions(signal),
  });
// Read credentials at execution time; they never become mutation variables/data.
export const loginOptions = (read: () => Credentials) =>
  mutationOptions({ mutationFn: () => api.login(read()) });
export const registrationOptions = (read: () => Registration) =>
  mutationOptions({ mutationFn: () => api.register(read()) });
export const logoutOptions = () => mutationOptions({ mutationFn: () => api.logout() });
export const accountActionOptions = (client: QueryClient, actor: number, id: number) =>
  mutationOptions({
    mutationFn: (action: AccountAction) => api.accountAction(id, action),
    onSettled: async () => {
      // Failed writes may still have committed membership before session revocation.
      await Promise.all([
        client.invalidateQueries({ queryKey: keys.member(actor) }),
        client.invalidateQueries({ queryKey: keys.me }),
      ]);
    },
  });
