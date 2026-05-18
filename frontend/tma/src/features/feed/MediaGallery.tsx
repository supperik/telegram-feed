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
  overlay?: string | null;
  onOpen?: () => void;
}

function Tile({ m, overlay, onOpen }: TileProps) {
  if (m.type === 'photo' || m.type === 'video') {
    const content = (
      <div className="relative h-full w-full overflow-hidden bg-black/5">
        <img src={mediaUrl(m.id)} alt="" loading="lazy" className="h-full w-full object-cover" />
        {m.type === 'video' ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/15">
            <span className="rounded-full bg-black/60 px-3 py-1 text-xs font-medium text-white">
              ▶ {m.duration ? `${m.duration}s` : 'Video'}
            </span>
          </div>
        ) : null}
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
        onClick={onOpen}
        aria-label="Open media"
        className="block h-full w-full p-0 text-left"
      >
        {content}
      </button>
    );
  }
  return (
    <div className="bg-secondary p-3 text-sm text-hint">Документ — открыть в Telegram.</div>
  );
}

export function MediaGallery({ media, channel, tgMessageId }: Props) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  if (media.length === 0) return null;
  const visible = media.slice(0, 5);
  const overflow = media.length - visible.length;
  const variant = variantFor(visible.length);
  return (
    <>
      <div data-grid={variant} className={`mt-1 gap-0.5 bg-black/10 ${VARIANT_CLASSES[variant]}`}>
        {visible.map((m, i) => (
          <Tile
            key={m.id}
            m={m}
            overlay={i === visible.length - 1 && overflow > 0 ? `+${overflow}` : null}
            onOpen={() => setOpenIndex(i)}
          />
        ))}
      </div>
      {openIndex !== null ? (
        <MediaLightbox
          media={media}
          channel={channel}
          tgMessageId={tgMessageId}
          openIndex={openIndex}
          onClose={() => setOpenIndex(null)}
        />
      ) : null}
    </>
  );
}
