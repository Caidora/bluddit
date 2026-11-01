import { Link, Navigate, useNavigate, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useAccount } from '@/components/session';
import { PageTitle, ErrorNotice, Loading } from '@/components/patterns';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { ApiError } from '@/lib/http';
import { accountOptions } from './queries';
import { AccountControls } from './account-controls';

export function AccountDetails() {
  const actor = useAccount();
  const navigate = useNavigate();
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
  if (!query.data)
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
      <button
        type="button"
        className="mb-5 inline-block text-sm text-primary"
        onClick={() => navigate(-1)}
      >
        ← Membership
      </button>
      <PageTitle
        description={
          target.battletag ??
          (target.username
            ? `u/${target.battletag ?? target.username ?? target.id}`
            : `Account #${target.id}`)
        }
      >
        {target.display_name}
      </PageTitle>
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
      {query.isError && (
        <ErrorNotice
          error={query.error}
          retry={() => {
            void query.refetch();
          }}
        />
      )}
      <AccountControls key={id} target={target} />
    </>
  );
}
