import { useState, type MouseEvent } from 'react';

import { getTokens } from '@/features/auth/tokenStore';
import { MediaLightbox } from '@/features/feed/MediaLightbox';
import type { FeedChannel, FeedMedia } from '@/shared/api/types';
import { openTelegramLink, tgPostUrl } from '@/shared/lib/telegram';

interface Props {
  media: FeedMedia[];
  channel: FeedChannel;
  tgMessageId: number;
}

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api';

function mediaUrl(id: number): string {
  const tokens = getTokens();
  return tokens
    ? `${BASE}/media/${id}?token=${encodeURIComponent(tokens.access_token)}`
    : `${BASE}/media/${id}`;
}

type Variant = 'one' | 'two' | 'three' | 'four' | 'five';

function variantFor(n: number): Variant {
  if (n <= 1) return 'one';
  if (n === 2) return 'two';
  if (n === 3) return 'three';
  if (n === 4) return 'four';
  return 'five';
}

const VARIANT_CLASSES: Record<Variant, string> = {
  one:   'grid grid-cols-1',
  two:   'grid grid-cols-2 [&>*]:aspect-square',
  three: 'grid grid-cols-3 grid-rows-2 [&>*:first-child]:col-span-2 [&>*:first-child]:row-span-2',
  four:  'grid grid-cols-2 [&>*]:aspect-square',
  five:  'grid grid-cols-3 grid-rows-2 [&>*:nth-child(1)]:col-span-2 [&>*:nth-child(2)]:col-span-1 [&>*:nth-child(n+3)]:aspect-square',
};

interface PhotoTileProps {
  m: FeedMedia;
  overlay?: string | null;
  onOpen: () => void;
}

function PhotoTile({ m, overlay, onOpen }: PhotoTileProps) {
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label="Open media"
      className="block h-full w-full p-0 text-left"
    >
      <div className="relative h-full w-full overflow-hidden bg-black/5">
        <img src={mediaUrl(m.id)} alt="" loading="lazy" className="h-full w-full object-cover" />
        {overlay ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/45 text-xl font-semibold text-white">
            {overlay}
          </div>
        ) : null}
      </div>
    </button>
  );
}

interface VideoRowProps {
  m: FeedMedia;
  channel: FeedChannel;
  tgMessageId: number;
}

function VideoRow({ m, channel, tgMessageId }: VideoRowProps) {
  const link = tgPostUrl(channel, tgMessageId);
  const onOpen = (e: MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    openTelegramLink(link);
  };
  const label = m.duration ? `Видео · ${m.duration}s` : 'Видео';
  return (
    <a
      href={link}
      onClick={onOpen}
      className="mt-1 flex items-center gap-2 rounded bg-secondary px-3 py-2 text-sm text-link"
    >
      <span aria-hidden>▶</span>
      <span>{label} — открыть в Telegram</span>
    </a>
  );
}

interface DocumentRowProps {
  channel: FeedChannel;
  tgMessageId: number;
}

function DocumentRow({ channel, tgMessageId }: DocumentRowProps) {
  const link = tgPostUrl(channel, tgMessageId);
  const onOpen = (e: MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    openTelegramLink(link);
  };
  return (
    <a
      href={link}
      onClick={onOpen}
      className="mt-1 flex items-center gap-2 rounded bg-secondary px-3 py-2 text-sm text-link"
    >
      <span aria-hidden>📎</span>
      <span>Файл — открыть в Telegram</span>
    </a>
  );
}

export function MediaGallery({ media, channel, tgMessageId }: Props) {
  // openIndex is into the PHOTO-only slide list (lightbox slides skip videos).
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  if (media.length === 0) return null;

  const photos = media.filter((m) => m.type === 'photo');
  const videos = media.filter((m) => m.type === 'video');
  const documents = media.filter((m) => m.type === 'document');

  const visiblePhotos = photos.slice(0, 5);
  const overflow = photos.length - visiblePhotos.length;
  const variant = variantFor(visiblePhotos.length);

  return (
    <>
      {visiblePhotos.length > 0 ? (
        <div data-grid={variant} className={`mt-1 gap-0.5 bg-black/10 ${VARIANT_CLASSES[variant]}`}>
          {visiblePhotos.map((m, i) => (
            <PhotoTile
              key={m.id}
              m={m}
              overlay={i === visiblePhotos.length - 1 && overflow > 0 ? `+${overflow}` : null}
              onOpen={() => setOpenIndex(i)}
            />
          ))}
        </div>
      ) : null}
      {videos.map((m) => (
        <VideoRow key={m.id} m={m} channel={channel} tgMessageId={tgMessageId} />
      ))}
      {documents.map((m) => (
        <DocumentRow key={m.id} channel={channel} tgMessageId={tgMessageId} />
      ))}
      {openIndex !== null ? (
        <MediaLightbox
          media={media}
          openIndex={openIndex}
          onClose={() => setOpenIndex(null)}
        />
      ) : null}
    </>
  );
}
