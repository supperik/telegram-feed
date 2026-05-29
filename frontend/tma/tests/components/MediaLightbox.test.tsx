import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { FeedMedia } from '@/shared/api/types';

// The pull-to-close gesture depends on pointer velocity and container layout,
// which jsdom doesn't model — so we assert the controller config MediaLightbox
// owns. The gesture itself is the library's job; the real swipe is verified
// on-device. The Zoom plugin suppresses pull-to-close while pinching or zoomed
// (it stops pointer-event propagation), so enabling both directions is safe.
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
}

function capturedController(): CapturedController {
  const call = lightboxProps.mock.calls.at(-1);
  return (call?.[0] as { controller: CapturedController }).controller;
}

describe('MediaLightbox — close gestures', () => {
  it('closes the viewer on a downward swipe', () => {
    render(<MediaLightbox media={[photo(1)]} openIndex={0} onClose={() => {}} />);
    expect(capturedController().closeOnPullDown).toBe(true);
  });

  it('closes the viewer on an upward swipe', () => {
    render(<MediaLightbox media={[photo(1)]} openIndex={0} onClose={() => {}} />);
    expect(capturedController().closeOnPullUp).toBe(true);
  });
});
