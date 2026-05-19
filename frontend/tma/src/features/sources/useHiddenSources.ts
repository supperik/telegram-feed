import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/shared/api/client';
import { FEED_QUERY_KEY } from '@/features/feed/useFeed';
import { SOURCES_QUERY_KEY } from '@/features/sources/useSources';
import type {
  HiddenSourceItem,
  HiddenSourceList,
  SourceList,
  SourceListItem,
} from '@/shared/api/types';

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
    mutationFn: (item: HiddenSourceItem) =>
      apiFetch<void>(`/sources/${item.channel.id}/hide`, { method: 'DELETE' }),
    onMutate: async (item) => {
      const channelId = item.channel.id;
      await qc.cancelQueries({ queryKey: HIDDEN_SOURCES_QUERY_KEY });
      await qc.cancelQueries({ queryKey: SOURCES_QUERY_KEY });
      const prevHidden = qc.getQueryData<HiddenSourceList>(HIDDEN_SOURCES_QUERY_KEY);
      qc.setQueryData<HiddenSourceList>(HIDDEN_SOURCES_QUERY_KEY, (old) =>
        old ? { items: old.items.filter((s) => s.channel.id !== channelId) } : old,
      );
      const prevSources = qc.getQueryData<SourceList>(SOURCES_QUERY_KEY);
      qc.setQueryData<SourceList>(SOURCES_QUERY_KEY, (old) => {
        const placeholder: SourceListItem = {
          channel: item.channel,
          added_at: new Date().toISOString(),
          subscription_status: 'active',
        };
        if (!old) return { items: [placeholder] };
        if (old.items.some((s) => s.channel.id === channelId)) return old;
        return { items: [placeholder, ...old.items] };
      });
      return { prevHidden, prevSources };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prevHidden) qc.setQueryData(HIDDEN_SOURCES_QUERY_KEY, ctx.prevHidden);
      if (ctx?.prevSources) qc.setQueryData(SOURCES_QUERY_KEY, ctx.prevSources);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: HIDDEN_SOURCES_QUERY_KEY });
      qc.invalidateQueries({ queryKey: FEED_QUERY_KEY });
      qc.invalidateQueries({ queryKey: SOURCES_QUERY_KEY });
    },
  });
}
