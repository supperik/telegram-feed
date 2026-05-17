import type { TokenPair } from '@/shared/api/types';

const KEY = 'tma:tokens';

export function getTokens(): TokenPair | null {
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<TokenPair>;
    if (
      typeof parsed.access_token !== 'string' ||
      typeof parsed.refresh_token !== 'string' ||
      typeof parsed.expires_in !== 'number'
    ) {
      return null;
    }
    return {
      access_token: parsed.access_token,
      refresh_token: parsed.refresh_token,
      token_type: 'bearer',
      expires_in: parsed.expires_in,
    };
  } catch {
    return null;
  }
}

export function setTokens(pair: TokenPair): void {
  localStorage.setItem(KEY, JSON.stringify(pair));
}

export function clearTokens(): void {
  localStorage.removeItem(KEY);
}
