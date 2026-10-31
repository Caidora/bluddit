import { useEffect, useState, type ReactNode } from 'react';
import { QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query';
import { Navigate, Outlet, useLocation, useOutletContext } from 'react-router';
import { createQueryClient, connectSession, meOptions, keys } from '@/lib/queries';
import type { CurrentAccount } from '@/lib/api';
import { ErrorNotice, Loading } from './patterns';

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(createQueryClient);
  useEffect(() => connectSession(client), [client]);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
export function useAccount() {
  return useOutletContext<CurrentAccount>();
}
export function SessionBoundary() {
  const session = useQuery(meOptions());
  const client = useQueryClient();
  const location = useLocation();
  useEffect(() => {
    void client.invalidateQueries({ queryKey: keys.me });
  }, [client, location.pathname]);
  if (session.isPending) return <Loading label="Loading your session…" />;
  if (session.isError)
    return (
      <div className="mx-auto max-w-lg p-6">
        <ErrorNotice
          error={session.error}
          retry={() => {
            void session.refetch();
          }}
        />
      </div>
    );
  if (!session.data)
    return (
      <Navigate
        to={`/login?returnTo=${encodeURIComponent(location.pathname + location.search)}`}
        replace
      />
    );
  return <Outlet context={session.data} />;
}
export function Entry() {
  const session = useQuery(meOptions());
  if (session.isPending) return <Loading label="Loading your session…" />;
  if (session.isError)
    return (
      <div className="mx-auto max-w-lg p-6">
        <ErrorNotice
          error={session.error}
          retry={() => {
            void session.refetch();
          }}
        />
      </div>
    );
  return <Navigate replace to={session.data ? '/home' : '/login'} />;
}
export function CapabilityGate({ permission }: { permission: string }) {
  const account = useAccount();
  return account.permissions.includes(permission) ? (
    <Outlet context={account} />
  ) : (
    <Navigate replace to="/unauthorized" />
  );
}
export default SessionBoundary;
