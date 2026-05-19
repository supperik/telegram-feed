import { useInfiniteQuery } from '@tanstack/react-query';
import { apiFetch } from '@/shared/api/client';
import type { FeedPage } from '@/shared/api/types';

export const SAVED_POSTS_QUERY_KEY = ['posts', 'saved'] as const;

export function useSavedPosts(limit = 20) {
  return useInfiniteQuery<FeedPage>({
    queryKey: [...SAVED_POSTS_QUERY_KEY, limit],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const search = new URLSearchParams({ limit: String(limit) });
      if (pageParam) search.set('cursor', pageParam as string);
      return apiFetch<FeedPage>(`/posts/saved?${search.toString()}`);
    },
    getNextPageParam: (last) => last.next_cursor,
  });
}
