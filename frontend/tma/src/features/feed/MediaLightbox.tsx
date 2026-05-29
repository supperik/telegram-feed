import { useMemo } from 'react';
import Lightbox from 'yet-another-react-lightbox';
import Zoom from 'yet-another-react-lightbox/plugins/zoom';
import 'yet-another-react-lightbox/styles.css';

import { getTokens } from '@/features/auth/tokenStore';
import type { FeedMedia } from '@/shared/api/types';

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api';

function mediaUrl(id: number): string {
  const tokens = getTokens();
  return tokens
    ? `${BASE}/media/${id}?token=${encodeURIComponent(tokens.access_token)}`
    : `${BASE}/media/${id}`;
}

interface Props {
  media: FeedMedia[];
  // Index into the PHOTO-only slide list (not into the full media[]).
  openIndex: number;
  onClose: () => void;
}

export function MediaLightbox({ media, openIndex, onClose }: Props) {
  // Photos only. Videos open Telegram from the tile directly; documents
  // have no preview. Filtering here keeps the slide indices stable.
  const slides = useMemo(
    () =>
      media
        .filter((m) => m.type === 'photo')
        .map((m) => ({
          src: mediaUrl(m.id),
          width: m.width ?? undefined,
          height: m.height ?? undefined,
        })),
    [media],
  );

  if (slides.length === 0) return null;

  return (
    <Lightbox
      open
      close={onClose}
      slides={slides}
      index={Math.min(openIndex, Math.max(0, slides.length - 1))}
      plugins={[Zoom]}
      // Only a close button in the toolbar. Zoom is driven by gestures
      // (pinch, double-tap) and keyboard (+/-) — no +/− chrome.
      toolbar={{ buttons: ['close'] }}
      // Swipe up or down to dismiss. The Zoom plugin stops pointer-event
      // propagation while pinching (2 pointers) or zoomed in (zoom > 1), so
      // the controller's pull-to-close only fires on a single-finger drag at
      // base zoom — it can't tear the viewer down mid-pinch. A tap on the
      // empty area around the photo closes too: YARL fires backdrop close only
      // when the tap's down and up land on the same empty slide area
      // (yarl__slide), so a tap on the photo itself (yarl__slide_image) is
      // ignored and a moving pinch never counts as a tap.
      controller={{
        closeOnBackdropClick: true,
        closeOnPullDown: true,
        closeOnPullUp: true,
      }}
      carousel={{ finite: true }}
      zoom={{ maxZoomPixelRatio: 3, doubleTapDelay: 250 }}
    />
  );
}
