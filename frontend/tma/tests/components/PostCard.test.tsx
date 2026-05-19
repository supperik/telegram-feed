import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PostCard } from '@/features/feed/PostCard';
import type { FeedPost } from '@/shared/api/types';

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const post: FeedPost = {
  id: 1,
  tg_message_id: 42,
  posted_at: new Date(Date.now() - 5 * 60_000).toISOString(),
  text: 'Hello world',
  text_html: null,
  views: 100,
  forwards: 1,
  channel: {
    id: 1,
    tg_chat_id: 1319248631,
    username: 'meduza',
    title: 'Meduza',
    photo_url: null,
    is_private: false,
    invite_url: null,
  },
  media: [],
  is_saved: false,
};

afterEach(() => {
  delete (window as unknown as { Telegram?: unknown }).Telegram;
  vi.restoreAllMocks();
});

describe('PostCard', () => {
  it('renders title, channel and text', () => {
    render(<PostCard post={post} />, { wrapper: wrap() });
    expect(screen.getByText('Meduza')).toBeInTheDocument();
    expect(screen.getByText('Hello world')).toBeInTheDocument();
    expect(screen.getByText(/@meduza/)).toBeInTheDocument();
  });

  it('shows view count when present', () => {
    render(<PostCard post={post} />, { wrapper: wrap() });
    expect(screen.getByText(/100/)).toBeInTheDocument();
  });

  it('renders "Open in Telegram" with t.me/<username>/<msg> href for a public channel', () => {
    render(<PostCard post={post} />, { wrapper: wrap() });
    const link = screen.getByRole('link', { name: /open in telegram/i });
    expect(link).toHaveAttribute('href', 'https://t.me/meduza/42');
  });

  it('renders "Open in Telegram" with t.me/c/<tg_chat_id>/<msg> href for a private channel', () => {
    const privatePost: FeedPost = {
      ...post,
      channel: { ...post.channel, username: null, is_private: true },
    };
    render(<PostCard post={privatePost} />, { wrapper: wrap() });
    const link = screen.getByRole('link', { name: /open in telegram/i });
    expect(link).toHaveAttribute('href', 'https://t.me/c/1319248631/42');
  });

  it('click calls Telegram.WebApp.openTelegramLink and prevents default navigation', () => {
    const openTelegramLink = vi.fn();
    (window as unknown as { Telegram: { WebApp: { openTelegramLink: typeof openTelegramLink } } })
      .Telegram = { WebApp: { openTelegramLink } };

    render(<PostCard post={post} />, { wrapper: wrap() });
    const link = screen.getByRole('link', { name: /open in telegram/i });
    // fireEvent.click returns false when the synthetic onClick called
    // preventDefault — that's how we assert the <a href> doesn't also navigate.
    const notCanceled = fireEvent.click(link);

    expect(openTelegramLink).toHaveBeenCalledWith('https://t.me/meduza/42');
    expect(notCanceled).toBe(false);
  });

  it('falls back to window.open when running outside Telegram WebView', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    render(<PostCard post={post} />, { wrapper: wrap() });
    fireEvent.click(screen.getByRole('link', { name: /open in telegram/i }));
    expect(open).toHaveBeenCalledWith('https://t.me/meduza/42', '_blank', 'noopener,noreferrer');
  });

  it('renders MoreVertical icon button in header', () => {
    render(<PostCard post={post} />, { wrapper: wrap() });
    expect(screen.getByRole('button', { name: /more options/i })).toBeInTheDocument();
  });

  it('uses gradient avatar fallback when photo_url is null', () => {
    render(<PostCard post={post} />, { wrapper: wrap() });
    expect(screen.getByText('M')).toBeInTheDocument();
  });

  it('renders as a card (rounded background container)', () => {
    const { container } = render(<PostCard post={post} />, { wrapper: wrap() });
    const article = container.querySelector('article');
    expect(article).toHaveClass('bg-secondary');
    expect(article).toHaveClass('rounded-2xl');
  });

  it('SaveButton reflects is_saved=true via aria-pressed', () => {
    const saved = { ...post, is_saved: true };
    render(<PostCard post={saved} />, { wrapper: wrap() });
    expect(screen.getByRole('button', { name: /unsave/i })).toHaveAttribute('aria-pressed', 'true');
  });
});
