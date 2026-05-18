import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { MediaGallery } from '@/features/feed/MediaGallery';
import type { ChannelSummary, FeedMedia } from '@/shared/api/types';

const channel: ChannelSummary = { id: 1, username: 'meduza', title: 'M', photo_url: null };

function makePhotos(n: number): FeedMedia[] {
  return Array.from({ length: n }, (_, i) => ({
    id: i + 1, type: 'photo' as const, width: 1280, height: 720, duration: null,
  }));
}

describe('MediaGallery', () => {
  it('renders nothing for empty media', () => {
    const { container } = render(<MediaGallery media={[]} channel={channel} tgMessageId={1} />);
    expect(container.firstChild).toBeNull();
  });

  it('1 photo — single image, full width', () => {
    const { container } = render(<MediaGallery media={makePhotos(1)} channel={channel} tgMessageId={1} />);
    expect(container.querySelectorAll('img')).toHaveLength(1);
    expect(container.querySelector('[data-grid="one"]')).not.toBeNull();
  });

  it('3 photos — uses "three" layout (one big + two small)', () => {
    const { container } = render(<MediaGallery media={makePhotos(3)} channel={channel} tgMessageId={1} />);
    expect(container.querySelectorAll('img')).toHaveLength(3);
    expect(container.querySelector('[data-grid="three"]')).not.toBeNull();
  });

  it('5 photos — uses "five" layout', () => {
    const { container } = render(<MediaGallery media={makePhotos(5)} channel={channel} tgMessageId={1} />);
    expect(container.querySelectorAll('img')).toHaveLength(5);
    expect(container.querySelector('[data-grid="five"]')).not.toBeNull();
  });

  it('6+ photos — shows first 5 tiles + "+N" overlay on the last one', () => {
    const { container } = render(<MediaGallery media={makePhotos(7)} channel={channel} tgMessageId={1} />);
    expect(container.querySelectorAll('img')).toHaveLength(5);
    expect(screen.getByText('+2')).toBeInTheDocument();
  });

  it('video tile shows the ▶ play badge', () => {
    const media: FeedMedia[] = [{ id: 1, type: 'video', width: 800, height: 600, duration: 30 }];
    render(<MediaGallery media={media} channel={channel} tgMessageId={42} />);
    expect(screen.getByText(/▶/)).toBeInTheDocument();
  });
});

describe('MediaGallery interaction (lightbox)', () => {
  beforeEach(() => {
    localStorage.setItem(
      'tma:tokens',
      JSON.stringify({
        access_token: 'tok-abc',
        refresh_token: 'r',
        token_type: 'bearer',
        expires_in: 60,
      }),
    );
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('click on a photo tile opens the lightbox', async () => {
    render(<MediaGallery media={makePhotos(2)} channel={channel} tgMessageId={1} />);
    const [firstTile] = screen.getAllByRole('button', { name: /open media/i });
    fireEvent.click(firstTile!);
    expect(await screen.findByRole('button', { name: /close/i })).toBeInTheDocument();
  });

  it('lightbox slide src points at /media/{id} with ?token query', async () => {
    render(<MediaGallery media={makePhotos(1)} channel={channel} tgMessageId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /open media/i }));
    await screen.findByRole('button', { name: /close/i });
    const lightboxImg = document.querySelector('.yarl__slide img');
    expect(lightboxImg).not.toBeNull();
    expect(lightboxImg?.getAttribute('src')).toMatch(/\/media\/1\?token=tok-abc/);
  });

  it('clicking a video tile opens the lightbox with a "Watch in Telegram" link', async () => {
    const media: FeedMedia[] = [{ id: 1, type: 'video', width: 800, height: 600, duration: 30 }];
    render(<MediaGallery media={media} channel={channel} tgMessageId={42} />);
    fireEvent.click(screen.getByRole('button', { name: /open media/i }));
    await screen.findByRole('button', { name: /close/i });
    const tgLink = screen.getByRole('link', { name: /watch in telegram/i });
    expect(tgLink).toHaveAttribute('href', 'tg://resolve?domain=meduza&post=42');
  });

  it('does not render a "Watch in Telegram" link for a photo slide', async () => {
    render(<MediaGallery media={makePhotos(1)} channel={channel} tgMessageId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /open media/i }));
    await screen.findByRole('button', { name: /close/i });
    expect(screen.queryByRole('link', { name: /watch in telegram/i })).toBeNull();
  });

  it('clicking close removes the lightbox', async () => {
    render(<MediaGallery media={makePhotos(1)} channel={channel} tgMessageId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /open media/i }));
    const closeBtn = await screen.findByRole('button', { name: /close/i });
    fireEvent.click(closeBtn);
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /close/i })).toBeNull(),
    );
  });
});
