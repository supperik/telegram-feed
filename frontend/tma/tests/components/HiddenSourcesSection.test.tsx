import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { HiddenSourcesSection } from '@/features/sources/HiddenSourcesSection';
import { setTokens } from '@/features/auth/tokenStore';
import { server } from '../msw/server';

const API_BASE = 'http://test.local';

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

function authenticate() {
  setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
}

describe('HiddenSourcesSection', () => {
  it('renders nothing when the list is empty', async () => {
    authenticate();
    server.use(
      http.get(`${API_BASE}/sources/hidden`, () => HttpResponse.json({ items: [] })),
    );
    const { container } = render(<HiddenSourcesSection />, { wrapper: wrap() });
    await waitFor(() => {
      expect(container.querySelector('details')).toBeNull();
    });
  });

  it('renders the section with channel count and details collapsed by default', async () => {
    authenticate();
    server.use(
      http.get(`${API_BASE}/sources/hidden`, () =>
        HttpResponse.json({
          items: [
            { channel: { id: 1, username: 'a', title: 'A', photo_url: null, is_private: false }, hidden_at: '2026-05-18T00:00:00Z' },
            { channel: { id: 2, username: 'b', title: 'B', photo_url: null, is_private: false }, hidden_at: '2026-05-19T00:00:00Z' },
          ],
        }),
      ),
    );
    render(<HiddenSourcesSection />, { wrapper: wrap() });
    await waitFor(() =>
      expect(screen.getByText(/скрыты из ленты \(2\)/i)).toBeInTheDocument(),
    );
    const details = document.querySelector('details');
    expect(details).not.toBeNull();
    expect(details?.hasAttribute('open')).toBe(false);
  });
});
