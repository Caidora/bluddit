import { Link, Navigate, useSearchParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useAccount } from '@/components/session';
import { PageTitle, ErrorNotice, Loading, EmptyState } from '@/components/patterns';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select';
import { ApiError } from '@/lib/http';
import { accountsOptions } from './queries';
import type { MembershipState } from './types';

export function AccountList() {
  const actor = useAccount();
  const [params, setParams] = useSearchParams();
  const state = params.get('state') ?? 'pending';
  const membershipState = ['pending', 'active', 'rejected', 'inactive'].includes(state)
    ? (state as MembershipState)
    : undefined;
  const requestedOffset = Number(params.get('offset'));
  const offset =
    Number.isSafeInteger(requestedOffset) && requestedOffset >= 0 ? requestedOffset : 0;
  const query = useQuery(
    accountsOptions(actor.id, { membership_state: membershipState, offset, limit: 20 })
  );
  if (query.error instanceof ApiError && query.error.status === 403)
    return <Navigate to="/unauthorized" replace />;
  return (
    <>
      <PageTitle description="Review applications and manage access to your guild.">
        Membership
      </PageTitle>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Label htmlFor="membership-state">Membership state</Label>
        <NativeSelect
          id="membership-state"
          value={membershipState ?? 'all'}
          onChange={(event) => setParams({ state: event.target.value })}
        >
          <NativeSelectOption value="all">All accounts</NativeSelectOption>
          {['pending', 'active', 'rejected', 'inactive'].map((value) => (
            <NativeSelectOption key={value} value={value}>
              {value[0].toUpperCase() + value.slice(1)}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </div>
      {query.isPending ? (
        <Loading label="Loading accounts…" />
      ) : query.isError ? (
        <ErrorNotice
          error={query.error}
          retry={() => {
            void query.refetch();
          }}
        />
      ) : (
        <>
          {query.data.accounts.length ? (
            <div className="space-y-3">
              {query.data.accounts.map((account) => (
                <Card key={account.id}>
                  <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
                    <div className="min-w-0 flex-1">
                      <Link
                        to={`/admin/accounts/${account.id}`}
                        className="block break-words font-semibold hover:text-primary"
                      >
                        {account.display_name}
                      </Link>
                      <p className="break-all text-sm text-muted-foreground">
                        {account.battletag ??
                          (account.username ? `u/${account.username}` : `Account #${account.id}`)}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="secondary">{account.role_name.replaceAll('_', ' ')}</Badge>
                      <Badge variant="outline">{account.membership_state}</Badge>
                      <Button asChild variant="outline" size="sm">
                        <Link to={`/admin/accounts/${account.id}`}>
                          Review
                          <span className="sr-only">
                            {' '}
                            {account.battletag ?? account.username ?? account.display_name}
                          </span>
                        </Link>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState title="No accounts here">
              No accounts match this membership state.
            </EmptyState>
          )}
          <nav aria-label="Account pages" className="mt-6 flex items-center justify-between gap-2">
            <Button
              variant="outline"
              disabled={offset === 0 || query.isFetching}
              onClick={() => setParams({ state, offset: String(Math.max(0, offset - 20)) })}
            >
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              Page {Math.floor(offset / 20) + 1}
            </span>
            <Button
              variant="outline"
              disabled={query.data.accounts.length < 20 || query.isFetching}
              onClick={() => setParams({ state, offset: String(offset + 20) })}
            >
              Next
            </Button>
          </nav>
        </>
      )}
    </>
  );
}
