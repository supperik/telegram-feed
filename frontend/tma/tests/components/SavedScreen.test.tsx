import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { SavedScreen } from '@/features/saved/SavedScreen';
import { setTokens } from '@/features/auth/tokenStore';
import { server } from '../msw/server';

const API_BASE = 'http://test.local';

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

function feedPost(id: number, text: string) {
  return {
    id, tg_message_id: id, posted_at: '2026-01-01T00:00:00Z',
    text, text_html: null, views: null, forwards: null,
    channel: { id: 1, tg_chat_id: 1000001, username: 'c', title: 'C', photo_url: null, is_private: false },
    media: [], is_saved: false,
  };
}

describe('SavedScreen — вкладка «Просмотренные»', () => {
  it('shows read posts from /posts/read when the tab is selected', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
    server.use(
      http.get(`${API_BASE}/posts/saved`, () =>
        HttpResponse.json({ posts: [], next_cursor: null }),
      ),
      http.get(`${API_BASE}/posts/hidden`, () =>
        HttpResponse.json({ posts: [], next_cursor: null }),
      ),
      http.get(`${API_BASE}/posts/read`, () =>
        HttpResponse.json({ posts: [feedPost(99, 'просмотренный пост')], next_cursor: null }),
      ),
    );
    const user = userEvent.setup();
    render(<SavedScreen />, { wrapper: wrap() });

    await user.click(screen.getByRole('button', { name: 'Просмотренные' }));

    expect(await screen.findByText('просмотренный пост')).toBeInTheDocument();
  });

  it('keeps the saved and hidden tabs working alongside the new tab', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
    server.use(
      http.get(`${API_BASE}/posts/saved`, () =>
        HttpResponse.json({ posts: [feedPost(1, 'сохранённый пост')], next_cursor: null }),
      ),
      http.get(`${API_BASE}/posts/hidden`, () =>
        HttpResponse.json({ posts: [feedPost(2, 'скрытый пост')], next_cursor: null }),
      ),
      http.get(`${API_BASE}/posts/read`, () =>
        HttpResponse.json({ posts: [], next_cursor: null }),
      ),
    );
    const user = userEvent.setup();
    render(<SavedScreen />, { wrapper: wrap() });

    expect(await screen.findByText('сохранённый пост')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Скрытые' }));
    expect(await screen.findByText('скрытый пост')).toBeInTheDocument();
  });
});
