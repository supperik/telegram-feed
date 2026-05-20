import { useInfiniteQuery } from '@tanstack/react-query';
import { apiFetch } from '@/shared/api/client';
import type { FeedPage } from '@/shared/api/types';

export const FEED_QUERY_KEY = ['feed'] as const;

export function useFeed(limit = 20) {
  return useInfiniteQuery<FeedPage>({
    queryKey: [...FEED_QUERY_KEY, limit],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const search = new URLSearchParams({ limit: String(limit) });
      if (pageParam) search.set('cursor', pageParam as string);
      return apiFetch<FeedPage>(`/feed?${search.toString()}`);
    },
    getNextPageParam: (last) => last.next_cursor,
    // The feed refreshes only on an explicit Refresh tap or a fresh app load
    // (page reload / full re-entry spins up a new QueryClient). Tab navigation
    // remounts FeedScreen, but Infinity stale/gc time keeps the cached pages so
    // no refetch fires. Manual refetch() and invalidateQueries() still work.
    staleTime: Infinity,
    gcTime: Infinity,
  });
}
