/** The sole frontend API contract. HTTP details and session tokens stay here. */
export type MembershipState = 'pending' | 'active' | 'rejected' | 'inactive';
export type Role = 'member' | 'officer' | 'guild_master';
export interface Account {
  id: number;
  username: string;
  display_name: string;
  membership_state: MembershipState;
  role_name: Role;
  timezone: string | null;
}
export interface CurrentAccount extends Account {
  permissions: string[];
}
export interface Credentials {
  username: string;
  password: string;
}
export interface Registration extends Credentials {
  display_name: string;
}
interface TokenResponse {
  access_token: string;
  token_type: 'Bearer';
  expires_in: number;
}
export interface AccountFilter {
  membership_state?: MembershipState;
  limit: number;
  offset: number;
}
export interface AccountPage {
  accounts: Account[];
  limit: number;
  offset: number;
}
export interface PermissionPolicy {
  permissions: string[];
  roles: Record<Role, string[]>;
}
export type AccountAction =
  | 'approve'
  | 'reject'
  | 'deactivate'
  | 'activate'
  | 'promote-to-officer'
  | 'demote-to-member'
  | 'pass-guild-master';
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public retryAfter?: string
  ) {
    super(message);
  }
}

type SessionEvent = { account: CurrentAccount | null; logoutFailed?: boolean };
type SessionMessage =
  | { type: 'logout' }
  | {
      type: 'token' | 'login';
      token: string;
      expiresAt: number;
      account?: CurrentAccount;
    };
let token: string | null = null;
let expiresAt = 0;
let epoch = 0;
let explicitlyLoggedOut = false;
let refreshPromise: Promise<void> | undefined;
const listeners = new Set<(event: SessionEvent) => void>();
const channel =
  typeof window !== 'undefined' && typeof BroadcastChannel !== 'undefined'
    ? new BroadcastChannel('bluddit-session')
    : null;
