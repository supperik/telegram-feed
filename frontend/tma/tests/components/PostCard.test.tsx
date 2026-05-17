import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PostCard } from '@/features/feed/PostCard';
import type { FeedPost } from '@/shared/api/types';

const post: FeedPost = {
  id: 1,
  tg_message_id: 42,
  posted_at: new Date(Date.now() - 5 * 60_000).toISOString(),
  text: 'Hello world',
  text_html: null,
  views: 100,
  forwards: 1,
  channel: { id: 1, username: 'meduza', title: 'Meduza', photo_url: null },
  media: [],
  is_saved: false,
};

describe('PostCard', () => {
  it('renders title, channel and text', () => {
    render(<PostCard post={post} />);
    expect(screen.getByText('Meduza')).toBeInTheDocument();
    expect(screen.getByText('Hello world')).toBeInTheDocument();
    expect(screen.getByText(/@meduza/)).toBeInTheDocument();
  });

  it('shows view count when present', () => {
    render(<PostCard post={post} />);
    expect(screen.getByText(/100/)).toBeInTheDocument();
  });

  it('renders "Open in Telegram" when username is set', () => {
    render(<PostCard post={post} />);
    const link = screen.getByRole('link', { name: /open in telegram/i });
    expect(link).toHaveAttribute('href', 'tg://resolve?domain=meduza&post=42');
  });
});
