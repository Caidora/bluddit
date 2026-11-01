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
Battle.net signup → approval → login and legacy migration tests. Its fixture creates and drops a separate
random database; the test user needs database-creation permission. `make verify`
includes frontend, API, database, infrastructure, and Compose checks.

## Where code belongs

```text
app/
  routes.ts                  URL patterns and layout composition
  routes/                    Thin route modules that select a screen and its props
  features/
    accounts/                Membership list, details, controls, API, query options, types
    bluds/                   Character directory, forms, progress, API and reference contracts
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

Before hydration the page stays blank (with a JavaScript notice for browsers that
disable scripts). The shell and general navigation render while the initial session
check runs; account details, permission-based links, and protected route content wait
for the account. Login and registration fields also render immediately, with submission
disabled until the check settles. If the initial check fails without a cached account,
show a retry notice inside the shell. A temporary background refresh
failure keeps the existing shell and route mounted and shows a retry notice. This
preserves forms and confirmation dialogs; do not treat an outage as logout.
Confirmed session loss clears the cached account, removes protected data, and
redirects to login. Cached permissions can be stale during an outage, so every
write remains subject to API authorization.

Keep form fields and dialog state local. Read and write refs in handlers or effects,
not during render. Legacy migration forms snapshot credentials in the submit handler and
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

## Battle.net sign-in

Login and registration start a full-page navigation to Battle.net. Password fields
appear only after choosing **Migrate existing account** and only establish a
short-lived linking attempt. The connection prompt must be completed before any
member session exists. New identities choose a display name on `/register/complete`
and explicitly confirm that they are requesting a new account.

The backend owns `/api/oauth-redirect`; provider codes and tokens never reach the
SPA. `/auth/complete` obtains a Bluddit token and current account under the existing
Web Lock, then publishes the new identity through BroadcastChannel and clears
protected caches. Starting sign-in first logs out the current browser across tabs.
Sessions have fixed provider-bound expiry up to 24 hours, without sliding renewal.
The browser test server exposes a synthetic authorization page only in its isolated
test fixture; no production provider URL override or test-login route exists.
