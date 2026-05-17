import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/shared/api/client';
import type { SourceList } from '@/shared/api/types';

export const SOURCES_QUERY_KEY = ['sources'] as const;

export function useSources() {
  return useQuery<SourceList>({
    queryKey: SOURCES_QUERY_KEY,
    queryFn: () => apiFetch<SourceList>('/sources'),
  });
}

export function useRemoveSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (channelId: number) =>
      apiFetch<void>(`/sources/${channelId}`, { method: 'DELETE' }),
    onMutate: async (channelId) => {
      await qc.cancelQueries({ queryKey: SOURCES_QUERY_KEY });
      const prev = qc.getQueryData<SourceList>(SOURCES_QUERY_KEY);
      qc.setQueryData<SourceList>(SOURCES_QUERY_KEY, (old) =>
        old ? { items: old.items.filter((s) => s.channel.id !== channelId) } : old,
      );
      return { prev };
    },
    onError: (_err, _channelId, ctx) => {
      if (ctx?.prev) qc.setQueryData(SOURCES_QUERY_KEY, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: SOURCES_QUERY_KEY }),
  });
}
