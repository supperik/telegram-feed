import { useCallback, useEffect, useRef } from 'react';
import { apiFetch } from '@/shared/api/client';

const DWELL_MS = 1000;
const DEBOUNCE_MS = 2000;

export interface PostReadTracker {
  /** Returns a stable ref callback for a feed card's root element. */
  observe: (postId: number) => (el: HTMLElement | null) => void;
  /** Mark a post read immediately (deep-link tap) and flush now. */
  markRead: (postId: number) => void;
}

/**
 * Tracks which feed posts the user has actually seen and reports them to
 * POST /feed/read. A post counts as read once it has dwelled in the viewport
 * for DWELL_MS; reads are flushed in debounced batches and on unmount.
 */
export function usePostRead(): PostReadTracker {
  const observerRef = useRef<IntersectionObserver | null>(null);
  const postByEl = useRef(new Map<Element, number>());
  const elByPost = useRef(new Map<number, Element>());
  const refCallbacks = useRef(new Map<number, (el: HTMLElement | null) => void>());
  const dwellTimers = useRef(new Map<number, ReturnType<typeof setTimeout>>());
  const pending = useRef(new Set<number>());
  const flushed = useRef(new Set<number>());
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flush = useCallback(() => {
    if (debounceTimer.current !== null) {
      clearTimeout(debounceTimer.current);
      debounceTimer.current = null;
    }
    if (pending.current.size === 0) return;
    const batch = [...pending.current];
    pending.current.clear();
    for (const id of batch) flushed.current.add(id);
    void apiFetch('/feed/read', {
      method: 'POST',
      body: JSON.stringify({ post_ids: batch }),
    }).catch(() => {
      // A failed read-mark is not user-facing; the post reappears next
      // session and is re-marked then.
    });
  }, []);

  const scheduleFlush = useCallback(() => {
    if (debounceTimer.current !== null) return; // window already open
    debounceTimer.current = setTimeout(flush, DEBOUNCE_MS);
  }, [flush]);

  const handleEntries = useCallback<IntersectionObserverCallback>(
    (entries) => {
      for (const entry of entries) {
        const postId = postByEl.current.get(entry.target);
        if (postId === undefined) continue;
        if (entry.isIntersecting) {
          if (flushed.current.has(postId) || pending.current.has(postId)) continue;
          if (dwellTimers.current.has(postId)) continue;
          dwellTimers.current.set(
            postId,
            setTimeout(() => {
              dwellTimers.current.delete(postId);
              if (flushed.current.has(postId)) return; // already sent (deep-link tap)
              pending.current.add(postId);
              scheduleFlush();
            }, DWELL_MS),
          );
        } else {
          const timer = dwellTimers.current.get(postId);
          if (timer !== undefined) {
            clearTimeout(timer);
            dwellTimers.current.delete(postId);
          }
        }
      }
    },
    [scheduleFlush],
  );

  const observe = useCallback((postId: number) => {
    let cb = refCallbacks.current.get(postId);
    if (cb === undefined) {
      cb = (el: HTMLElement | null) => {
        const prev = elByPost.current.get(postId);
        if (prev !== undefined) {
          observerRef.current?.unobserve(prev);
          postByEl.current.delete(prev);
          elByPost.current.delete(postId);
          const timer = dwellTimers.current.get(postId);
          if (timer !== undefined) {
            clearTimeout(timer);
            dwellTimers.current.delete(postId);
          }
        }
        if (el !== null) {
          elByPost.current.set(postId, el);
          postByEl.current.set(el, postId);
          observerRef.current?.observe(el);
        }
      };
      refCallbacks.current.set(postId, cb);
    }
    return cb;
  }, []);

  const markRead = useCallback(
    (postId: number) => {
      if (flushed.current.has(postId)) return;
      pending.current.add(postId);
      flush();
    },
    [flush],
  );

  useEffect(() => {
    const observer = new IntersectionObserver(handleEntries);
    observerRef.current = observer;
    // Observe cards whose ref fired before this effect ran.
    for (const el of postByEl.current.keys()) observer.observe(el);
    const dwell = dwellTimers.current;
    return () => {
      flush();
      for (const timer of dwell.values()) clearTimeout(timer);
      dwell.clear();
      observer.disconnect();
    };
  }, [handleEntries, flush]);

  return { observe, markRead };
}
