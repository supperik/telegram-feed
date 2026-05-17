import type { ChannelSummary, FeedMedia } from '@/shared/api/types';

interface Props {
  media: FeedMedia[];
  channel: ChannelSummary;
  tgMessageId: number;
}

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api';

function mediaUrl(id: number): string {
  return `${BASE}/media/${id}`;
}

function tgPostUrl(channel: ChannelSummary, msgId: number): string | null {
  if (!channel.username) return null;
  return `tg://resolve?domain=${channel.username}&post=${msgId}`;
}

export function MediaGallery({ media, channel, tgMessageId }: Props) {
  if (media.length === 0) return null;
  const tgLink = tgPostUrl(channel, tgMessageId);

  return (
    <div className={`mt-2 grid gap-1 ${media.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
      {media.map((m) => {
        if (m.type === 'photo') {
          return (
            <img
              key={m.id}
              src={mediaUrl(m.id)}
              alt=""
              loading="lazy"
              className="w-full rounded object-cover"
            />
          );
        }
        if (m.type === 'video') {
          const thumb = (
            <div key={m.id} className="relative">
              <img src={mediaUrl(m.id)} alt="" loading="lazy" className="w-full rounded object-cover" />
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="rounded-full bg-black/60 px-3 py-1 text-xs text-white">
                  ▶ {m.duration ? `${m.duration}s` : 'Video'}
                </span>
              </div>
            </div>
          );
          return tgLink ? (
            <a key={m.id} href={tgLink}>{thumb}</a>
          ) : (
            thumb
          );
        }
        return (
          <div key={m.id} className="rounded bg-secondary p-3 text-sm text-hint">
            Document attached — open original in Telegram.
          </div>
        );
      })}
    </div>
  );
}
