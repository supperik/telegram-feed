import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { HiddenSourceListItem } from '@/features/sources/HiddenSourceListItem';
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog';
import type { HiddenSourceItem } from '@/shared/api/types';

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const item: HiddenSourceItem = {
  channel: { id: 9, username: 'foo', title: 'Foo', photo_url: null, is_private: false },
  hidden_at: new Date().toISOString(),
};

afterEach(() => vi.restoreAllMocks());

describe('HiddenSourceListItem', () => {
  it('shows channel title and @username', () => {
    render(<HiddenSourceListItem item={item} />, { wrapper: wrap() });
    expect(screen.getByText('Foo')).toBeInTheDocument();
    expect(screen.getByText(/@foo/)).toBeInTheDocument();
  });

  it('Return button calls DELETE /sources/{id}/hide', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(null, { status: 204 }));
    render(<HiddenSourceListItem item={item} />, { wrapper: wrap() });
    await userEvent.click(screen.getByRole('button', { name: /вернуть/i }));
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining('/sources/9/hide'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('Delete asks ConfirmDialog and skips on cancel', async () => {
    vi.spyOn(ConfirmDialog, 'confirm').mockResolvedValue(false);
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(null, { status: 204 }));
    render(<HiddenSourceListItem item={item} />, { wrapper: wrap() });
    await userEvent.click(screen.getByRole('button', { name: /удалить/i }));
    expect(ConfirmDialog.confirm).toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('renders LockIcon for is_private=true', () => {
    const priv: HiddenSourceItem = {
      channel: { id: 11, username: null, title: 'Secret', photo_url: null, is_private: true },
      hidden_at: new Date().toISOString(),
    };
    render(<HiddenSourceListItem item={priv} />, { wrapper: wrap() });
    expect(screen.getByText(/приватный/i)).toBeInTheDocument();
    expect(document.querySelector('svg[data-icon="lock"]')).toBeInTheDocument();
  });
});
