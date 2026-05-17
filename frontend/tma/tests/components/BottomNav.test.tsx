import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { BottomNav } from '@/shared/ui/BottomNav';

function renderAtPath(path: string) {
  const rootRoute = createRootRoute({ component: () => <BottomNav /> });
  const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: '/', component: () => <div>feed</div> });
  const sourcesRoute = createRoute({ getParentRoute: () => rootRoute, path: '/sources', component: () => <div>sources</div> });
  const routeTree = rootRoute.addChildren([indexRoute, sourcesRoute]);
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: [path] }) });
  return render(<RouterProvider router={router} />);
}

describe('BottomNav', () => {
  it('renders Feed and Sources links', async () => {
    renderAtPath('/');
    // TanStack Router renders asynchronously after the initial route resolves;
    // use `findByRole` for the first lookup so the test waits for the tree.
    expect(await screen.findByRole('link', { name: /feed/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /sources/i })).toBeInTheDocument();
  });

  it('marks the active tab via aria-current', async () => {
    renderAtPath('/sources');
    expect(await screen.findByRole('link', { name: /sources/i })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByRole('link', { name: /feed/i })).not.toHaveAttribute('aria-current');
  });

  it('navigates on click', async () => {
    renderAtPath('/');
    const sourcesLink = await screen.findByRole('link', { name: /sources/i });
    await userEvent.click(sourcesLink);
    // The active tab has switched.
    expect(screen.getByRole('link', { name: /sources/i })).toHaveAttribute('aria-current', 'page');
  });
});
