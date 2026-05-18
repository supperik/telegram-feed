import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { SourcesScreen } from '@/features/sources/SourcesScreen';
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

describe('SourcesScreen', () => {
  it('does not show legacy "only public channels" notice', async () => {
    authenticate();
    server.use(
      http.get(`${API_BASE}/sources`, () => HttpResponse.json({ items: [] })),
    );
    render(<SourcesScreen />, { wrapper: wrap() });
    // Wait for the screen to render past the pending state (empty list shows EmptyState title).
    await waitFor(() =>
      expect(screen.getByText(/подключите первый канал/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/только публичные каналы/i)).not.toBeInTheDocument();
  });
});
