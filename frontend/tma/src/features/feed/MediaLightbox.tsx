import { useMemo } from 'react';
import Lightbox, { type SlideImage } from 'yet-another-react-lightbox';
import Counter from 'yet-another-react-lightbox/plugins/counter';
import Zoom from 'yet-another-react-lightbox/plugins/zoom';
import 'yet-another-react-lightbox/styles.css';
import 'yet-another-react-lightbox/plugins/counter.css';

import { getTokens } from '@/features/auth/tokenStore';
import type { ChannelSummary, FeedMedia } from '@/shared/api/types';

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api';

function mediaUrl(id: number): string {
  const tokens = getTokens();
  return tokens
    ? `${BASE}/media/${id}?token=${encodeURIComponent(tokens.access_token)}`
    : `${BASE}/media/${id}`;
}

function tgPostUrl(channel: ChannelSummary, msgId: number): string | null {
  return channel.username ? `tg://resolve?domain=${channel.username}&post=${msgId}` : null;
}

interface MediaSlide extends SlideImage {
  mediaType: 'photo' | 'video';
}

interface Props {
  media: FeedMedia[];
  channel: ChannelSummary;
  tgMessageId: number;
  openIndex: number;
  onClose: () => void;
}

export function MediaLightbox({ media, channel, tgMessageId, openIndex, onClose }: Props) {
  const tgUrl = tgPostUrl(channel, tgMessageId);

  // Documents have no preview — skip them in the lightbox carousel.
  const slides = useMemo<MediaSlide[]>(() => {
    return media
      .filter((m): m is FeedMedia & { type: 'photo' | 'video' } =>
        m.type === 'photo' || m.type === 'video',
      )
      .map((m) => ({
        src: mediaUrl(m.id),
        width: m.width ?? undefined,
        height: m.height ?? undefined,
        mediaType: m.type,
      }));
  }, [media]);

  // openIndex is an index into the original media[]. After filtering out
  // documents, find the position of that media item in the slide list.
  const slideIndex = useMemo(() => {
    const count = media
      .slice(0, openIndex)
      .filter((m) => m.type === 'photo' || m.type === 'video').length;
    return Math.min(count, Math.max(0, slides.length - 1));
  }, [media, openIndex, slides.length]);

  if (slides.length === 0) return null;

  return (
    <Lightbox
      open
      close={onClose}
      slides={slides}
      index={slideIndex}
      plugins={[Zoom, Counter]}
      controller={{ closeOnBackdropClick: true, closeOnPullDown: true }}
      carousel={{ finite: true }}
      zoom={{ maxZoomPixelRatio: 4 }}
      render={{
        slideFooter: ({ slide }) => {
          const s = slide as MediaSlide;
          if (s.mediaType !== 'video' || !tgUrl) return null;
          return (
            <a
              href={tgUrl}
              className="absolute bottom-12 left-1/2 z-10 -translate-x-1/2 rounded-full bg-black/75 px-5 py-3 text-sm font-medium text-white shadow-lg"
            >
              ▶ Watch in Telegram
            </a>
          );
        },
      }}
    />
  );
}
