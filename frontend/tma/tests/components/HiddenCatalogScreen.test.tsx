import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { HiddenCatalogScreen } from '@/features/sources/HiddenCatalogScreen';
import { setTokens } from '@/features/auth/tokenStore';
import { server } from '../msw/server';

const API_BASE = 'http://test.local';

function renderWithRouter() {
  const rootRoute = createRootRoute({ component: () => <HiddenCatalogScreen /> });
  const sourcesRoute = createRoute({ getParentRoute: () => rootRoute, path: '/sources', component: () => null });
  const catalogHiddenRoute = createRoute({ getParentRoute: () => sourcesRoute, path: '/catalog-hidden', component: () => null });
  const routeTree = rootRoute.addChildren([sourcesRoute.addChildren([catalogHiddenRoute])]);
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ['/sources/catalog-hidden'] }),
  });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

function authenticate() {
  setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
}

describe('HiddenCatalogScreen', () => {
  it('shows empty state when no hidden channels', async () => {
    authenticate();
    server.use(
      http.get(`${API_BASE}/channels/catalog`, () =>
        HttpResponse.json({ items: [], next_cursor: null }),
      ),
    );
    renderWithRouter();
    await waitFor(() =>
      expect(screen.getByText(/нет скрытых каналов/i)).toBeInTheDocument(),
    );
  });

  it('return button calls DELETE /channels/catalog/{id}/hide', async () => {
    authenticate();
    let deleted = false;
    const item = {
      channel: { id: 9, username: 'hh', title: 'HH', photo_url: null, is_private: false },
      subscribers_count: 1,
      last_post_at: null,
      is_subscribed: false,
      is_hidden_from_catalog: true,
    };
    server.use(
      http.get(`${API_BASE}/channels/catalog`, () =>
        HttpResponse.json({ items: [item], next_cursor: null }),
      ),
      http.delete(`${API_BASE}/channels/catalog/9/hide`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithRouter();
    await screen.findByText('HH');
    await userEvent.click(screen.getByRole('button', { name: /вернуть/i }));
    await waitFor(() => expect(deleted).toBe(true));
  });
});
