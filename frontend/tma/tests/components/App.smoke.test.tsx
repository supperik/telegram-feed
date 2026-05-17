import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { FeedScreen } from '@/features/feed/FeedScreen';
import { setTokens } from '@/features/auth/tokenStore';
import { server } from '../msw/server';

describe('App smoke', () => {
  it('renders a post from a mocked /api/feed', async () => {
    setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
    server.use(
      http.get('http://test.local/feed', () =>
        HttpResponse.json({
          posts: [
            {
              id: 7,
              tg_message_id: 70,
              posted_at: new Date().toISOString(),
              text: 'Smoke post body',
              text_html: null,
              views: 3,
              forwards: 0,
              channel: { id: 1, username: 'smoke', title: 'Smoke', photo_url: null },
              media: [],
              is_saved: false,
            },
          ],
          next_cursor: null,
        }),
      ),
    );

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <FeedScreen />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('Smoke post body')).toBeInTheDocument();
    expect(screen.getByText('Smoke')).toBeInTheDocument();
  });
});
