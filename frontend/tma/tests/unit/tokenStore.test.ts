import { afterEach, describe, expect, it } from 'vitest';
import { clearTokens, getTokens, setTokens } from '@/features/auth/tokenStore';

afterEach(() => localStorage.clear());

describe('tokenStore', () => {
  it('roundtrips the pair', () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
    expect(getTokens()).toEqual({
      access_token: 'a',
      refresh_token: 'r',
      token_type: 'bearer',
      expires_in: 60,
    });
  });

  it('returns null when empty', () => {
    expect(getTokens()).toBeNull();
  });

  it('clears tokens', () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
    clearTokens();
    expect(getTokens()).toBeNull();
  });

  it('returns null on malformed storage', () => {
    localStorage.setItem('tma:tokens', 'not-json');
    expect(getTokens()).toBeNull();
  });
});
