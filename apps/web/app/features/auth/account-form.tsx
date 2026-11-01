import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PageTitle, ErrorNotice } from '@/components/patterns';
import { battleNetOptions, loginOptions, meOptions } from './queries';
import { AuthFrame } from './auth-frame';
import { safeReturn } from './safe-return';

const authErrors: Record<string, string> = {
  expired: 'This sign-in attempt expired or was already used. Please start again.',
  cancelled: 'Battle.net sign-in was cancelled. You can try again.',
  provider: 'Battle.net could not complete sign-in. Please try again.',
  link_conflict:
    'The account could not be linked. It may already be linked, or your password changed. Start again or contact a guild officer.',
  membership: 'This account does not have active membership. Contact a guild officer.',
};

export function AccountForm({ registering = false }: { registering?: boolean }) {
  const [params] = useSearchParams();
  const session = useQuery(meOptions());
  const [migrating, setMigrating] = useState(params.get('migrate') === '1');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [authorizationUrl, setAuthorizationUrl] = useState('');
  const [error, setError] = useState<unknown>();
  const credentials = useRef({ username: '', password: '' });
  const returnTo = safeReturn(params.get('returnTo'));
  const login = useMutation(loginOptions(() => credentials.current, returnTo));
  const start = useMutation(battleNetOptions());
  useEffect(
    () => () => {
      credentials.current = { username: '', password: '' };
    },
    []
  );
  useEffect(() => {
    setPassword('');
    setAuthorizationUrl('');
    setError(undefined);
    setMigrating(params.get('migrate') === '1');
  }, [registering, params]);
  const busy = session.isPending || login.isPending || start.isPending;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError(undefined);
    credentials.current = { username, password };
    login.mutate(undefined, {
      onSuccess: (result) => {
        setAuthorizationUrl(result.authorization_url);
        setPassword('');
      },
      onError: setError,
      onSettled: () => {
        credentials.current = { username: '', password: '' };
        login.reset();
      },
    });
  }
  function beginBattleNet() {
    setError(undefined);
    start.mutate(returnTo, {
      onSuccess: (result) => window.location.assign(result.authorization_url),
      onError: setError,
    });
  }
  if (session.data) return <Navigate to={returnTo} replace />;
  return (
    <AuthFrame>
      <PageTitle
        description={
          migrating
            ? 'Keep your membership and Bluds by linking your existing account.'
            : registering
              ? 'Sign in with Battle.net, then request membership. An officer will approve your account.'
              : 'Welcome back. Continue with Battle.net to reach your guild.'
        }
      >
        {migrating ? 'Migrate account' : registering ? 'Join Bluds' : 'Log in'}
      </PageTitle>
      {session.isError && (
        <ErrorNotice
          error={session.error}
          retry={() => {
            void session.refetch();
          }}
        />
      )}
      {authErrors[params.get('authError') ?? ''] && (
        <ErrorNotice error={new Error(authErrors[params.get('authError')!])} />
      )}
      {error != null && <ErrorNotice error={error} />}
      {!migrating && (
        <>
          <Button className="h-11 w-full rounded-full" disabled={busy} onClick={beginBattleNet}>
            {session.isPending
              ? 'Checking session…'
              : start.isPending
                ? 'Please wait…'
                : 'Continue with Battle.net'}
          </Button>
          <p className="mt-4 text-sm text-muted-foreground">
            Already have a username and password? Migrate your existing account first to preserve
            your Bluds and membership.
          </p>
        </>
      )}
      <Button
        variant="link"
        className="mt-2 px-0"
        onClick={() => {
          setMigrating(!migrating);
          setAuthorizationUrl('');
          setPassword('');
        }}
        aria-expanded={migrating}
      >
        {migrating ? 'Back to Battle.net sign-in' : 'Migrate existing account'}
      </Button>
      {migrating &&
        (authorizationUrl ? (
          <div className="mt-4 space-y-4" role="region" aria-label="Connect Battle.net">
            <p>
              Your old credentials are verified. Connect the Battle.net account you want to use for
              future sign-ins.
            </p>
            <Button asChild className="w-full rounded-full">
              <a href={authorizationUrl}>Connect Battle.net</a>
            </Button>
            <p className="text-sm text-muted-foreground">
              Your password will be removed only after linking succeeds.
            </p>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-4 space-y-5" aria-label="Migrate existing account">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                name="username"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={3}
                maxLength={32}
                pattern="[a-zA-Z0-9_]{3,32}"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={1}
                maxLength={128}
              />
            </div>
            <Button type="submit" className="w-full rounded-full" disabled={busy}>
              {login.isPending ? 'Please wait…' : 'Verify existing account'}
            </Button>
            <p className="text-sm text-muted-foreground">
              Need help with your old password? Contact a guild officer. Linked accounts use
              Battle.net account recovery.
            </p>
          </form>
        ))}
      <p className="mt-6 text-sm text-muted-foreground">
        {registering ? 'Already a member? ' : 'New to Bluds? '}
        <Link
          className="font-medium text-primary underline"
          to={registering ? '/login' : '/register'}
        >
          {registering ? 'Log in' : 'Create an account'}
        </Link>
      </p>
    </AuthFrame>
  );
}
