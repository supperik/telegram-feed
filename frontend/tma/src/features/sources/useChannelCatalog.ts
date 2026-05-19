import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import { apiFetch } from '@/shared/api/client';
import { SOURCES_QUERY_KEY } from '@/features/sources/useSources';
import type { AddSourceOut, CatalogPage } from '@/shared/api/types';

export const CATALOG_QUERY_KEY = ['catalog'] as const;

type View = 'available' | 'hidden';

export function useChannelCatalog(view: View, q?: string) {
  return useInfiniteQuery<CatalogPage>({
    queryKey: [...CATALOG_QUERY_KEY, view, q ?? ''],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const search = new URLSearchParams({ view });
      if (q) search.set('q', q);
      if (pageParam) search.set('cursor', pageParam as string);
      return apiFetch<CatalogPage>(`/channels/catalog?${search.toString()}`);
    },
    getNextPageParam: (last) => last.next_cursor,
  });
}

export function useSubscribeByChannelId() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (channelId: number) =>
      apiFetch<AddSourceOut>(`/sources/${channelId}`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SOURCES_QUERY_KEY });
      qc.invalidateQueries({ queryKey: CATALOG_QUERY_KEY });
    },
  });
}

export function useHideFromCatalog() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (channelId: number) =>
      apiFetch<void>(`/channels/catalog/${channelId}/hide`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: CATALOG_QUERY_KEY }),
  });
}

export function useUnhideFromCatalog() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (channelId: number) =>
      apiFetch<void>(`/channels/catalog/${channelId}/hide`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: CATALOG_QUERY_KEY }),
  });
}
