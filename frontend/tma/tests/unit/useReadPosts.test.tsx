import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import type { ReactNode } from 'react';
import { useReadPosts } from '@/features/posts/useReadPosts';
import { setTokens } from '@/features/auth/tokenStore';
import { server } from '../msw/server';

function wrap(): (props: { children: ReactNode }) => JSX.Element {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useReadPosts', () => {
  it('returns the first page of read posts', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
    server.use(
      http.get('http://test.local/posts/read', () =>
        HttpResponse.json({
          posts: [
            {
              id: 1, tg_message_id: 10, posted_at: '2026-01-01T00:00:00Z',
              text: 'read post', text_html: null, views: null, forwards: null,
              channel: { id: 1, tg_chat_id: 1000001, username: 'c', title: 'C', photo_url: null, is_private: false },
              media: [], is_saved: false,
            },
          ],
          next_cursor: 'CURSOR-1',
        }),
      ),
    );
    const { result } = renderHook(() => useReadPosts(), { wrapper: wrap() });
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(result.current.data!.pages[0]!.posts[0]!.id).toBe(1);
    expect(result.current.hasNextPage).toBe(true);
  });

  it('reports no more pages when next_cursor is null', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
    server.use(
      http.get('http://test.local/posts/read', () =>
        HttpResponse.json({ posts: [], next_cursor: null }),
      ),
    );
    const { result } = renderHook(() => useReadPosts(), { wrapper: wrap() });
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(result.current.hasNextPage).toBe(false);
  });
});
