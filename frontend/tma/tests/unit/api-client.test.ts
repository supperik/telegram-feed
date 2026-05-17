import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { apiFetch } from '@/shared/api/client';
import { ApiError } from '@/shared/api/errors';
import { getTokens, setTokens } from '@/features/auth/tokenStore';
import { server } from '../msw/server';

const tokens = {
  access_token: 'a1',
  refresh_token: 'r1',
  token_type: 'bearer' as const,
  expires_in: 60,
};

describe('apiFetch', () => {
  it('sends Bearer header from tokenStore', async () => {
    setTokens(tokens);
    let seenAuth = '';
    server.use(
      http.get('http://test.local/feed', ({ request }) => {
        seenAuth = request.headers.get('authorization') ?? '';
        return HttpResponse.json({ posts: [], next_cursor: null });
      }),
    );
    const body = await apiFetch<{ posts: unknown[] }>('/feed');
    expect(seenAuth).toBe('Bearer a1');
    expect(body.posts).toEqual([]);
  });

  it('returns undefined on 204', async () => {
    setTokens(tokens);
    server.use(
      http.post('http://test.local/posts/1/save', () => new HttpResponse(null, { status: 204 })),
    );
    await expect(apiFetch('/posts/1/save', { method: 'POST' })).resolves.toBeUndefined();
  });

  it('throws ApiError with code on 4xx envelope', async () => {
    setTokens(tokens);
    server.use(
      http.post('http://test.local/sources', () =>
        HttpResponse.json(
          { error: { code: 'channel_banned', message: 'banned' } },
          { status: 403 },
        ),
      ),
    );
    try {
      await apiFetch('/sources', { method: 'POST', body: JSON.stringify({ username: 'x' }) });
      throw new Error('should not reach');
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      expect((e as ApiError).code).toBe('channel_banned');
      expect((e as ApiError).status).toBe(403);
    }
  });

  it('on 401: refreshes then retries, persists new tokens', async () => {
    setTokens(tokens);
    let call = 0;
    server.use(
      http.get('http://test.local/feed', ({ request }) => {
        call += 1;
        const auth = request.headers.get('authorization');
        if (call === 1)
          return HttpResponse.json(
            { error: { code: 'expired_token', message: 'gone' } },
            { status: 401 },
          );
        if (auth === 'Bearer a2')
          return HttpResponse.json({ posts: ['ok'], next_cursor: null });
        return HttpResponse.json(
          { error: { code: 'wrong_auth_header', message: auth ?? '' } },
          { status: 400 },
        );
      }),
      http.post('http://test.local/auth/refresh', () =>
        HttpResponse.json({
          access_token: 'a2',
          refresh_token: 'r2',
          token_type: 'bearer',
          expires_in: 60,
        }),
      ),
    );

    const body = await apiFetch<{ posts: string[] }>('/feed');
    expect(body.posts).toEqual(['ok']);
    expect(getTokens()?.access_token).toBe('a2');
    expect(call).toBe(2);
  });

  it('on 401 with failed refresh: clears tokens and rethrows', async () => {
    setTokens(tokens);
    server.use(
      http.get('http://test.local/feed', () =>
        HttpResponse.json(
          { error: { code: 'expired_token', message: 'gone' } },
          { status: 401 },
        ),
      ),
      http.post('http://test.local/auth/refresh', () =>
        HttpResponse.json(
          { error: { code: 'bad_token', message: 'denied' } },
          { status: 401 },
        ),
      ),
    );
    await expect(apiFetch('/feed')).rejects.toMatchObject({ code: 'expired_token', status: 401 });
    expect(getTokens()).toBeNull();
  });
});
