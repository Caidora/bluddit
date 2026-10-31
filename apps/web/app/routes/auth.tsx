import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Brand, PageTitle, ErrorNotice, Loading } from '@/components/patterns';
import { loginOptions, registrationOptions, logoutOptions, meOptions } from '@/lib/queries';
import { ArrowRight, CheckCircle2 } from 'lucide-react';

export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-svh">
      <header className="flex h-20 items-center justify-between border-b px-5 sm:px-10">
        <Link to="/" aria-label="Bluddit home">
          <Brand />
        </Link>
        <Badge variant="outline">Bluds guild</Badge>
      </header>
      <main
        id="main-content"
        className="mx-auto grid max-w-5xl items-center gap-10 px-4 py-10 md:min-h-[calc(100svh-5rem)] md:grid-cols-2 md:gap-16 md:px-8"
      >
        <aside className="hidden space-y-6 md:block">
          <Badge variant="secondary">AU · NZ · PERTH</Badge>
          <h2 className="text-5xl font-bold leading-tight">
            Good company.
            <br />
            <span className="text-primary">Shared progress.</span>
          </h2>
          <p className="max-w-sm leading-relaxed text-muted-foreground">
            A home for Bluds. Dungeons, raids, and helping each other along the way.
          </p>
          <p className="text-sm text-muted-foreground">Progress together. Keep it friendly.</p>
        </aside>
        <Card className="w-full min-w-0 rounded-2xl">
          <CardContent className="p-6 sm:p-8">{children}</CardContent>
          <CardFooter className="justify-center border-t px-6 py-4 text-xs text-muted-foreground">
            A relaxed guild. A shared adventure.
          </CardFooter>
        </Card>
      </main>
    </div>
  );
}
export function safeReturn(value: string | null) {
  if (
    !value ||
    !value.startsWith('/') ||
    value.startsWith('//') ||
    /[\\\u0000-\u0020\u007f]/.test(value)
  )
    return '/home';
  const path = value.split(/[?#]/)[0];
  if (['/', '/login', '/register', '/logout', '/pending-approval'].includes(path)) return '/home';
  return value;
}
export function AccountForm() {
  const location = useLocation();
  const registering = location.pathname === '/register';
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const session = useQuery(meOptions());
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<unknown>();
  const credentials = useRef({ username, password, display_name: displayName });
  credentials.current = { username, password, display_name: displayName };
  const login = useMutation(loginOptions(() => credentials.current));
  const register = useMutation(registrationOptions(() => credentials.current));
  const mutation = registering ? register : login;
  useEffect(() => {
    setError(undefined);
    setPassword('');
    return () => {
      credentials.current = { username: '', password: '', display_name: '' };
    };
  }, [registering]);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    // HTML constraints handle field validation without discarding entered values.
    if (registering && !displayName.trim()) {
      setError(new Error('Display name is required.'));
      return;
    }
    const callbacks = {
      onSuccess: () => {
        setPassword('');
        credentials.current.password = '';
        navigate(registering ? '/pending-approval' : safeReturn(params.get('returnTo')), {
          replace: true,
        });
      },
      onError: (failure: unknown) => setError(failure),
      onSettled: () => {
        login.reset();
        register.reset();
      },
    };
    if (registering) register.mutate(undefined, callbacks);
    else login.mutate(undefined, callbacks);
  }
  if (session.isPending)
    return (
      <AuthFrame>
        <Loading label="Checking your session…" />
      </AuthFrame>
    );
  if (session.data) return <Navigate to={safeReturn(params.get('returnTo'))} replace />;
  return (
    <AuthFrame>
      <PageTitle
        description={
          registering
            ? 'Create an account. An officer will approve your membership before you can log in.'
            : 'Welcome back. Your guild is right here.'
        }
      >
        {registering ? 'Join Bluds' : 'Log in'}
      </PageTitle>
      {session.isError && (
        <ErrorNotice
          error={session.error}
          retry={() => {
            void session.refetch();
          }}
        />
      )}
      {error != null && <ErrorNotice error={error} />}
      <form
        onSubmit={submit}
        className="space-y-5"
        aria-label={registering ? 'Registration' : 'Login'}
      >
        {registering && (
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
        )}
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
            aria-describedby="username-help"
          />
          <p id="username-help" className="text-xs text-muted-foreground">
            3–32 letters, numbers, or underscores.
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete={registering ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={registering ? 12 : 1}
            maxLength={128}
            aria-describedby={registering ? 'password-help' : undefined}
          />
          {registering && (
            <p id="password-help" className="text-xs text-muted-foreground">
              Use 12–128 characters.
            </p>
          )}
        </div>
        <Button type="submit" className="h-11 w-full rounded-full" disabled={mutation.isPending}>
          {mutation.isPending ? 'Please wait…' : registering ? 'Request membership' : 'Log in'}
          <ArrowRight />
        </Button>
      </form>
      <p className="mt-6 text-sm text-muted-foreground">
        {registering ? 'Already registered? ' : 'New to Bluds? '}
        <Link
          className="font-medium text-primary underline-offset-4 hover:underline"
          to={registering ? '/login' : '/register'}
        >
          {registering ? 'Log in' : 'Create an account'}
        </Link>
      </p>
      {!registering && (
        <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
          Waiting for approval or need a password reset? Contact a guild officer.
        </p>
      )}
    </AuthFrame>
  );
}
export function PendingApproval() {
  return (
    <AuthFrame>
      <CheckCircle2 className="mb-6 size-10 text-primary" />
      <PageTitle description="An officer needs to approve your account before you can log in. Contact a guild officer if you need help.">
        Awaiting approval
      </PageTitle>
      <p className="mb-6 text-sm text-muted-foreground">
        After approval, use the username and password you registered with.
      </p>
      <Button asChild className="w-full rounded-full">
        <Link to="/login">Back to login</Link>
      </Button>
    </AuthFrame>
  );
}
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
export function Unauthorized() {
  return (
    <AuthFrame>
      <PageTitle description="Your account does not have permission to open this page.">
        Access restricted
      </PageTitle>
      <Button asChild>
        <Link to="/home">Back to home</Link>
      </Button>
    </AuthFrame>
  );
}
export function NotFound() {
  return (
    <AuthFrame>
      <PageTitle description="This page could not be found.">Page not found</PageTitle>
      <Button asChild>
        <Link to="/">Back to Bluddit</Link>
      </Button>
    </AuthFrame>
  );
}
export default function AuthRoute() {
  const { pathname } = useLocation();
  if (pathname === '/pending-approval') return <PendingApproval />;
  if (pathname === '/logout') return <Logout />;
  if (pathname === '/unauthorized') return <Unauthorized />;
  if (pathname === '/login' || pathname === '/register') return <AccountForm />;
  return <NotFound />;
}
