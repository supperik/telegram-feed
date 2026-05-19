import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/shared/api/client';
import { FEED_QUERY_KEY } from '@/features/feed/useFeed';
import { SOURCES_QUERY_KEY } from '@/features/sources/useSources';
import type { HiddenSourceList } from '@/shared/api/types';

export const HIDDEN_SOURCES_QUERY_KEY = ['sources', 'hidden'] as const;

export function useHiddenSources() {
  return useQuery<HiddenSourceList>({
    queryKey: HIDDEN_SOURCES_QUERY_KEY,
    queryFn: () => apiFetch<HiddenSourceList>('/sources/hidden'),
  });
}

export function useUnhideSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (channelId: number) =>
      apiFetch<void>(`/sources/${channelId}/hide`, { method: 'DELETE' }),
    onMutate: async (channelId) => {
      await qc.cancelQueries({ queryKey: HIDDEN_SOURCES_QUERY_KEY });
      const prev = qc.getQueryData<HiddenSourceList>(HIDDEN_SOURCES_QUERY_KEY);
      qc.setQueryData<HiddenSourceList>(HIDDEN_SOURCES_QUERY_KEY, (old) =>
        old ? { items: old.items.filter((s) => s.channel.id !== channelId) } : old,
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(HIDDEN_SOURCES_QUERY_KEY, ctx.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: HIDDEN_SOURCES_QUERY_KEY });
      qc.invalidateQueries({ queryKey: FEED_QUERY_KEY });
      qc.invalidateQueries({ queryKey: SOURCES_QUERY_KEY });
    },
  });
}
