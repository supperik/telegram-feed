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
  });
}
