import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { MediaGallery } from '@/features/feed/MediaGallery';
import type { FeedChannel, FeedMedia } from '@/shared/api/types';

const channel: FeedChannel = {
  id: 1,
  tg_chat_id: 1319248631,
  username: 'meduza',
  title: 'M',
  photo_url: null,
  is_private: false,
  invite_url: null,
};

function makePhotos(n: number): FeedMedia[] {
  return Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    type: 'photo' as const,
    width: 1280,
    height: 720,
    duration: null,
    has_video_file: false,
  }));
}

function videoMedia(overrides: Partial<FeedMedia> = {}): FeedMedia {
  return {
    id: 1,
    type: 'video',
    width: 800,
    height: 600,
    duration: 30,
    has_video_file: false,
    ...overrides,
  };
}

function documentMedia(overrides: Partial<FeedMedia> = {}): FeedMedia {
  return {
    id: 1,
    type: 'document',
    width: null,
    height: null,
    duration: null,
    has_video_file: false,
    ...overrides,
  };
}

describe('MediaGallery — photo carousel', () => {
  it('renders nothing for empty media', () => {
    const { container } = render(<MediaGallery media={[]} channel={channel} tgMessageId={1} />);
    expect(container.firstChild).toBeNull();
  });

  it('1 photo — a single slide, no pager', () => {
    const { container } = render(
      <MediaGallery media={makePhotos(1)} channel={channel} tgMessageId={1} />,
    );
    expect(container.querySelectorAll('img')).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: /open media/i })).toHaveLength(1);
    expect(screen.queryByText('1 / 1')).toBeNull();
  });

  it('3 photos — three swipeable slides with a counter', () => {
    const { container } = render(
      <MediaGallery media={makePhotos(3)} channel={channel} tgMessageId={1} />,
    );
    expect(container.querySelectorAll('img')).toHaveLength(3);
    expect(screen.getAllByRole('button', { name: /open media/i })).toHaveLength(3);
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
  });

  it('many photos — every photo is a slide, no "+N" cap', () => {
    const { container } = render(
      <MediaGallery media={makePhotos(7)} channel={channel} tgMessageId={1} />,
    );
    expect(container.querySelectorAll('img')).toHaveLength(7);
    expect(screen.getAllByRole('button', { name: /open media/i })).toHaveLength(7);
  });
});

describe('MediaGallery — video row', () => {
  it('video renders a t.me link with a "Видео" label', () => {
    const { container } = render(
      <MediaGallery media={[videoMedia()]} channel={channel} tgMessageId={42} />,
    );
    const a = container.querySelector('a[href^="https://t.me/"]');
    expect(a).not.toBeNull();
    expect(a?.getAttribute('href')).toBe('https://t.me/meduza/42');
    expect(screen.getByText(/Видео/)).toBeInTheDocument();
  });

  it('video in a private channel links via t.me/c/<tg_chat_id>/<msg>', () => {
    const privateChannel: FeedChannel = { ...channel, username: null, is_private: true };
    const { container } = render(
      <MediaGallery media={[videoMedia()]} channel={privateChannel} tgMessageId={42} />,
    );
    const a = container.querySelector('a[href^="https://t.me/c/"]');
    expect(a?.getAttribute('href')).toBe('https://t.me/c/1319248631/42');
  });

  it('never plays video inline regardless of has_video_file', () => {
    for (const hvf of [false, true]) {
      const { unmount } = render(
        <MediaGallery media={[videoMedia({ has_video_file: hvf })]} channel={channel} tgMessageId={1} />,
      );
      expect(screen.queryByTestId('inline-video')).toBeNull();
      expect(screen.getByRole('link')).toBeInTheDocument();
      expect(screen.getByText(/Видео/)).toBeInTheDocument();
      unmount();
    }
  });
});

describe('MediaGallery — document row', () => {
  it('document renders a t.me link with a "Файл" label', () => {
    const { container } = render(
      <MediaGallery media={[documentMedia()]} channel={channel} tgMessageId={42} />,
    );
    const a = container.querySelector('a[href^="https://t.me/"]');
    expect(a?.getAttribute('href')).toBe('https://t.me/meduza/42');
    expect(screen.getByText(/Файл/)).toBeInTheDocument();
  });

  it('document in a private channel links via t.me/c/<tg_chat_id>/<msg>', () => {
    const privateChannel: FeedChannel = { ...channel, username: null, is_private: true };
    const { container } = render(
      <MediaGallery media={[documentMedia()]} channel={privateChannel} tgMessageId={42} />,
    );
    const a = container.querySelector('a[href^="https://t.me/c/"]');
    expect(a?.getAttribute('href')).toBe('https://t.me/c/1319248631/42');
  });
});

describe('MediaGallery — lightbox', () => {
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

  it('tapping a photo slide opens the lightbox', async () => {
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

  it('opens the lightbox at the photo index, skipping leading videos', async () => {
    // openIndex passed to MediaLightbox must address the photo-only slide
    // list — a leading video must not shift the photo to a missing slot.
    const media: FeedMedia[] = [
      { id: 10, type: 'video', width: 800, height: 600, duration: 30, has_video_file: false },
      { id: 11, type: 'photo', width: 800, height: 600, duration: null, has_video_file: false },
    ];
    render(<MediaGallery media={media} channel={channel} tgMessageId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /open media/i }));
    await screen.findByRole('button', { name: /close/i });
    const lightboxImg = document.querySelector('.yarl__slide img');
    expect(lightboxImg?.getAttribute('src')).toMatch(/\/media\/11\?token=/);
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
