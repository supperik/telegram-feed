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
import { HiddenSourcesScreen } from '@/features/sources/HiddenSourcesScreen';
import { setTokens } from '@/features/auth/tokenStore';
import { server } from '../msw/server';

const API_BASE = 'http://test.local';

function renderWithRouter() {
  const rootRoute = createRootRoute({ component: () => <HiddenSourcesScreen /> });
  const sourcesRoute = createRoute({ getParentRoute: () => rootRoute, path: '/sources', component: () => null });
  const hiddenRoute = createRoute({ getParentRoute: () => sourcesRoute, path: '/hidden', component: () => null });
  const routeTree = rootRoute.addChildren([sourcesRoute.addChildren([hiddenRoute])]);
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ['/sources/hidden'] }),
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

describe('HiddenSourcesScreen', () => {
  it('shows empty state when there are no hidden channels', async () => {
    authenticate();
    server.use(
      http.get(`${API_BASE}/sources/hidden`, () => HttpResponse.json({ items: [] })),
    );
    renderWithRouter();
    await waitFor(() =>
      expect(screen.getByText(/нет скрытых каналов/i)).toBeInTheDocument(),
    );
  });

  it('renders hidden channel titles from GET /sources/hidden', async () => {
    authenticate();
    server.use(
      http.get(`${API_BASE}/sources/hidden`, () =>
        HttpResponse.json({
          items: [
            { channel: { id: 1, username: 'a', title: 'Alpha', photo_url: null, is_private: false }, hidden_at: '2026-05-18T00:00:00Z' },
            { channel: { id: 2, username: 'b', title: 'Beta', photo_url: null, is_private: false }, hidden_at: '2026-05-19T00:00:00Z' },
          ],
        }),
      ),
    );
    renderWithRouter();
    expect(await screen.findByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
  });

  it('return button calls DELETE /sources/{id}/hide', async () => {
    authenticate();
    let deleted = false;
    server.use(
      http.get(`${API_BASE}/sources/hidden`, () =>
        HttpResponse.json({
          items: [
            { channel: { id: 9, username: 'hh', title: 'HH', photo_url: null, is_private: false }, hidden_at: '2026-05-19T00:00:00Z' },
          ],
        }),
      ),
      http.delete(`${API_BASE}/sources/9/hide`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithRouter();
    await screen.findByText('HH');
    await userEvent.click(screen.getByRole('button', { name: /вернуть/i }));
    await waitFor(() => expect(deleted).toBe(true));
  });

  it('has a back link to /sources', async () => {
    authenticate();
    server.use(
      http.get(`${API_BASE}/sources/hidden`, () => HttpResponse.json({ items: [] })),
    );
    renderWithRouter();
    const back = await screen.findByRole('link', { name: /к источникам/i });
    expect(back).toHaveAttribute('href', '/sources');
  });
});
