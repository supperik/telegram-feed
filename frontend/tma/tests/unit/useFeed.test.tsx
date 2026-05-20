import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import type { ReactNode } from 'react';
import { useFeed } from '@/features/feed/useFeed';
import { setTokens } from '@/features/auth/tokenStore';
import { server } from '../msw/server';

function wrap(): (props: { children: ReactNode }) => JSX.Element {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useFeed', () => {
  it('returns the first page of posts', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
    server.use(
      http.get('http://test.local/feed', () =>
        HttpResponse.json({
          posts: [
            {
              id: 1, tg_message_id: 10, posted_at: '2026-01-01T00:00:00Z',
              text: 'hello', text_html: null, views: null, forwards: null,
              channel: { id: 1, tg_chat_id: 1000001, username: 'c', title: 'C', photo_url: null, is_private: false },
              media: [], is_saved: false,
            },
          ],
          next_cursor: 'CURSOR-1',
        }),
      ),
    );
    const { result } = renderHook(() => useFeed(), { wrapper: wrap() });
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(result.current.data!.pages[0]!.posts[0]!.id).toBe(1);
    expect(result.current.hasNextPage).toBe(true);
  });

  it('reports no more pages when next_cursor is null', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
    server.use(
      http.get('http://test.local/feed', () =>
        HttpResponse.json({ posts: [], next_cursor: null }),
      ),
    );
    const { result } = renderHook(() => useFeed(), { wrapper: wrap() });
    await waitFor(() => expect(result.current.status).toBe('success'));
    expect(result.current.hasNextPage).toBe(false);
  });

  it('does not refetch when the feed remounts (tab navigation keeps cached data)', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
    let calls = 0;
    server.use(
      http.get('http://test.local/feed', () => {
        calls += 1;
        return HttpResponse.json({
          posts: [
            {
              id: calls, tg_message_id: calls, posted_at: '2026-01-01T00:00:00Z',
              text: 'p', text_html: null, views: null, forwards: null,
              channel: { id: 1, tg_chat_id: 1000001, username: 'c', title: 'C', photo_url: null, is_private: false },
              media: [], is_saved: false,
            },
          ],
          next_cursor: null,
        });
      }),
    );
    // One QueryClient survives across mounts — the app-level client while the
    // feed screen unmounts on tab navigation and remounts on return.
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );

    const first = renderHook(() => useFeed(), { wrapper });
    await waitFor(() => expect(first.result.current.status).toBe('success'));
    expect(calls).toBe(1);
    first.unmount(); // leave the feed tab

    const second = renderHook(() => useFeed(), { wrapper }); // return to the feed tab
    await waitFor(() => expect(second.result.current.isFetching).toBe(false));
    expect(calls).toBe(1); // served from cache — no refetch on remount
    expect(second.result.current.data!.pages[0]!.posts[0]!.id).toBe(1);
  });
});
