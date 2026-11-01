import { useRef, useState, type FormEvent } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ErrorNotice, Loading, PageTitle } from '@/components/patterns';
import { AuthFrame } from './auth-frame';
import { registrationContextOptions, registrationOptions } from './queries';

export function RegistrationComplete() {
  const context = useQuery(registrationContextOptions());
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const input = useRef({ display_name: '' });
  const register = useMutation(registrationOptions(() => input.current));
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmed || !displayName.trim() || register.isPending) return;
    input.current = { display_name: displayName };
    register.mutate(undefined, {
      onSuccess: () => navigate('/pending-approval', { replace: true }),
    });
  }
  return (
    <AuthFrame>
      <PageTitle description="Choose the name your guild knows you by.">
        Request membership
      </PageTitle>
      {context.isPending ? (
        <Loading label="Checking Battle.net sign-in…" />
      ) : context.isError ? (
        <>
          <ErrorNotice
            error={context.error}
            retry={() => {
              void context.refetch();
            }}
          />
          <Button asChild>
            <Link to="/register">Sign in with Battle.net again</Link>
          </Button>
        </>
      ) : (
        <>
          <p className="mb-5 text-sm">
            Signed in as <strong>{context.data.battletag}</strong>.
          </p>
          {register.isError && <ErrorNotice error={register.error} />}
          <form className="space-y-5" onSubmit={submit}>
            <div className="space-y-2">
              <Label htmlFor="display-name">Display name</Label>
              <Input
                id="display-name"
                autoComplete="nickname"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
                maxLength={100}
              />
            </div>
            <label className="flex items-start gap-3 text-sm">
              <input
                className="mt-1 size-4 shrink-0"
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
                required
              />
              I am requesting a new Bluddit account. I do not have an existing account to migrate.
            </label>
            <Button
              type="submit"
              className="w-full rounded-full"
              disabled={!confirmed || register.isPending}
            >
              {register.isPending ? 'Please wait…' : 'Request membership'}
            </Button>
          </form>
          <Button asChild variant="link" className="mt-4">
            <Link to="/login?migrate=1">Migrate existing account instead</Link>
          </Button>
        </>
      )}
    </AuthFrame>
  );
}
