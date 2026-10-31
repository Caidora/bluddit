import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import { useMutation } from '@tanstack/react-query';
import { logoutOptions } from './queries';
import { AuthFrame } from './auth-frame';
import { PageTitle, ErrorNotice, Loading } from '@/components/patterns';

export function Logout() {
  const navigate = useNavigate();
  const mutation = useMutation(logoutOptions());
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    mutation.mutate(undefined, { onSuccess: () => navigate('/login', { replace: true }) });
  }, [mutation.mutate, navigate]);
  return (
    <AuthFrame>
      <PageTitle>Logging out</PageTitle>
      {mutation.isError ? (
        <>
          <p className="text-sm text-muted-foreground">
            This browser has cleared your member data. The server could not confirm session
            revocation; retry to finish logging out.
          </p>
          <ErrorNotice
            error={mutation.error}
            retry={() =>
              mutation.mutate(undefined, { onSuccess: () => navigate('/login', { replace: true }) })
            }
          />
        </>
      ) : (
        <Loading label="Ending your session…" />
      )}
    </AuthFrame>
  );
}
