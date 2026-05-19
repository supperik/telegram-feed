import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { CatalogChannelItem } from '@/features/sources/CatalogChannelItem';
import type { CatalogChannelItem as Item } from '@/shared/api/types';

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

function makeItem(overrides: Partial<Item> = {}): Item {
  return {
    channel: { id: 1, username: 'meduzaproject', title: 'Meduza', photo_url: null, is_private: false },
    subscribers_count: 1,
    last_post_at: null,
    is_subscribed: false,
    is_hidden_from_catalog: false,
    ...overrides,
  };
}

describe('CatalogChannelItem', () => {
  it('renders title and @username', () => {
    render(
      <CatalogChannelItem item={makeItem()} actions="available" onSubscribe={vi.fn()} onHide={vi.fn()} />,
      { wrapper: wrap() },
    );
    expect(screen.getByText('Meduza')).toBeInTheDocument();
    expect(screen.getByText('@meduzaproject')).toBeInTheDocument();
  });

  it('shows Lock for private channels', () => {
    render(
      <CatalogChannelItem
        item={makeItem({
          channel: { id: 2, username: null, title: 'Privy', photo_url: null, is_private: true },
        })}
        actions="available"
        onSubscribe={vi.fn()}
        onHide={vi.fn()}
      />,
      { wrapper: wrap() },
    );
    expect(screen.getByText(/приватный/i)).toBeInTheDocument();
  });

  it('shows subscribed badge when is_subscribed=true and disables Subscribe', () => {
    render(
      <CatalogChannelItem
        item={makeItem({ is_subscribed: true })}
        actions="available"
        onSubscribe={vi.fn()}
        onHide={vi.fn()}
      />,
      { wrapper: wrap() },
    );
    expect(screen.getByText(/подписан/i)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /подписаться/i }),
    ).not.toBeInTheDocument();
  });

  it('hidden actions render a Return button only', () => {
    render(
      <CatalogChannelItem
        item={makeItem({ is_hidden_from_catalog: true })}
        actions="hidden"
        onUnhide={vi.fn()}
      />,
      { wrapper: wrap() },
    );
    expect(screen.getByRole('button', { name: /вернуть/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /скрыть/i })).not.toBeInTheDocument();
  });
});
