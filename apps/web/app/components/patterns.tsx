import { useEffect, useRef, type ReactNode } from 'react';
import { useLocation } from 'react-router';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';
import { ApiError } from '@/lib/api';
import { CircleAlert, Orbit } from 'lucide-react';

export function PageTitle({
  children,
  description,
}: {
  children: ReactNode;
  description?: string;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const location = useLocation();
  useEffect(() => {
    heading.current?.focus();
    document.title = `${heading.current?.textContent} · Bluddit`;
  }, [location.pathname, children]);
  return (
    <div className="mb-6 space-y-2">
      <h1 ref={heading} tabIndex={-1} className="text-2xl font-bold outline-none sm:text-3xl">
        {children}
      </h1>
      {description && (
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">{description}</p>
      )}
    </div>
  );
}
export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="space-y-4 p-6">
      <span className="text-sm text-muted-foreground">{label}</span>
      <Skeleton className="h-8 w-2/3" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}
export function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  const text = error instanceof Error ? error.message : 'Something went wrong. Please try again.';
  return (
    <Alert variant="destructive" role="alert" className="my-4 break-words">
      <CircleAlert />
      <AlertTitle>Couldn’t complete that</AlertTitle>
      <AlertDescription>
        <p>{text}</p>
        {error instanceof ApiError && error.status === 429 && (
          <p>
            Please wait{error.retryAfter ? ` ${error.retryAfter} seconds` : ' a little'} before
            trying again.
          </p>
        )}
        {retry && (
          <Button variant="outline" size="sm" onClick={retry}>
            Try again
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}
export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-start gap-4 py-10">
        <div className="rounded-full bg-muted p-3">
          <Orbit className="size-6 text-primary" />
        </div>
        <h2 className="text-lg font-semibold">{title}</h2>
        <div className="max-w-xl text-sm leading-relaxed text-muted-foreground">{children}</div>
      </CardContent>
    </Card>
  );
}
export function Brand() {
  return (
    <span className="text-2xl font-extrabold tracking-tight text-primary">
      bluddit<span className="text-foreground">.</span>
    </span>
  );
}
