import { index, layout, route, type RouteConfig } from '@react-router/dev/routes';

export default [
  index('routes/entry.tsx'),
  route('login', 'routes/login.tsx'),
  route('register', 'routes/register.tsx'),
  route('pending-approval', 'routes/pending-approval.tsx'),
  route('logout', 'routes/logout.tsx'),
  route('unauthorized', 'routes/unauthorized.tsx'),
  layout('components/session.tsx', [
    layout('components/shell.tsx', [
      ...['home', 'roster', 'gear', 'events', 'crafting', 'handbook'].map((path) =>
        route(path, `routes/${path}.tsx`)
      ),
      layout('routes/membership-gate.tsx', [
        route('admin/accounts', 'routes/accounts.tsx'),
        route('admin/accounts/:accountId', 'routes/account.tsx'),
      ]),
      layout('routes/policy-gate.tsx', [route('admin/permissions', 'routes/permissions.tsx')]),
    ]),
  ]),
  route('*', 'routes/not-found.tsx'),
] satisfies RouteConfig;
