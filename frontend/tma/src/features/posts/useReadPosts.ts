import { useInfiniteQuery } from '@tanstack/react-query';
import { apiFetch } from '@/shared/api/client';
import type { FeedPage } from '@/shared/api/types';

export const READ_POSTS_QUERY_KEY = ['posts', 'read'] as const;

export function useReadPosts(limit = 20) {
  return useInfiniteQuery<FeedPage>({
    queryKey: [...READ_POSTS_QUERY_KEY, limit],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const search = new URLSearchParams({ limit: String(limit) });
      if (pageParam) search.set('cursor', pageParam as string);
      return apiFetch<FeedPage>(`/posts/read?${search.toString()}`);
    },
    getNextPageParam: (last) => last.next_cursor,
  });
}
