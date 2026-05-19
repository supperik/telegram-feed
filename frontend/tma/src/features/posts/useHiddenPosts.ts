import { useInfiniteQuery } from '@tanstack/react-query';
import { apiFetch } from '@/shared/api/client';
import type { FeedPage } from '@/shared/api/types';

export const HIDDEN_POSTS_QUERY_KEY = ['posts', 'hidden'] as const;

export function useHiddenPosts(limit = 20) {
  return useInfiniteQuery<FeedPage>({
    queryKey: [...HIDDEN_POSTS_QUERY_KEY, limit],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const search = new URLSearchParams({ limit: String(limit) });
      if (pageParam) search.set('cursor', pageParam as string);
      return apiFetch<FeedPage>(`/posts/hidden?${search.toString()}`);
    },
    getNextPageParam: (last) => last.next_cursor,
  });
}
