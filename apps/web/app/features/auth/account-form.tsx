import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PageTitle, ErrorNotice, Loading } from '@/components/patterns';
import { loginOptions, registrationOptions, meOptions } from './queries';
import { ArrowRight } from 'lucide-react';
import { AuthFrame } from './auth-frame';
import { safeReturn } from './safe-return';

export function AccountForm({ registering = false }: { registering?: boolean }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const session = useQuery(meOptions());
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<unknown>();
  const credentials = useRef({ username: '', password: '', display_name: '' });
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
    credentials.current = { username, password, display_name: displayName };
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
        credentials.current = { username: '', password: '', display_name: '' };
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
