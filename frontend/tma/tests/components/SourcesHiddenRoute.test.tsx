import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { setTokens } from '@/features/auth/tokenStore';
import { HiddenCatalogScreen } from '@/features/sources/HiddenCatalogScreen';
import { SourcesScreen } from '@/features/sources/SourcesScreen';
import { routeTree as generatedRouteTree } from '@/routeTree.gen';
import { server } from '../msw/server';

const API_BASE = 'http://test.local';

// Regression test for the routing bug where `/sources/hidden` was registered
// as a nested child of `/sources` in `routeTree.gen.ts`. Because the parent
// `SourcesScreen` does not render `<Outlet />`, that nesting caused
// `/sources/hidden` to render `SourcesScreen` again — never the
// `HiddenCatalogScreen`. The fix is the `src/routes/sources/` directory
// layout, which makes both routes direct siblings of root.
//
// We verify in two layers:
//   1. structural assertion against the real `routeTree.gen.ts` — the
//      `/sources/hidden` route must NOT have `/sources` as its parent.
//   2. render assertion using a stub tree that mirrors the post-fix layout
//      (both routes as direct siblings under root) — `/sources/hidden`
//      renders `HiddenCatalogScreen`, and `/sources` renders `SourcesScreen`.
function renderAtPath(path: string) {
  const rootRoute = createRootRoute({ component: () => <Outlet /> });
  const sourcesRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/sources',
    component: SourcesScreen,
  });
  const hiddenRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/sources/hidden',
    component: HiddenCatalogScreen,
  });
  const routeTree = rootRoute.addChildren([sourcesRoute, hiddenRoute]);
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

function authenticate() {
  setTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 60 });
}

describe('routeTree /sources/hidden structure', () => {
  it('registers /sources/hidden as a sibling of /sources, not a nested child', () => {
    // Both routes must be direct children of the root, not nested. The
    // previous (buggy) gen file registered SourcesHiddenRoute with
    // `getParentRoute: () => SourcesRoute`, so it would appear as a
    // grandchild of root via `SourcesRoute.children`. After the fix, both
    // show up directly in `root.children` and the parent chain of
    // `/sources/hidden` does NOT go through `/sources`.
    type RouteOptions = { id?: string; getParentRoute?: () => RouteLike };
    type RouteLike = {
      options?: RouteOptions;
      children?: RouteLike[] | Record<string, RouteLike>;
    };
    const root = generatedRouteTree as unknown as RouteLike;

    function collect(node: RouteLike, acc: RouteLike[] = []): RouteLike[] {
      acc.push(node);
      const children = node.children;
      if (children) {
        for (const child of Array.isArray(children) ? children : Object.values(children)) {
          collect(child, acc);
        }
      }
      return acc;
    }

    const all = collect(root);
    const idOf = (n: RouteLike) => n.options?.id;
    const parentOf = (n: RouteLike) => n.options?.getParentRoute?.();
    const hidden = all.find((n) => idOf(n) === '/sources/hidden');
    const sources = all.find((n) => idOf(n) === '/sources/');
    expect(hidden, 'expected /sources/hidden route to exist in the tree').toBeDefined();
    expect(sources, 'expected /sources/ route to exist in the tree').toBeDefined();
    // The hidden route's parent must be the root (no `options.id`), NOT the
    // `/sources` route — otherwise the bug is back.
    const hiddenParentId = idOf(parentOf(hidden!) ?? {});
    expect(hiddenParentId).toBeUndefined();
  });
});

describe('routeTree /sources/hidden integration', () => {
  it('renders HiddenCatalogScreen at /sources/hidden, not SourcesScreen', async () => {
    authenticate();
    server.use(
      http.get(`${API_BASE}/channels/catalog`, () =>
        HttpResponse.json({ items: [], next_cursor: null }),
      ),
    );

    renderAtPath('/sources/hidden');

    await waitFor(() =>
      expect(screen.getByText(/скрытые из каталога/i)).toBeInTheDocument(),
    );
    // SourcesScreen's empty-state title must NOT appear — that would mean the
    // wrong screen was rendered.
    expect(screen.queryByText(/подключите первый канал/i)).not.toBeInTheDocument();
  });

  it('renders SourcesScreen at /sources', async () => {
    authenticate();
    server.use(
      http.get(`${API_BASE}/sources`, () => HttpResponse.json({ items: [] })),
      http.get(`${API_BASE}/channels/catalog`, () =>
        HttpResponse.json({ items: [], next_cursor: null }),
      ),
    );

    renderAtPath('/sources');

    await waitFor(() =>
      expect(screen.getByText(/подключите первый канал/i)).toBeInTheDocument(),
    );
    // HiddenCatalogScreen's heading must NOT appear.
    expect(screen.queryByText(/скрытые из каталога/i)).not.toBeInTheDocument();
  });
});
