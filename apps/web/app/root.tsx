import { Links, Meta, Outlet, Scripts, ScrollRestoration } from 'react-router';
import type { ReactNode } from 'react';
import './styles.css';
import { Providers } from './components/session';
import { TooltipProvider } from './components/ui/tooltip';

export function Layout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
        >
          Skip to content
        </a>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export function HydrateFallback() {
  return (
    <main id="main-content" data-bluddit-shell>
      <noscript>Enable JavaScript to use Bluddit.</noscript>
    </main>
  );
}

export default function App() {
  return (
    <Providers>
      <TooltipProvider>
        <Outlet />
      </TooltipProvider>
    </Providers>
  );
}
