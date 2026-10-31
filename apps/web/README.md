# Bluddit web

React Router framework mode with client rendering (`ssr: false`), React, TypeScript,
TanStack Query, and local shadcn/ui components. The API remains the authority for
membership, permissions, and validation. See the [operations runbook](../../docs/operations.md)
for environment setup, browser requirements, and the full stack.

## Develop and verify

From the repository root:

```sh
npm --prefix apps/web ci
npm --prefix apps/web run dev
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
npm --prefix apps/web test
```

The development server proxies `/api` to `http://127.0.0.1:8000`; configure the API's
allowed origin to match the frontend. Install Chromium once with
`cd apps/web && npx playwright install chromium`.

Browser tests use mocked API responses by default. Set `TEST_DATABASE_URL` to a
disposable PostgreSQL database ending in `_test` to also run the real
registration → approval → login test. Its fixture creates and drops a separate
random database; the test user needs database-creation permission. `make verify`
includes frontend, API, database, infrastructure, and Compose checks.

## Where code belongs

```text
app/
  routes.ts                  URL patterns and layout composition
  routes/                    Thin route modules that select a screen and its props
  features/
    accounts/                Membership list, details, controls, API, query options, types
    auth/                    Account forms, session lifecycle, API contracts, query options
    permissions/             Permission matrix, API, query options, types
  components/                Shared page patterns, shell, session boundary
    ui/                      Local shadcn/ui primitives
  hooks/                     Shared UI hooks
  lib/
    http.ts                  Fetch transport, CSRF headers, ApiError
    query-client.ts          QueryClient defaults and protected-cache namespace
  navigation.ts              Shared member navigation metadata
```

Keep feature-specific components, API calls, types, and query options together.
Import their concrete modules; avoid importing a screen from another route module
or creating broad barrel exports. Shared components should earn their place through
reuse. Keep UI primitives independent of business rules.

React Router chooses the screen. Do not add a second router using exact
`location.pathname` comparisons: the router also accepts trailing slashes and
case-insensitive paths. Login and registration use an explicit form prop; temporary
member pages receive navigation metadata as a prop. Pathname observation in the
session boundary is for session revalidation, not screen selection.

## Server state and cache ownership

Use TanStack Query for server data and mutations. Feature `api.ts` modules own
endpoint paths and contracts; feature `queries.ts` modules own query keys, query
options, and mutation invalidation. Components consume those options rather than
calling `fetch`. `lib/http.ts` owns transport behavior; `features/auth/session.ts`
adds access tokens, refresh/retry coordination, and session lifecycle events.

Create one stable QueryClient per mounted application. Pass each query's AbortSignal
to its API request. Do not duplicate server data in component state or introduce a
second cache through router loaders. If loaders are added for prefetching, they
should use the same QueryClient and feature query options.

Protected keys begin with `['member', actorId, ...]`. Account list keys include
filters and pagination; detail keys include the target ID. An account mutation
invalidates account lists, its target detail, and the current session. It does not
invalidate unrelated features, other account details, or other actors' data. Keep
invalidation local to a mutation's actual effects as new features are added. Use
`onSettled` for account writes because a failed response can follow a committed
membership change. Await invalidation before reporting completion.

The global member prefix is reserved for session cleanup. On logout or identity
change, cancel protected queries before removing their cached data so late
responses cannot restore a previous identity's records. Session events also update
the current-account query. Capability gates and hidden controls improve navigation;
they do not replace API authorization.

## Session errors and local UI state

An initial session check must finish before showing protected content. If it fails
without a cached account, show a retry screen. A temporary background refresh
failure keeps the existing shell and route mounted and shows a retry notice. This
preserves forms and confirmation dialogs; do not treat an outage as logout.
Confirmed session loss clears the cached account, removes protected data, and
redirects to login. Cached permissions can be stale during an outage, so every
write remains subject to API authorization.

Keep form fields and dialog state local. Read and write refs in handlers or effects,
not during render. Account forms snapshot credentials in the submit handler and
provide a reader to the mutation function: passwords are not mutation variables or
cached results. Clear the snapshot after settlement and on unmount; retain field
values after errors so users can retry. Access tokens stay in session-module memory;
there is no persistent query cache or token storage. Web Locks and BroadcastChannel
coordinate refresh and logout across tabs.

## Adding a feature

1. Add its contracts, endpoint functions, query keys/options, and screen under
   `features/<name>/`.
2. Add a thin route module and register it in `routes.ts`. Use route parameters and
   search parameters for resource identity, filters, and pagination.
3. Add navigation and a capability gate where appropriate; enforce permissions in
   the API too.
4. Add behavioral browser coverage for success, errors, and permission boundaries.
   For cache/session changes, cover cancellation, identity changes, and background
   refresh without discarding local state.