function emit(event: SessionEvent) {
  listeners.forEach((listener) => listener(event));
}
function clearSession() {
  epoch++;
  token = null;
  expiresAt = 0;
  explicitlyLoggedOut = true;
}
channel?.addEventListener('message', ({ data }: MessageEvent<SessionMessage>) => {
  if (data.type === 'logout') {
    clearSession();
    emit({ account: null });
  } else if (data.type === 'login') {
    epoch++;
    token = data.token;
    expiresAt = data.expiresAt;
    explicitlyLoggedOut = false;
    if (data.account) emit({ account: data.account });
  } else if (!explicitlyLoggedOut) {
    token = data.token;
    expiresAt = data.expiresAt;
  }
});
function lock<T>(callback: () => Promise<T>): Promise<T> {
  if (!navigator.locks || !channel)
    return Promise.reject(
      new ApiError(0, 'Please use a current browser with secure session support.')
    );
  return navigator.locks.request('bluddit-session', callback);
}
function assertEpoch(expected: number) {
  if (epoch !== expected) throw new DOMException('Session changed', 'AbortError');
}
async function send<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      credentials: 'same-origin',
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.method && options.method !== 'GET' ? { 'X-CSRF-Protection': '1' } : {}),
        ...options.headers,
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, 'Couldn’t connect. Check your connection and try again.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      typeof body?.detail === 'string' ? body.detail : 'The request could not be completed.',
      response.headers.get('Retry-After') ?? undefined
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
function acceptToken(
  result: TokenResponse,
  type: 'token' | 'login' = 'token',
  account?: CurrentAccount
) {
  token = result.access_token;
  expiresAt = Date.now() + result.expires_in * 1000;
  explicitlyLoggedOut = false;
  channel?.postMessage({ type, token, expiresAt, account } satisfies SessionMessage);
}
async function refresh(failedToken?: string | null) {
  if (refreshPromise) return refreshPromise;
  const expected = epoch;
  refreshPromise = lock(async () => {
    assertEpoch(expected);
    if (explicitlyLoggedOut) throw new ApiError(401, 'Please log in to continue.');
    // Another tab/request may already have supplied a replacement while we waited.
    if (token && expiresAt > Date.now() + 5000 && (!failedToken || token !== failedToken)) return;
    let result: TokenResponse;
    try {
      result = await send<TokenResponse>('/api/auth/token', { method: 'POST' });
    } catch (error) {
      assertEpoch(expected);
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
      // Bounded recovery if another tab rotated the cookie before our request.
      try {
        result = await send<TokenResponse>('/api/auth/token', { method: 'POST' });
      } catch (retryError) {
        assertEpoch(expected);
        if (retryError instanceof ApiError && retryError.status === 401) {
          clearSession();
          emit({ account: null });
        }
        throw retryError;
      }
    }
    assertEpoch(expected);
    acceptToken(result);
  }).finally(() => {
    refreshPromise = undefined;
  });
  return refreshPromise;
}
async function authenticated<T>(path: string, options: RequestInit = {}): Promise<T> {
  const expected = epoch;
  if (!token || expiresAt <= Date.now() + 5000) await refresh();
  assertEpoch(expected);
  const usedToken = token;
  try {
    const result = await send<T>(path, {
      ...options,
      headers: { Authorization: `Bearer ${usedToken}` },
    });
    assertEpoch(expected);
    return result;
  } catch (error) {
    assertEpoch(expected);
    if (!(error instanceof ApiError) || error.status !== 401) throw error;
    await refresh(usedToken);
    assertEpoch(expected);
    try {
      const result = await send<T>(path, {
        ...options,
        headers: { Authorization: `Bearer ${token}` },
      });
      assertEpoch(expected);
      return result;
    } catch (retryError) {
      assertEpoch(expected);
      if (retryError instanceof ApiError && retryError.status === 401) {
        clearSession();
        emit({ account: null });
      }
      throw retryError;
    }
  }
}
export const api = {
  subscribe(listener: (event: SessionEvent) => void) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
  async me(signal?: AbortSignal): Promise<CurrentAccount | null> {
    if (explicitlyLoggedOut) return null;
    try {
      return await authenticated<CurrentAccount>('/api/auth/me', { signal });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return null;
      throw error;
    }
  },
  async login(credentials: Credentials): Promise<CurrentAccount> {
    const expected = ++epoch;
    return lock(async () => {
      assertEpoch(expected);
      const result = await send<TokenResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: credentials.username, password: credentials.password }),
      });
      assertEpoch(expected);
      // Verify the current account before publishing the new identity.
      const account = await send<CurrentAccount>('/api/auth/me', {
        headers: { Authorization: `Bearer ${result.access_token}` },
      });
      assertEpoch(expected);
      acceptToken(result, 'login', account);
      emit({ account });
      return account;
    });
  },
  register(input: Registration) {
    return send<Account>('/api/auth/register', { method: 'POST', body: JSON.stringify(input) });
  },
  async logout(): Promise<void> {
    clearSession();
    emit({ account: null });
    channel?.postMessage({ type: 'logout' } satisfies SessionMessage);
    await lock(async () => {
      await send<void>('/api/auth/token', { method: 'DELETE' });
    });
  },
  accounts(filter: AccountFilter, signal?: AbortSignal) {
    const params = new URLSearchParams({
      limit: String(filter.limit),
      offset: String(filter.offset),
    });
    if (filter.membership_state) params.set('membership_state', filter.membership_state);
    return authenticated<AccountPage>(`/api/accounts?${params}`, { signal });
  },
  account(id: number, signal?: AbortSignal) {
    return authenticated<Account>(`/api/accounts/${id}`, { signal });
  },
  permissions(signal?: AbortSignal) {
    return authenticated<PermissionPolicy>('/api/permissions', { signal });
  },
  accountAction(id: number, action: AccountAction) {
    return authenticated<Account>(`/api/accounts/${id}/${action}`, { method: 'POST' });
  },
};
