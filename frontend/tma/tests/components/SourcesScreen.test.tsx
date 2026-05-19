import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { SourcesScreen } from '@/features/sources/SourcesScreen';
import { setTokens } from '@/features/auth/tokenStore';
import { server } from '../msw/server';

const API_BASE = 'http://test.local';

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => {
    const rootRoute = createRootRoute({ component: () => <>{children}</> });
    const sourcesRoute = createRoute({
      getParentRoute: () => rootRoute,
      path: '/sources',
      component: () => null,
    });
    const hiddenRoute = createRoute({
      getParentRoute: () => sourcesRoute,
      path: '/hidden',
      component: () => null,
    });
    const catalogHiddenRoute = createRoute({
      getParentRoute: () => sourcesRoute,
      path: '/catalog-hidden',
      component: () => null,
    });
    const routeTree = rootRoute.addChildren([
      sourcesRoute.addChildren([hiddenRoute, catalogHiddenRoute]),
    ]);
    const router = createRouter({
      routeTree,
      history: createMemoryHistory({ initialEntries: ['/sources'] }),
    });
    return (
      <QueryClientProvider client={qc}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    );
  };
}

function authenticate() {
  setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
}

function emptyHandlers() {
  server.use(
    http.get(`${API_BASE}/sources`, () => HttpResponse.json({ items: [] })),
    http.get(`${API_BASE}/sources/hidden`, () => HttpResponse.json({ items: [] })),
    http.get(`${API_BASE}/channels/catalog`, () =>
      HttpResponse.json({ items: [], next_cursor: null }),
    ),
  );
}

describe('SourcesScreen', () => {
  it('does not show legacy "only public channels" notice', async () => {
    authenticate();
    emptyHandlers();
    render(<SourcesScreen />, { wrapper: wrap() });
    await waitFor(() =>
      expect(screen.getByText(/подключите первый канал/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/только публичные каналы/i)).not.toBeInTheDocument();
  });

  it('renders ChannelCatalogSection above subscriptions list', async () => {
    authenticate();
    server.use(
      http.get(`${API_BASE}/sources`, () => HttpResponse.json({ items: [] })),
      http.get(`${API_BASE}/sources/hidden`, () => HttpResponse.json({ items: [] })),
      http.get(`${API_BASE}/channels/catalog`, () =>
        HttpResponse.json({
          items: [
            {
              channel: { id: 5, username: 'show', title: 'Show', photo_url: null, is_private: false },
              subscribers_count: 1,
              last_post_at: null,
              is_subscribed: false,
              is_hidden_from_catalog: false,
            },
          ],
          next_cursor: null,
        }),
      ),
    );
    render(<SourcesScreen />, { wrapper: wrap() });
    await waitFor(() => expect(screen.getByText('Show')).toBeInTheDocument());
    expect(screen.getByText(/доступные каналы/i)).toBeInTheDocument();
  });

  it('renders the "hidden from feed" section when API returns items', async () => {
    authenticate();
    server.use(
      http.get(`${API_BASE}/sources`, () =>
        HttpResponse.json({
          items: [
            {
              channel: { id: 1, username: 'a', title: 'A', photo_url: null, is_private: false },
              added_at: '2026-05-18T00:00:00Z',
              subscription_status: 'active',
            },
          ],
        }),
      ),
      http.get(`${API_BASE}/sources/hidden`, () =>
        HttpResponse.json({
          items: [
            {
              channel: { id: 2, username: 'h', title: 'H', photo_url: null, is_private: false },
              hidden_at: '2026-05-19T00:00:00Z',
            },
          ],
        }),
      ),
      http.get(`${API_BASE}/channels/catalog`, () =>
        HttpResponse.json({ items: [], next_cursor: null }),
      ),
    );
    render(<SourcesScreen />, { wrapper: wrap() });
    await waitFor(() =>
      expect(screen.getByText(/скрыты из ленты \(1\)/i)).toBeInTheDocument(),
    );
  });
});
