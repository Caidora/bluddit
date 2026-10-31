import { useState } from 'react';
import { Link, Navigate, useParams, useSearchParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAccount } from '@/components/session';
import { PageTitle, ErrorNotice, Loading, EmptyState } from '@/components/patterns';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from '@/components/ui/alert-dialog';
import {
  accountsOptions,
  accountOptions,
  accountActionOptions,
  policyOptions,
} from '@/lib/queries';
import { ApiError, type Account, type AccountAction, type MembershipState } from '@/lib/api';

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
                        u/{account.username}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="secondary">{account.role_name.replaceAll('_', ' ')}</Badge>
                      <Badge variant="outline">{account.membership_state}</Badge>
                      <Button asChild variant="outline" size="sm">
                        <Link to={`/admin/accounts/${account.id}`}>
                          Review<span className="sr-only"> {account.username}</span>
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
const actionLabels: Record<AccountAction, string> = {
  approve: 'Approve membership',
  reject: 'Reject application',
  deactivate: 'Deactivate account',
  activate: 'Activate account',
  'promote-to-officer': 'Promote to Officer',
  'demote-to-member': 'Demote to Member',
  'pass-guild-master': 'Pass Guild Master',
};
function AccountControls({ target }: { target: Account }) {
  const actor = useAccount();
  const client = useQueryClient();
  const mutation = useMutation(accountActionOptions(client, actor.id, target.id));
  const [confirmation, setConfirmation] = useState<AccountAction | null>(null);
  const [completed, setCompleted] = useState('');
  const actions: AccountAction[] = [];
  if (target.role_name !== 'guild_master') {
    if (target.membership_state === 'pending') actions.push('approve', 'reject');
    else if (target.membership_state === 'active') actions.push('deactivate');
    else actions.push('activate');
    if (actor.role_name === 'guild_master' && actor.id !== target.id) {
      if (target.role_name === 'member') actions.push('promote-to-officer');
      if (target.role_name === 'officer') actions.push('demote-to-member');
      if (target.membership_state === 'active') actions.push('pass-guild-master');
    }
  }
  function act(action: AccountAction) {
    setCompleted('');
    mutation.mutate(action, {
      onSuccess: () => setCompleted(`${actionLabels[action]} completed.`),
    });
  }
  return (
    <div className="mt-6">
      <h2 className="mb-3 text-lg font-semibold">Account actions</h2>
      {target.role_name === 'guild_master' && (
        <p className="text-sm text-muted-foreground">
          The Guild Master is protected. Only the current GM can pass the role to another active
          account.
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        {actions.map((action) => (
          <Button
            key={action}
            variant={action === 'approve' || action === 'activate' ? 'default' : 'outline'}
            disabled={mutation.isPending}
            onClick={() =>
              action === 'approve' || action === 'activate' ? act(action) : setConfirmation(action)
            }
          >
            {actionLabels[action]}
          </Button>
        ))}
      </div>
      {mutation.isPending && (
        <p role="status" className="mt-3 text-sm">
          Updating and refreshing account…
        </p>
      )}
      {completed && (
        <p role="status" className="mt-3 text-sm text-primary">
          {completed}
        </p>
      )}
      {mutation.isError && <ErrorNotice error={mutation.error} />}
      <AlertDialog
        open={confirmation !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmation(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmation && actionLabels[confirmation]}?</AlertDialogTitle>
            <AlertDialogDescription>
              {confirmation === 'pass-guild-master'
                ? `Transfer leadership to ${target.display_name}? You will become an Officer and lose GM-only controls.`
                : `This will change access for ${target.display_name} (${target.username}). Confirm that this is the intended account.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (confirmation) act(confirmation);
                setConfirmation(null);
              }}
            >
              Confirm
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
export function AccountDetails() {
  const actor = useAccount();
  const { accountId } = useParams();
  const id = Number(accountId);
  const query = useQuery({
    ...accountOptions(actor.id, id),
    enabled: Number.isSafeInteger(id) && id > 0,
  });
  if (!Number.isSafeInteger(id) || id <= 0)
    return (
      <>
        <PageTitle>Account not found</PageTitle>
        <Link to="/admin/accounts">Back to membership</Link>
      </>
    );
  if (query.error instanceof ApiError && query.error.status === 403)
    return <Navigate to="/unauthorized" replace />;
  if (query.isPending) return <Loading label="Loading account…" />;
  if (query.isError)
    return (
      <ErrorNotice
        error={query.error}
        retry={() => {
          void query.refetch();
        }}
      />
    );
  const target = query.data;
  return (
    <>
      <Link className="mb-5 inline-block text-sm text-primary" to="/admin/accounts">
        ← Membership
      </Link>
      <PageTitle description={`u/${target.username}`}>{target.display_name}</PageTitle>
      <Card>
        <CardContent className="p-5">
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-5 gap-y-3 text-sm">
            <dt className="text-muted-foreground">Membership</dt>
            <dd>
              <Badge variant="outline">{target.membership_state}</Badge>
            </dd>
            <dt className="text-muted-foreground">Role</dt>
            <dd className="break-words">{target.role_name.replaceAll('_', ' ')}</dd>
            <dt className="text-muted-foreground">Timezone</dt>
            <dd className="break-words">{target.timezone ?? 'Not set'}</dd>
          </dl>
        </CardContent>
      </Card>
      <AccountControls key={id} target={target} />
    </>
  );
}
export function Permissions() {
  const actor = useAccount();
  const query = useQuery(policyOptions(actor.id));
  if (query.error instanceof ApiError && query.error.status === 403)
    return <Navigate to="/unauthorized" replace />;
  return (
    <>
      <PageTitle description="Permissions are fixed in application code. This view is read-only.">
        Permissions
      </PageTitle>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorNotice
          error={query.error}
          retry={() => {
            void query.refetch();
          }}
        />
      ) : (
        <>
          <Table className="table-fixed text-xs sm:text-sm">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[43%]">Permission</TableHead>
                <TableHead>Member</TableHead>
                <TableHead>Officer</TableHead>
                <TableHead>GM</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {query.data.permissions.map((permission) => (
                <TableRow key={permission}>
                  <TableCell className="whitespace-normal break-all font-mono">
                    {permission}
                  </TableCell>
                  {(['member', 'officer', 'guild_master'] as const).map((role) => (
                    <TableCell key={role}>
                      <span
                        aria-label={
                          query.data.roles[role].includes(permission) ? 'Allowed' : 'Not allowed'
                        }
                      >
                        {query.data.roles[role].includes(permission) ? '✓' : '—'}
                      </span>
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="mt-5 text-sm leading-relaxed text-muted-foreground">
            Officers and the Guild Master share the same permission set. Only the current GM can
            promote or demote roles and pass leadership. Resource ownership and assignments further
            restrict actions.
          </p>
        </>
      )}
    </>
  );
}
export default function AccountsRoute() {
  const { accountId } = useParams();
  return accountId ? <AccountDetails /> : <AccountList />;
}
