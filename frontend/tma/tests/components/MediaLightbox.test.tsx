import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { FeedMedia } from '@/shared/api/types';

// Close affordances depend on pointer velocity / hit-testing, which jsdom
// doesn't model — so we assert the controller config MediaLightbox owns and
// leave the actual gestures to the library (verified on-device). The Zoom
// plugin stops pointer-event propagation while pinching or zoomed, and YARL's
// backdrop close only fires when the tap's down/up target is the same empty
// slide area — so neither affordance can tear the viewer down mid-pinch or on
// a tap that lands on the photo itself.
const { lightboxProps } = vi.hoisted(() => ({ lightboxProps: vi.fn() }));

vi.mock('yet-another-react-lightbox', () => ({
  default: (props: Record<string, unknown>) => {
    lightboxProps(props);
    return null;
  },
}));

import { MediaLightbox } from '@/features/feed/MediaLightbox';

function photo(id: number): FeedMedia {
  return { id, type: 'photo', width: 1280, height: 720, duration: null, has_video_file: false };
}

interface CapturedController {
  closeOnPullDown?: boolean;
  closeOnPullUp?: boolean;
  closeOnBackdropClick?: boolean;
}

function capturedController(): CapturedController {
  const call = lightboxProps.mock.calls.at(-1);
  return (call?.[0] as { controller: CapturedController }).controller;
}

describe('MediaLightbox — close affordances', () => {
  it('closes the viewer on a downward swipe', () => {
    render(<MediaLightbox media={[photo(1)]} openIndex={0} onClose={() => {}} />);
    expect(capturedController().closeOnPullDown).toBe(true);
  });

  it('closes the viewer on an upward swipe', () => {
    render(<MediaLightbox media={[photo(1)]} openIndex={0} onClose={() => {}} />);
    expect(capturedController().closeOnPullUp).toBe(true);
  });

  it('closes the viewer on a tap in the empty area around the photo', () => {
    render(<MediaLightbox media={[photo(1)]} openIndex={0} onClose={() => {}} />);
    expect(capturedController().closeOnBackdropClick).toBe(true);
  });
});
