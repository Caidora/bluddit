import { mutationOptions, queryOptions, type QueryClient } from '@tanstack/react-query';
import { authKeys } from '@/features/auth/queries';
import { accountsApi } from './api';
import type { AccountFilter, AccountAction } from './types';

export const accountKeys = {
  lists: (actor: number) => ['member', actor, 'accounts', 'list'] as const,
  list: (actor: number, filter: AccountFilter) => [...accountKeys.lists(actor), filter] as const,
  detail: (actor: number, id: number) => ['member', actor, 'accounts', 'detail', id] as const,
};

export const accountsOptions = (actor: number, filter: AccountFilter) =>
  queryOptions({
    queryKey: accountKeys.list(actor, filter),
    queryFn: ({ signal }) => accountsApi.accounts(filter, signal),
  });
export const accountOptions = (actor: number, id: number) =>
  queryOptions({
    queryKey: accountKeys.detail(actor, id),
    queryFn: ({ signal }) => accountsApi.account(id, signal),
  });
export const accountActionOptions = (client: QueryClient, actor: number, id: number) =>
  mutationOptions({
    mutationFn: (action: AccountAction) => accountsApi.accountAction(id, action),
    onSettled: async () => {
      // Failed writes may still have committed membership before session revocation.
      await Promise.all([
        client.invalidateQueries({ queryKey: accountKeys.lists(actor) }),
        client.invalidateQueries({ queryKey: accountKeys.detail(actor, id) }),
        client.invalidateQueries({ queryKey: authKeys.me }),
      ]);
    },
  });
