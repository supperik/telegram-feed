import type { ChannelSummary, FeedMedia } from '@/shared/api/types';

interface Props {
  media: FeedMedia[];
  channel: ChannelSummary;
  tgMessageId: number;
}

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api';
const mediaUrl = (id: number) => `${BASE}/media/${id}`;
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

function Tile({ m, channel, tgMessageId, overlay }: { m: FeedMedia; channel: ChannelSummary; tgMessageId: number; overlay?: string | null }) {
  if (m.type === 'photo' || m.type === 'video') {
    const img = (
      <div className="relative h-full w-full overflow-hidden bg-black/5">
        <img src={mediaUrl(m.id)} alt="" loading="lazy" className="h-full w-full object-cover" />
        {m.type === 'video' ? (
          <div className="absolute inset-0 flex items-center justify-center bg-black/15">
            <span className="rounded-full bg-black/60 px-3 py-1 text-xs font-medium text-white">
              ▶ {m.duration ? `${m.duration}s` : 'Video'}
            </span>
          </div>
        ) : null}
        {overlay ? (
          <div className="absolute inset-0 flex items-center justify-center bg-black/45 text-xl font-semibold text-white">
            {overlay}
          </div>
        ) : null}
      </div>
    );
    const link = tgPostUrl(channel, tgMessageId);
    return m.type === 'video' && link ? <a href={link} className="block h-full w-full">{img}</a> : img;
  }
  return (
    <div className="bg-secondary p-3 text-sm text-hint">Документ — открыть в Telegram.</div>
  );
}

export function MediaGallery({ media, channel, tgMessageId }: Props) {
  if (media.length === 0) return null;
  const visible = media.slice(0, 5);
  const overflow = media.length - visible.length;
  const variant = variantFor(visible.length);
  return (
    <div data-grid={variant} className={`mt-1 gap-0.5 bg-black/10 ${VARIANT_CLASSES[variant]}`}>
      {visible.map((m, i) => (
        <Tile
          key={m.id}
          m={m}
          channel={channel}
          tgMessageId={tgMessageId}
          overlay={i === visible.length - 1 && overflow > 0 ? `+${overflow}` : null}
        />
      ))}
    </div>
  );
}
