import { useQuery } from '@tanstack/react-query';
import { Link, Navigate, useSearchParams } from 'react-router';
import { Button } from '@/components/ui/button';
import { ErrorNotice, Loading } from '@/components/patterns';
import { AuthFrame } from './auth-frame';
import { completionOptions } from './queries';
import { safeReturn } from './safe-return';

export function OAuthComplete() {
  const [params] = useSearchParams();
  const completion = useQuery(completionOptions());
  if (completion.isPending)
    return (
      <AuthFrame>
        <Loading label="Completing sign-in…" />
      </AuthFrame>
    );
  if (completion.isError)
    return (
      <AuthFrame>
        <ErrorNotice
          error={completion.error}
          retry={() => {
            void completion.refetch();
          }}
        />
        <Button asChild variant="link">
          <Link to="/login">Start sign-in again</Link>
        </Button>
      </AuthFrame>
    );
  return <Navigate to={safeReturn(params.get('returnTo'))} replace />;
}
