import { Navigate } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useAccount } from '@/components/session';
import { PageTitle, ErrorNotice, Loading } from '@/components/patterns';
import { ApiError } from '@/lib/http';
import { policyOptions } from './queries';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';

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
            The Guild Master has all Officer permissions and can also delete handbook sections.
            Only the current GM can promote or demote roles and pass leadership. Resource ownership and assignments further
            restrict actions.
          </p>
        </>
      )}
    </>
  );
}
