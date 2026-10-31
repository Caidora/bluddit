import { authenticated } from '@/features/auth/session';
import type { Account, AccountAction, AccountFilter, AccountPage } from './types';

export const accountsApi = {
  accounts(filter: AccountFilter, signal?: AbortSignal) {
    const params = new URLSearchParams({
      limit: String(filter.limit),
      offset: String(filter.offset),
    });
    if (filter.membership_state) params.set('membership_state', filter.membership_state);
    return authenticated<AccountPage>(`/api/accounts?${params}`, { signal });
  },
  account(id: number, signal?: AbortSignal) {
    return authenticated<Account>(`/api/accounts/${id}`, { signal });
  },
  accountAction(id: number, action: AccountAction) {
    return authenticated<Account>(`/api/accounts/${id}/${action}`, { method: 'POST' });
  },
};
