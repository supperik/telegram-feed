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
import { ChannelCatalogSection } from '@/features/sources/ChannelCatalogSection';
import { setTokens } from '@/features/auth/tokenStore';
import { server } from '../msw/server';

const API_BASE = 'http://test.local';

function renderWithRouter() {
  const rootRoute = createRootRoute({ component: () => <ChannelCatalogSection /> });
  const sourcesRoute = createRoute({ getParentRoute: () => rootRoute, path: '/sources', component: () => null });
  const hiddenRoute = createRoute({ getParentRoute: () => sourcesRoute, path: '/hidden', component: () => null });
  const routeTree = rootRoute.addChildren([sourcesRoute.addChildren([hiddenRoute])]);
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: ['/sources'] }) });
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

function catalogHandler(byView: Record<'available' | 'hidden', unknown[]>) {
  return http.get(`${API_BASE}/channels/catalog`, ({ request }) => {
    const view = new URL(request.url).searchParams.get('view') ?? 'available';
    const items = byView[view as 'available' | 'hidden'] ?? [];
    return HttpResponse.json({ items, next_cursor: null });
  });
}

const dormantChannel = {
  id: 7,
  username: 'dormant',
  title: 'Dormant',
  photo_url: null,
  is_private: false,
};

/** Catalog with a single dormant, not-yet-subscribed channel (id 7). */
const dormantCatalog = () =>
  catalogHandler({
    available: [
      {
        channel: dormantChannel,
        subscribers_count: 0,
        last_post_at: null,
        is_subscribed: false,
        is_hidden_from_catalog: false,
      },
    ],
    hidden: [],
  });

describe('ChannelCatalogSection', () => {
  it('renders empty state when catalog is empty', async () => {
    authenticate();
    server.use(catalogHandler({ available: [], hidden: [] }));
    renderWithRouter();
    expect(
      await screen.findByText(/пока никто не добавил каналов/i),
    ).toBeInTheDocument();
  });

  it('subscribes via POST /sources/{id} when "+ Подписаться" clicked', async () => {
    authenticate();
    const channel = { id: 7, username: 'ch', title: 'Ch', photo_url: null, is_private: false };
    let isSubscribed = false;
    server.use(
      http.get(`${API_BASE}/channels/catalog`, ({ request }) => {
        const view = new URL(request.url).searchParams.get('view') ?? 'available';
        if (view === 'hidden') return HttpResponse.json({ items: [], next_cursor: null });
        return HttpResponse.json({
          items: [
            {
              channel,
              subscribers_count: 1,
              last_post_at: null,
              is_subscribed: isSubscribed,
              is_hidden_from_catalog: false,
            },
          ],
          next_cursor: null,
        });
      }),
      http.post(`${API_BASE}/sources/7`, () => {
        isSubscribed = true;
        return HttpResponse.json({ status: 'subscribed', channel, queue_id: null });
      }),
    );
    renderWithRouter();
    await screen.findByText('Ch');
    await userEvent.click(screen.getByRole('button', { name: /подписаться/i }));
    await waitFor(() =>
      expect(screen.getByText(/подписан/i)).toBeInTheDocument(),
    );
  });

  it('reflects queued status and polls the queue until a dormant channel becomes subscribed', async () => {
    authenticate();
    let polls = 0;
    server.use(
      dormantCatalog(),
      http.post(`${API_BASE}/sources/7`, () =>
        HttpResponse.json(
          { status: 'queued', channel: null, queue_id: 42 },
          { status: 202 },
        ),
      ),
      http.get(`${API_BASE}/sources/queue/42`, () => {
        polls += 1;
        return HttpResponse.json({
          queue_id: 42,
          status: polls < 2 ? 'pending' : 'done',
          error_code: null,
          error_reason: null,
          channel: dormantChannel,
        });
      }),
    );
    renderWithRouter();
    await userEvent.click(
      await screen.findByRole('button', { name: /подписаться/i }),
    );
    // 202 queued — the row must surface the in-queue state, not stay "Подписаться".
    expect(await screen.findByText('В очереди')).toBeInTheDocument();
    // Polling /sources/queue/{id} resolves to done — the row flips to subscribed.
    expect(
      await screen.findByText('✓ Подписан', undefined, { timeout: 8000 }),
    ).toBeInTheDocument();
  });

  it('shows a localized error when the queued join fails', async () => {
    authenticate();
    server.use(
      dormantCatalog(),
      http.post(`${API_BASE}/sources/7`, () =>
        HttpResponse.json(
          { status: 'queued', channel: null, queue_id: 9 },
          { status: 202 },
        ),
      ),
      http.get(`${API_BASE}/sources/queue/9`, () =>
        HttpResponse.json({
          queue_id: 9,
          status: 'failed',
          error_code: 'channels_too_much',
          error_reason: null,
          channel: null,
        }),
      ),
    );
    renderWithRouter();
    await userEvent.click(
      await screen.findByRole('button', { name: /подписаться/i }),
    );
    expect(
      await screen.findByText(/превышен лимит каналов/i, undefined, {
        timeout: 8000,
      }),
    ).toBeInTheDocument();
  });

  it('keeps the row waiting when the queued join needs channel-admin approval', async () => {
    authenticate();
    server.use(
      dormantCatalog(),
      http.post(`${API_BASE}/sources/7`, () =>
        HttpResponse.json(
          { status: 'queued', channel: null, queue_id: 5 },
          { status: 202 },
        ),
      ),
      http.get(`${API_BASE}/sources/queue/5`, () =>
        HttpResponse.json({
          queue_id: 5,
          status: 'pending_approval',
          error_code: null,
          error_reason: null,
          channel: null,
        }),
      ),
    );
    renderWithRouter();
    await userEvent.click(
      await screen.findByRole('button', { name: /подписаться/i }),
    );
    expect(
      await screen.findByText(/заявка отправлена админу/i, undefined, {
        timeout: 8000,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Ждёт одобрения')).toBeInTheDocument();
  });
});
