import { clearTokens, getTokens, setTokens } from '@/features/auth/tokenStore';
import { parseApiError } from '@/shared/api/errors';
import type { TokenPair } from '@/shared/api/types';

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api';

type FetchInit = Omit<RequestInit, 'headers'> & {
  headers?: Record<string, string>;
  /** Skip auth header. Use only for `/auth/telegram` and `/auth/refresh`. */
  anonymous?: boolean;
};

async function doFetch(path: string, init: FetchInit): Promise<Response> {
  const headers: Record<string, string> = {
    'content-type': 'application/json',
    ...(init.headers ?? {}),
  };
  if (!init.anonymous) {
    const tokens = getTokens();
    if (tokens) headers.authorization = `Bearer ${tokens.access_token}`;
  }
  return fetch(`${BASE}${path}`, { ...init, headers });
}

async function refresh(): Promise<TokenPair | null> {
  const tokens = getTokens();
  if (!tokens) return null;
  const res = await doFetch('/auth/refresh', {
    method: 'POST',
    anonymous: true,
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  });
  if (!res.ok) return null;
  const pair = (await res.json()) as TokenPair;
  setTokens(pair);
  return pair;
}

export async function apiFetch<T = unknown>(path: string, init: FetchInit = {}): Promise<T> {
  let res = await doFetch(path, init);

  if (res.status === 401 && !init.anonymous) {
    const newPair = await refresh();
    if (newPair) {
      res = await doFetch(path, init);
    } else {
      clearTokens();
      throw await parseApiError(res);
    }
  }

  if (res.status === 204) return undefined as T;
  if (!res.ok) throw await parseApiError(res);

  const ct = res.headers.get('content-type') ?? '';
  if (ct.includes('application/json')) return (await res.json()) as T;
  // Non-JSON success (e.g. 302) — return the raw Response cast to T for callers that need it.
  return res as unknown as T;
}

/** For the two anonymous auth endpoints. */
export async function apiPost<T = unknown>(
  path: string,
  body: unknown,
  opts: { anonymous?: boolean } = {},
): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
    anonymous: opts.anonymous,
  });
}
