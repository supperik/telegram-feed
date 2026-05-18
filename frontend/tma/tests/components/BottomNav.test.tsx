import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { BottomNav } from '@/shared/ui/BottomNav';

function renderAtPath(path: string) {
  const rootRoute = createRootRoute({ component: () => <BottomNav /> });
  const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: '/', component: () => <div>feed</div> });
  const savedRoute = createRoute({ getParentRoute: () => rootRoute, path: '/saved', component: () => <div>saved</div> });
  const sourcesRoute = createRoute({ getParentRoute: () => rootRoute, path: '/sources', component: () => <div>sources</div> });
  const routeTree = rootRoute.addChildren([indexRoute, savedRoute, sourcesRoute]);
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: [path] }) });
  return render(<RouterProvider router={router} />);
}

describe('BottomNav', () => {
  it('renders Лента, Сохранёнки and Источники links', async () => {
    renderAtPath('/');
    expect(await screen.findByRole('link', { name: /лента/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /сохранёнки/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /источники/i })).toBeInTheDocument();
  });

  it('marks Saved active when at /saved', async () => {
    renderAtPath('/saved');
    expect(await screen.findByRole('link', { name: /сохранёнки/i })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: /лента/i })).not.toHaveAttribute('aria-current');
  });

  it('marks Sources active when at /sources', async () => {
    renderAtPath('/sources');
    expect(await screen.findByRole('link', { name: /источники/i })).toHaveAttribute('aria-current', 'page');
  });

  it('navigates on click', async () => {
    renderAtPath('/');
    await userEvent.click(await screen.findByRole('link', { name: /источники/i }));
    expect(screen.getByRole('link', { name: /источники/i })).toHaveAttribute('aria-current', 'page');
  });
});
