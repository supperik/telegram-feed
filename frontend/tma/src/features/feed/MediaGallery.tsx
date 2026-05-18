import { useState } from 'react';

import { getTokens } from '@/features/auth/tokenStore';
import { MediaLightbox } from '@/features/feed/MediaLightbox';
import type { ChannelSummary, FeedMedia } from '@/shared/api/types';

interface Props {
  media: FeedMedia[];
  channel: ChannelSummary;
  tgMessageId: number;
}

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api';
// Native <img> tags can't send custom headers, so we pass the JWT via
// query param. /api/media/{id} accepts either ?token=... or Authorization.
function mediaUrl(id: number): string {
  const tokens = getTokens();
  return tokens
    ? `${BASE}/media/${id}?token=${encodeURIComponent(tokens.access_token)}`
    : `${BASE}/media/${id}`;
}

const tgPostUrl = (channel: ChannelSummary, msgId: number): string | null =>
  channel.username ? `tg://resolve?domain=${channel.username}&post=${msgId}` : null;

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

interface TileProps {
  m: FeedMedia;
  channel: ChannelSummary;
  tgMessageId: number;
  overlay?: string | null;
  onOpenPhoto?: () => void;
}

function Tile({ m, channel, tgMessageId, overlay, onOpenPhoto }: TileProps) {
  if (m.type === 'photo') {
    const content = (
      <div className="relative h-full w-full overflow-hidden bg-black/5">
        <img src={mediaUrl(m.id)} alt="" loading="lazy" className="h-full w-full object-cover" />
        {overlay ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/45 text-xl font-semibold text-white">
            {overlay}
          </div>
        ) : null}
      </div>
    );
    return (
      <button
        type="button"
        onClick={onOpenPhoto}
        aria-label="Open media"
        className="block h-full w-full p-0 text-left"
      >
        {content}
      </button>
    );
  }
  if (m.type === 'video') {
    // Backend doesn't serve video bytes (only thumbnails), so playing it
    // inside the TMA isn't possible yet — tap takes the user straight to
    // the Telegram client where the video plays natively.
    const link = tgPostUrl(channel, tgMessageId);
    const content = (
      <div className="relative h-full w-full overflow-hidden bg-black/5">
        <img src={mediaUrl(m.id)} alt="" loading="lazy" className="h-full w-full object-cover" />
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/15">
          <span className="rounded-full bg-black/60 px-3 py-1 text-xs font-medium text-white">
            ▶ {m.duration ? `${m.duration}s` : 'Video'}
          </span>
        </div>
        {overlay ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/45 text-xl font-semibold text-white">
            {overlay}
          </div>
        ) : null}
      </div>
    );
    return link ? (
      <a href={link} className="block h-full w-full">{content}</a>
    ) : (
      content
    );
  }
  return (
    <div className="bg-secondary p-3 text-sm text-hint">Документ — открыть в Telegram.</div>
  );
}

export function MediaGallery({ media, channel, tgMessageId }: Props) {
  // openIndex is into the PHOTO-only slide list (lightbox slides skip videos).
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  if (media.length === 0) return null;
  const visible = media.slice(0, 5);
  const overflow = media.length - visible.length;
  const variant = variantFor(visible.length);
  return (
    <>
      <div data-grid={variant} className={`mt-1 gap-0.5 bg-black/10 ${VARIANT_CLASSES[variant]}`}>
        {visible.map((m, i) => {
          const photoIndex =
            m.type === 'photo'
              ? media.slice(0, i).filter((x) => x.type === 'photo').length
              : -1;
          return (
            <Tile
              key={m.id}
              m={m}
              channel={channel}
              tgMessageId={tgMessageId}
              overlay={i === visible.length - 1 && overflow > 0 ? `+${overflow}` : null}
              onOpenPhoto={photoIndex >= 0 ? () => setOpenIndex(photoIndex) : undefined}
            />
          );
        })}
      </div>
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
