import { useRef, useState, type MouseEvent, type PointerEvent } from 'react';
import { getTokens } from '@/features/auth/tokenStore';
import { MediaLightbox } from '@/features/feed/MediaLightbox';
import type { FeedChannel, FeedMedia } from '@/shared/api/types';
import { openTelegramLink, tgPostUrl } from '@/shared/lib/telegram';
import {
  ArrowUpRightIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  FileIcon,
  PlayIcon,
} from '@/shared/ui/icons';

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api';

function mediaUrl(id: number): string {
  const tokens = getTokens();
  return tokens
    ? `${BASE}/media/${id}?token=${encodeURIComponent(tokens.access_token)}`
    : `${BASE}/media/${id}`;
}

function formatDuration(sec: number): string {
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
}

interface Props {
  media: FeedMedia[];
  channel: FeedChannel;
  tgMessageId: number;
}

export function MediaGallery({ media, channel, tgMessageId }: Props) {
  // openIndex addresses the photo-only slide list (videos never reach here).
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  if (media.length === 0) return null;

  const photos = media.filter((m) => m.type === 'photo');
  const videos = media.filter((m) => m.type === 'video');
  const documents = media.filter((m) => m.type === 'document');

  return (
    <>
      {photos.length > 0 ? <PhotoCarousel photos={photos} onOpen={setOpenIndex} /> : null}
      {videos.map((m) => (
        <MediaLinkRow key={m.id} kind="video" media={m} channel={channel} tgMessageId={tgMessageId} />
      ))}
      {documents.map((m) => (
        <MediaLinkRow key={m.id} kind="document" media={m} channel={channel} tgMessageId={tgMessageId} />
      ))}
      {openIndex !== null ? (
        <MediaLightbox media={media} openIndex={openIndex} onClose={() => setOpenIndex(null)} />
      ) : null}
    </>
  );
}

interface CarouselProps {
  photos: FeedMedia[];
  onOpen: (index: number) => void;
}

// Swipeable single-photo-per-frame reel. Touch swipe rides native scroll-snap;
// mouse drag is emulated via pointer capture. Tapping a slide opens the lightbox.
function PhotoCarousel({ photos, onOpen }: CarouselProps) {
  const [active, setActive] = useState(0);
  const reelRef = useRef<HTMLDivElement>(null);
  const drag = useRef({ id: -1, startX: 0, startScroll: 0, dx: 0, dragged: false });
  const n = photos.length;

  const onScroll = () => {
    const el = reelRef.current;
    if (!el || !el.clientWidth) return;
    const idx = Math.round(el.scrollLeft / el.clientWidth);
    if (idx !== active) setActive(idx);
  };

  const goTo = (i: number) => {
    const el = reelRef.current;
    if (!el || !el.clientWidth) return;
    const next = Math.max(0, Math.min(n - 1, i));
    el.scrollTo({ left: next * el.clientWidth, behavior: 'smooth' });
  };

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    const el = reelRef.current;
    if (!el) return;
    drag.current = {
      id: e.pointerId,
      startX: e.clientX,
      startScroll: el.scrollLeft,
      dx: 0,
      dragged: false,
    };
    try {
      el.setPointerCapture(e.pointerId);
    } catch {
      /* setPointerCapture can throw if the pointer is already gone */
    }
    el.style.scrollSnapType = 'none';
    el.style.scrollBehavior = 'auto';
  };

  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (d.id !== e.pointerId) return;
    const el = reelRef.current;
    if (!el) return;
    d.dx = e.clientX - d.startX;
    if (Math.abs(d.dx) > 4) d.dragged = true;
    el.scrollLeft = d.startScroll - d.dx;
  };

  const endDrag = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (d.id !== e.pointerId) return;
    const el = reelRef.current;
    if (!el) return;
    try {
      el.releasePointerCapture(e.pointerId);
    } catch {
      /* already released */
    }
    el.style.scrollSnapType = '';
    el.style.scrollBehavior = '';
    const w = el.clientWidth || 1;
    let target = Math.round(el.scrollLeft / w);
    if (Math.abs(d.dx) > w * 0.18) {
      target =
        d.dx < 0
          ? Math.min(n - 1, Math.floor(d.startScroll / w) + 1)
          : Math.max(0, Math.ceil(d.startScroll / w) - 1);
    }
    el.scrollTo({ left: target * w, behavior: 'smooth' });
    drag.current.id = -1;
  };

  const onSlideClick = (i: number) => () => {
    // Swallow the click that ends a drag so a swipe never opens the lightbox.
    if (drag.current.dragged) {
      drag.current.dragged = false;
      return;
    }
    onOpen(i);
  };

  return (
    <div className="tf-media">
      <div
        className="reel"
        ref={reelRef}
        onScroll={onScroll}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        {photos.map((m, i) => (
          <button
            key={m.id}
            type="button"
            className="slide"
            aria-label="Open media"
            onClick={onSlideClick(i)}
          >
            <img src={mediaUrl(m.id)} alt="" loading="lazy" draggable={false} />
          </button>
        ))}
      </div>
      {n > 1 && active > 0 ? (
        <button
          type="button"
          className="nav-arrow prev"
          aria-label="Предыдущее"
          onClick={() => goTo(active - 1)}
        >
          <ChevronLeftIcon size={18} />
        </button>
      ) : null}
      {n > 1 && active < n - 1 ? (
        <button
          type="button"
          className="nav-arrow next"
          aria-label="Следующее"
          onClick={() => goTo(active + 1)}
        >
          <ChevronRightIcon size={18} />
        </button>
      ) : null}
      {n > 1 ? (
        <div className="dots">
          {photos.map((m, i) => (
            <div key={m.id} className={`dot${i === active ? ' active' : ''}`} />
          ))}
        </div>
      ) : null}
      {n > 1 ? <div className="count">{active + 1} / {n}</div> : null}
    </div>
  );
}

interface LinkRowProps {
  kind: 'video' | 'document';
  media: FeedMedia;
  channel: FeedChannel;
  tgMessageId: number;
}

// Videos and documents have no servable bytes — they render as a row that
// hands off to the Telegram client.
function MediaLinkRow({ kind, media, channel, tgMessageId }: LinkRowProps) {
  const link = tgPostUrl(channel, tgMessageId);
  const onOpen = (e: MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    openTelegramLink(link);
  };
  const isVideo = kind === 'video';
  const title = isVideo
    ? media.duration
      ? `Видео · ${formatDuration(media.duration)}`
      : 'Видео'
    : 'Файл';
  return (
    <a href={link} onClick={onOpen} className="tf-doc">
      <div className="ic">{isVideo ? <PlayIcon size={15} /> : <FileIcon size={16} />}</div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {title}
        </div>
        <div className="sub">Открыть в Telegram</div>
      </div>
      <ArrowUpRightIcon size={16} />
    </a>
  );
}
