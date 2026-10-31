import { index, layout, route, type RouteConfig } from '@react-router/dev/routes';

export default [
  index('routes/entry.tsx'),
  ...['login', 'register', 'pending-approval', 'logout', 'unauthorized'].map((path) =>
    route(path, 'routes/auth.tsx', { id: path })
  ),
  layout('components/session.tsx', [
    layout('components/shell.tsx', [
      ...['home', 'roster', 'gear', 'events', 'crafting', 'handbook'].map((path) =>
        route(path, 'routes/home.tsx', { id: path })
      ),
      layout('routes/membership-gate.tsx', [
        route('admin/accounts', 'routes/accounts.tsx', { id: 'accounts' }),
        route('admin/accounts/:accountId', 'routes/accounts.tsx', { id: 'account' }),
      ]),
      layout('routes/policy-gate.tsx', [route('admin/permissions', 'routes/permissions.tsx')]),
    ]),
  ]),
  route('*', 'routes/auth.tsx', { id: 'not-found' }),
] satisfies RouteConfig;
