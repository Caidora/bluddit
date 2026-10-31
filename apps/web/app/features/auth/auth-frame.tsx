import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Brand } from '@/components/patterns';

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
