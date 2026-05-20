import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { usePostRead } from '@/features/feed/usePostRead';
import { apiFetch } from '@/shared/api/client';

vi.mock('@/shared/api/client', () => ({
  apiFetch: vi.fn(() => Promise.resolve({ marked: 0 })),
}));

class FakeIntersectionObserver {
  static instances: FakeIntersectionObserver[] = [];
  callback: IntersectionObserverCallback;
  constructor(cb: IntersectionObserverCallback) {
    this.callback = cb;
    FakeIntersectionObserver.instances.push(this);
  }
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
  fire(el: Element, isIntersecting: boolean): void {
    this.callback(
      [{ target: el, isIntersecting } as IntersectionObserverEntry],
      this as unknown as IntersectionObserver,
    );
  }
}

const io = (): FakeIntersectionObserver => FakeIntersectionObserver.instances.at(-1)!;
const POST = (ids: number[]) => ({
  method: 'POST',
  body: JSON.stringify({ post_ids: ids }),
});

beforeEach(() => {
  vi.useFakeTimers();
  FakeIntersectionObserver.instances = [];
  vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver);
  vi.mocked(apiFetch).mockClear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('usePostRead', () => {
  it('marks a post read after it dwells in the viewport', () => {
    const { result } = renderHook(() => usePostRead());
    const el = document.createElement('article');
    result.current.observe(1)(el);

    io().fire(el, true);
    vi.advanceTimersByTime(1000); // dwell completes
    expect(apiFetch).not.toHaveBeenCalled(); // debounce not elapsed
    vi.advanceTimersByTime(2000); // debounce flush
    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(apiFetch).toHaveBeenCalledWith('/feed/read', POST([1]));
  });

  it('does not mark a post that leaves before the dwell time', () => {
    const { result } = renderHook(() => usePostRead());
    const el = document.createElement('article');
    result.current.observe(2)(el);

    io().fire(el, true);
    vi.advanceTimersByTime(500);
    io().fire(el, false); // scrolled away early
    vi.advanceTimersByTime(5000);
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it('batches multiple dwelled posts into one request', () => {
    const { result } = renderHook(() => usePostRead());
    const el1 = document.createElement('article');
    const el2 = document.createElement('article');
    result.current.observe(10)(el1);
    result.current.observe(11)(el2);

    io().fire(el1, true);
    io().fire(el2, true);
    vi.advanceTimersByTime(1000);
    vi.advanceTimersByTime(2000);
    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(apiFetch).toHaveBeenCalledWith('/feed/read', POST([10, 11]));
  });

  it('markRead flushes immediately without the debounce', () => {
    const { result } = renderHook(() => usePostRead());
    result.current.markRead(99);
    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(apiFetch).toHaveBeenCalledWith('/feed/read', POST([99]));
  });

  it('flushes pending reads when the hook unmounts', () => {
    const { result, unmount } = renderHook(() => usePostRead());
    const el = document.createElement('article');
    result.current.observe(7)(el);
    io().fire(el, true);
    vi.advanceTimersByTime(1000); // dwell done, debounce pending
    expect(apiFetch).not.toHaveBeenCalled();
    unmount();
    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(apiFetch).toHaveBeenCalledWith('/feed/read', POST([7]));
  });

  it('does not re-send a post marked read mid-dwell', () => {
    const { result } = renderHook(() => usePostRead());
    const el = document.createElement('article');
    result.current.observe(5)(el);

    io().fire(el, true); // dwell timer running
    result.current.markRead(5); // deep-link tap before dwell completes
    expect(apiFetch).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1000); // dwell timer fires
    vi.advanceTimersByTime(2000); // any debounce window elapses
    expect(apiFetch).toHaveBeenCalledTimes(1); // not sent a second time
  });
});
