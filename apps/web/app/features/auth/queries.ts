import { mutationOptions, queryOptions, type QueryClient } from '@tanstack/react-query';
import { memberKeys } from '@/lib/query-client';
import { sessionApi } from './session';
import type { Credentials, Registration, CurrentAccount } from './types';

export const authKeys = { me: ['auth', 'me'] as const };

export function connectSession(client: QueryClient) {
  return sessionApi.subscribe(({ account }) => {
    const previous = client.getQueryData<CurrentAccount | null>(authKeys.me);
    // Cancel before removal: stale responses must not restore protected data.
    if (!account || previous?.id !== account.id) {
      void client.cancelQueries({ queryKey: memberKeys.all });
      client.removeQueries({ queryKey: memberKeys.all });
    }
    void client.cancelQueries({ queryKey: authKeys.me });
    client.setQueryData(authKeys.me, account);
  });
}
export const meOptions = () =>
  queryOptions({ queryKey: authKeys.me, queryFn: ({ signal }) => sessionApi.me(signal) });
// Read credentials at execution time; they never become mutation variables/data.
export const loginOptions = (read: () => Credentials, returnTo = '/home') =>
  mutationOptions({ mutationFn: () => sessionApi.login(read(), returnTo) });
export const battleNetOptions = () =>
  mutationOptions({
    mutationFn: (returnTo: string) => sessionApi.startBattleNet(returnTo),
  });
export const registrationContextOptions = () =>
  queryOptions({
    queryKey: ['auth', 'registration'],
    queryFn: ({ signal }) => sessionApi.registrationContext(signal),
    gcTime: 0,
  });
export const completionOptions = () =>
  queryOptions({
    queryKey: ['auth', 'completion'],
    queryFn: async () => {
      await sessionApi.completeOAuth();
      return true;
    },
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  });
export const registrationOptions = (read: () => Registration) =>
  mutationOptions({ mutationFn: () => sessionApi.register(read()) });
export const logoutOptions = () => mutationOptions({ mutationFn: () => sessionApi.logout() });
