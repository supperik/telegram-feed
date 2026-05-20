import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SourceListItem } from '@/features/sources/SourceListItem';
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog';
import type { SourceListItem as Item } from '@/shared/api/types';

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

function wrapWithClient(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const item: Item = {
  channel: { id: 7, username: 'meduza', title: 'Meduza', photo_url: null, is_private: false },
  added_at: new Date().toISOString(),
  subscription_status: 'active',
};

afterEach(() => vi.restoreAllMocks());

describe('SourceListItem', () => {
  it('shows channel title and @username', () => {
    render(<SourceListItem item={item} />, { wrapper: wrap() });
    expect(screen.getByText('Meduza')).toBeInTheDocument();
    expect(screen.getByText(/@meduza/)).toBeInTheDocument();
  });

  it('shows pending hint when subscription_status is pending_backfill', () => {
    render(
      <SourceListItem item={{ ...item, subscription_status: 'pending_backfill' }} />,
      { wrapper: wrap() },
    );
    expect(screen.getByText(/подгружаем/i)).toBeInTheDocument();
  });

  it('Hide button calls hide.mutate without confirm', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }));
    render(<SourceListItem item={item} />, { wrapper: wrap() });
    await userEvent.click(screen.getByRole('button', { name: /скрыть/i }));
    expect(fetchSpy).toHaveBeenCalledWith(expect.stringContaining('/sources/7/hide'), expect.any(Object));
  });

  it('Delete asks ConfirmDialog and skips mutation on cancel', async () => {
    vi.spyOn(ConfirmDialog, 'confirm').mockResolvedValue(false);
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }));
    render(<SourceListItem item={item} />, { wrapper: wrap() });
    await userEvent.click(screen.getByRole('button', { name: /удалить/i }));
    expect(ConfirmDialog.confirm).toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('Delete with confirm=true mutates', async () => {
    vi.spyOn(ConfirmDialog, 'confirm').mockResolvedValue(true);
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }));
    render(<SourceListItem item={item} />, { wrapper: wrap() });
    await userEvent.click(screen.getByRole('button', { name: /удалить/i }));
    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith(expect.stringContaining('/sources/7'), expect.objectContaining({ method: 'DELETE' })),
    );
  });

  it('renders LockIcon + "Приватный" for is_private=true', () => {
    const privateItem: Item = {
      channel: { id: 10, username: null, title: 'Secret Club', photo_url: null, is_private: true },
      added_at: new Date().toISOString(),
      subscription_status: 'active',
    };
    render(<SourceListItem item={privateItem} />, { wrapper: wrap() });
    expect(screen.getByText(/приватный/i)).toBeInTheDocument();
    const svg = document.querySelector('svg[data-icon="lock"]');
    expect(svg).toBeInTheDocument();
  });

  it('renders @username (no LockIcon) for is_private=false', () => {
    render(<SourceListItem item={item} />, { wrapper: wrap() });
    expect(screen.getByText('@meduza')).toBeInTheDocument();
    expect(screen.queryByText(/приватный/i)).not.toBeInTheDocument();
    expect(document.querySelector('svg[data-icon="lock"]')).not.toBeInTheDocument();
  });

  it('Delete invalidates the catalog query (so "Подписаться" appears without reload)', async () => {
    vi.spyOn(ConfirmDialog, 'confirm').mockResolvedValue(true);
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries');
    render(<SourceListItem item={item} />, { wrapper: wrapWithClient(qc) });
    await userEvent.click(screen.getByRole('button', { name: /удалить/i }));
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['catalog'] }),
    );
  });

  it('Hide invalidates the catalog query (so "Подписаться" appears without reload)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries');
    render(<SourceListItem item={item} />, { wrapper: wrapWithClient(qc) });
    await userEvent.click(screen.getByRole('button', { name: /скрыть/i }));
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['catalog'] }),
    );
  });
});
