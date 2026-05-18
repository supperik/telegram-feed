import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
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

  it('video tile wraps in <a> to tg:// when channel username is set', () => {
    const media: FeedMedia[] = [{ id: 1, type: 'video', width: 800, height: 600, duration: 30 }];
    const { container } = render(<MediaGallery media={media} channel={channel} tgMessageId={42} />);
    const a = container.querySelector('a[href^="tg://"]');
    expect(a).not.toBeNull();
  });
});
