import { ApiError, send } from '@/lib/http';
import type { Account } from '@/features/accounts/types';
import type {
  AuthorizationResponse,
  Credentials,
  CurrentAccount,
  Registration,
  RegistrationContext,
  TokenResponse,
} from './types';

type SessionEvent = { account: CurrentAccount | null };
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
export async function authenticated<T>(path: string, options: RequestInit = {}): Promise<T> {
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
export const sessionApi = {
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
  async startBattleNet(returnTo: string): Promise<AuthorizationResponse> {
    await sessionApi.logout();
    const expected = epoch;
    const result = await send<AuthorizationResponse>('/api/auth/battlenet/start', {
      method: 'POST',
      body: JSON.stringify({ return_to: returnTo }),
    });
    assertEpoch(expected);
    return result;
  },
  async login(credentials: Credentials, returnTo = '/home'): Promise<AuthorizationResponse> {
    await sessionApi.logout();
    const expected = epoch;
    const result = await send<AuthorizationResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        username: credentials.username,
        password: credentials.password,
        return_to: returnTo,
      }),
    });
    assertEpoch(expected);
    return result;
  },
  async completeOAuth(): Promise<void> {
    const expected = ++epoch;
    explicitlyLoggedOut = false;
    token = null;
    return lock(async () => {
      assertEpoch(expected);
      const result = await send<TokenResponse>('/api/auth/token', { method: 'POST' });
      assertEpoch(expected);
      const account = await send<CurrentAccount>('/api/auth/me', {
        headers: { Authorization: `Bearer ${result.access_token}` },
      });
      assertEpoch(expected);
      acceptToken(result, 'login', account);
      emit({ account });
    });
  },
  registrationContext(signal?: AbortSignal) {
    return send<RegistrationContext>('/api/auth/battlenet/registration', { signal });
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
};
